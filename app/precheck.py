"""자동 편성 전 조건 충돌 사전 검사.

각 문제는 관련 학생·조건과 '바로 이동' 정보(goto)를 함께 돌려준다.
필수 조건은 절대 스스로 완화하지 않는다.
"""
from collections import deque

from .evaluate import Ctx, must_units, rel_members, rel_pairs, rel_text


def _issue(level, code, title, message, students=None, relations=None, goto=None):
    return {"level": level, "code": code, "title": title, "message": message, "students": students or [],
            "relations": relations or [], "goto": goto or {}}


def _max_clique(nodes, adj, limit=20000):
    """작은 그래프의 최대 클릭 (Bron–Kerbosch, 탐색 한도 포함)."""
    best = []
    count = [0]

    def bk(r, p, x):
        count[0] += 1
        if count[0] > limit:
            return
        if not p and not x:
            if len(r) > len(best):
                best[:] = r
            return
        if len(r) + len(p) <= len(best):
            return
        pivot = max(p | x, key=lambda u: len(adj[u] & p))
        for v in list(p - adj[pivot]):
            bk(r + [v], p & adj[v], x & adj[v])
            p = p - {v}
            x = x | {v}

    bk([], set(nodes), set())
    return best


def precheck(project, locks=None):
    ctx = Ctx(project)
    locks = locks or {}
    errors, warnings, infos = [], [], []
    K = ctx.K
    names = {c["id"]: c["name"] for c in ctx.classes}
    N = ctx.N

    if K == 0:
        errors.append(_issue("error", "no_class", "학급이 없습니다", "프로젝트 화면에서 편성할 학급을 1개 이상 만드세요.", goto={"tab": "project"}))
        return {"ok": False, "errors": errors, "warnings": warnings, "infos": infos}
    if N == 0:
        errors.append(_issue("error", "no_student", "편성 대상 학생이 없습니다", "학생 명단에서 학생을 입력하거나 편성 대상으로 표시하세요.", goto={"tab": "students"}))
        return {"ok": False, "errors": errors, "warnings": warnings, "infos": infos}

    # 학생 ID 중복 / 필수값
    seen = {}
    for s in project["students"]:
        sid = (s.get("sid") or "").strip()
        if not sid:
            errors.append(_issue("error", "no_sid", "학생 ID가 비어 있음", f"{s.get('name') or '(이름 없음)'} 학생의 학생 ID를 입력하세요.", [s["key"]], goto={"tab": "students", "student": s["key"]}))
        elif sid in seen:
            errors.append(_issue("error", "dup_sid", "학생 ID 중복", f"학생 ID ‘{sid}’가 2명 이상에게 쓰였습니다. 학생 ID는 학생마다 달라야 합니다.",
                                 [seen[sid], s["key"]], goto={"tab": "students", "student": s["key"]}))
        else:
            seen[sid] = s["key"]
        if not (s.get("name") or "").strip():
            errors.append(_issue("error", "no_name", "이름이 비어 있음", f"학생 ID {sid}의 이름을 입력하세요.", [s["key"]], goto={"tab": "students", "student": s["key"]}))

    total_cap = sum(ctx.cap)
    if N > total_cap:
        errors.append(_issue("error", "capacity_total", "전체 정원 부족",
                             f"편성 대상 학생 {N}명이 학급 최대 인원 합계 {total_cap}명보다 많습니다. 학급 수나 최대 인원을 늘리세요.", goto={"tab": "project"}))
    tsum = sum(int(c.get("target") or 0) for c in ctx.classes)
    if tsum != N:
        infos.append(_issue("info", "target_sum", "목표 인원 합계 안내",
                            f"학급 목표 인원 합계는 {tsum}명, 편성 대상은 {N}명입니다. 인원 균형은 목표 인원 비율에 맞춰 계산합니다.", goto={"tab": "project"}))

    # 지정 배정 / 고정
    fixed = {}  # key -> (class, source)
    for s in ctx.students:
        fc = s.get("fixed_class")
        if fc:
            if fc not in ctx.cidx:
                errors.append(_issue("error", "fixed_missing", "존재하지 않는 학급에 지정 배정",
                                     f"{ctx.name_of(s['key'])} 학생의 지정 학급이 현재 학급 목록에 없습니다.", [s["key"]], goto={"tab": "students", "student": s["key"]}))
            else:
                fixed[s["key"]] = (fc, "지정 배정")
    for k, c in locks.items():
        if k not in ctx.idx:
            continue
        if c not in ctx.cidx:
            continue
        if k in fixed and fixed[k][0] != c:
            errors.append(_issue("error", "fixed_conflict", "같은 학생에게 서로 다른 학급 고정",
                                 f"{ctx.name_of(k)} 학생은 {names[fixed[k][0]]}에 지정 배정되어 있지만, 편성안에서는 {names[c]}에 고정되어 있습니다.",
                                 [k], goto={"tab": "students", "student": k}))
        else:
            fixed.setdefault(k, (c, "편성안 고정"))

    # 같은 반 묶음
    units, find = must_units(project, ctx)
    unit_of = {}
    for ui, u in enumerate(units):
        for k in u:
            unit_of[k] = ui
    # 같은 반 연결 그래프 (경로 설명용)
    sg = {k: [] for k in ctx.keys}
    for r in project.get("relations", []):
        if r.get("strength") == "must" and r["kind"] == "same":
            m = rel_members(ctx, r)
            for a in m[1:]:
                sg[m[0]].append((a, r["id"]))
                sg[a].append((m[0], r["id"]))

    def path(a, b):
        prev = {a: None}
        dq = deque([a])
        while dq:
            x = dq.popleft()
            if x == b:
                break
            for y, rid in sg[x]:
                if y not in prev:
                    prev[y] = (x, rid)
                    dq.append(y)
        if b not in prev:
            return [], []
        nodes, rels = [b], []
        while prev[nodes[-1]] is not None:
            x, rid = prev[nodes[-1]]
            rels.append(rid)
            nodes.append(x)
        return list(reversed(nodes)), list(reversed(rels))

    unit_fixed = {}
    for ui, u in enumerate(units):
        fs = {}
        for k in u:
            if k in fixed:
                fs.setdefault(fixed[k][0], []).append(k)
        if len(fs) > 1:
            desc = "; ".join(f"{names[c]}: " + ", ".join(ctx.name_of(k) for k in ks) for c, ks in fs.items())
            rels = sorted({rid for k in u for _, rid in sg[k]})
            errors.append(_issue("error", "unit_fixed_conflict", "같은 반 그룹에 서로 다른 학급 고정",
                                 f"반드시 같은 반이어야 하는 그룹 안에 서로 다른 학급으로 고정된 학생이 있습니다. ({desc})",
                                 list(u), rels, goto={"tab": "relations", "relation": rels[0] if rels else None}))
        elif fs:
            unit_fixed[ui] = next(iter(fs))
        if len(u) > max(ctx.cap):
            rels = sorted({rid for k in u for _, rid in sg[k]})
            errors.append(_issue("error", "unit_too_big", "같은 반 그룹이 학급 최대 인원보다 큼",
                                 f"반드시 같은 반이어야 하는 학생 {len(u)}명이 연결되어 있지만, 가장 큰 학급의 최대 인원은 {max(ctx.cap)}명입니다.",
                                 list(u), rels, goto={"tab": "relations", "relation": rels[0] if rels else None}))
        elif ui in unit_fixed and len(u) > ctx.cap[ctx.cidx[unit_fixed[ui]]]:
            errors.append(_issue("error", "unit_too_big_fixed", "고정 학급 정원 초과",
                                 f"{names[unit_fixed[ui]]}에 고정된 같은 반 그룹 {len(u)}명이 그 학급 최대 인원보다 많습니다.", list(u), goto={"tab": "relations"}))

    # 고정 배정만으로 정원 초과
    load = [0] * K
    for ui, c in unit_fixed.items():
        load[ctx.cidx[c]] += len(units[ui])
    for k in range(K):
        if load[k] > ctx.cap[k]:
            ks = [x for ui, c in unit_fixed.items() if ctx.cidx[c] == k for x in units[ui]]
            errors.append(_issue("error", "fixed_over", "고정 배정만으로 정원 초과",
                                 f"{ctx.classes[k]['name']}에 지정·고정된 학생이 {load[k]}명으로 최대 인원 {ctx.cap[k]}명을 넘습니다.", ks,
                                 goto={"tab": "students"}))

    # 다른 반 조건
    diff_adj = {}
    for r in project.get("relations", []):
        if r.get("strength") != "must":
            continue
        m = rel_members(ctx, r)
        allm = [k for k in r.get("members", [])]
        excluded = [k for k in allm if k not in ctx.idx and k in ctx.by_key]
        missing = [k for k in allm if k not in ctx.by_key]
        if excluded:
            warnings.append(_issue("warning", "rel_excluded", "편성 제외 학생이 포함된 조건",
                                   rel_text(ctx, r) + " — 편성 제외 학생은 이 조건에서 무시됩니다: " + ", ".join(ctx.name_of(k) for k in excluded),
                                   excluded, [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
        if missing:
            errors.append(_issue("error", "rel_missing", "삭제된 학생을 참조하는 조건", "명단에 없는 학생이 조건에 남아 있습니다. 조건을 수정하세요.",
                                 [], [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
        if r["kind"] in ("all_diff", "pairs_diff"):
            for a, b in rel_pairs(ctx, r):
                if find(a) == find(b):
                    nodes, rels = path(a, b)
                    chain = " → ".join(ctx.name_of(x) for x in nodes)
                    errors.append(_issue("error", "same_diff_conflict", "같은 반 조건과 다른 반 조건 충돌",
                                         f"{ctx.name_of(a)}와(과) {ctx.name_of(b)}는 반드시 다른 반이어야 하지만, ‘반드시 같은 반’ 조건이 "
                                         f"{chain} 으로 이어져 같은 반이 되어야 합니다.",
                                         nodes, rels + [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
                else:
                    ua, ub = unit_of[a], unit_of[b]
                    diff_adj.setdefault(ua, set()).add(ub)
                    diff_adj.setdefault(ub, set()).add(ua)
                    if ua in unit_fixed and ub in unit_fixed and unit_fixed[ua] == unit_fixed[ub]:
                        errors.append(_issue("error", "fixed_diff_conflict", "다른 반 조건과 고정 학급 충돌",
                                             f"{ctx.name_of(a)}와(과) {ctx.name_of(b)}는 반드시 다른 반이어야 하지만 둘 다 {names[unit_fixed[ua]]}에 고정되어 있습니다.",
                                             [a, b], [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
            if r["kind"] == "all_diff" and len({unit_of[k] for k in m}) > K:
                errors.append(_issue("error", "all_diff_too_many", "모두 다른 반 그룹이 학급 수보다 많음",
                                     f"‘모두 서로 다른 반’ 그룹의 학생은 {len(m)}명인데 학급은 {K}개뿐입니다. 이 조건은 ‘반마다 최대 N명’으로 바꾸는 것을 검토하세요.",
                                     m, [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
        if r["kind"] == "max_per_class":
            n = int(r.get("max_n") or 0)
            if n <= 0:
                errors.append(_issue("error", "max_zero", "반마다 최대 인원이 0", "‘반마다 최대 N명’의 N을 1 이상으로 입력하세요.", m, [r["id"]],
                                     goto={"tab": "relations", "relation": r["id"]}))
                continue
            if len(m) > n * K:
                errors.append(_issue("error", "max_impossible", "반마다 최대 N명 조건을 지킬 수 없음",
                                     f"그룹 학생 {len(m)}명을 {K}개 학급에 반마다 최대 {n}명씩 배치하면 최대 {n * K}명까지만 가능합니다.",
                                     m, [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
            per_unit = {}
            for k in m:
                per_unit.setdefault(unit_of[k], []).append(k)
            for ui, ks in per_unit.items():
                if len(ks) > n:
                    errors.append(_issue("error", "max_unit_conflict", "같은 반 조건과 반마다 최대 N명 조건 충돌",
                                         f"같은 반이어야 하는 학생 중 {len(ks)}명이 이 그룹에 속해 있어 ‘반마다 최대 {n}명’을 지킬 수 없습니다: " + ", ".join(ctx.name_of(k) for k in ks),
                                         ks, [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
            fc = {}
            for k in m:
                ui = unit_of[k]
                if ui in unit_fixed:
                    fc.setdefault(unit_fixed[ui], []).append(k)
            for c, ks in fc.items():
                if len(ks) > n:
                    errors.append(_issue("error", "max_fixed_conflict", "고정 배정과 반마다 최대 N명 조건 충돌",
                                         f"{names[c]}에 고정된 그룹 학생이 {len(ks)}명으로 ‘반마다 최대 {n}명’을 넘습니다.", ks, [r["id"]],
                                         goto={"tab": "relations", "relation": r["id"]}))
        if len(m) < 2 and r["kind"] != "max_per_class":
            warnings.append(_issue("warning", "rel_small", "학생이 1명 이하인 조건", rel_text(ctx, r) + " — 편성 대상 학생이 2명 미만이라 의미가 없습니다.",
                                   m, [r["id"]], goto={"tab": "relations", "relation": r["id"]}))

    # 서로 반드시 다른 반인 묶음이 학급 수보다 많은지 (클릭 검사)
    seen_nodes = set()
    for start in list(diff_adj):
        if start in seen_nodes:
            continue
        comp, dq = [], deque([start])
        seen_nodes.add(start)
        while dq:
            x = dq.popleft()
            comp.append(x)
            for y in diff_adj.get(x, ()):
                if y not in seen_nodes:
                    seen_nodes.add(y)
                    dq.append(y)
        if len(comp) <= K or len(comp) > 60:
            continue
        cl = _max_clique(comp, {u: diff_adj.get(u, set()) for u in comp})
        if len(cl) > K:
            ks = [units[u][0] for u in cl]
            errors.append(_issue("error", "diff_clique", "서로 다른 반이어야 하는 학생이 학급 수보다 많음",
                                 f"서로 모두 다른 반이어야 하는 학생(또는 같은 반 그룹) {len(cl)}개가 서로 얽혀 있는데 학급은 {K}개입니다: "
                                 + ", ".join(ctx.name_of(k) for k in ks), ks, goto={"tab": "relations"}))
    # 다른 반 상대가 모든 학급에 고정되어 갈 곳이 없는 경우
    for ui, nb in diff_adj.items():
        if ui in unit_fixed:
            continue
        blocked = {unit_fixed[v] for v in nb if v in unit_fixed}
        if len(blocked) >= K:
            errors.append(_issue("error", "no_room", "배정 가능한 학급이 없음",
                                 f"{ctx.name_of(units[ui][0])} 학생과 반드시 다른 반이어야 하는 학생들이 모든 학급에 고정되어 있어 배정할 학급이 없습니다.",
                                 units[ui], goto={"tab": "relations"}))

    # 선호 조건과 필수 조건 충돌 (경고)
    must_diff_pairs = set()
    for r in project.get("relations", []):
        if r.get("strength") == "must" and r["kind"] in ("all_diff", "pairs_diff"):
            for a, b in rel_pairs(ctx, r):
                must_diff_pairs.add(frozenset((a, b)))
    for r in project.get("relations", []):
        if r.get("strength") != "prefer":
            continue
        m = rel_members(ctx, r)
        if r["kind"] == "same":
            for i in range(len(m)):
                for j in range(i + 1, len(m)):
                    if frozenset((m[i], m[j])) in must_diff_pairs:
                        warnings.append(_issue("warning", "prefer_conflict", "충족할 수 없는 ‘가급적’ 조건",
                                               f"{ctx.name_of(m[i])}·{ctx.name_of(m[j])}는 ‘반드시 다른 반’이므로 ‘가급적 같은 반’ 조건은 충족될 수 없습니다.",
                                               [m[i], m[j]], [r["id"]], goto={"tab": "relations", "relation": r["id"]}))
        if r["kind"] in ("all_diff", "pairs_diff"):
            for a, b in rel_pairs(ctx, r):
                if find(a) == find(b):
                    warnings.append(_issue("warning", "prefer_conflict", "충족할 수 없는 ‘가급적’ 조건",
                                           f"{ctx.name_of(a)}·{ctx.name_of(b)}는 ‘반드시 같은 반’이므로 ‘가급적 다른 반’ 조건은 충족될 수 없습니다.",
                                           [a, b], [r["id"]], goto={"tab": "relations", "relation": r["id"]}))

    # 자료 부족
    for it in ctx.items:
        if it["enabled"] and it["kind"] in ("feature", "combo") and ctx.N:
            rate = len(it["missing"]) / ctx.N
            if rate >= 0.2:
                warnings.append(_issue("warning", "missing_data", "자료 부족 항목",
                                       f"‘{it['name']}’은(는) 편성 대상 {ctx.N}명 중 {len(it['missing'])}명({round(rate * 100)}%)이 미입력입니다. "
                                       f"입력된 학생만으로 균형을 맞추므로 결과 해석에 한계가 있습니다.",
                                       goto={"tab": "students"}))
            if not any(c["members"] for c in it["cats"]) and not (it.get("mean") and it["mean"].get("use")):
                warnings.append(_issue("warning", "no_data", "입력 자료가 없는 균형 항목",
                                       f"‘{it['name']}’을(를) 편성에 반영하도록 설정했지만 해당 학생 자료가 없습니다.", goto={"tab": "features"}))
    nogender = [s["key"] for s in ctx.students if not (s.get("gender") or "").strip()]
    if nogender:
        infos.append(_issue("info", "no_gender", "성별 미입력", f"성별이 입력되지 않은 학생 {len(nogender)}명은 성별 균형 계산에서 제외됩니다.",
                            nogender, goto={"tab": "students"}))
    byname = {}
    for s in project["students"]:
        byname.setdefault((s.get("name") or "").strip(), []).append(s)
    dups = {n: ss for n, ss in byname.items() if n and len(ss) > 1}
    if dups:
        infos.append(_issue("info", "same_name", "동명이인 안내",
                            "이름이 같은 학생이 있습니다. 프로그램은 학생 ID로 구분합니다: "
                            + "; ".join(f"{n} — " + ", ".join(f"{s.get('sid')}({s.get('cls') or '반 없음'})" for s in ss) for n, ss in dups.items()),
                            [s["key"] for ss in dups.values() for s in ss], goto={"tab": "students"}))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "infos": infos}
