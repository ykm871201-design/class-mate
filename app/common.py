"""공통 상수와 도우미 함수.

학생 특성 값의 규칙 (미입력과 '해당 없음'을 엄격히 구분한다)
- single : 선택지 문자열, 미입력은 None
- multi  : 선택지 목록(list). 빈 목록 [] 은 '해당 없음', None 은 미입력
- level  : 숫자, 미입력은 None (0 으로 바꾸지 않는다)
- yesno  : True / False, 미입력은 None
- text   : 문자열 (편성 계산에 사용하지 않음)
"""
import math
import time
import uuid

IMPORTANCE = ["low", "normal", "high", "very_high"]
IMPORTANCE_LABEL = {"low": "낮음", "normal": "보통", "high": "높음", "very_high": "매우 높음"}
IMPORTANCE_W = {"low": 1.0, "normal": 2.0, "high": 4.0, "very_high": 8.0}

FEATURE_TYPES = {
    "single": "단일 선택",
    "multi": "다중 선택",
    "level": "숫자 또는 단계",
    "yesno": "예/아니요",
    "text": "자유 메모",
}
METHODS = {
    "distribution": "선택지·단계별 인원을 고르게",
    "mean": "학급 평균을 비슷하게",
    "both": "단계별 분포 + 평균",
    "count": "특정 값에 해당하는 학생 수를 고르게",
    "none": "균형 계산에 사용 안 함",
}
ALLOWED_METHODS = {
    "single": ["distribution", "count", "none"],
    "multi": ["distribution", "count", "none"],
    "level": ["distribution", "mean", "both", "count", "none"],
    "yesno": ["count", "distribution", "none"],
    "text": ["none"],
}
REL_KINDS = {
    "same": "모두 같은 반",
    "all_diff": "모두 서로 다른 반",
    "pairs_diff": "특정 학생 쌍끼리 다른 반",
    "max_per_class": "반마다 최대 N명",
}
STRENGTH = {"must": "반드시 (필수 조건)", "prefer": "가급적 (균형 조건)"}

BUILTIN_ITEMS = {
    "builtin:size": "학급별 전체 인원 균형",
    "builtin:gender": "성별 분포 균형",
    "builtin:origin": "현재 같은 반 학생들을 새 학급에 고르게 나누기",
}

MAX_BINS = 7  # 단계 수가 이보다 많으면 구간으로 묶어 분포를 계산한다.


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_id(prefix):
    return prefix + uuid.uuid4().hex[:10]


def is_missing(feature, value):
    """미입력 여부. multi 의 [] 는 '해당 없음'이므로 미입력이 아니다."""
    if value is None:
        return True
    if feature["type"] in ("single", "text") and value == "":
        return True
    return False


def fmt_num(x):
    if x is None:
        return ""
    if isinstance(x, bool):
        return "예" if x else "아니요"
    if float(x).is_integer():
        return str(int(x))
    return ("%.2f" % x).rstrip("0").rstrip(".")


def level_steps(f):
    lo = float(f.get("min", 1))
    hi = float(f.get("max", 5))
    step = float(f.get("step", 1) or 1)
    if step <= 0:
        step = 1
    vals = []
    v = lo
    guard = 0
    while v <= hi + 1e-9 and guard < 10000:
        vals.append(round(v, 6))
        v += step
        guard += 1
    return vals


def level_label(f, v):
    labels = f.get("labels") or {}
    key = fmt_num(v)
    lab = labels.get(key)
    return f"{key} ({lab})" if lab else key


def level_categories(f):
    """단계형 항목의 분포 계산용 범주 목록: [(key, label, test_fn)]"""
    steps = level_steps(f)
    if len(steps) <= MAX_BINS:
        cats = []
        for s in steps:
            cats.append(("v" + fmt_num(s), level_label(f, s), (lambda x, s=s: abs(x - s) < 1e-9)))
        return cats
    # 범위가 넓은 숫자 항목: 5개 구간으로 묶는다 (선택지 수가 많다는 이유로 영향이 커지지 않도록)
    lo, hi = steps[0], steps[-1]
    nb = 5
    width = (hi - lo) / nb
    cats = []
    for b in range(nb):
        a = lo + width * b
        z = lo + width * (b + 1)
        last = b == nb - 1
        label = f"{fmt_num(round(a, 2))} 이상 {fmt_num(round(z, 2))} {'이하' if last else '미만'}"
        cats.append(("b%d" % b, label, (lambda x, a=a, z=z, last=last: (a - 1e-9 <= x <= z + 1e-9) if last else (a - 1e-9 <= x < z - 1e-9))))
    return cats


def feature_categories(f):
    """특성의 분포 범주: [(key, label, member_fn(value)->bool)]  (미입력은 어느 범주에도 속하지 않음)"""
    t = f["type"]
    if t == "single":
        return [("o" + o, o, (lambda v, o=o: v == o)) for o in f.get("options", [])]
    if t == "multi":
        return [("o" + o, o, (lambda v, o=o: isinstance(v, list) and o in v)) for o in f.get("options", [])]
    if t == "yesno":
        return [("yes", "예", lambda v: v is True), ("no", "아니요", lambda v: v is False)]
    if t == "level":
        out = []
        for key, label, test in level_categories(f):
            out.append((key, label, (lambda v, test=test: isinstance(v, (int, float)) and not isinstance(v, bool) and test(float(v)))))
        return out
    return []


def count_rule(f):
    """count 방식에서 '해당' 으로 셀 학생 판정 함수와 설명."""
    t = f["type"]
    if t == "yesno":
        return (lambda v: v is True), "‘예’인 학생"
    if t == "level":
        th = f.get("count_min")
        if th is None:
            th = level_steps(f)[-1]
        th = float(th)
        return (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) >= th - 1e-9), f"{level_label(f, th)} 이상인 학생"
    vals = list(f.get("count_values") or [])
    if not vals and f.get("options"):
        vals = [f["options"][0]]
    if t == "single":
        return (lambda v: v in vals), "‘" + "·".join(vals) + "’인 학생"
    if t == "multi":
        return (lambda v: isinstance(v, list) and any(x in vals for x in v)), "‘" + "·".join(vals) + "’ 중 하나 이상 해당 학생"
    return (lambda v: False), ""


def natural_key(s):
    s = "" if s is None else str(s)
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits and len(digits) == len(s.replace("반", "").strip()):
        return (0, int(digits), s)
    return (1, 0, s)


def safe_float(v):
    try:
        if v is None or v == "" or isinstance(v, bool):
            return None
        x = float(v)
        if math.isnan(x):
            return None
        return x
    except (TypeError, ValueError):
        return None
