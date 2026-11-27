"""자동 편성 엔진.

1) 필수 조건을 모두 만족하는 첫 편성을 '되돌아가며 찾기' 방식으로 찾는다.
   - 모든 경우를 확인했는데도 없으면 → 조건상 불가능(증명됨)
   - 탐색 한도 안에 못 찾으면 → 제한 내 미발견 (불가능하다고 단정하지 않음)
2) 필수 조건을 깨는 이동·교환은 아예 시도하지 않으면서 균형 조건을 개선한다.
   (필수 조건 위반을 감점으로만 처리하지 않음)
3) 난수 시드와 반복 횟수만으로 진행하므로 같은 입력·시드면 같은 결과가 나온다 (시간 기준 중단 없음).
4) 학급 이름만 바뀐 결과는 같은 편성으로 보고, 서로 충분히 다른 대안만 고른다.
"""
import math
import random

from .common import IMPORTANCE_W
from .evaluate import Ctx, check_hard, evaluate, must_units, rel_members, rel_pairs, structural_distance

EFFORT_ITERS = {"fast": 30000, "normal": 90000, "thorough": 250000}


class Cancelled(Exception):
    pass


class SearchModel:
    def __init__(self, project, locks=None, weight_override=None, only_items=None, ctx=None,
                 linear=None, move_penalty=0.0, origin_assign=None, max_moved=None, boost=None):
        self.project = project
        self.ctx = ctx or Ctx(project, weight_override, only_items)
        ctx = self.ctx
        K, N = ctx.K, ctx.N
        self.K, self.N = K, N
        self.cap = ctx.cap[:]
        self.share = ctx.share[:]
        units, find = must_units(project, ctx)
        self.unit_keys = units
        self.units = [[ctx.idx[k] for k in u] for u in units]
        U = len(units)
        self.U = U
        self.unit_of = [0] * N
        for ui, u in enumerate(self.units):
            for i in u:
                self.unit_of[i] = ui
        self.usize = [len(u) for u in self.units]
        # 고정 (지정 배정 + 편성안 고정)
        locks = locks or {}
        self.fixed = [None] * U
        for s in ctx.students:
            fc = s.get("fixed_class")
            if fc in ctx.cidx:
                ui = self.unit_of[ctx.idx[s["key"]]]
                if self.fixed[ui] is not None and self.fixed[ui] != ctx.cidx[fc]:
                    raise ValueError("fixed conflict")
                self.fixed[ui] = ctx.cidx[fc]
        for k, c in locks.items():
            if k in ctx.idx and c in ctx.cidx:
                ui = self.unit_of[ctx.idx[k]]
                if self.fixed[ui] is not None and self.fixed[ui] != ctx.cidx[c]:
                    raise ValueError("lock conflict")
                self.fixed[ui] = ctx.cidx[c]
        # 필수: 다른 반, 반마다 최대 N명
        self.diff = [set() for _ in range(U)]
        self.gmax = []
        self.ugc = [[] for _ in range(U)]
        # 선호
        sp = {}
        self.sgmax, self.sgw = [], []
        self.usgc = [[] for _ in range(U)]
        for r in project.get("relations", []):
            m = rel_members(ctx, r)
            must = r.get("strength") == "must"
            w = IMPORTANCE_W.get(r.get("importance", "high"), 4.0)
            if r["kind"] in ("all_diff", "pairs_diff"):
                for a, b in rel_pairs(ctx, r):
                    ua, ub = self.unit_of[ctx.idx[a]], self.unit_of[ctx.idx[b]]
                    if ua == ub:
                        continue
                    if must:
                        self.diff[ua].add(ub)
                        self.diff[ub].add(ua)
                    else:
                        key = (min(ua, ub), max(ua, ub))
                        ws, wd = sp.get(key, (0.0, 0.0))
                        sp[key] = (ws, wd + w)
            elif r["kind"] == "same" and not must and len(m) >= 2:
                pw = w / (len(m) - 1)
                for x in range(len(m)):
                    for y in range(x + 1, len(m)):
                        ua, ub = self.unit_of[ctx.idx[m[x]]], self.unit_of[ctx.idx[m[y]]]
                        if ua == ub:
                            continue
                        key = (min(ua, ub), max(ua, ub))
                        ws, wd = sp.get(key, (0.0, 0.0))
                        sp[key] = (ws + pw, wd)
            elif r["kind"] == "max_per_class" and m:
                n = int(r.get("max_n") or 0)
                cnt = {}
                for k in m:
                    ui = self.unit_of[ctx.idx[k]]
                    cnt[ui] = cnt.get(ui, 0) + 1
                if must:
                    g = len(self.gmax)
                    self.gmax.append(n)
                    for ui, c in cnt.items():
                        self.ugc[ui].append((g, c))
                else:
                    g = len(self.sgmax)
                    self.sgmax.append(n)
                    self.sgw.append(w)
                    for ui, c in cnt.items():
                        self.usgc[ui].append((g, c))
        self.spairs = [[] for _ in range(U)]
        for (a, b), (ws, wd) in sorted(sp.items()):
            self.spairs[a].append((b, ws, wd))
            self.spairs[b].append((a, ws, wd))
        # 균형 차원
        boost = boost or {}
        F, Ecol, uvec = [], [], [dict() for _ in range(U)]
        for it in ctx.items:
            if not it["enabled"]:
                continue
            W = it["weight"] * boost.get(it["id"], 1.0)
            for c in it["cats"]:
                if not c["members"]:
                    continue
                d = len(F)
                F.append(W * it["cat_factor"])
                Ecol.append(len(c["members"]))
                for i in c["members"]:
                    u = self.unit_of[i]
                    uvec[u][d] = uvec[u].get(d, 0.0) + 1.0
                c["_dim"] = d
            m = it.get("mean")
            if m and m.get("use") and m["z"]:
                d = len(F)
                F.append(W * m["factor"])
                Ecol.append(sum(m["z"].values()))
                for i, z in m["z"].items():
                    u = self.unit_of[i]
                    uvec[u][d] = uvec[u].get(d, 0.0) + z
                m["_dim"] = d
        self.D = len(F)
        self.F = F
        self.E = [[tot * self.share[k] for tot in Ecol] for k in range(K)]
        self.uvec = [sorted(v.items()) for v in uvec]
        self.L = linear  # [[coef per dim] per class] or None
        self.mu = move_penalty
        self.orig = None
        if origin_assign is not None:
            self.orig = [ctx.cidx.get(origin_assign.get(self.unit_keys[u][0]), -1) for u in range(U)]
        self.max_moved = max_moved
        self.cls = [-1] * U

    # ------------------------------------------------------------------ 상태
    def set_assignment(self, cls):
        K = self.K
        self.cls = list(cls)
        self.size = [0] * K
        self.dev = [[-self.E[k][d] for d in range(self.D)] for k in range(K)]
        self.gcnt = [[0] * K for _ in self.gmax]
        self.sgcnt = [[0] * K for _ in self.sgmax]
        self.moved = 0
        for u, k in enumerate(self.cls):
            self._add(u, k, +1)
            if self.orig is not None and k != self.orig[u]:
                self.moved += self.usize[u]

    def _add(self, u, k, sign):
        self.size[k] += sign * self.usize[u]
        row = self.dev[k]
        for d, val in self.uvec[u]:
            row[d] += sign * val
        for g, c in self.ugc[u]:
            self.gcnt[g][k] += sign * c
        for g, c in self.usgc[u]:
            self.sgcnt[g][k] += sign * c

    def apply(self, moves):
        for u, to in moves:
            fr = self.cls[u]
            if fr == to:
                continue
            self._add(u, fr, -1)
            self._add(u, to, +1)
            if self.orig is not None:
                o = self.orig[u]
                self.moved += self.usize[u] * ((to != o) - (fr != o))
            self.cls[u] = to

    def full_cost(self):
        c = 0.0
        for k in range(self.K):
            row = self.dev[k]
            for d in range(self.D):
                c += self.F[d] * row[d] * row[d]
            if self.L:
                for d in range(self.D):
                    c += self.L[k][d] * (row[d] + self.E[k][d])
        for u in range(self.U):
            for v, ws, wd in self.spairs[u]:
                if v > u:
                    c += wd if self.cls[u] == self.cls[v] else ws
        for g, n in enumerate(self.sgmax):
            for k in range(self.K):
                c += self.sgw[g] * max(0, self.sgcnt[g][k] - n)
        c += self.mu * self.moved
        return c

    # ------------------------------------------------------------- 이동 평가
    def delta(self, moves):
        """필수 조건을 깨는 이동이면 None, 아니면 비용 변화량."""
        cls = self.cls
        newc = {u: to for u, to in moves}
        dsize = {}
        dm = 0
        for u, to in moves:
            fr = cls[u]
            if fr == to:
                continue
            f = self.fixed[u]
            if f is not None and to != f:
                return None
            s = self.usize[u]
            dsize[fr] = dsize.get(fr, 0) - s
            dsize[to] = dsize.get(to, 0) + s
            if self.orig is not None:
                o = self.orig[u]
                dm += s * ((to != o) - (fr != o))
        for k, dv in dsize.items():
            if dv > 0 and self.size[k] + dv > self.cap[k]:
                return None
        for u, to in moves:
            for v in self.diff[u]:
                if newc.get(v, cls[v]) == to:
                    return None
        if self.gmax:
            dg = {}
            for u, to in moves:
                fr = cls[u]
                for g, c in self.ugc[u]:
                    dg[(g, fr)] = dg.get((g, fr), 0) - c
                    dg[(g, to)] = dg.get((g, to), 0) + c
            for (g, k), dv in dg.items():
                if dv > 0 and self.gcnt[g][k] + dv > self.gmax[g]:
                    return None
        if self.max_moved is not None and dm > 0 and self.moved + dm > self.max_moved:
            return None
        acc = {}
        for u, to in moves:
            fr = cls[u]
            if fr == to:
                continue
            for d, val in self.uvec[u]:
                a = (fr, d)
                b = (to, d)
                acc[a] = acc.get(a, 0.0) - val
                acc[b] = acc.get(b, 0.0) + val
        F, dev, L = self.F, self.dev, self.L
        delta = 0.0
        for (k, d), dv in acc.items():
            if dv == 0.0:
                continue
            delta += F[d] * (2.0 * dev[k][d] * dv + dv * dv)
            if L:
                delta += L[k][d] * dv
        for u, to in moves:
            for v, ws, wd in self.spairs[u]:
                if v in newc and v < u:
                    continue
                before = wd if cls[u] == cls[v] else ws
                after = wd if to == newc.get(v, cls[v]) else ws
                delta += after - before
        if self.sgmax:
            dg = {}
            for u, to in moves:
                fr = cls[u]
                for g, c in self.usgc[u]:
                    dg[(g, fr)] = dg.get((g, fr), 0) - c
                    dg[(g, to)] = dg.get((g, to), 0) + c
            for (g, k), dv in dg.items():
                n = self.sgmax[g]
                cur = self.sgcnt[g][k]
                delta += self.sgw[g] * (max(0, cur + dv - n) - max(0, cur - n))
        if self.mu:
            delta += self.mu * dm
        return delta

    # ------------------------------------------------- 필수 조건 만족 편성 찾기
    def _cands(self, u, rng, cls, size, gcnt):
        s = self.usize[u]
        ks = [self.fixed[u]] if self.fixed[u] is not None else list(range(self.K))
        out = []
        for k in ks:
            if size[k] + s > self.cap[k]:
                continue
            bad = False
            for v in self.diff[u]:
                if cls[v] == k:
                    bad = True
                    break
            if bad:
                continue
            for g, c in self.ugc[u]:
                if gcnt[g][k] + c > self.gmax[g]:
                    bad = True
                    break
            if not bad:
                out.append(k)
        out.sort(key=lambda k: ((size[k] + s) / max(self.share[k], 1e-9), rng.random()))
        # 대칭 제거: 아직 비어 있고 정원·비율이 같은 학급은 서로 바꿔도 같으므로 하나만 시도
        seen, res = set(), []
        for k in out:
            if size[k] == 0 and self.fixed[u] is None:
                sig = (self.cap[k], round(self.share[k], 9))
                if sig in seen:
                    continue
                seen.add(sig)
            res.append(k)
        return res

    def find_feasible(self, rng, node_limit=300000, cancel=None):
        U, K = self.U, self.K
        cls = [-1] * U
        size = [0] * K
        gcnt = [[0] * K for _ in self.gmax]
        fixed_u = [u for u in range(U) if self.fixed[u] is not None]
        cons = [u for u in range(U) if self.fixed[u] is None and (self.diff[u] or self.ugc[u])]
        free = [u for u in range(U) if self.fixed[u] is None and not self.diff[u] and not self.ugc[u]]
        fixed_u.sort(key=lambda u: (-self.usize[u], u))
        cons.sort(key=lambda u: (-len(self.diff[u]) - 2 * len(self.ugc[u]), -self.usize[u], rng.random()))
        rng.shuffle(free)
        free.sort(key=lambda u: -self.usize[u])
        order = fixed_u + cons + free
        n = len(order)
        if n == 0:
            return "ok", cls
        pc = [None] * n
        pj = [0] * n

        def assign(u, k, sign):
            size[k] += sign * self.usize[u]
            for g, c in self.ugc[u]:
                gcnt[g][k] += sign * c
            cls[u] = k if sign > 0 else -1

        def forward_ok(u):
            for v in self.diff[u]:
                if cls[v] >= 0:
                    continue
                ks = [self.fixed[v]] if self.fixed[v] is not None else range(K)
                ok = False
                for k in ks:
                    if size[k] + self.usize[v] > self.cap[k]:
                        continue
                    if any(cls[w] == k for w in self.diff[v]):
                        continue
                    ok = True
                    break
                if not ok:
                    return False
            return True

        nodes = 0
        i = 0
        pc[0] = self._cands(order[0], rng, cls, size, gcnt)
        while i >= 0:
            u = order[i]
            if cls[u] >= 0:
                assign(u, cls[u], -1)
            if pj[i] < len(pc[i]):
                k = pc[i][pj[i]]
                pj[i] += 1
                assign(u, k, +1)
                nodes += 1
                if nodes > node_limit:
                    return "limit", None
                if cancel and nodes % 5000 == 0 and cancel():
                    raise Cancelled()
                if not forward_ok(u):
                    continue
                i += 1
                if i == n:
                    return "ok", cls
                pc[i] = self._cands(order[i], rng, cls, size, gcnt)
                pj[i] = 0
            else:
                i -= 1
        return "infeasible", None

    # ------------------------------------------------------------ 균형 개선
    def improve(self, rng, iters, T0=3.0, T1=0.02, progress=None, cancel=None):
        movable = [u for u in range(self.U) if self.fixed[u] is None]
        cur = self.full_cost()
        best = cur
        best_cls = self.cls[:]
        if len(movable) >= 1 and iters > 0:
            K = self.K
            lnr = math.log(T1 / T0)
            for it in range(iters):
                if it % 2000 == 0:
                    if cancel and cancel():
                        raise Cancelled()
                    if progress:
                        progress(it / iters)
                T = T0 * math.exp(lnr * it / iters)
                u = movable[rng.randrange(len(movable))]
                if rng.random() < 0.45 or len(movable) < 2:
                    to = rng.randrange(K)
                    if to == self.cls[u]:
                        continue
                    moves = [(u, to)]
                else:
                    v = movable[rng.randrange(len(movable))]
                    if self.cls[v] == self.cls[u]:
                        continue
                    moves = [(u, self.cls[v]), (v, self.cls[u])]
                d = self.delta(moves)
                if d is None:
                    continue
                if d <= 0 or rng.random() < math.exp(-d / T):
                    self.apply(moves)
                    cur += d
                    if cur < best - 1e-9:
                        best = cur
                        best_cls = self.cls[:]
        self.set_assignment(best_cls)
        self.polish(cancel)
        return self.full_cost()

    def polish(self, cancel=None, max_pass=6):
        """한 명 이동·두 명 교환 중 좋아지는 것만 차례로 적용 (결정적)."""
        movable = [u for u in range(self.U) if self.fixed[u] is None]
        for _ in range(max_pass):
            improved = False
            for u in movable:
                for k in range(self.K):
                    if k == self.cls[u]:
                        continue
                    d = self.delta([(u, k)])
                    if d is not None and d < -1e-9:
                        self.apply([(u, k)])
                        improved = True
            if cancel and cancel():
                raise Cancelled()
            for a in range(len(movable)):
                u = movable[a]
                for b in range(a + 1, len(movable)):
                    v = movable[b]
                    if self.cls[u] == self.cls[v]:
                        continue
                    mv = [(u, self.cls[v]), (v, self.cls[u])]
                    d = self.delta(mv)
                    if d is not None and d < -1e-9:
                        self.apply(mv)
                        improved = True
            if not improved:
                break

    def assignment(self):
        out = {}
        for u, keys in enumerate(self.unit_keys):
            for k in keys:
                out[k] = self.ctx.cids[self.cls[u]]
        return out

    def cls_from_assignment(self, assignment):
        res = []
        for keys in self.unit_keys:
            res.append(self.ctx.cidx.get(assignment.get(keys[0]), -1))
        return res


# ----------------------------------------------------------------------------
def _seed_rng(seed, r):
    return random.Random(int(seed) * 7919 + r * 104729 + 17)


def solve(project, options=None, locks=None, progress=None, cancel=None):
    """반환: {status, message, alternatives:[{assignment, report, cost}], ...}
    status: ok | precheck_failed | infeasible | not_found | cancelled
    """
    from .precheck import precheck
    options = options or {}
    seed = int(options.get("seed", project.get("solver", {}).get("seed", 2027)))
    n_alt = max(1, min(3, int(options.get("alternatives", 3))))
    effort = options.get("effort", "normal")
    iters = EFFORT_ITERS.get(effort, EFFORT_ITERS["normal"])
    locks = locks or {}
    prog = progress or (lambda f, m="": None)
    prog(0.01, "조건 충돌을 검사하는 중")
    pc = precheck(project, locks)
    if not pc["ok"]:
        return {"status": "precheck_failed", "message": "조건 충돌이 있어 편성을 시작하지 않았습니다. 아래 문제를 먼저 해결하세요.", "precheck": pc}
    model = SearchModel(project, locks)
    runs = n_alt + 2
    found = []
    limit_hits = 0
    for r in range(runs):
        rng = _seed_rng(seed, r)
        base = r / runs
        prog(base + 0.02 / runs, f"대안 후보 {r + 1}/{runs}: 필수 조건을 만족하는 배치를 찾는 중")
        try:
            st, cls = model.find_feasible(rng, cancel=cancel)
        except Cancelled:
            return {"status": "cancelled", "message": "사용자가 편성을 취소했습니다. 기존 편성안은 바뀌지 않았습니다."}
        if st == "infeasible":
            return {"status": "infeasible", "precheck": pc,
                    "message": "모든 경우를 확인한 결과, 현재 필수 조건(같은 반·다른 반·반마다 최대 인원·정원·고정 배정)을 동시에 만족하는 편성은 존재하지 않습니다. "
                               "필수 조건 일부를 ‘가급적’으로 바꾸거나 정원을 조정해야 합니다. (프로그램은 필수 조건을 스스로 완화하지 않습니다)"}
        if st == "limit":
            limit_hits += 1
            continue
        model.set_assignment(cls)

        def sub(f, r=r):
            prog((r + 0.05 + 0.9 * f) / runs, f"대안 후보 {r + 1}/{runs}: 균형을 개선하는 중")

        try:
            cost = model.improve(rng, iters, progress=sub, cancel=cancel)
        except Cancelled:
            return {"status": "cancelled", "message": "사용자가 편성을 취소했습니다. 기존 편성안은 바뀌지 않았습니다."}
        found.append((cost, r, model.assignment()))
    if not found:
        return {"status": "not_found", "precheck": pc,
                "message": "정해진 탐색 한도 안에서 필수 조건을 모두 만족하는 편성을 찾지 못했습니다. 조건이 불가능하다고 확인된 것은 아닙니다. "
                           "‘꼼꼼하게’로 다시 실행하거나, 서로 얽힌 필수 조건을 줄여 보세요."}
    prog(0.97, "서로 다른 대안을 고르는 중")
    ctx = model.ctx
    min_diff = max(3, round(0.05 * ctx.N))
    found.sort(key=lambda x: (x[0], x[1]))
    chosen = []
    for cost, r, a in found:
        if all(structural_distance(ctx, a, b["assignment"]) >= min_diff for b in chosen):
            chosen.append({"assignment": a, "cost": round(cost, 3), "run": r})
        if len(chosen) >= n_alt:
            break
    alts = []
    for c in chosen:
        hard = check_hard(project, c["assignment"], locks)
        if hard:  # 안전장치: 필수 조건을 어긴 결과는 절대 내보내지 않는다
            continue
        rep = evaluate(project, c["assignment"], locks)
        alts.append({"assignment": c["assignment"], "report": rep, "seed": seed, "run": c["run"]})
    diffs = []
    for i in range(len(alts)):
        for j in range(i + 1, len(alts)):
            diffs.append({"a": i, "b": j, "students": structural_distance(ctx, alts[i]["assignment"], alts[j]["assignment"])})
    msg = f"서로 다른 대안 {len(alts)}개를 찾았습니다."
    if len(alts) < n_alt:
        msg += f" (요청 {n_alt}개 중 조건상 충분히 다른 대안은 {len(alts)}개뿐이었습니다)"
    if limit_hits:
        msg += f" 일부 시도({limit_hits}회)는 탐색 한도에 걸려 제외되었습니다."
    prog(1.0, "완료")
    return {"status": "ok", "message": msg, "alternatives": alts, "differences": diffs, "precheck": pc,
            "min_diff": min_diff, "seed": seed, "effort": effort}


# ----------------------------------------------------------------------------
# 수정 제안 (교사 요청 → 조건 → 알고리즘이 실제 이동·교환 계산)
# ----------------------------------------------------------------------------

def suggest_fix(project, assignment, locks, objective, seed=1):
    """objective = {focus:[{target, class_id?, direction: decrease|increase|balance, category?}],
                    max_moved:int, minimize_moves:bool, keep_locked:bool}"""
    ctx = Ctx(project)
    pre = check_hard(project, assignment, locks, ctx)
    if pre:
        return {"ok": False, "message": "현재 편성안이 필수 조건을 충족하지 않아 수정 제안을 계산할 수 없습니다. 먼저 필수 조건 위반을 해결하세요.", "candidates": []}
    keep_locked = objective.get("keep_locked", True)
    use_locks = locks if keep_locked else {}
    boost = {}
    for f in objective.get("focus", []):
        boost[f["target"]] = boost.get(f["target"], 1.0) * 3.0
    base_model = SearchModel(project, use_locks, ctx=Ctx(project))
    lin = None
    for f in objective.get("focus", []):
        if f.get("class_id") and f.get("direction") in ("decrease", "increase"):
            if lin is None:
                lin = [[0.0] * base_model.D for _ in range(base_model.K)]
            it = next((x for x in base_model.ctx.items if x["id"] == f["target"]), None)
            if not it:
                continue
            k = base_model.ctx.cidx.get(f["class_id"])
            if k is None:
                continue
            sign = 1.0 if f["direction"] == "decrease" else -1.0
            cats = it["cats"]
            if f.get("category"):
                cats = [c for c in cats if c["key"] == f["category"] or c["label"] == f["category"]]
            elif it["kind"] == "feature" and it.get("ftype") == "level" and len(cats) > 1:
                cats = cats[-1:]  # 단계형은 가장 높은 단계(지원 필요가 큰 쪽)를 기본 대상으로
            for c in cats:
                d = c.get("_dim")
                if d is not None:
                    lin[k][d] += sign * 3.0 * it["weight"] * it["cat_factor"] * 4
    max_moved = int(objective.get("max_moved") or 6)
    max_moved = max(1, min(40, max_moved))
    mu = 0.6 if objective.get("minimize_moves", True) else 0.05
    before = evaluate(project, assignment, locks, ctx)
    cands = []
    limits = sorted({max_moved, max(2, max_moved // 2)}, reverse=True)
    for lim in limits:
        model = SearchModel(project, use_locks, ctx=Ctx(project), linear=lin, move_penalty=mu,
                            origin_assign=assignment, max_moved=lim, boost=boost)
        model.set_assignment(model.cls_from_assignment(assignment))
        start_cost = model.full_cost()
        rng = random.Random(seed * 31 + lim)
        model.improve(rng, 20000, T0=0.4, T1=0.01)
        new = model.assignment()
        if model.full_cost() >= start_cost - 1e-6:
            continue
        if any(new == c["assignment"] for c in cands):
            continue
        hard = check_hard(project, new, use_locks)
        if hard:
            continue
        after = evaluate(project, new, locks, ctx)
        names = {c["id"]: c["name"] for c in ctx.classes}
        moves = [{"key": k, "name": ctx.name_of(k), "from": names.get(assignment.get(k)), "to": names.get(new.get(k)),
                  "from_id": assignment.get(k), "to_id": new.get(k)} for k in ctx.keys if assignment.get(k) != new.get(k)]
        improved, worse = [], []
        for b, a in zip(before["items"], after["items"]):
            if not b["enabled"]:
                continue
            if a["cost"] < b["cost"] - 1e-6:
                improved.append({"name": b["name"], "before": b["status_label"], "after": a["status_label"], "before_dev": b["max_dev"], "after_dev": a["max_dev"]})
            elif a["cost"] > b["cost"] + 1e-6:
                worse.append({"name": b["name"], "before": b["status_label"], "after": a["status_label"], "before_dev": b["max_dev"], "after_dev": a["max_dev"]})
        focus_change = []
        for f in objective.get("focus", []):
            ib = next((x for x in before["items"] if x["id"] == f["target"]), None)
            ia = next((x for x in after["items"] if x["id"] == f["target"]), None)
            if ib and ia:
                k = ctx.cidx.get(f.get("class_id")) if f.get("class_id") else None
                row = {"name": ib["name"], "class": names.get(f.get("class_id")) if f.get("class_id") else None}
                if k is not None and ib["cats"]:
                    cb = ib["cats"][-1] if not f.get("category") else next((c for c in ib["cats"] if c["key"] == f["category"] or c["label"] == f["category"]), ib["cats"][-1])
                    ca = next((c for c in ia["cats"] if c["key"] == cb["key"]), None)
                    row.update({"category": cb["label"], "before": cb["counts"][k], "after": ca["counts"][k] if ca else None})
                focus_change.append(row)
        cands.append({"assignment": new, "moves": moves, "moved_count": len(moves), "improved": improved, "worse": worse,
                      "hard_ok": True, "focus_change": focus_change,
                      "sizes_before": [c["size"] for c in before["classes"]], "sizes_after": [c["size"] for c in after["classes"]],
                      "class_names": [c["name"] for c in ctx.classes], "soft_before": len(before["soft"]["unmet"]),
                      "soft_after": len(after["soft"]["unmet"]), "limit": lim})
    if not cands:
        return {"ok": True, "message": "필수 조건과 이동 인원 제한을 지키면서 개선되는 이동·교환을 찾지 못했습니다.", "candidates": []}
    return {"ok": True, "message": f"검증을 통과한 수정 후보 {len(cands)}개를 찾았습니다. 적용하기 전에는 편성안이 바뀌지 않습니다.", "candidates": cands}


def analyze_item(project, assignment, locks, item_id, seed=7):
    """특정 항목의 불균형 원인 확인: 필수 조건만 지키고 이 항목만 우선하여 재계산해 본다."""
    ctx = Ctx(project)
    it = next((x for x in ctx.items if x["id"] == item_id), None)
    if not it:
        return {"ok": False, "message": "항목을 찾을 수 없습니다."}
    cur = evaluate(project, assignment, locks, ctx, light=True)
    ci = next(x for x in cur["items"] if x["id"] == item_id)
    proj2 = dict(project)
    model = SearchModel(proj2, locks, only_items={item_id, "builtin:size"}, weight_override={item_id: 8.0, "builtin:size": 0.5})
    model.set_assignment(model.cls_from_assignment(assignment))
    model.improve(random.Random(seed), 25000, T0=1.0, T1=0.01)
    alt = model.assignment()
    ae = evaluate(project, alt, locks, ctx, light=True)
    ai = next(x for x in ae["items"] if x["id"] == item_id)
    if ai["cost"] < ci["cost"] - 1e-3 and ai["max_dev"] < ci["max_dev"] - 0.25:
        concl = (f"확인 결과: 필수 조건만 지킨다면 ‘{ci['name']}’은(는) 최대 차이 {ci['max_dev']}명 → {ai['max_dev']}명까지 더 고르게 만들 수 있었습니다. "
                 f"따라서 현재 차이는 필수 조건 때문이라기보다 다른 균형 항목과 함께 맞추는 과정에서 생긴 절충일 가능성이 큽니다. "
                 f"이 항목의 중요도를 높이고 다시 편성하거나 ‘수정 제안’을 사용해 보세요.")
        cause = "tradeoff"
    else:
        concl = (f"확인 결과: 필수 조건을 지키면서 ‘{ci['name']}’만 우선하여 다시 계산해도 더 나은 배치를 찾지 못했습니다 (최대 차이 {ci['max_dev']}명 → {ai['max_dev']}명). "
                 f"현재 필수 조건·고정 배정·학생 분포 때문에 남은 차이일 가능성이 큽니다. (재계산 방식이므로 완전한 증명은 아닙니다)")
        cause = "constraints"
    return {"ok": True, "item": ci["name"], "current_dev": ci["max_dev"], "best_dev": ai["max_dev"],
            "current_status": ci["status_label"], "best_status": ai["status_label"], "cause": cause, "message": concl}
