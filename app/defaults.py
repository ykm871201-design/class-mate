"""기본 특성 항목, 새 프로젝트, 가상 예시 데이터."""
import copy
import random

from .common import new_id, now_iso

SCHEMA_VERSION = 1


def _lv(fid, cat, name, desc, lo, hi, labels, method="distribution", importance="normal", count_min=None):
    return {
        "id": fid, "category": cat, "name": name, "desc": desc, "type": "level",
        "options": [], "min": lo, "max": hi, "step": 1, "labels": labels,
        "use_in_balance": True, "method": method, "importance": importance,
        "count_values": [], "count_min": count_min, "include_in_export": False, "active": False,
    }


def _yn(fid, cat, name, desc, importance="high"):
    return {
        "id": fid, "category": cat, "name": name, "desc": desc, "type": "yesno",
        "options": [], "use_in_balance": True, "method": "count", "importance": importance,
        "count_values": [], "include_in_export": False, "active": False,
    }


def _sel(fid, cat, name, desc, typ, options, method="distribution", importance="low", use=True):
    return {
        "id": fid, "category": cat, "name": name, "desc": desc, "type": typ,
        "options": list(options), "use_in_balance": use, "method": method, "importance": importance,
        "count_values": [], "include_in_export": False, "active": False,
    }


L5 = {"1": "기초부터 차근차근", "2": "조금 지원 필요", "3": "보통", "4": "잘함", "5": "매우 잘함"}
NEED3 = {"1": "거의 필요 없음", "2": "가끔 필요", "3": "자주 필요"}
LOW3 = {"1": "낮음", "2": "보통", "3": "높음"}


def default_features():
    A, B, C, D = "학습 관련", "생활 및 관계 관련", "교육적 지원 관련", "기타"
    feats = [
        _lv("f_learn", A, "전반적인 학습 수준", "교사가 판단한 전반적인 학습 수준 (1~5단계)", 1, 5, L5, "both", "high"),
        _lv("f_kor", A, "국어 학습 수준", "국어 교과 학습 수준 (1~5단계)", 1, 5, L5),
        _lv("f_math", A, "수학 학습 수준", "수학 교과 학습 수준 (1~5단계)", 1, 5, L5),
        _yn("f_basic", A, "기초학습 지원 필요 여부", "기초학습(읽기·쓰기·셈하기) 지원이 필요한지"),
        _lv("f_engage", A, "과제 수행 및 학습 참여 정도", "과제 수행과 수업 참여 정도", 1, 3, {"1": "지원 필요", "2": "보통", "3": "적극적"}),
        _lv("f_active", B, "활동성", "수업·생활 중 활동성 (차분함~활발함)", 1, 3, {"1": "차분함", "2": "보통", "3": "활발함"}, "distribution", "normal"),
        _lv("f_selfreg", B, "자기조절 지원 필요 정도", "감정·행동 조절에 교사 지원이 필요한 정도", 1, 3, NEED3, "distribution", "high"),
        _lv("f_peer", B, "또래 관계 지원 필요 정도", "친구 관계 형성에 지원이 필요한 정도", 1, 3, NEED3, "distribution", "normal"),
        _lv("f_leader", B, "리더 역할 성향", "모둠이나 학급에서 이끄는 역할을 맡는 성향", 1, 3, LOW3, "count", "normal", count_min=3),
        _lv("f_coop", B, "협력 활동 참여 정도", "모둠·협력 활동 참여 정도", 1, 3, LOW3),
        _lv("f_guide", B, "갈등 중재 및 생활지도 지원 필요 정도", "갈등 상황에서 교사의 중재·생활지도가 필요한 정도", 1, 3, NEED3, "distribution", "high"),
        _yn("f_iep", C, "개별적인 교육 지원 필요 여부", "개별화된 교육 지원이 필요한지 (구체적 진단명은 입력하지 마세요)"),
        _yn("f_kolang", C, "한국어 학습 지원 필요 여부", "한국어 학습 지원이 필요한지"),
        _lv("f_extra", C, "수업 참여를 위한 추가 지원 필요 정도", "수업 참여에 추가 지원이 필요한 정도", 1, 3, NEED3, "distribution", "normal"),
        _sel("f_othersup", C, "기타 지원 항목 (교사 지정)", "교사가 선택지 이름을 바꿔 사용하세요", "multi", ["지원 항목 1", "지원 항목 2"], "distribution", "normal"),
        _sel("f_arts", D, "예체능 관심 분야", "관심 있는 예체능 분야 (여러 개 선택 가능)", "multi", ["음악", "미술", "체육", "무용·연극"], "distribution", "low"),
        _sel("f_tags", D, "교사 태그", "교사가 직접 만든 태그 (선택지를 자유롭게 바꾸세요)", "multi", ["태그 A", "태그 B", "태그 C"], "none", "low", use=False),
        {"id": "f_note", "category": D, "name": "참고용 메모", "desc": "참고용 메모 (편성 계산에 사용하지 않음)", "type": "text",
         "options": [], "use_in_balance": False, "method": "none", "importance": "low", "count_values": [],
         "include_in_export": False, "active": False},
    ]
    return feats


def default_balance():
    return {
        "size": {"enabled": True, "importance": "very_high"},
        "gender": {"enabled": True, "importance": "high"},
        "origin": {"enabled": True, "importance": "normal"},
    }


def class_names(pattern, n):
    if pattern == "number":
        return [f"{i + 1}반" for i in range(n)]
    ga = "가나다라마바사아자차카타파하"
    return [f"{ga[i]}반" if i < len(ga) else f"{i + 1}반" for i in range(n)]


def new_project(name="새 편성 프로젝트", school_year=2027, current_grade=3, next_grade=4,
                n_classes=5, pattern="ga", target=24, max_size=26):
    classes = [{"id": f"c{i + 1}", "name": nm, "target": target, "max": max_size}
               for i, nm in enumerate(class_names(pattern, n_classes))]
    return {
        "schema": SCHEMA_VERSION,
        "id": new_id("p"),
        "name": name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "settings": {"school_year": school_year, "current_grade": current_grade, "next_grade": next_grade},
        "classes": classes,
        "students": [],
        "features": default_features(),
        "combos": [],
        "relations": [],
        "balance": default_balance(),
        "solver": {"seed": 2027, "alternatives": 3, "effort": "normal"},
        "plans": [],
        "active_plan_id": None,
        "change_log": [],
        "import_hashes": [],
    }


def normalize_project(p):
    """예전 저장본이나 불완전한 자료를 안전하게 보완한다 (학생 값은 바꾸지 않는다)."""
    base = new_project()
    for k, v in base.items():
        if k not in p:
            p[k] = copy.deepcopy(v)
    for k, v in default_balance().items():
        p["balance"].setdefault(k, v)
    for s in p["students"]:
        s.setdefault("traits", {})
        s.setdefault("eligible", True)
        s.setdefault("transfer_in", False)
        s.setdefault("memo", "")
        s.setdefault("fixed_class", None)
    for pl in p["plans"]:
        pl.setdefault("locks", {})
        pl.setdefault("original", dict(pl.get("assignment", {})))
        pl.setdefault("confirmed", False)
        pl.setdefault("new_numbers", {})
    return p


# ----------------------------------------------------------------------------
# 가상 예시 데이터 (실존 인물과 무관한 무작위 조합 이름)
# ----------------------------------------------------------------------------
SURNAMES = list("김이박최정강조윤장임한오서신권황안송류홍")
GIVEN_M = ["민준", "서준", "도윤", "예준", "시우", "하준", "주원", "지호", "지후", "준우", "준서", "건우", "현우", "우진", "선우",
           "연우", "유준", "정우", "승우", "승현", "시윤", "준혁", "은우", "지환", "승민", "지우", "윤우", "민재", "현준", "태윤"]
GIVEN_F = ["서연", "서윤", "지우", "서현", "민서", "하은", "하윤", "윤서", "지유", "지민", "채원", "수아", "지아", "지윤", "다은",
           "은서", "예은", "수빈", "소율", "예린", "하린", "유나", "시은", "채은", "가은", "윤아", "아린", "예원", "나연", "다인"]
MEMOS = ["모둠 활동에서 친구를 잘 도와줌", "수학 문장제 연습 중", "발표를 어려워하지만 꾸준히 노력함", "미술 활동에 관심이 많음",
         "체육 시간에 적극적으로 참여함", "독서를 좋아함", "새 학년 적응을 위해 담임 관심 필요", "음악 시간에 리코더를 즐겨 연주함",
         "", "", "", "", "", ""]


def _pick(rng, weights):
    r = rng.random() * sum(weights)
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return i
    return len(weights) - 1


def sample_project(seed=2026):
    rng = random.Random(seed)
    p = new_project(name="[예시] 2027학년도 4학년 학급 편성 (가상 학생 120명)", school_year=2027,
                    current_grade=3, next_grade=4, n_classes=5, pattern="ga", target=24, max_size=26)
    p["solver"]["seed"] = 2027
    active = {"f_learn", "f_math", "f_basic", "f_active", "f_selfreg", "f_peer", "f_leader", "f_guide",
              "f_iep", "f_kolang", "f_arts", "f_tags", "f_note"}
    for f in p["features"]:
        f["active"] = f["id"] in active
        if f["id"] in ("f_learn", "f_basic", "f_iep", "f_leader"):
            f["include_in_export"] = True
        if f["id"] == "f_tags":
            f["options"] = ["또래 도우미", "학급 행사 참여", "방과후 연계"]
    students = []
    used = set()
    seq = 0

    def make_name(gender):
        while True:
            nm = rng.choice(SURNAMES) + rng.choice(GIVEN_M if gender == "남" else GIVEN_F)
            if nm not in used:
                used.add(nm)
                return nm

    for cls in range(1, 5):
        for num in range(1, 31):
            seq += 1
            gender = "남" if (num <= 15) else "여"
            students.append({
                "key": "k%04d" % seq, "sid": "S%04d" % seq, "name": make_name(gender),
                "grade": 3, "cls": f"{cls}반", "num": num, "gender": gender,
                "eligible": True, "transfer_in": False, "memo": "", "fixed_class": None, "traits": {},
            })
    # 동명이인: 다른 반에 '김민준' 2명, 같은 반(2반)에 '이서연' 2명
    students[2]["name"] = "김민준"
    students[62]["name"] = "김민준"
    students[45]["name"] = "이서연"
    students[46]["name"] = "이서연"
    # 전출 예정(편성 제외) 2명
    for idx in (10, 95):
        students[idx]["eligible"] = False
        students[idx]["memo"] = "전출 예정 (편성 제외)"
    # 전입 예정 2명
    for g in ("남", "여"):
        seq += 1
        students.append({
            "key": "k%04d" % seq, "sid": "S%04d" % seq, "name": make_name(g), "grade": 3, "cls": "", "num": None,
            "gender": g, "eligible": True, "transfer_in": True, "memo": "전입 예정", "fixed_class": None, "traits": {},
        })
    for s in students:
        t = s["traits"]
        lv = 1 + _pick(rng, [1, 2, 4, 2.5, 1])
        if rng.random() > 0.04:
            t["f_learn"] = lv
        if rng.random() > 0.06:
            t["f_math"] = max(1, min(5, lv + rng.choice([-1, 0, 0, 1])))
        if rng.random() > 0.03:
            t["f_basic"] = lv <= 1 or (lv == 2 and rng.random() < 0.3)
        if rng.random() > 0.03:
            t["f_active"] = 1 + _pick(rng, [1, 2, 1.3] if s["gender"] == "여" else [0.8, 2, 1.6])
        if rng.random() > 0.05:
            t["f_selfreg"] = 1 + _pick(rng, [6, 2.5, 0.8])
        if rng.random() > 0.27:  # 일부러 미입력이 많은 항목 (자료 부족 안내 확인용)
            t["f_peer"] = 1 + _pick(rng, [6, 2.5, 1])
        if rng.random() > 0.03:
            t["f_leader"] = 1 + _pick(rng, [2, 3, 1.2])
        if rng.random() > 0.05:
            t["f_guide"] = 1 + _pick(rng, [6, 2.5, 0.8])
        if rng.random() > 0.02:
            t["f_iep"] = rng.random() < 0.05
        if rng.random() > 0.02:
            t["f_kolang"] = rng.random() < 0.04
        r = rng.random()
        if r < 0.08:
            pass  # 미입력
        elif r < 0.25:
            t["f_arts"] = []  # 해당 없음
        else:
            t["f_arts"] = sorted(rng.sample(["음악", "미술", "체육", "무용·연극"], k=1 + _pick(rng, [5, 2, 0.5])),
                                 key=["음악", "미술", "체육", "무용·연극"].index)
        if rng.random() < 0.2:
            t["f_tags"] = [rng.choice(["또래 도우미", "학급 행사 참여", "방과후 연계"])]
        memo = rng.choice(MEMOS)
        if memo and not s["memo"]:
            s["memo"] = memo
    p["students"] = students
    K = {s["sid"]: s["key"] for s in students}

    def rel(kind, strength, sids, reason="", max_n=None, pairs=None, importance="high"):
        return {"id": new_id("r"), "kind": kind, "strength": strength, "members": [K[x] for x in sids],
                "pairs": [[K[a], K[b]] for a, b in (pairs or [])], "max_n": max_n, "reason": reason,
                "importance": importance}

    p["relations"] = [
        rel("all_diff", "must", ["S0005", "S0017"], "교사 판단: 서로 다른 반 배치 필요"),
        rel("all_diff", "must", ["S0033", "S0051", "S0078", "S0102"], "교사 판단 (4명 모두 다른 반)"),
        rel("same", "must", ["S0030", "S0045"], "교사 판단: 같은 반 배치"),
        rel("same", "must", ["S0061", "S0062"], "교사 판단"),
        rel("same", "must", ["S0062", "S0090"], "교사 판단 (S0061-S0062와 연결되어 3명이 한 그룹이 됨)"),
        rel("max_per_class", "must", ["S0003", "S0014", "S0025", "S0040", "S0071", "S0099"], "교사 판단: 한 반에 몰리지 않게", max_n=2),
        rel("pairs_diff", "must", ["S0008", "S0009", "S0038", "S0039"], "교사 판단", pairs=[("S0008", "S0009"), ("S0038", "S0039")]),
        rel("same", "prefer", ["S0012", "S0020"], "적응 지원을 위해 가능하면 같은 반"),
        rel("all_diff", "prefer", ["S0050", "S0052"], "가능하면 다른 반", importance="normal"),
        rel("all_diff", "prefer", ["S0070", "S0080", "S0085"], "가능하면 서로 다른 반", importance="normal"),
    ]
    # 지정 배정 1명 (교사가 특정 학급을 지정)
    for s in students:
        if s["sid"] == "S0110":
            s["fixed_class"] = "c3"
    return p
