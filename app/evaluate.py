"""편성안 평가: 필수 조건 검사, 항목별 균형 상태, 학급별 통계, 비교, 새 번호 부여.

균형 평가 방식 (정규화)
- 각 범주(선택지·단계·태그)마다 학급별 기대 인원 = 범주 전체 인원 × (학급 목표 인원 / 목표 인원 합)
  → 학급 정원이 달라도 규모에 비례하여 비교한다.
- 항목 비용 = Σ(실제-기대)² / (2 × 범주 수)  : 선택지가 많다고 영향이 커지지 않도록 범주 수로 나눈다.
- 평균은 표준화 점수(z) 합으로 계산하여 숫자 범위의 크기와 무관하게 한다.
- 미입력 학생은 어떤 범주에도 넣지 않고 따로 센다 (0점·낮음으로 바꾸지 않음).
"""
import itertools
import math

from .common import (BUILTIN_ITEMS, IMPORTANCE_LABEL, IMPORTANCE_W, REL_KINDS, count_rule, feature_categories,
                     fmt_num, is_missing, natural_key)

STATUS_LABEL = {"good": "✔ 고름", "caution": "△ 약간 차이", "bad": "✖ 차이 큼", "no_data": "ⓘ 자료 없음"}
STATUS_RANK = {"good": 0, "caution": 1, "bad": 2, "no_data": -1}


class Ctx:
    """프로젝트에서 계산에 필요한 정보를 한 번 정리한 것."""

    def __init__(self, project, weight_override=None, only_items=None):
        self.project = project
        self.classes = project["classes"]
        self.K = len(self.classes)
        self.cids = [c["id"] for c in self.classes]
        self.cidx = {c: i for i, c in enumerate(self.cids)}
        self.cap = [int(c.get("max") or 0) for c in self.classes]
        tg = [max(0.0, float(c.get("target") or 0)) for c in self.classes]
        if sum(tg) <= 0:
            tg = [1.0] * self.K
        self.share = [t / sum(tg) for t in tg]
        self.by_key = {s["key"]: s for s in project["students"]}
        self.students = [s for s in project["students"] if s.get("eligible", True)]
        self.keys = [s["key"] for s in self.students]
        self.idx = {k: i for i, k in enumerate(self.keys)}
        self.N = len(self.students)
        self.features = {f["id"]: f for f in project.get("features", [])}
        self.items = build_items(self, weight_override or {}, only_items)

    def name_of(self, key):
        s = self.by_key.get(key)
        if not s:
            return "(삭제된 학생)"
        return f"{s.get('name', '')}({s.get('sid', '')})"


def _origin_label(s):
    c = (s.get("cls") or "").strip()
    return c if c else None


def build_items(ctx, override, only_items):
    """균형 항목 목록. enabled=False 인 항목도 통계 표시용으로 만든다 (비용에는 미반영)."""
    p = ctx.project
    bal = p.get("balance", {})
    items = []
    studs = ctx.students
    N = ctx.N

    def mk(iid, name, kind, enabled, importance, method="distribution", note=""):
        imp = override.get(iid, importance)
        w = IMPORTANCE_W.get(imp, 2.0) if not isinstance(imp, (int, float)) else float(imp)
        en = enabled
        if only_items is not None:
            en = iid in only_items
        return {"id": iid, "name": name, "kind": kind, "enabled": bool(en), "importance": importance if not isinstance(importance, (int, float)) else "normal",
                "weight": w, "method": method, "cats": [], "mean": None, "missing": [], "na": [], "note": note,
                "multi": False, "count_desc": ""}

    # 1) 전체 인원
    b = bal.get("size", {})
    it = mk("builtin:size", BUILTIN_ITEMS["builtin:size"], "size", b.get("enabled", True), b.get("importance", "very_high"))
    it["cats"] = [{"key": "all", "label": "전체 인원", "members": list(range(N))}]
    items.append(it)
    # 2) 성별
    b = bal.get("gender", {})
    it = mk("builtin:gender", BUILTIN_ITEMS["builtin:gender"], "gender", b.get("enabled", True), b.get("importance", "high"))
    genders = []
    for s in studs:
        g = (s.get("gender") or "").strip()
        if g and g not in genders:
            genders.append(g)
    order = {"남": 0, "여": 1}
    genders.sort(key=lambda g: (order.get(g, 9), g))
    for g in genders:
        it["cats"].append({"key": "g" + g, "label": g, "members": [i for i, s in enumerate(studs) if (s.get("gender") or "").strip() == g]})
    it["missing"] = [i for i, s in enumerate(studs) if not (s.get("gender") or "").strip()]
    items.append(it)
    # 3) 현재 반
    b = bal.get("origin", {})
    it = mk("builtin:origin", BUILTIN_ITEMS["builtin:origin"], "origin", b.get("enabled", True), b.get("importance", "normal"))
    origins = sorted({_origin_label(s) for s in studs if _origin_label(s)}, key=natural_key)
    for o in origins:
        it["cats"].append({"key": "c" + o, "label": "현재 " + o, "members": [i for i, s in enumerate(studs) if _origin_label(s) == o]})
    it["missing"] = [i for i, s in enumerate(studs) if not _origin_label(s)]
    it["note"] = "현재 반이 비어 있는 학생(전입 예정 등)은 이 항목 계산에서 제외됩니다."
    items.append(it)
    # 4) 사용자 특성
    for f in p.get("features", []):
        if not f.get("active") or f["type"] == "text":
            continue
        method = f.get("method", "none")
        enabled = bool(f.get("use_in_balance")) and method != "none"
        it = mk("feature:" + f["id"], f["name"], "feature", enabled, f.get("importance", "normal"), method)
        it["feature_id"] = f["id"]
        it["ftype"] = f["type"]
        vals = [s.get("traits", {}).get(f["id"]) for s in studs]
        it["missing"] = [i for i, v in enumerate(vals) if is_missing(f, v)]
        if f["type"] == "multi":
            it["na"] = [i for i, v in enumerate(vals) if isinstance(v, list) and len(v) == 0]
            it["multi"] = True
        if method == "count":
            fn, desc = count_rule(f)
            it["count_desc"] = desc
            it["cats"] = [{"key": "count", "label": desc, "members": [i for i, v in enumerate(vals) if not is_missing(f, v) and fn(v)]}]
            # 표시용 전체 분포도 함께 계산한다 (비용에는 count 범주만 사용)
            it["display_cats"] = [{"key": k, "label": lab, "members": [i for i, v in enumerate(vals) if not is_missing(f, v) and t(v)]}
                                  for k, lab, t in feature_categories(f)]
        else:
            cats = [{"key": k, "label": lab, "members": [i for i, v in enumerate(vals) if not is_missing(f, v) and t(v)]}
                    for k, lab, t in feature_categories(f)]
            it["cats"] = cats if method in ("distribution", "both", "none") else []
            it["display_cats"] = cats
            if f["type"] == "level" and method in ("mean", "both", "none"):
                raw = {i: float(v) for i, v in enumerate(vals) if not is_missing(f, v)}
                if raw:
                    m = sum(raw.values()) / len(raw)
                    sd = math.sqrt(sum((x - m) ** 2 for x in raw.values()) / len(raw)) or 1.0
                    it["mean"] = {"raw": raw, "z": {i: (x - m) / sd for i, x in raw.items()}, "overall": m, "sd": sd,
                                  "use": method in ("mean", "both")}
        items.append(it)
    # 5) 특성 조합
    for cb in p.get("combos", []):
        it = mk("combo:" + cb["id"], cb.get("name") or "특성 조합", "combo", bool(cb.get("use_in_balance")), cb.get("importance", "normal"), "count")
        members, missing = combo_members(ctx, cb)
        it["cats"] = [{"key": "combo", "label": combo_desc(ctx, cb), "members": members}]
        it["missing"] = missing
        it["count_desc"] = combo_desc(ctx, cb)
        items.append(it)
    for it in items:
        it.setdefault("display_cats", it["cats"])
        ncat = sum(1 for c in it["cats"] if c["members"])
        it["cat_factor"] = 1.0 / (2 * ncat) if ncat else 0.0
        if it.get("mean"):
            nd = sum(1 for c in it["display_cats"] if c["members"]) or 1
            it["mean"]["factor"] = (0.5 if it["method"] == "both" else 1.0) / (2 * nd)
    return items


def combo_desc(ctx, cb):
    parts = []
    for c in cb.get("conds", []):
        f = ctx.features.get(c.get("feature_id"))
        if not f:
            parts.append("(삭제된 항목)")
            continue
        vals = c.get("values") or []
        if f["type"] == "yesno":
            vs = ["예" if v is True or v == "예" else "아니요" for v in vals]
        else:
            vs = [fmt_num(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v) for v in vals]
        parts.append(f"{f['name']}={'/'.join(vs)}")
    return " 그리고 ".join(parts) + " 인 학생"


def _match_value(f, v, vals):
    if f["type"] == "yesno":
        want = {True if (x is True or x == "예") else False for x in vals}
        return v in want
    if f["type"] == "multi":
        return isinstance(v, list) and any(x in v for x in vals)
    if f["type"] == "level":
        try:
            return any(abs(float(v) - float(x)) < 1e-9 for x in vals)
        except (TypeError, ValueError):
            return False
    return v in vals


def combo_members(ctx, cb):
    """조합 조건(모두 만족: AND)에 해당하는 학생. 조건 항목 중 하나라도 미입력이면 '판단 불가'로 따로 센다."""
    members, missing = [], []
    conds = [c for c in cb.get("conds", []) if c.get("feature_id") in ctx.features]
    for i, s in enumerate(ctx.students):
        ok = True
        miss = False
        for c in conds:
            f = ctx.features[c["feature_id"]]
            v = s.get("traits", {}).get(f["id"])
            if is_missing(f, v):
                miss = True
                ok = False
                continue
            if not _match_value(f, v, c.get("values") or []):
                ok = False
        if ok and conds:
            members.append(i)
        elif miss:
            missing.append(i)
    return members, missing


# ----------------------------------------------------------------------------
# 필수 조건 검사 (최종 결과 검증용, 계산 모델과 독립적으로 직접 확인)
# ----------------------------------------------------------------------------

def rel_members(ctx, r):
    return [k for k in r.get("members", []) if k in ctx.idx]


def rel_pairs(ctx, r):
    if r["kind"] == "all_diff":
        m = rel_members(ctx, r)
        return list(itertools.combinations(m, 2))
    if r["kind"] == "pairs_diff":
        return [(a, b) for a, b in r.get("pairs", []) if a in ctx.idx and b in ctx.idx]
    return []


def rel_text(ctx, r):
    names = ", ".join(ctx.name_of(k) for k in r.get("members", []))
    kind = REL_KINDS.get(r["kind"], r["kind"])
    if r["kind"] == "max_per_class":
        kind = f"반마다 최대 {r.get('max_n')}명"
    st = "반드시" if r.get("strength") == "must" else "가급적"
    if r["kind"] == "pairs_diff":
        prs = "; ".join(f"{ctx.name_of(a)}↔{ctx.name_of(b)}" for a, b in r.get("pairs", []))
        return f"[{st}] {kind}: {prs}"
    return f"[{st}] {kind}: {names}"


def check_hard(project, assignment, locks=None, ctx=None):
    ctx = ctx or Ctx(project)
    locks = locks or {}
    v = []
    assignment = assignment or {}
    for k in ctx.keys:
        c = assignment.get(k)
        if c is None:
            v.append({"code": "unassigned", "message": f"{ctx.name_of(k)} 학생이 어느 학급에도 배정되지 않았습니다.", "students": [k]})
        elif c not in ctx.cidx:
            v.append({"code": "invalid_class", "message": f"{ctx.name_of(k)} 학생의 배정 학급이 존재하지 않습니다.", "students": [k]})
    for k, c in assignment.items():
        if k not in ctx.idx and c is not None:
            s = ctx.by_key.get(k)
            if s is not None:
                v.append({"code": "excluded_assigned", "message": f"편성 제외 학생 {ctx.name_of(k)}이(가) 배정되어 있습니다.", "students": [k]})
    sizes = [0] * ctx.K
    for k in ctx.keys:
        c = assignment.get(k)
        if c in ctx.cidx:
            sizes[ctx.cidx[c]] += 1
    for i, c in enumerate(ctx.classes):
        if sizes[i] > ctx.cap[i]:
            v.append({"code": "capacity", "message": f"{c['name']} 인원 {sizes[i]}명이 최대 인원 {ctx.cap[i]}명을 넘습니다.", "students": [], "class": c["id"]})
    for s in ctx.students:
        fc = s.get("fixed_class")
        if fc and assignment.get(s["key"]) != fc:
            cname = next((c["name"] for c in ctx.classes if c["id"] == fc), fc)
            v.append({"code": "fixed", "message": f"{ctx.name_of(s['key'])} 학생은 {cname}에 지정 배정되어 있습니다.", "students": [s["key"]]})
    for k, c in locks.items():
        if k in ctx.idx and assignment.get(k) != c:
            cname = next((x["name"] for x in ctx.classes if x["id"] == c), c)
            v.append({"code": "lock", "message": f"{ctx.name_of(k)} 학생은 {cname}에 고정되어 있습니다.", "students": [k]})
    for r in project.get("relations", []):
        if r.get("strength") != "must":
            continue
        ok, detail = relation_satisfied(ctx, r, assignment)
        if not ok:
            v.append({"code": "rel_" + r["kind"], "message": "필수 조건 위반 — " + rel_text(ctx, r) + (" (" + detail + ")" if detail else ""),
                      "students": rel_members(ctx, r), "relation": r["id"]})
    return v


def relation_satisfied(ctx, r, assignment):
    m = rel_members(ctx, r)
    if r["kind"] == "same":
        cl = {assignment.get(k) for k in m}
        return len(cl) <= 1, ("서로 다른 반에 나뉘어 있음" if len(cl) > 1 else "")
    if r["kind"] in ("all_diff", "pairs_diff"):
        bad = [(a, b) for a, b in rel_pairs(ctx, r) if assignment.get(a) is not None and assignment.get(a) == assignment.get(b)]
        return not bad, ("같은 반: " + ", ".join(f"{ctx.name_of(a)}·{ctx.name_of(b)}" for a, b in bad) if bad else "")
    if r["kind"] == "max_per_class":
        n = int(r.get("max_n") or 0)
        cnt = {}
        for k in m:
            c = assignment.get(k)
            cnt[c] = cnt.get(c, 0) + 1
        over = [(c, x) for c, x in cnt.items() if c is not None and x > n]
        names = {c["id"]: c["name"] for c in ctx.classes}
        return not over, ("; ".join(f"{names.get(c, c)}에 {x}명" for c, x in over) if over else "")
    return True, ""


def must_units(project, ctx=None):
    """'반드시 같은 반' 관계를 연결하여 함께 움직여야 하는 학생 묶음을 만든다."""
    ctx = ctx or Ctx(project)
    parent = {k: k for k in ctx.keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in project.get("relations", []):
        if r.get("strength") == "must" and r["kind"] == "same":
            m = rel_members(ctx, r)
            for a in m[1:]:
                ra, rb = find(m[0]), find(a)
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for k in ctx.keys:
        groups.setdefault(find(k), []).append(k)
    return [g for g in groups.values()], find


# ----------------------------------------------------------------------------
# 균형 평가
# ----------------------------------------------------------------------------

def _cat_stat(ctx, members, cls_of):
    total = len(members)
    counts = [0] * ctx.K
    for i in members:
        c = cls_of[i]
        if c is not None and c >= 0:
            counts[c] += 1
    expected = [total * w for w in ctx.share]
    dev = max((abs(c - e) for c, e in zip(counts, expected)), default=0.0)
    return total, counts, expected, dev


def _dev_status(dev, expected):
    e = max(expected) if expected else 0
    if dev <= 1.0 + 0.1 * e:
        return "good"
    if dev <= 2.0 + 0.2 * e:
        return "caution"
    return "bad"


def item_eval(ctx, it, cls_of, sizes):
    out = {"id": it["id"], "name": it["name"], "kind": it["kind"], "enabled": it["enabled"], "importance": it["importance"],
           "importance_label": IMPORTANCE_LABEL.get(it["importance"], ""), "method": it["method"], "count_desc": it.get("count_desc", ""),
           "note": it.get("note", ""), "cats": [], "display": [], "mean": None}
    cost = 0.0
    worst = None
    ncat = 0
    for c in it["cats"]:
        total, counts, expected, dev = _cat_stat(ctx, c["members"], cls_of)
        if total == 0:
            continue
        ncat += 1
        cost += it["cat_factor"] * sum((a - b) ** 2 for a, b in zip(counts, expected))
        st = _dev_status(dev, expected)
        if worst is None or STATUS_RANK[st] > STATUS_RANK[worst]:
            worst = st
        out["cats"].append({"key": c["key"], "label": c["label"], "total": total, "counts": counts,
                            "expected": [round(e, 2) for e in expected], "max_dev": round(dev, 2), "status": st})
    for c in it.get("display_cats", []):
        total, counts, expected, dev = _cat_stat(ctx, c["members"], cls_of)
        out["display"].append({"key": c["key"], "label": c["label"], "total": total, "counts": counts,
                               "expected": [round(e, 2) for e in expected]})
    m = it.get("mean")
    if m:
        sums = [0.0] * ctx.K
        ns = [0] * ctx.K
        zs = [0.0] * ctx.K
        for i, x in m["raw"].items():
            c = cls_of[i]
            if c is None or c < 0:
                continue
            sums[c] += x
            ns[c] += 1
            zs[c] += m["z"][i]
        means = [round(sums[k] / ns[k], 2) if ns[k] else None for k in range(ctx.K)]
        valid = [x for x in means if x is not None]
        spread = (max(valid) - min(valid)) if valid else 0.0
        rel = spread / m["sd"] if m["sd"] else 0
        st = "good" if rel <= 0.25 else ("caution" if rel <= 0.5 else "bad")
        out["mean"] = {"class_means": means, "overall": round(m["overall"], 2), "spread": round(spread, 2), "sd": round(m["sd"], 2),
                       "status": st, "use": m.get("use", False)}
        if m.get("use"):
            Z = sum(m["z"].values())
            cost += m["factor"] * sum((zs[k] - Z * ctx.share[k]) ** 2 for k in range(ctx.K))
            if worst is None or STATUS_RANK[st] > STATUS_RANK[worst]:
                worst = st
    miss = [0] * ctx.K
    for i in it["missing"]:
        c = cls_of[i]
        if c is not None and c >= 0:
            miss[c] += 1
    na = [0] * ctx.K
    for i in it.get("na", []):
        c = cls_of[i]
        if c is not None and c >= 0:
            na[c] += 1
    n_miss = len(it["missing"])
    rate = n_miss / ctx.N if ctx.N else 0
    out["missing"] = {"total": n_miss, "by_class": miss, "rate": round(rate, 3)}
    if it.get("multi"):
        out["na"] = {"total": len(it.get("na", [])), "by_class": na}
        tag_total = sum(len(c["members"]) for c in it.get("display_cats", []))
        tagged = len({i for c in it.get("display_cats", []) for i in c["members"]})
        out["multi_note"] = (f"한 학생이 여러 선택지에 해당하면 각 선택지에 모두 집계됩니다 (중복 집계). "
                             f"선택지 합계 {tag_total}건 / 해당 학생 {tagged}명")
    if worst is None:
        worst = "no_data"
    out["status"] = worst
    out["status_label"] = STATUS_LABEL[worst]
    out["cost"] = round(cost, 4)
    out["max_dev"] = round(max([c["max_dev"] for c in out["cats"]] or [0]), 2)
    out["data_limited"] = rate >= 0.2
    if rate >= 0.2 and it["kind"] in ("feature", "combo"):
        out["data_note"] = (f"미입력 {n_miss}명({round(rate * 100)}%) — 입력된 학생만으로 균형을 판단하므로 "
                            f"이 항목의 평가에는 한계가 있습니다.")
    elif n_miss and it["kind"] in ("feature", "combo"):
        out["data_note"] = f"미입력 {n_miss}명은 계산에서 제외되었습니다 (0점·‘해당 없음’으로 바꾸지 않음)."
    return out


def soft_relations(ctx, project, assignment):
    unmet, met = [], 0
    for r in project.get("relations", []):
        if r.get("strength") != "prefer":
            continue
        ok, detail = relation_satisfied(ctx, r, assignment)
        if ok:
            met += 1
        else:
            unmet.append({"relation": r["id"], "message": rel_text(ctx, r) + (" — " + detail if detail else ""),
                          "students": rel_members(ctx, r), "importance": r.get("importance", "high")})
    return {"met": met, "unmet": unmet, "total": met + len(unmet)}


def evaluate(project, assignment, locks=None, ctx=None, light=False):
    ctx = ctx or Ctx(project)
    assignment = assignment or {}
    cls_of = [ctx.cidx.get(assignment.get(k), -1) for k in ctx.keys]
    sizes = [0] * ctx.K
    for c in cls_of:
        if c >= 0:
            sizes[c] += 1
    hard = check_hard(project, assignment, locks, ctx)
    items = [item_eval(ctx, it, cls_of, sizes) for it in ctx.items]
    soft = soft_relations(ctx, project, assignment)
    rep = {"hard": {"ok": not hard, "violations": hard}, "items": items, "soft": soft}
    summ = {"good": 0, "caution": 0, "bad": 0, "no_data": 0}
    for it in items:
        if it["enabled"]:
            summ[it["status"]] += 1
    rep["summary"] = dict(summ, n_eligible=ctx.N, n_assigned=sum(sizes))
    if light:
        rep["sizes"] = sizes
        return rep
    classes = []
    gender_item = next(it for it in ctx.items if it["id"] == "builtin:gender")
    for k, c in enumerate(ctx.classes):
        g = {}
        for cat in gender_item["cats"]:
            g[cat["label"]] = sum(1 for i in cat["members"] if cls_of[i] == k)
        gm = sum(1 for i in gender_item["missing"] if cls_of[i] == k)
        if gm:
            g["미입력"] = gm
        origin = {}
        for i, s in enumerate(ctx.students):
            if cls_of[i] == k:
                o = _origin_label(s) or "현재 반 없음"
                origin[o] = origin.get(o, 0) + 1
        classes.append({"id": c["id"], "name": c["name"], "size": sizes[k], "target": c.get("target"), "max": ctx.cap[k],
                        "over": sizes[k] > ctx.cap[k], "gender": g,
                        "origin": dict(sorted(origin.items(), key=lambda x: natural_key(x[0])))})
    rep["classes"] = classes
    # 현재 반 × 새 학급 표
    rows = sorted({_origin_label(s) or "현재 반 없음(전입 등)" for s in ctx.students}, key=natural_key)
    table = []
    for o in rows:
        r = [0] * ctx.K
        for i, s in enumerate(ctx.students):
            if (_origin_label(s) or "현재 반 없음(전입 등)") == o and cls_of[i] >= 0:
                r[cls_of[i]] += 1
        table.append({"origin": o, "counts": r, "total": sum(r)})
    rep["cross"] = {"rows": table, "classes": [c["name"] for c in ctx.classes]}
    units, _ = must_units(project, ctx)
    rep["units"] = [u for u in units if len(u) > 1]
    return rep


# ----------------------------------------------------------------------------
# 미리보기 / 비교
# ----------------------------------------------------------------------------

def preview_change(project, assignment, locks, changes):
    """changes: [{key, to}] — 실제 편성안은 바꾸지 않고 결과만 계산한다."""
    ctx = Ctx(project)
    before = evaluate(project, assignment, locks, ctx, light=True)
    new = dict(assignment)
    for ch in changes:
        new[ch["key"]] = ch["to"]
    after = evaluate(project, new, locks, ctx, light=True)
    units, find = must_units(project, ctx)
    unit_map = {}
    for u in units:
        for k in u:
            unit_map[k] = u
    moving = {ch["key"] for ch in changes}
    group_hint = []
    for ch in changes:
        u = unit_map.get(ch["key"], [ch["key"]])
        rest = [k for k in u if k not in moving]
        if rest:
            group_hint.append({"key": ch["key"], "to": ch["to"], "members": u})
    old_v = {(v["code"], v.get("relation"), tuple(v.get("students", [])), v.get("class")) for v in before["hard"]["violations"]}
    new_v = [v for v in after["hard"]["violations"] if (v["code"], v.get("relation"), tuple(v.get("students", [])), v.get("class")) not in old_v]
    item_changes = []
    for b, a in zip(before["items"], after["items"]):
        if not b["enabled"]:
            continue
        d = a["cost"] - b["cost"]
        trend = "same"
        if d < -1e-6:
            trend = "better"
        elif d > 1e-6:
            trend = "worse"
        item_changes.append({"id": b["id"], "name": b["name"], "before": b["status_label"], "after": a["status_label"],
                             "before_dev": b["max_dev"], "after_dev": a["max_dev"], "trend": trend})
    ctx_names = [c["name"] for c in ctx.classes]
    return {
        "sizes_before": before["sizes"], "sizes_after": after["sizes"], "class_names": ctx_names,
        "caps": ctx.cap,
        "new_violations": new_v, "all_violations_after": after["hard"]["violations"],
        "allowed": not after["hard"]["violations"],
        "items": item_changes,
        "soft_before": len(before["soft"]["unmet"]), "soft_after": len(after["soft"]["unmet"]),
        "group_hint": group_hint,
        "assignment_after": new,
    }


def best_label_matching(ctx, a, b):
    """학급 이름만 바뀐 결과를 같은 편성으로 보기 위해, 겹치는 학생 수가 최대가 되도록 학급을 짝짓는다."""
    K = ctx.K
    ov = [[0] * K for _ in range(K)]
    for k in ctx.keys:
        x, y = ctx.cidx.get(a.get(k)), ctx.cidx.get(b.get(k))
        if x is not None and y is not None:
            ov[x][y] += 1
    if K <= 8:
        best, bp = -1, None
        for perm in itertools.permutations(range(K)):
            s = sum(ov[i][perm[i]] for i in range(K))
            if s > best:
                best, bp = s, perm
        return best, bp
    # 학급이 많으면 탐욕적 짝짓기
    used, perm, tot = set(), [0] * K, 0
    pairs = sorted(((ov[i][j], i, j) for i in range(K) for j in range(K)), reverse=True)
    done = set()
    for v, i, j in pairs:
        if i in done or j in used:
            continue
        perm[i] = j
        done.add(i)
        used.add(j)
        tot += v
    return tot, tuple(perm)


def structural_distance(ctx, a, b):
    same, _ = best_label_matching(ctx, a, b)
    return ctx.N - same


def compare(project, a, b, label_a="A", label_b="B"):
    ctx = Ctx(project)
    ea = evaluate(project, a, None, ctx, light=True)
    eb = evaluate(project, b, None, ctx, light=True)
    names = {c["id"]: c["name"] for c in ctx.classes}
    moved = []
    for k in ctx.keys:
        if a.get(k) != b.get(k):
            moved.append({"key": k, "name": ctx.name_of(k), "from": names.get(a.get(k), "-"), "to": names.get(b.get(k), "-")})
    items = []
    for x, y in zip(ea["items"], eb["items"]):
        if x["enabled"]:
            items.append({"name": x["name"], "a": x["status_label"], "b": y["status_label"], "a_dev": x["max_dev"], "b_dev": y["max_dev"]})
    return {"moved": moved, "moved_count": len(moved), "structural": structural_distance(ctx, a, b), "items": items,
            "hard_a": ea["hard"]["ok"], "hard_b": eb["hard"]["ok"], "soft_a": len(ea["soft"]["unmet"]), "soft_b": len(eb["soft"]["unmet"]),
            "label_a": label_a, "label_b": label_b}


# ----------------------------------------------------------------------------
# 새 번호
# ----------------------------------------------------------------------------
NUMBER_RULES = {
    "name": "이름 가나다순 (성별 구분 없음)",
    "male_first": "남학생 먼저, 각각 이름 가나다순",
    "female_first": "여학생 먼저, 각각 이름 가나다순",
    "origin": "현재 반·현재 번호 순",
}


def assign_numbers(project, assignment, rule="name"):
    ctx = Ctx(project)
    result = {}
    for cid in ctx.cids:
        members = [ctx.by_key[k] for k in ctx.keys if assignment.get(k) == cid]

        def nk(s):
            return (s.get("name") or "", s.get("sid") or "")

        if rule == "male_first":
            members.sort(key=lambda s: ((0 if s.get("gender") == "남" else 1 if s.get("gender") == "여" else 2),) + nk(s))
        elif rule == "female_first":
            members.sort(key=lambda s: ((0 if s.get("gender") == "여" else 1 if s.get("gender") == "남" else 2),) + nk(s))
        elif rule == "origin":
            members.sort(key=lambda s: (natural_key(s.get("cls") or "~"), s.get("num") if isinstance(s.get("num"), (int, float)) else 9999) + nk(s))
        else:
            members.sort(key=nk)
        for i, s in enumerate(members):
            result[s["key"]] = i + 1
    return result


# ----------------------------------------------------------------------------
# 결과 설명용 사실 목록 (AI 없이도 표시, AI는 이 값만 사용하도록 함)
# ----------------------------------------------------------------------------

def explain_facts(project, assignment, locks=None):
    ctx = Ctx(project)
    rep = evaluate(project, assignment, locks, ctx)
    names = [c["name"] for c in ctx.classes]
    facts = []

    def seq(counts):
        return ", ".join(f"{n} {c}명" for n, c in zip(names, counts))

    facts.append({"type": "hard", "text": "필수 조건을 모두 충족합니다." if rep["hard"]["ok"]
                  else f"필수 조건 위반이 {len(rep['hard']['violations'])}건 있습니다."})
    facts.append({"type": "size", "text": "학급별 인원: " + seq([c["size"] for c in rep["classes"]]) + "."})
    for it in rep["items"]:
        if not it["enabled"] or it["kind"] == "size":
            continue
        if it["kind"] == "origin":
            for row in rep["cross"]["rows"]:
                facts.append({"type": "origin", "text": f"{row['origin']} 학생 {row['total']}명은 새 학급에 " + "·".join(str(x) for x in row["counts"]) + "명으로 나뉘었습니다."})
            continue
        if it["kind"] in ("feature", "combo") and it["method"] == "count" or it["kind"] == "combo":
            c = it["cats"][0] if it["cats"] else None
            if c:
                facts.append({"type": "item", "text": f"{it['name']} — {it['count_desc'] or c['label']} {c['total']}명은 " + seq(c["counts"]) + f"으로 배치되었습니다. (상태: {it['status_label']})"})
        else:
            for c in it["cats"]:
                facts.append({"type": "item", "text": f"{it['name']} ‘{c['label']}’ {c['total']}명: " + seq(c["counts"]) + "."})
            if it.get("mean") and it["mean"]["use"]:
                means = ", ".join(f"{n} {fmt_num(m) if m is not None else '-'}" for n, m in zip(names, it["mean"]["class_means"]))
                facts.append({"type": "item", "text": f"{it['name']} 학급 평균: {means} (전체 평균 {fmt_num(it['mean']['overall'])})."})
            facts.append({"type": "status", "text": f"{it['name']} 균형 상태: {it['status_label']}."})
        if it.get("data_limited"):
            facts.append({"type": "limit", "text": f"{it['name']}: {it['data_note']}"})
    if rep["soft"]["total"]:
        facts.append({"type": "soft", "text": f"‘가급적’ 조건 {rep['soft']['total']}개 중 {rep['soft']['met']}개를 충족했습니다."})
        for u in rep["soft"]["unmet"]:
            facts.append({"type": "soft", "text": "충족하지 못한 선호 조건: " + u["message"]})
    bad = [it for it in rep["items"] if it["enabled"] and it["status"] in ("bad", "caution")]
    for it in bad:
        facts.append({"type": "possible", "text": f"[가능성 — 확인되지 않음] {it['name']}의 차이는 필수 조건·고정 배정·다른 균형 항목과의 절충 때문일 수 있습니다. ‘원인 확인(재계산)’으로 확인할 수 있습니다."})
    return {"facts": facts, "report": rep}
