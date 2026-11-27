"""검증 기준 자동 테스트.   실행: python tests/test_core.py   (pytest 로도 실행 가능)"""
import copy
import io
import json
import os
import random
import sys
import tempfile
import types

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "vendor"))
sys.path.insert(0, BASE)

from openpyxl import load_workbook  # noqa: E402

from app import ai, evaluate, excel_io, precheck, solver  # noqa: E402
from app.defaults import new_project, sample_project  # noqa: E402
from app.storage import Storage  # noqa: E402

_CACHE = {}


def solved_sample():
    if "s" not in _CACHE:
        p = sample_project()
        r = solver.solve(p, {"seed": 2027, "alternatives": 3, "effort": "fast"})
        assert r["status"] == "ok", r.get("message")
        _CACHE["s"] = (p, r)
    return _CACHE["s"]


def plan_of(p, a, locks=None):
    p = copy.deepcopy(p)
    p["plans"] = [{"id": "pl1", "name": "테스트안", "assignment": a, "original": dict(a), "locks": locks or {}, "confirmed": True, "new_numbers": {}}]
    p["active_plan_id"] = "pl1"
    return p


# 1. 편성 대상 학생의 누락과 중복이 없음 ------------------------------------------------
def test_no_missing_or_duplicate():
    p, r = solved_sample()
    elig = {s["key"] for s in p["students"] if s["eligible"]}
    excl = {s["key"] for s in p["students"] if not s["eligible"]}
    assert len(elig) == 120 and len(excl) == 2
    assert len(r["alternatives"]) == 3
    for alt in r["alternatives"]:
        a = alt["assignment"]
        lists = {c["id"]: [k for k, v in a.items() if v == c["id"]] for c in p["classes"]}
        allk = [k for ks in lists.values() for k in ks]
        assert len(allk) == len(set(allk)) == 120, "중복 또는 누락"
        assert set(allk) == elig, "편성 대상과 배정 학생이 다름"
        assert not (set(a) & excl), "편성 제외 학생이 배정됨"


# 2. 필수 조건이 모두 충족됨 (평가 모듈과 별도로 직접 확인) --------------------------------
def test_hard_constraints_all_met():
    p, r = solved_sample()
    by_sid = {s["sid"]: s["key"] for s in p["students"]}
    for alt in r["alternatives"]:
        a = alt["assignment"]
        assert evaluate.check_hard(p, a) == []
        sizes = {c["id"]: 0 for c in p["classes"]}
        for v in a.values():
            sizes[v] += 1
        assert all(sizes[c["id"]] <= c["max"] for c in p["classes"])
        assert a[by_sid["S0110"]] == "c3"  # 지정 배정
        assert a[by_sid["S0005"]] != a[by_sid["S0017"]]
        four = [a[by_sid[x]] for x in ("S0033", "S0051", "S0078", "S0102")]
        assert len(set(four)) == 4
        assert a[by_sid["S0030"]] == a[by_sid["S0045"]]
        grp = [a[by_sid[x]] for x in ("S0003", "S0014", "S0025", "S0040", "S0071", "S0099")]
        assert max(grp.count(c) for c in set(grp)) <= 2
        assert a[by_sid["S0008"]] != a[by_sid["S0009"]] and a[by_sid["S0038"]] != a[by_sid["S0039"]]


# 3. 동명이인이 정확히 구분됨 ----------------------------------------------------------
def test_same_name_students_distinct():
    p, r = solved_sample()
    kim = [s for s in p["students"] if s["name"] == "김민준"]
    lee = [s for s in p["students"] if s["name"] == "이서연"]
    assert len(kim) == 2 and len(lee) == 2
    assert len({s["key"] for s in kim + lee}) == 4 and len({s["sid"] for s in kim + lee}) == 4
    a = r["alternatives"][0]["assignment"]
    assert all(s["key"] in a for s in kim + lee)
    # 한 명에게만 조건을 걸면 다른 동명이인에게는 영향이 없어야 한다
    p2 = copy.deepcopy(p)
    p2["relations"] = [{"id": "rx", "kind": "same", "strength": "must", "members": [kim[0]["key"], lee[0]["key"]], "pairs": [], "max_n": None, "reason": ""}]
    r2 = solver.solve(p2, {"seed": 5, "alternatives": 1, "effort": "fast"})
    a2 = r2["alternatives"][0]["assignment"]
    assert a2[kim[0]["key"]] == a2[lee[0]["key"]]
    # 엑셀에서도 ID로 구분되어 두 행 모두 나와야 함
    data = excel_io.export_excel(plan_of(p, a), {"plan_id": "pl1", "mode": "public", "columns": ["name", "sid", "new_class"]})
    ws = load_workbook(io.BytesIO(data))["① 전체 편성 명단"]
    rows = [r for r in ws.iter_rows(min_row=3, values_only=True) if r[0] == "김민준"]
    assert len(rows) == 2 and rows[0][1] != rows[1][1]


# 4. 미입력이 0이나 '해당 없음'으로 바뀌지 않음 -------------------------------------------
def test_missing_is_not_zero_or_na():
    p, r = solved_sample()
    a = r["alternatives"][0]["assignment"]
    rep = evaluate.evaluate(p, a)
    peer = next(it for it in rep["items"] if it["id"] == "feature:f_peer")
    entered = sum(1 for s in p["students"] if s["eligible"] and "f_peer" in s["traits"])
    assert peer["missing"]["total"] == 120 - entered > 0
    assert sum(c["total"] for c in peer["cats"]) == entered  # 미입력은 어떤 단계에도 들어가지 않음
    assert peer["data_limited"] is True and "한계" in peer["data_note"]
    arts = next(it for it in rep["items"] if it["id"] == "feature:f_arts")
    na = sum(1 for s in p["students"] if s["eligible"] and s["traits"].get("f_arts") == [])
    miss = sum(1 for s in p["students"] if s["eligible"] and "f_arts" not in s["traits"])
    assert arts["na"]["total"] == na > 0 and arts["missing"]["total"] == miss > 0
    assert "중복 집계" in arts["multi_note"]
    learn = next(it for it in rep["items"] if it["id"] == "feature:f_learn")
    vals = [s["traits"]["f_learn"] for s in p["students"] if s["eligible"] and "f_learn" in s["traits"]]
    assert abs(learn["mean"]["overall"] - round(sum(vals) / len(vals), 2)) < 0.01  # 평균에 미입력(0) 미포함
    # 불러오기: 빈칸=미입력, '해당 없음'=[] , 범위 밖 0 은 오류 (임의 변환 금지)
    f_level = next(f for f in p["features"] if f["id"] == "f_peer")
    f_multi = next(f for f in p["features"] if f["id"] == "f_arts")
    assert excel_io.parse_feature_value(f_level, "") == (None, None)
    assert excel_io.parse_feature_value(f_multi, "해당 없음") == ([], None)
    v, err = excel_io.parse_feature_value(f_level, "0")
    assert v is None and "범위" in err
    # 저장/불러오기 후에도 미입력이 유지됨
    with tempfile.TemporaryDirectory() as d:
        st = Storage(d)
        q = copy.deepcopy(p)
        st.create(q)
        back = st.load(q["id"])
        for s0, s1 in zip(q["students"], back["students"]):
            assert ("f_peer" in s0["traits"]) == ("f_peer" in s1["traits"])
            assert s0["traits"].get("f_arts", "MISSING") == s1["traits"].get("f_arts", "MISSING")


# 5. 같은 반 그룹의 연결 관계가 올바르게 처리됨 -------------------------------------------
def test_same_group_chain():
    p, r = solved_sample()
    units, _ = evaluate.must_units(p)
    by_sid = {s["sid"]: s["key"] for s in p["students"]}
    chain = {by_sid["S0061"], by_sid["S0062"], by_sid["S0090"]}
    assert any(set(u) == chain for u in units), "A-B, B-C 가 하나의 그룹(3명)으로 묶이지 않음"
    for alt in r["alternatives"]:
        a = alt["assignment"]
        assert len({a[k] for k in chain}) == 1


# 6. 불가능한 조건을 구체적으로 안내함 ---------------------------------------------------
def _small(n_classes=3, n=12, maxs=6):
    p = new_project(n_classes=n_classes, target=n // n_classes, max_size=maxs)
    p["students"] = [{"key": f"k{i}", "sid": f"T{i:02d}", "name": f"학생{i}", "grade": 3, "cls": f"{i % 2 + 1}반", "num": i, "gender": "남" if i % 2 else "여",
                      "eligible": True, "transfer_in": False, "memo": "", "fixed_class": None, "traits": {}} for i in range(n)]
    return p


def _rel(kind, strength, members, **kw):
    d = {"id": "r" + "".join(members) + kind, "kind": kind, "strength": strength, "members": members, "pairs": kw.get("pairs", []), "max_n": kw.get("max_n"), "reason": "", "importance": "high"}
    return d


def test_impossible_conditions_reported_specifically():
    # A-B 같은 반, B-C 같은 반, A-C 반드시 다른 반
    p = _small()
    p["relations"] = [_rel("same", "must", ["k0", "k1"]), _rel("same", "must", ["k1", "k2"]), _rel("all_diff", "must", ["k0", "k2"])]
    pc = precheck.precheck(p)
    e = [x for x in pc["errors"] if x["code"] == "same_diff_conflict"]
    assert e and "학생0(T00)" in e[0]["message"] and "학생2(T02)" in e[0]["message"] and "→" in e[0]["message"]
    assert e[0]["goto"]["tab"] == "relations" and len(e[0]["relations"]) == 3
    r = solver.solve(p, {"seed": 1, "alternatives": 1, "effort": "fast"})
    assert r["status"] == "precheck_failed"
    # 모두 다른 반 그룹 > 학급 수
    p = _small()
    p["relations"] = [_rel("all_diff", "must", ["k0", "k1", "k2", "k3"])]
    assert any(x["code"] == "all_diff_too_many" for x in precheck.precheck(p)["errors"])
    # 전체 정원 부족
    p = _small(maxs=3)
    assert any(x["code"] == "capacity_total" for x in precheck.precheck(p)["errors"])
    # 같은 반 그룹 > 최대 인원
    p = _small(maxs=5)
    p["relations"] = [_rel("same", "must", ["k0", "k1", "k2", "k3", "k4", "k5"])]
    assert any(x["code"] == "unit_too_big" for x in precheck.precheck(p)["errors"])
    # 고정만으로 정원 초과
    p = _small(maxs=4)
    for i in range(5):
        p["students"][i]["fixed_class"] = "c1"
    assert any(x["code"] == "fixed_over" for x in precheck.precheck(p)["errors"])
    # 같은 학생에게 서로 다른 고정 (지정 배정 vs 편성안 고정)
    p = _small()
    p["students"][0]["fixed_class"] = "c1"
    assert any(x["code"] == "fixed_conflict" for x in precheck.precheck(p, {"k0": "c2"})["errors"])
    # 같은 반 그룹 안 서로 다른 고정
    p = _small()
    p["relations"] = [_rel("same", "must", ["k0", "k1"])]
    p["students"][0]["fixed_class"] = "c1"
    p["students"][1]["fixed_class"] = "c2"
    assert any(x["code"] == "unit_fixed_conflict" for x in precheck.precheck(p)["errors"])


def test_infeasible_vs_not_found_are_distinguished():
    # 5명이 고리 모양으로 서로 다른 반이어야 하고 학급은 2개 → 사전 검사는 통과, 전체 탐색으로 불가능 증명
    p = _small(n_classes=2, n=10, maxs=6)
    ring = [_rel("all_diff", "must", [f"k{i}", f"k{(i + 1) % 5}"]) for i in range(5)]
    p["relations"] = ring
    assert precheck.precheck(p)["ok"]
    r = solver.solve(p, {"seed": 1, "alternatives": 1, "effort": "fast"})
    assert r["status"] == "infeasible" and "모든 경우" in r["message"]
    # 탐색 한도 초과 → 'not_found' (불가능하다고 단정하지 않음)
    orig = solver.SearchModel.find_feasible
    try:
        solver.SearchModel.find_feasible = lambda self, rng, node_limit=0, cancel=None: ("limit", None)
        r2 = solver.solve(_small(), {"seed": 1, "alternatives": 1, "effort": "fast"})
    finally:
        solver.SearchModel.find_feasible = orig
    assert r2["status"] == "not_found" and "확인된 것은 아닙니다" in r2["message"]


# 7. 고정 후 재편성 시 고정 상태가 유지됨 ------------------------------------------------
def test_locks_kept_on_rerun():
    p, r = solved_sample()
    a = r["alternatives"][0]["assignment"]
    rng = random.Random(3)
    keys = rng.sample(sorted(a), 15)
    locks = {k: a[k] for k in keys}
    locks.update({k: v for k, v in a.items() if v == "c2"})  # 학급 전체 고정
    r2 = solver.solve(p, {"seed": 99, "alternatives": 3, "effort": "fast"}, locks=locks)
    assert r2["status"] == "ok"
    for alt in r2["alternatives"]:
        assert all(alt["assignment"][k] == c for k, c in locks.items())
        assert evaluate.check_hard(p, alt["assignment"], locks) == []


# 8. 수동 이동 및 교환 후 조건과 통계가 정확히 갱신됨 --------------------------------------
def test_manual_move_and_swap_update_stats():
    p, r = solved_sample()
    a = dict(r["alternatives"][0]["assignment"])
    by_key = {s["key"]: s for s in p["students"]}
    units, _ = evaluate.must_units(p)
    in_unit = {k for u in units if len(u) > 1 for k in u}
    fixed = {s["key"] for s in p["students"] if s.get("fixed_class")}
    restricted = in_unit | fixed
    for rr in p["relations"]:
        restricted |= set(rr["members"])
    k = next(k for k in sorted(a) if a[k] == "c1" and k not in restricted)
    before = evaluate.evaluate(p, a)
    pv = evaluate.preview_change(p, a, {}, [{"key": k, "to": "c2"}])
    assert pv["allowed"] and pv["sizes_after"][0] == pv["sizes_before"][0] - 1 and pv["sizes_after"][1] == pv["sizes_before"][1] + 1
    a2 = pv["assignment_after"]
    after = evaluate.evaluate(p, a2)
    g = by_key[k]["gender"]
    assert after["classes"][0]["gender"][g] == before["classes"][0]["gender"][g] - 1
    assert after["classes"][1]["gender"][g] == before["classes"][1]["gender"][g] + 1
    org = by_key[k]["cls"]
    row_b = next(x for x in before["cross"]["rows"] if x["origin"] == org)
    row_a = next(x for x in after["cross"]["rows"] if x["origin"] == org)
    assert row_a["counts"][0] == row_b["counts"][0] - 1 and row_a["counts"][1] == row_b["counts"][1] + 1
    # 교환: 인원 불변, 두 학생 반이 서로 바뀜
    k2 = next(x for x in sorted(a) if a[x] == "c3" and x not in restricted)
    pv2 = evaluate.preview_change(p, a, {}, [{"key": k, "to": "c3"}, {"key": k2, "to": "c1"}])
    assert pv2["sizes_after"] == pv2["sizes_before"] and pv2["assignment_after"][k] == "c3" and pv2["assignment_after"][k2] == "c1"
    # 같은 반 그룹 중 한 명만 이동 → 필수 조건 위반으로 확정 불가 + 그룹 이동 안내
    chain = next(u for u in units if len(u) == 3)
    tgt = next(c["id"] for c in p["classes"] if c["id"] != a[chain[0]])
    pv3 = evaluate.preview_change(p, a, {}, [{"key": chain[0], "to": tgt}])
    assert not pv3["allowed"] and pv3["group_hint"] and set(pv3["group_hint"][0]["members"]) == set(chain)
    # 그룹 전체를 옮기면 같은 반 조건은 깨지지 않는다
    pv4 = evaluate.preview_change(p, a, {}, [{"key": x, "to": tgt} for x in chain])
    assert not any(v["code"] == "rel_same" for v in pv4["new_violations"])
    # 지정 배정 학생 이동 → 위반
    fk = next(iter(fixed))
    pv5 = evaluate.preview_change(p, a, {}, [{"key": fk, "to": "c1"}])
    assert any(v["code"] == "fixed" for v in pv5["new_violations"]) and not pv5["allowed"]
    # 고정 학생 이동 → 위반
    pv6 = evaluate.preview_change(p, a, {k: a[k]}, [{"key": k, "to": "c4"}])
    assert any(v["code"] == "lock" for v in pv6["new_violations"])
    # 정원 초과 이동 → 위반
    movers = [x for x in sorted(a) if a[x] == "c1" and x not in restricted][:3]
    pv7 = evaluate.preview_change(p, a, {}, [{"key": x, "to": "c5"} for x in movers])
    assert any(v["code"] == "capacity" for v in pv7["new_violations"])


# 9. 저장 후 다시 불러와도 동일한 자료와 편성 결과가 유지됨 -------------------------------
def test_save_and_reload_identical():
    p, r = solved_sample()
    a = r["alternatives"][1]["assignment"]
    locks = {k: a[k] for k in sorted(a)[:7]}
    q = plan_of(p, a, locks)
    q["plans"][0]["new_numbers"] = evaluate.assign_numbers(q, a, "male_first")
    with tempfile.TemporaryDirectory() as d:
        st = Storage(d)
        st.create(q)
        back = st.load(q["id"])
        for k in ("students", "features", "relations", "classes", "plans", "balance", "combos", "settings"):
            assert json.dumps(q[k], sort_keys=True, ensure_ascii=False) == json.dumps(back[k], sort_keys=True, ensure_ascii=False), k
        assert evaluate.evaluate(back, back["plans"][0]["assignment"], back["plans"][0]["locks"])["items"] == evaluate.evaluate(q, a, locks)["items"]
        assert st.list()[0]["id"] == q["id"]
        st.delete(q["id"])
        assert st.list() == []


# 10. 일반 배부용 엑셀에 학생 특성 및 관계 사유가 포함되지 않음 ------------------------------
def test_public_excel_has_no_traits_or_reasons():
    p, r = solved_sample()
    q = plan_of(p, r["alternatives"][0]["assignment"])
    q["plans"][0]["new_numbers"] = evaluate.assign_numbers(q, q["plans"][0]["assignment"], "name")
    data = excel_io.export_excel(q, {"plan_id": "pl1", "mode": "public", "columns": [c for c, _ in excel_io.PUBLIC_COLUMNS]})
    assert excel_io.verify_public(data, q) == []
    wb = load_workbook(io.BytesIO(data))
    names = [ws.title for ws in wb.worksheets]
    assert names == ["① 전체 편성 명단", "② 학급별 명단", "③ 현재 반 기준 확인표", "④ 학급별 인원 및 통계"]
    text = "\n".join(str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row if v is not None)
    for f in q["features"]:
        assert f["name"] not in text
    for rr in q["relations"]:
        assert rr["reason"] not in text
    for s in q["students"]:
        if len(s["memo"]) >= 4:
            assert s["memo"] not in text
    assert all(ws.sheet_state == "visible" for ws in wb.worksheets)
    assert not any(d.hidden for ws in wb.worksheets for d in ws.column_dimensions.values())
    # 담당 교사용: 선택한 특성 포함, 사유는 선택할 때만
    staff = excel_io.export_excel(q, {"plan_id": "pl1", "mode": "staff", "columns": ["new_class", "name"], "features": ["f_learn"], "include_conditions": True})
    st_text = "\n".join(str(v) for ws in load_workbook(io.BytesIO(staff)).worksheets for row in ws.iter_rows(values_only=True) for v in row if v is not None)
    assert "전반적인 학습 수준" in st_text and q["relations"][0]["reason"] not in st_text
    staff2 = excel_io.export_excel(q, {"plan_id": "pl1", "mode": "staff", "columns": ["name"], "features": [], "include_conditions": True, "include_reasons": True})
    st2 = "\n".join(str(v) for ws in load_workbook(io.BytesIO(staff2)).worksheets for row in ws.iter_rows(values_only=True) for v in row if v is not None)
    assert q["relations"][0]["reason"] in st2
    # 새 번호와 현재 번호가 따로 보존됨
    ws = wb["① 전체 편성 명단"]
    hdr = [c.value for c in ws[2]]
    assert "새 번호" in hdr and "현재 번호" in hdr


# 추가 검증 ------------------------------------------------------------------------
def test_reproducible_with_seed_and_distinct_alternatives():
    p = sample_project()
    r1 = solver.solve(p, {"seed": 11, "alternatives": 2, "effort": "fast"})
    r2 = solver.solve(p, {"seed": 11, "alternatives": 2, "effort": "fast"})
    assert [a["assignment"] for a in r1["alternatives"]] == [a["assignment"] for a in r2["alternatives"]]
    r3 = solver.solve(p, {"seed": 12, "alternatives": 1, "effort": "fast"})
    assert r3["alternatives"][0]["assignment"] != r1["alternatives"][0]["assignment"]
    ctx = evaluate.Ctx(p)
    a = r1["alternatives"][0]["assignment"]
    swapped = {k: {"c1": "c2", "c2": "c1"}.get(v, v) for k, v in a.items()}
    assert evaluate.structural_distance(ctx, a, swapped) == 0  # 학급 이름만 바뀐 결과는 같은 편성
    assert r1["differences"][0]["students"] >= r1["min_diff"]


def test_balance_quality_and_level_distribution():
    p, r = solved_sample()
    rep = r["alternatives"][0]["report"]
    assert [c["size"] for c in rep["classes"]] == [24] * 5
    learn = next(it for it in rep["items"] if it["id"] == "feature:f_learn")
    assert learn["status"] in ("good", "caution")
    top = next(c for c in learn["cats"] if c["key"] == "v5")
    assert max(top["counts"]) - min(top["counts"]) <= 2  # 상위 단계 학생이 한 반에 몰리지 않음
    origin = next(it for it in rep["items"] if it["id"] == "builtin:origin")
    assert origin["max_dev"] <= 2.0


def test_unequal_class_sizes_proportional():
    p = sample_project()
    p["classes"][0]["target"], p["classes"][0]["max"] = 30, 31
    for c in p["classes"][1:]:
        c["target"], c["max"] = 22, 24
    r = solver.solve(p, {"seed": 3, "alternatives": 1, "effort": "fast"})
    rep = r["alternatives"][0]["report"]
    assert rep["classes"][0]["size"] in (30, 31) and all(c["size"] in (22, 23) for c in rep["classes"][1:])  # 120명 × 30/118 = 30.5
    g = next(it for it in rep["items"] if it["id"] == "builtin:gender")
    assert abs(g["cats"][0]["expected"][0] - g["cats"][0]["total"] * 30 / 118) < 0.01  # 규모에 비례한 기대 인원


def test_normalization_many_options_not_dominant():
    p = sample_project()
    for f in p["features"]:
        if f["id"] == "f_arts":
            assert f["type"] == "multi"
    ctx = evaluate.Ctx(p)
    for it in ctx.items:
        n = sum(1 for c in it["cats"] if c["members"])
        if n:
            assert abs(it["cat_factor"] - 1 / (2 * n)) < 1e-12
    wide = {"id": "f_score", "category": "기타", "name": "점수", "type": "level", "min": 0, "max": 100, "step": 1, "labels": {},
            "use_in_balance": True, "method": "distribution", "importance": "normal", "active": True, "options": []}
    p["features"].append(wide)
    ctx = evaluate.Ctx(p)
    it = next(x for x in ctx.items if x["id"] == "feature:f_score")
    assert len(it["cats"]) == 5  # 101단계를 5구간으로 묶음


def test_excel_template_import_validation():
    p = sample_project()
    tpl = excel_io.make_template(p)
    wb = load_workbook(io.BytesIO(tpl))
    assert [ws.title for ws in wb.worksheets][:3] == ["학생 명단", "특성 입력 안내", "학생 간 관계"] and "입력 예시" in wb.sheetnames
    ws = wb["학생 명단"]
    hdr = [c.value for c in ws[1]]
    col = {h: i for i, h in enumerate(hdr)}
    rows = [
        ["N001", "새학생", 3, "2", 5, "여", "", "", "", "", ],
        ["N002", "", 3, "2반", 6, "남", "", "", "", ""],               # 이름 누락
        ["N001", "중복", 3, "2반", 7, "남", "", "", "", ""],           # ID 중복
        ["N003", "다른값", 3, "2반", 8, "중성", "", "", "", ""],        # 성별 오류
        ["S0001", "덮어쓰기", 3, "1반", 1, "남", "", "", "", ""],       # 기존 학생(다름)
    ]
    for r in rows:
        r += [""] * (len(hdr) - len(r))
    rows[0][col["활동성"]] = "5"          # 범위 오류
    rows[0][col["예체능 관심 분야"]] = "음악, 요리"  # 선택지 오류
    for r in rows:
        ws.append(r)
    ws2 = wb["학생 간 관계"]
    ws2.append(["반드시", "모두 다른 반", "N001, S9999", "", "", "", ""])   # 없는 학생
    ws2.append(["가급적", "같은 반", "S0001, S0002", "", "", "높음", "테스트"])
    bio = io.BytesIO()
    wb.save(bio)
    parsed = excel_io.parse_upload(bio.getvalue(), "t.xlsx")
    sh = next(s for s in parsed["sheets"] if s["name"] == "학생 명단")
    mp = excel_io.guess_mapping(p, sh["headers"], "students")
    assert mp["sid"] == 0 and mp["name"] == 1 and "feature:f_active" in mp
    res = excel_io.validate_students(p, sh, mp)
    errs = {(e["row"], e["field"]) for e in res["errors"]}
    assert (2, "활동성") in errs and (2, "예체능 관심 분야") in errs
    assert (3, "이름") in errs and (4, "학생 ID") in errs and (5, "성별") in errs
    assert all(e["row"] is not None and e["message"] for e in res["errors"])
    assert not res["ok"]
    assert any(n["row"] == 6 and "이미 명단" in n["message"] for n in res["notes"])  # 기존 학생 내용 다름 → 기본은 건너뜀
    assert any("2반" in n["message"] for n in res["notes"])  # 숫자 반 → '2반' 저장 안내
    rsh = next(s for s in parsed["sheets"] if s["name"] == "학생 간 관계")
    rm = excel_io.guess_mapping(p, rsh["headers"], "relations")
    rr = excel_io.validate_relations(p, rsh, rm, extra_sids=["N001"])
    assert any("S9999" in e["message"] and e["row"] == 2 for e in rr["errors"])
    # 열 이름이 다른 학교 양식 (성명/학번) → 열 연결 추정
    mp2 = excel_io.guess_mapping(p, ["학번", "성명", "반", "번호", "성별"], "students")
    assert mp2["sid"] == 0 and mp2["name"] == 1 and mp2["cls"] == 2
    # 같은 파일 다시 올리면 같은 해시
    assert excel_io.parse_upload(bio.getvalue(), "t.xlsx")["hash"] == parsed["hash"]


# AI 응답 검증 --------------------------------------------------------------------
def test_ai_validation_and_privacy():
    p, r = solved_sample()
    a = r["alternatives"][0]["assignment"]
    with tempfile.TemporaryDirectory() as d:
        svc = ai.AIService(d)
        try:
            svc.prepare("settings", p, {"text": "학습 지원 학생 고르게"})
            assert False, "꺼져 있으면 준비되면 안 됨"
        except ai.AIError:
            pass
        svc.update_settings({"enabled": True, "provider": "builtin", "api_key": "sk-test-SECRET"})
        pub = svc.public_settings()
        assert "SECRET" not in json.dumps(pub) and pub["has_key"]
        assert "SECRET" not in json.dumps(p)
        prep = svc.prepare("settings", p, {"text": "학습 지원이 필요한 학생을 고르게 나누고 활동성이 높은 학생이 몰리지 않게, 협력 활동을 이끌 학생도 골고루"})
        assert not prep["external"]
        for s in p["students"]:
            assert s["name"] not in prep["payload_text"] and (not s["memo"] or s["memo"] not in prep["payload_text"])
        res = svc.send(prep["token"])
        assert res["ok"], res
        targets = {c["target"] for c in res["changes"]}
        assert "feature:f_basic" in targets and "feature:f_active" in targets
        assert any("협력" in m for m in res["missing"])  # 꺼진 항목은 '자료 없음' 안내
        # 잘못된 응답은 거부되고 아무것도 바뀌지 않음
        bad = ai.validate("settings", p, {"proposals": [{"target": "feature:없는항목", "importance": "high"}]}, {}, {})
        assert not bad["ok"] and bad["changes"] == []
        bad2 = ai.validate("settings", p, {"proposals": [{"target": "feature:f_active", "importance": "최고"}]}, {}, {})
        assert not bad2["ok"]
        bad3 = ai.validate("settings", p, {"proposals": [{"target": "feature:f_active", "method": "mean_of_everything"}]}, {}, {})
        assert not bad3["ok"]
        # 설명: 계산하지 않은 숫자를 쓰면 거부
        prep = svc.prepare("explain", p, {"assignment": a})
        for s in p["students"]:
            assert s["name"] not in prep["payload_text"]
        facts = json.loads(prep["payload_text"])["facts"]
        ok = ai.validate("explain", p, {"summary": "요약", "points": [facts[1]], "possible_causes": []}, {"facts": facts}, {})
        assert ok["ok"]
        fake = ai.validate("explain", p, {"summary": "학습 지원 학생은 9876명입니다", "points": [], "possible_causes": []}, {"facts": facts}, {})
        assert not fake["ok"] and "9876" in fake["errors"][0]
        # 수정 조건: 없는 학급 → 거부 / 정상 → 알고리즘이 후보 계산 + 필수 조건 검증
        badfix = ai.validate("fix", p, {"objective": {"focus": [{"target": "builtin:size", "class_id": "c99", "direction": "decrease"}], "max_moved": 4}}, {}, {"assignment": a})
        assert not badfix["ok"]
        good = ai.validate("fix", p, {"objective": {"focus": [{"target": "feature:f_active", "class_id": None, "direction": "balance"}], "max_moved": 6, "keep_locked": False}}, {}, {"assignment": a, "locks": {}})
        assert good["ok"] and good["objective"]["keep_locked"] is True and good["notes"]
        for c in good["fix"]["candidates"]:
            assert evaluate.check_hard(p, c["assignment"]) == [] and c["moved_count"] <= 6
        # 외부 전송은 허용하지 않으면 보내지 않음
        svc.update_settings({"provider": "openai_compat", "endpoint": "https://example.invalid/v1", "allow_external": False})
        prep = svc.prepare("settings", p, {"text": "성별 균형"})
        assert prep["external"]
        try:
            svc.send(prep["token"])
            assert False
        except ai.AIError as e:
            assert "외부 전송" in str(e)
        # 메모: 고른 학생 것만, 이름 가림
        svc.update_settings({"provider": "builtin"})
        q = copy.deepcopy(p)
        k0 = q["students"][0]["key"]
        q["students"][0]["memo"] = q["students"][1]["name"] + "와 또래 도우미 활동, 010-1234-5678"
        prep = svc.prepare("memo_tags", q, {"keys": [k0]})
        assert q["students"][1]["name"] not in prep["payload_text"] and "010-1234-5678" not in prep["payload_text"]
        res = svc.send(prep["token"])
        assert res["ok"] and res["suggestions"] and res["suggestions"][0]["proposed"] == ["또래 도우미"]
        badm = ai.validate("memo_tags", q, {"suggestions": [{"temp_id": "M1", "feature_id": "f_tags", "values": ["진단명"]}]}, {"idmap": {"M1": k0}}, {})
        assert not badm["ok"]


def test_anthropic_call_shape_with_fake_sdk():
    """실제 키 없이 SDK 호출 형태만 확인 (모델, 시스템 지시, 거부 처리)."""
    calls = {}

    class Resp:
        stop_reason = "end_turn"
        content = [types.SimpleNamespace(type="text", text='{"interpretation":"x","proposals":[],"new_combos":[],"unclear":[],"missing":[]}')]

    class Msgs:
        def create(self, **kw):
            calls.update(kw)
            return Resp()

    class Client:
        def __init__(self, **kw):
            calls["client"] = kw
            self.messages = Msgs()
            self.beta = types.SimpleNamespace(messages=Msgs())

    fake = types.ModuleType("anthropic")
    fake.Anthropic = Client
    for n in ("AuthenticationError", "PermissionDeniedError", "NotFoundError", "RateLimitError", "APIStatusError", "APIConnectionError"):
        setattr(fake, n, type(n, (Exception,), {}))
    sys.modules["anthropic"] = fake
    try:
        p = sample_project()
        with tempfile.TemporaryDirectory() as d:
            svc = ai.AIService(d)
            svc.update_settings({"enabled": True, "provider": "anthropic", "allow_external": True, "api_key": "k-test"})
            prep = svc.prepare("settings", p, {"text": "성별 균형"})
            res = svc.send(prep["token"])
            assert res["ok"]
            assert calls["model"] == "claude-opus-5-5" and calls["fallbacks"] == "default" and calls["system"].startswith("당신은")
            assert calls["messages"][0]["content"] == prep["payload_text"]  # 미리보기 = 실제 전송 내용
            assert calls["client"]["api_key"] == "k-test"
    finally:
        del sys.modules["anthropic"]


def test_numbering_keeps_current_numbers():
    p, r = solved_sample()
    a = r["alternatives"][0]["assignment"]
    nums = evaluate.assign_numbers(p, a, "name")
    for cid in ("c1", "c2"):
        ks = [k for k in a if a[k] == cid]
        assert sorted(nums[k] for k in ks) == list(range(1, len(ks) + 1))
        names = [next(s for s in p["students"] if s["key"] == k)["name"] for k in sorted(ks, key=lambda k: nums[k])]
        assert names == sorted(names)
    assert all("num" in s for s in p["students"])  # 현재 번호 필드는 그대로


def test_fix_suggestion_decrease_in_class():
    p, r = solved_sample()
    a = r["alternatives"][0]["assignment"]
    rep = evaluate.evaluate(p, a)
    basic = next(it for it in rep["items"] if it["id"] == "feature:f_basic")
    k = max(range(5), key=lambda i: basic["cats"][0]["counts"][i])
    cid = p["classes"][k]["id"]
    res = solver.suggest_fix(p, a, {}, {"focus": [{"target": "feature:f_basic", "class_id": cid, "direction": "decrease"}], "max_moved": 6, "minimize_moves": True})
    assert res["ok"] and res["candidates"]
    c = res["candidates"][0]
    after = evaluate.evaluate(p, c["assignment"])
    nb = next(it for it in after["items"] if it["id"] == "feature:f_basic")
    assert nb["cats"][0]["counts"][k] < basic["cats"][0]["counts"][k]
    assert evaluate.check_hard(p, c["assignment"]) == [] and c["moved_count"] <= 6


def test_cause_check_by_recalculation():
    p, r = solved_sample()
    a = dict(r["alternatives"][0]["assignment"])
    # 활동성 3단계 학생을 일부러 한 반에 몰아 불균형을 만든 뒤 원인 확인
    by_key = {s["key"]: s for s in p["students"]}
    units, _ = evaluate.must_units(p)
    restricted = {k for u in units if len(u) > 1 for k in u} | {s["key"] for s in p["students"] if s.get("fixed_class")}
    for rr in p["relations"]:
        restricted |= set(rr["members"])
    act3 = [k for k in sorted(a) if by_key[k]["traits"].get("f_active") == 3 and k not in restricted and a[k] != "c1"][:6]
    others = [k for k in sorted(a) if a[k] == "c1" and by_key[k]["traits"].get("f_active") != 3 and k not in restricted][:6]
    for x, y in zip(act3, others):
        a[x], a[y] = "c1", a[x]
    assert evaluate.check_hard(p, a) == []
    res = solver.analyze_item(p, a, {}, "feature:f_active")
    assert res["ok"] and res["cause"] == "tradeoff" and res["best_dev"] < res["current_dev"]
    assert "확인 결과" in res["message"]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for n, f in tests:
        try:
            f()
            print("✔ 통과", n)
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print("✖ 실패", n, e)
    print(f"\n{len(tests) - failed}/{len(tests)} 통과")
    sys.exit(1 if failed else 0)
