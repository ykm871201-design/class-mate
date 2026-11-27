"""엑셀 입력 양식, 불러오기(열 연결·검사), 결과 내보내기."""
import hashlib
import io
import re

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .common import FEATURE_TYPES, IMPORTANCE_LABEL, METHODS, fmt_num, is_missing, level_label, level_steps, natural_key, new_id
from .evaluate import Ctx, evaluate, rel_text

HEAD_FILL = PatternFill("solid", fgColor="DDE7F3")
TITLE_FONT = Font(bold=True, size=14)
BOLD = Font(bold=True)
THIN = Side(style="thin", color="999999")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

BASE_FIELDS = [
    ("sid", "학생 ID", True), ("name", "이름", True), ("grade", "현재 학년", False), ("cls", "현재 반", False),
    ("num", "현재 번호", False), ("gender", "성별", False), ("eligible", "편성 대상", False),
    ("transfer_in", "전입 예정", False), ("fixed_class", "지정 학급", False), ("memo", "교사용 메모", False),
]
SYNONYMS = {
    "sid": ["학생id", "학생 id", "id", "고유번호", "학생고유id", "학번", "학생번호", "학생 고유 id", "학생코드"],
    "name": ["이름", "성명", "학생명", "학생 이름", "학생이름", "성 명"],
    "grade": ["현재 학년", "학년", "현재학년"],
    "cls": ["현재 반", "반", "현재반", "학급", "현재 학급"],
    "num": ["현재 번호", "번호", "현재번호", "출석번호", "출석 번호"],
    "gender": ["성별", "남녀", "성"],
    "eligible": ["편성 대상", "편성대상", "대상", "편성 대상 여부"],
    "transfer_in": ["전입 예정", "전입예정", "전입"],
    "fixed_class": ["지정 학급", "지정학급", "배정 학급", "지정 배정"],
    "memo": ["교사용 메모", "메모", "비고", "교사 메모", "특이사항"],
}
REL_FIELDS = [("strength", "강도", True), ("kind", "조건", True), ("members", "학생 ID 목록", True),
              ("pairs", "다른 반 쌍 목록", False), ("max_n", "최대 인원(N)", False), ("importance", "중요도", False), ("reason", "사유", False)]
REL_SYNONYMS = {
    "strength": ["강도", "구분", "필수/선호"], "kind": ["조건", "조건 종류", "관계"],
    "members": ["학생 id 목록", "학생id 목록", "학생 id", "대상 학생", "학생 목록", "학생"],
    "pairs": ["다른 반 쌍 목록", "쌍 목록", "쌍"], "max_n": ["최대 인원(n)", "최대 인원", "n", "최대"],
    "importance": ["중요도"], "reason": ["사유", "사유(선택)", "이유", "메모"],
}
YES = {"예", "네", "o", "y", "yes", "1", "true", "대상", "해당", "○", "ㅇ", "v", "있음", "필요"}
NO = {"아니요", "아니오", "아니", "x", "n", "no", "0", "false", "제외", "비대상", "×", "없음", "불필요"}


def _norm(h):
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def _cell_str(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = BOLD
        cell.fill = HEAD_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def feature_input_help(f):
    t = f["type"]
    if t == "single":
        return "다음 중 하나: " + ", ".join(f.get("options", []))
    if t == "multi":
        return "다음 중 여러 개를 쉼표(,)로 구분: " + ", ".join(f.get("options", [])) + " / 해당하는 것이 없으면 ‘해당 없음’"
    if t == "level":
        steps = level_steps(f)
        if len(steps) <= 11:
            return "다음 숫자 중 하나: " + ", ".join(level_label(f, s) for s in steps)
        return f"{fmt_num(f.get('min'))} ~ {fmt_num(f.get('max'))} 사이의 숫자 (간격 {fmt_num(f.get('step', 1))})"
    if t == "yesno":
        return "예 또는 아니요"
    return "자유롭게 입력 (편성 계산에 사용하지 않음)"


# ----------------------------------------------------------------------------
# 입력 양식
# ----------------------------------------------------------------------------

def make_template(project):
    feats = [f for f in project.get("features", []) if f.get("active")]
    wb = Workbook()
    ws = wb.active
    ws.title = "학생 명단"
    headers = [lab + (" *" if req else "") for _, lab, req in BASE_FIELDS] + [f["name"] for f in feats]
    ws.append(headers)
    _style_header(ws, 1, len(headers))
    _widths(ws, [12, 10, 9, 9, 9, 7, 9, 9, 10, 28] + [16] * len(feats))
    ws.freeze_panes = "C2"
    dv_g = DataValidation(type="list", formula1='"남,여"', allow_blank=True)
    dv_yn = DataValidation(type="list", formula1='"예,아니요"', allow_blank=True)
    ws.add_data_validation(dv_g)
    ws.add_data_validation(dv_yn)
    dv_g.add("F2:F1000")
    dv_yn.add("G2:H1000")
    # 선택지 목록은 별도 시트에 적고 드롭다운이 그 범위를 참조한다
    # (엑셀의 드롭다운 직접 입력은 255자 제한이 있고 쉼표가 든 선택지를 쓸 수 없기 때문)
    lists = wb.create_sheet("선택 목록")
    lists.append(["드롭다운 선택지 목록 — 이 시트는 고치지 마세요"])
    list_col = [0]

    def dropdown(col, values, title, prompt, strict=True):
        list_col[0] += 1
        lc = get_column_letter(list_col[0])
        lists.cell(row=2, column=list_col[0], value=title[:40]).font = BOLD
        for i, v in enumerate(values):
            lists.cell(row=3 + i, column=list_col[0], value=v)
        dv = DataValidation(type="list", formula1=f"'선택 목록'!${lc}$3:${lc}${2 + len(values)}", allow_blank=True)
        dv.promptTitle = title[:32]
        dv.prompt = prompt[:250]
        dv.showInputMessage = True
        dv.errorTitle = "입력할 수 없는 값"
        dv.error = (prompt + " (빈칸 = 미입력)")[:250]
        dv.showErrorMessage = strict  # 다중 선택은 쉼표로 여러 개를 직접 입력할 수 있어야 함
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}1000")

    if project["classes"]:
        dropdown("I", [c["name"] for c in project["classes"]], "지정 학급", "이 학생을 반드시 배정할 학급을 고르세요. 지정하지 않으면 비워 두세요.")
    for j, f in enumerate(feats):
        col = get_column_letter(len(BASE_FIELDS) + 1 + j)
        t = f["type"]
        if t == "single" and f.get("options"):
            dropdown(col, list(f["options"]), f["name"], "목록에서 하나를 고르세요.")
        elif t == "yesno":
            dropdown(col, ["예", "아니요"], f["name"], "예 또는 아니요를 고르세요.")
        elif t == "multi" and f.get("options"):
            dropdown(col, list(f["options"]) + ["해당 없음"], f["name"],
                     "하나는 목록에서 고르고, 여러 개는 쉼표로 구분해 직접 입력하세요 (예: " + ", ".join(f["options"][:2]) + "). 해당하는 것이 없으면 ‘해당 없음’.",
                     strict=False)
        elif t == "level":
            steps = level_steps(f)
            if len(steps) <= 11:
                dropdown(col, [level_label(f, s) for s in steps], f["name"], "목록에서 단계를 고르세요. 숫자만 입력해도 됩니다.")
            else:
                dv = DataValidation(type="decimal", operator="between", formula1=str(f.get("min", 1)), formula2=str(f.get("max", 5)), allow_blank=True)
                dv.error = feature_input_help(f)
                dv.promptTitle = f["name"][:32]
                dv.prompt = feature_input_help(f)[:250]
                ws.add_data_validation(dv)
                dv.add(f"{col}2:{col}1000")
    _widths(lists, [22] * max(1, list_col[0]))
    lists.sheet_state = "hidden"

    g = wb.create_sheet("특성 입력 안내")
    g.append(["학생 특성 입력 안내"])
    g["A1"].font = TITLE_FONT
    for line in [
        "· ‘*’ 표시 항목(학생 ID, 이름)만 반드시 입력하고, 나머지는 비워 둘 수 있습니다.",
        "· 학생 ID는 학생마다 달라야 합니다. 동명이인이 있어도 학생 ID로 구분합니다.",
        "· 빈칸은 ‘미입력’으로 저장됩니다. 미입력은 ‘0점’, ‘낮음’, ‘해당 없음’과 다르게 처리됩니다.",
        "· 다중 선택 항목에서 해당하는 것이 없으면 ‘해당 없음’이라고 쓰세요 (빈칸 = 미입력).",
        "· 편성 대상 칸을 비우면 ‘예(편성 대상)’로 봅니다. 전출 예정 등은 ‘아니요’로 쓰세요.",
        "· 현재 반이 없는 전입 예정 학생은 현재 반을 비우고 ‘전입 예정’에 ‘예’를 쓰세요.",
        "· 학생을 낙인찍는 표현이나 진단명은 입력하지 마세요. 교사가 판단한 지원 필요 정도만 입력합니다.",
        "· 자유 메모는 편성 계산에 자동으로 사용되지 않습니다.",
    ]:
        g.append([line])
    g.append([])
    hr = g.max_row + 1
    g.append(["항목명", "분류", "입력 형식", "입력할 수 있는 값", "설명", "편성 반영"])
    _style_header(g, hr, 6)
    for f in feats:
        g.append([f["name"], f.get("category", ""), FEATURE_TYPES.get(f["type"], f["type"]), feature_input_help(f), f.get("desc", ""),
                  ("반영 (" + IMPORTANCE_LABEL.get(f.get("importance"), "") + ")") if f.get("use_in_balance") and f.get("method") != "none" else "반영 안 함"])
    if not feats:
        g.append(["(활성화된 특성 항목이 없습니다. 프로그램의 ‘특성 항목 관리’에서 필요한 항목을 켠 뒤 양식을 다시 받으세요.)"])
    _widths(g, [28, 14, 14, 60, 40, 14])

    r = wb.create_sheet("학생 간 관계")
    rh = ["강도", "조건", "학생 ID 목록", "다른 반 쌍 목록", "최대 인원(N)", "중요도", "사유(선택)"]
    r.append(rh)
    _style_header(r, 1, len(rh))
    _widths(r, [10, 22, 36, 30, 12, 10, 36])
    dv_s = DataValidation(type="list", formula1='"반드시,가급적"', allow_blank=True)
    dv_k = DataValidation(type="list", formula1='"같은 반,모두 다른 반,쌍끼리 다른 반,반마다 최대 N명"', allow_blank=True)
    dv_i = DataValidation(type="list", formula1='"낮음,보통,높음,매우 높음"', allow_blank=True)
    for dv, rng in ((dv_s, "A2:A500"), (dv_k, "B2:B500"), (dv_i, "F2:F500")):
        r.add_data_validation(dv)
        dv.add(rng)
    r2 = wb.create_sheet("관계 입력 안내")
    for line in [
        "학생 간 관계 입력 방법",
        "· 강도: ‘반드시’(필수 조건, 꼭 지킴) 또는 ‘가급적’(가능하면 지킴)",
        "· 조건: 같은 반 / 모두 다른 반 / 쌍끼리 다른 반 / 반마다 최대 N명",
        "· 학생 ID 목록: 쉼표로 구분 (예: S0001, S0002, S0003). 2명 이상 그룹도 가능합니다.",
        "· 쌍끼리 다른 반: ‘다른 반 쌍 목록’에 S0001-S0002; S0003-S0004 처럼 씁니다.",
        "· 반마다 최대 N명: ‘최대 인원(N)’에 숫자를 씁니다. (예: 5명 그룹, 반마다 최대 2명)",
        "· ‘모두 다른 반’과 ‘반마다 최대 1명’은 같은 뜻이지만, ‘반마다 최대 2명’은 다른 조건입니다.",
        "· 사유는 선택 사항이며 일반 배부용 결과 파일에는 절대 포함되지 않습니다.",
        "· 형제자매·쌍둥이 등의 사유만으로 같은 반/다른 반이 자동 결정되지 않습니다. 조건을 직접 지정하세요.",
    ]:
        r2.append([line])
    r2["A1"].font = TITLE_FONT
    _widths(r2, [100])

    e = wb.create_sheet("입력 예시")
    e.append(["입력 예시 (가상 학생 — 실제 자료를 입력할 때는 ‘학생 명단’ 시트를 사용하세요)"])
    e["A1"].font = TITLE_FONT
    e.append(headers)
    _style_header(e, 2, len(headers))

    def ex_val(f, i):
        t = f["type"]
        if t == "single":
            return (f.get("options") or [""])[i % max(1, len(f.get("options") or [""]))]
        if t == "multi":
            return ["", "해당 없음", ", ".join((f.get("options") or [])[:2])][i % 3]
        if t == "level":
            st = level_steps(f)
            return [fmt_num(st[len(st) // 2]), "", fmt_num(st[-1])][i % 3]
        if t == "yesno":
            return ["아니요", "예", ""][i % 3]
        return ["", "참고 메모 예시", ""][i % 3]

    ex_rows = [["S0001", "김가람", 3, "1반", 1, "남", "예", "", "", "모둠 활동 적극적"],
               ["S0002", "김가람", 3, "2반", 4, "여", "예", "", "", "동명이인 — 학생 ID로 구분"],
               ["S0003", "박나래", 3, "", "", "여", "예", "예", "", "전입 예정 학생 (현재 반 없음)"],
               ["S0004", "이도담", 3, "3반", 12, "남", "아니요", "", "", "전출 예정 — 편성 제외"]]
    for i, row in enumerate(ex_rows):
        e.append(row + [ex_val(f, i) for f in feats])
    e.append([])
    e.append(["관계 입력 예시"])
    e.cell(row=e.max_row, column=1).font = BOLD
    e.append(rh)
    _style_header(e, e.max_row, len(rh))
    for row in [["반드시", "모두 다른 반", "S0001, S0002", "", "", "", "교사 판단"],
                ["가급적", "같은 반", "S0001, S0003", "", "", "높음", ""],
                ["반드시", "쌍끼리 다른 반", "S0001, S0002, S0003, S0004", "S0001-S0002; S0003-S0004", "", "", ""],
                ["반드시", "반마다 최대 N명", "S0001, S0002, S0003", "", 2, "", ""]]:
        e.append(row)
    _widths(e, [12, 10, 9, 9, 9, 7, 9, 9, 10, 28] + [16] * len(feats))
    wb.move_sheet(lists, offset=len(wb.sheetnames) - 1 - wb.sheetnames.index(lists.title))  # 숨김 목록 시트는 맨 뒤로
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ----------------------------------------------------------------------------
# 불러오기
# ----------------------------------------------------------------------------

def parse_upload(data, filename=""):
    h = hashlib.sha256(data).hexdigest()
    sheets = []
    if filename.lower().endswith(".csv"):
        import csv
        text = None
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("CSV 파일의 글자 인코딩을 알 수 없습니다. 엑셀(.xlsx)로 저장하여 올려 주세요.")
        rows = list(csv.reader(io.StringIO(text)))
        sheets.append(_sheet_from_rows("CSV", rows))
    else:
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise ValueError("엑셀 파일을 읽을 수 없습니다. .xlsx 형식인지 확인하세요. (.xls 는 엑셀에서 .xlsx 로 다시 저장해 주세요)")
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            sheets.append(_sheet_from_rows(ws.title, rows))
        wb.close()
    return {"hash": h, "filename": filename, "sheets": sheets}


def _sheet_from_rows(name, rows):
    hdr_idx = None
    for i, r in enumerate(rows[:30]):
        filled = [c for c in r if _cell_str(c)]
        if len(filled) >= 2:
            hdr_idx = i
            break
    if hdr_idx is None:
        return {"name": name, "headers": [], "rows": [], "header_row": None}
    headers = [_cell_str(c) for c in rows[hdr_idx]]
    while headers and not headers[-1]:
        headers.pop()
    data = []
    for j, r in enumerate(rows[hdr_idx + 1:]):
        vals = [_cell_str(c) for c in r[:len(headers)]]
        vals += [""] * (len(headers) - len(vals))
        if any(vals):
            data.append({"row": hdr_idx + 2 + j, "values": vals})
    return {"name": name, "headers": headers, "rows": data, "header_row": hdr_idx + 1}


def guess_mapping(project, headers, kind="students"):
    nh = [_norm(h).replace("*", "").strip() for h in headers]
    mp = {}
    fields = BASE_FIELDS if kind == "students" else REL_FIELDS
    syn = SYNONYMS if kind == "students" else REL_SYNONYMS
    for fid, lab, _ in fields:
        cands = [_norm(lab)] + [_norm(x) for x in syn.get(fid, [])]
        for i, h in enumerate(nh):
            if h in cands and i not in mp.values():
                mp[fid] = i
                break
    if kind == "students":
        for f in project.get("features", []):
            if not f.get("active"):
                continue
            for i, h in enumerate(nh):
                if h == _norm(f["name"]) and i not in mp.values():
                    mp["feature:" + f["id"]] = i
                    break
    return mp


def _yn(v):
    s = _norm(v)
    if s in YES:
        return True
    if s in NO:
        return False
    return "ERR"


def parse_feature_value(f, raw):
    """(값, 오류메시지) — 빈칸은 None(미입력). 잘못된 값은 바꾸지 않고 오류로 돌려준다."""
    s = (raw or "").strip()
    t = f["type"]
    if s == "":
        return None, None
    if t == "text":
        return s, None
    if t == "single":
        if s in f.get("options", []):
            return s, None
        return None, f"‘{s}’은(는) 선택지에 없습니다. 가능한 값: {', '.join(f.get('options', []))}"
    if t == "multi":
        if s in ("해당 없음", "해당없음", "없음"):
            return [], None
        parts = [x.strip() for x in re.split(r"[,;/\n]", s) if x.strip()]
        bad = [x for x in parts if x not in f.get("options", [])]
        if bad:
            return None, f"선택지에 없는 값: {', '.join(bad)}. 가능한 값: {', '.join(f.get('options', []))} (해당 없음은 ‘해당 없음’)"
        return [o for o in f.get("options", []) if o in parts], None
    if t == "yesno":
        v = _yn(s)
        if v == "ERR":
            return None, f"‘{s}’ — 예 또는 아니요로 입력하세요."
        return v, None
    if t == "level":
        labels = {v: k for k, v in (f.get("labels") or {}).items()}
        m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", s)
        if m:
            x = float(m.group(1))
        elif s in labels:
            x = float(labels[s])
        else:
            return None, f"‘{s}’은(는) 숫자가 아닙니다. {feature_input_help(f)}"
        lo, hi = float(f.get("min", 1)), float(f.get("max", 5))
        if x < lo - 1e-9 or x > hi + 1e-9:
            return None, f"{fmt_num(x)}은(는) 입력 범위({fmt_num(lo)}~{fmt_num(hi)})를 벗어났습니다."
        steps = level_steps(f)
        if not any(abs(x - st) < 1e-6 for st in steps):
            return None, f"{fmt_num(x)}은(는) 허용 단계가 아닙니다. {feature_input_help(f)}"
        return (int(x) if x.is_integer() else x), None
    return None, "알 수 없는 형식"


def validate_students(project, sheet, mapping, existing_policy="skip"):
    """학생 명단 미리보기 검사. 오류 행은 조용히 버리지 않고 행 번호와 함께 모두 보고한다."""
    feats = {f["id"]: f for f in project.get("features", [])}
    cname = {c["name"]: c["id"] for c in project["classes"]}
    by_sid = {s["sid"]: s for s in project["students"]}
    errors, notes, parsed = [], [], []
    seen = {}
    if "sid" not in mapping or "name" not in mapping:
        return {"ok": False, "errors": [{"row": None, "field": "열 연결", "message": "‘학생 ID’와 ‘이름’ 열을 반드시 연결해야 합니다."}],
                "students": [], "notes": [], "summary": {}}
    for r in sheet["rows"]:
        vals = r["values"]

        def get(fid):
            i = mapping.get(fid)
            if i is None or i >= len(vals):
                return ""
            return vals[i]

        rowno = r["row"]
        st = {"traits": {}}
        rerr = []
        sid = get("sid").strip()
        name = get("name").strip()
        if not sid:
            rerr.append(("학생 ID", "학생 ID가 비어 있습니다. 학생마다 다른 ID를 입력하세요."))
        if not name:
            rerr.append(("이름", "이름이 비어 있습니다."))
        st["sid"], st["name"] = sid, name
        g = get("grade").strip()
        if g:
            m = re.match(r"^(\d+)", g)
            if m:
                st["grade"] = int(m.group(1))
            else:
                rerr.append(("현재 학년", f"‘{g}’은(는) 학년 숫자가 아닙니다."))
        else:
            st["grade"] = None
        c = get("cls").strip()
        if c.isdigit():
            notes.append({"row": rowno, "message": f"현재 반 ‘{c}’을(를) ‘{c}반’으로 저장합니다."})
            c = c + "반"
        st["cls"] = c
        n = get("num").strip()
        if n:
            try:
                st["num"] = int(float(n))
            except ValueError:
                rerr.append(("현재 번호", f"‘{n}’은(는) 번호 숫자가 아닙니다."))
        else:
            st["num"] = None
        gd = get("gender").strip()
        gl = gd.lower()
        if not gd:
            st["gender"] = ""
        elif gl in ("남", "남자", "m", "male", "남학생"):
            st["gender"] = "남"
        elif gl in ("여", "여자", "f", "female", "여학생"):
            st["gender"] = "여"
        else:
            rerr.append(("성별", f"‘{gd}’ — 남 또는 여로 입력하세요."))
        el = get("eligible").strip()
        if not el:
            st["eligible"] = True
        else:
            v = _yn(el)
            if v == "ERR":
                rerr.append(("편성 대상", f"‘{el}’ — 예 또는 아니요로 입력하세요."))
            else:
                st["eligible"] = v
        ti = get("transfer_in").strip()
        if not ti:
            st["transfer_in"] = False
        else:
            v = _yn(ti)
            if v == "ERR":
                rerr.append(("전입 예정", f"‘{ti}’ — 예 또는 아니요로 입력하세요."))
            else:
                st["transfer_in"] = v
        fc = get("fixed_class").strip()
        if fc:
            if fc in cname:
                st["fixed_class"] = cname[fc]
            else:
                rerr.append(("지정 학급", f"‘{fc}’ 학급이 없습니다. 가능한 학급: {', '.join(cname)}"))
        else:
            st["fixed_class"] = None
        st["memo"] = get("memo").strip()
        for key, i in mapping.items():
            if not key.startswith("feature:"):
                continue
            f = feats.get(key[8:])
            if not f:
                continue
            v, err = parse_feature_value(f, get(key))
            if err:
                rerr.append((f["name"], err))
            elif v is not None:
                st["traits"][f["id"]] = v
        if sid:
            if sid in seen:
                rerr.append(("학생 ID", f"학생 ID ‘{sid}’가 {seen[sid]}행에도 있습니다 (중복). 학생마다 다른 ID를 쓰세요."))
            else:
                seen[sid] = rowno
        for field, msg in rerr:
            errors.append({"row": rowno, "field": field, "message": msg})
        st["_row"] = rowno
        st["_ok"] = not rerr
        if sid in by_sid and not rerr:
            ex = by_sid[sid]
            same = all((ex.get(k) or None) == (st.get(k) or None) for k in ("name", "grade", "cls", "num", "gender", "memo", "fixed_class")) \
                and bool(ex.get("eligible", True)) == bool(st.get("eligible")) and ex.get("traits", {}) == st["traits"]
            st["_existing"] = "same" if same else "different"
            if same:
                notes.append({"row": rowno, "message": f"학생 ID {sid}({name})는 이미 같은 자료가 있어 건너뜁니다 (중복 불러오기)."})
            elif existing_policy == "skip":
                notes.append({"row": rowno, "message": f"학생 ID {sid}는 이미 명단에 있고 내용이 다릅니다. ‘기존 정보 유지’를 선택하여 건너뜁니다."})
            else:
                notes.append({"row": rowno, "message": f"학생 ID {sid}의 기존 정보를 이 파일의 내용으로 갱신합니다."})
        parsed.append(st)
    ok_rows = [s for s in parsed if s["_ok"]]
    new = [s for s in ok_rows if "_existing" not in s]
    upd = [s for s in ok_rows if s.get("_existing") == "different" and existing_policy == "update"]
    summary = {"total": len(parsed), "error_rows": len({e["row"] for e in errors}), "new": len(new), "update": len(upd),
               "skip_same": sum(1 for s in ok_rows if s.get("_existing") == "same"),
               "skip_diff": sum(1 for s in ok_rows if s.get("_existing") == "different" and existing_policy != "update")}
    dup_hash = None
    return {"ok": not errors, "errors": errors, "notes": notes, "students": parsed, "summary": summary, "dup_hash": dup_hash}


KIND_MAP = {"같은 반": "same", "같은반": "same", "모두 같은 반": "same", "모두 다른 반": "all_diff", "다른 반": "all_diff", "다른반": "all_diff",
            "모두 서로 다른 반": "all_diff", "쌍끼리 다른 반": "pairs_diff", "특정 학생 쌍끼리 다른 반": "pairs_diff", "특정 쌍 다른 반": "pairs_diff",
            "반마다 최대 n명": "max_per_class", "반마다 최대": "max_per_class", "반마다 최대 n 명": "max_per_class"}
IMP_MAP = {v: k for k, v in IMPORTANCE_LABEL.items()}


def validate_relations(project, sheet, mapping, extra_sids=None):
    sid2key = {s["sid"]: s["key"] for s in project["students"]}
    extra = set(extra_sids or [])
    errors, rels = [], []
    if not all(k in mapping for k in ("strength", "kind", "members")):
        return {"ok": False, "errors": [{"row": None, "field": "열 연결", "message": "‘강도’, ‘조건’, ‘학생 ID 목록’ 열을 연결해야 합니다."}], "relations": []}
    existing = {(r["kind"], r["strength"], tuple(sorted(r["members"])), r.get("max_n")) for r in project.get("relations", [])}
    for r in sheet["rows"]:
        vals = r["values"]

        def get(fid):
            i = mapping.get(fid)
            return vals[i].strip() if i is not None and i < len(vals) else ""

        rowno = r["row"]
        rerr = []
        st = get("strength")
        strength = {"반드시": "must", "필수": "must", "가급적": "prefer", "선호": "prefer"}.get(st)
        if not strength:
            rerr.append(("강도", f"‘{st}’ — ‘반드시’ 또는 ‘가급적’으로 입력하세요."))
        kd = get("kind")
        kind = KIND_MAP.get(_norm(kd)) or KIND_MAP.get(kd)
        if not kind:
            rerr.append(("조건", f"‘{kd}’ — 같은 반 / 모두 다른 반 / 쌍끼리 다른 반 / 반마다 최대 N명 중 하나로 입력하세요."))
        ids = [x.strip() for x in re.split(r"[,;\s]+", get("members")) if x.strip()]
        unknown = [x for x in ids if x not in sid2key and x not in extra]
        if unknown:
            rerr.append(("학생 ID 목록", "명단에 없는 학생 ID: " + ", ".join(unknown) + " — 학생 명단을 먼저 불러오거나 ID를 확인하세요."))
        if len(ids) < 2 and kind != "max_per_class":
            rerr.append(("학생 ID 목록", "2명 이상의 학생 ID가 필요합니다."))
        if len(set(ids)) != len(ids):
            rerr.append(("학생 ID 목록", "같은 학생 ID가 두 번 이상 적혀 있습니다."))
        pairs = []
        if kind == "pairs_diff":
            for p in [x.strip() for x in re.split(r"[;\n]", get("pairs")) if x.strip()]:
                ab = [x.strip() for x in re.split(r"[-–~:↔]", p) if x.strip()]
                if len(ab) != 2:
                    rerr.append(("다른 반 쌍 목록", f"‘{p}’ — S0001-S0002 형식으로 쓰세요."))
                    continue
                if ab[0] not in ids or ab[1] not in ids:
                    rerr.append(("다른 반 쌍 목록", f"‘{p}’의 학생이 학생 ID 목록에 없습니다."))
                    continue
                pairs.append(ab)
            if not pairs and not rerr:
                rerr.append(("다른 반 쌍 목록", "쌍끼리 다른 반 조건에는 쌍 목록이 필요합니다."))
        max_n = None
        if kind == "max_per_class":
            mx = get("max_n")
            try:
                max_n = int(float(mx))
                if max_n < 1:
                    raise ValueError
            except ValueError:
                rerr.append(("최대 인원(N)", f"‘{mx}’ — 1 이상의 숫자를 입력하세요."))
        imp = get("importance")
        importance = IMP_MAP.get(imp, "high") if imp else "high"
        if imp and imp not in IMP_MAP:
            rerr.append(("중요도", f"‘{imp}’ — 낮음/보통/높음/매우 높음 중 하나로 입력하세요."))
        for f, m in rerr:
            errors.append({"row": rowno, "field": f, "message": m})
        if not rerr:
            rel = {"kind": kind, "strength": strength, "member_sids": ids, "pair_sids": pairs, "max_n": max_n,
                   "importance": importance, "reason": get("reason"), "_row": rowno}
            keys = tuple(sorted(sid2key.get(x, x) for x in ids))
            rel["_duplicate"] = (kind, strength, keys, max_n) in existing
            rels.append(rel)
    return {"ok": not errors, "errors": errors, "relations": rels}


# ----------------------------------------------------------------------------
# 내보내기
# ----------------------------------------------------------------------------
PUBLIC_COLUMNS = [("new_class", "새 학급"), ("new_num", "새 번호"), ("name", "이름"), ("gender", "성별"),
                  ("grade", "현재 학년"), ("cls", "현재 반"), ("num", "현재 번호"), ("sid", "학생 ID")]
DEFAULT_PUBLIC = ["new_class", "new_num", "name", "gender", "cls", "num"]


def _trait_text(f, v):
    if is_missing(f, v):
        return "미입력"
    t = f["type"]
    if t == "multi":
        return ", ".join(v) if v else "해당 없음"
    if t == "yesno":
        return "예" if v else "아니요"
    if t == "level":
        return level_label(f, v)
    return str(v)


def export_plan_info(project, options):
    plan = next((p for p in project.get("plans", []) if p["id"] == options.get("plan_id")), None)
    if not plan:
        raise ValueError("편성안을 찾을 수 없습니다.")
    mode = options.get("mode", "public")
    cols = [c for c in options.get("columns") or DEFAULT_PUBLIC if c in dict(PUBLIC_COLUMNS)]
    feats = []
    if mode == "staff":
        fids = options.get("features")
        if fids is None:
            fids = [f["id"] for f in project.get("features", []) if f.get("active") and f.get("include_in_export")]
        feats = [f for f in project.get("features", []) if f["id"] in fids and f.get("active")]
    return plan, mode, cols, feats


def export_preview(project, options):
    plan, mode, cols, feats = export_plan_info(project, options)
    colnames = [dict(PUBLIC_COLUMNS)[c] for c in cols]
    sheets = [
        {"name": "① 전체 편성 명단", "columns": colnames + ([f["name"] for f in feats] if mode == "staff" else [])
         + (["교사용 메모"] if mode == "staff" and options.get("include_memo") else []) + (["고정 여부"] if mode == "staff" else [])},
        {"name": "② 학급별 명단", "columns": colnames + ([f["name"] for f in feats] if mode == "staff" else [])},
        {"name": "③ 현재 반 기준 새 학급 확인표", "columns": ["현재 반 × 새 학급 인원표", "현재 반", "현재 번호", "이름", "새 학급", "새 번호"]},
        {"name": "④ 학급별 인원 및 통계", "columns": ["학급", "인원", "성별 인원"] + (["선택한 특성별 분포·평균·미입력"] if mode == "staff" else [])},
    ]
    if mode == "staff" and options.get("include_conditions", True):
        sheets.append({"name": "⑤ 조건 설정 및 충족 현황", "columns": ["필수 조건 충족 여부", "학생 간 관계 조건"] + (["관계 사유"] if options.get("include_reasons") else [])
                       + ["균형 조건 설정과 상태", "지정·고정 배정"]})
    if mode == "staff" and options.get("include_excluded", True):
        sheets.append({"name": "참고 - 편성 제외 학생", "columns": ["학생 ID", "이름", "현재 반", "현재 번호"]})
    excluded = []
    if mode == "public":
        excluded = ["학생 특성(모든 항목)", "교사용 메모", "학생 간 관계와 사유", "편성 조건 설정", "편성 제외 학생 정보"]
    else:
        unsel = [f["name"] for f in project.get("features", []) if f.get("active") and f not in feats]
        if unsel:
            excluded.append("선택하지 않은 특성: " + ", ".join(unsel))
        if not options.get("include_reasons"):
            excluded.append("관계 사유")
        if not options.get("include_memo"):
            excluded.append("교사용 메모")
    numbered = bool(plan.get("new_numbers"))
    return {"mode": mode, "sheets": sheets, "excluded": excluded, "plan_name": plan.get("name"), "confirmed": plan.get("confirmed", False),
            "numbered": numbered,
            "warning": None if numbered else "새 번호가 아직 부여되지 않았습니다. 최종 확정 후 새 번호를 부여하면 번호가 함께 출력됩니다."}


def export_excel(project, options):
    plan, mode, cols, feats = export_plan_info(project, options)
    ctx = Ctx(project)
    a = plan["assignment"]
    locks = plan.get("locks", {})
    rep = evaluate(project, a, locks, ctx)
    nums = plan.get("new_numbers") or {}
    cname = {c["id"]: c["name"] for c in project["classes"]}
    corder = {c["id"]: i for i, c in enumerate(project["classes"])}
    studs = [s for s in ctx.students if a.get(s["key"])]
    studs.sort(key=lambda s: (corder.get(a.get(s["key"]), 99), nums.get(s["key"], 9999), s.get("name") or "", s.get("sid") or ""))
    staff = mode == "staff"
    s_year = project.get("settings", {})
    title = f"{s_year.get('school_year', '')}학년도 {s_year.get('next_grade', '')}학년 학급 편성 결과"

    def base_val(s, c):
        if c == "new_class":
            return cname.get(a.get(s["key"]), "")
        if c == "new_num":
            return nums.get(s["key"], "")
        if c == "name":
            return s.get("name", "")
        if c == "gender":
            return s.get("gender", "")
        if c == "grade":
            return s.get("grade", "")
        if c == "cls":
            return s.get("cls") or ("전입" if s.get("transfer_in") else "")
        if c == "num":
            return s.get("num") if s.get("num") is not None else ""
        if c == "sid":
            return s.get("sid", "")
        return ""

    head = [dict(PUBLIC_COLUMNS)[c] for c in cols]
    wb = Workbook()
    ws = wb.active
    ws.title = "① 전체 편성 명단"
    ws.append([title + (" (담당 교사용 — 외부 배부 금지)" if staff else "")])
    ws["A1"].font = TITLE_FONT
    h1 = head + ([f["name"] for f in feats] if staff else []) + (["교사용 메모"] if staff and options.get("include_memo") else []) + (["고정 여부"] if staff else [])
    ws.append(h1)
    _style_header(ws, 2, len(h1))
    for s in studs:
        row = [base_val(s, c) for c in cols]
        if staff:
            row += [_trait_text(f, s.get("traits", {}).get(f["id"])) for f in feats]
            if options.get("include_memo"):
                row.append(s.get("memo", ""))
            fx = []
            if s.get("fixed_class"):
                fx.append("지정 배정")
            if s["key"] in locks:
                fx.append("편성안 고정")
            row.append(", ".join(fx))
        ws.append(row)
    ws.freeze_panes = "A3"
    _widths(ws, [10] * len(h1))

    ws2 = wb.create_sheet("② 학급별 명단")
    ws2.append([title + " — 학급별 명단"])
    ws2["A1"].font = TITLE_FONT
    h2 = head + ([f["name"] for f in feats] if staff else [])
    for c in rep["classes"]:
        ws2.append([])
        g = " · ".join(f"{k} {v}명" for k, v in c["gender"].items())
        ws2.append([f"{c['name']} — {c['size']}명 ({g})"])
        ws2.cell(row=ws2.max_row, column=1).font = Font(bold=True, size=12)
        ws2.append(h2)
        _style_header(ws2, ws2.max_row, len(h2))
        for s in studs:
            if a.get(s["key"]) == c["id"]:
                row = [base_val(s, x) for x in cols]
                if staff:
                    row += [_trait_text(f, s.get("traits", {}).get(f["id"])) for f in feats]
                ws2.append(row)
    _widths(ws2, [10] * max(1, len(h2)))

    ws3 = wb.create_sheet("③ 현재 반 기준 확인표")
    ws3.append(["현재 반 × 새 학급 인원표"])
    ws3["A1"].font = TITLE_FONT
    hh = ["현재 반"] + rep["cross"]["classes"] + ["합계"]
    ws3.append(hh)
    _style_header(ws3, 2, len(hh))
    for r in rep["cross"]["rows"]:
        ws3.append([r["origin"]] + r["counts"] + [r["total"]])
    ws3.append([])
    ws3.append(["현재 반 순서 명단"])
    ws3.cell(row=ws3.max_row, column=1).font = BOLD
    hl = ["현재 반", "현재 번호", "이름", "새 학급", "새 번호"]
    ws3.append(hl)
    _style_header(ws3, ws3.max_row, len(hl))
    for s in sorted(studs, key=lambda s: (natural_key(s.get("cls") or "~"), s.get("num") if isinstance(s.get("num"), int) else 9999, s.get("name") or "")):
        ws3.append([s.get("cls") or ("전입" if s.get("transfer_in") else ""), s.get("num") if s.get("num") is not None else "",
                    s.get("name", ""), cname.get(a.get(s["key"]), ""), nums.get(s["key"], "")])
    _widths(ws3, [16, 10, 12, 10, 10] + [8] * len(rep["cross"]["classes"]))

    ws4 = wb.create_sheet("④ 학급별 인원 및 통계")
    ws4.append(["학급별 인원 및 통계"])
    ws4["A1"].font = TITLE_FONT
    gkeys = []
    for c in rep["classes"]:
        for k in c["gender"]:
            if k not in gkeys:
                gkeys.append(k)
    hs = ["학급", "인원", "목표", "최대"] + gkeys
    ws4.append(hs)
    _style_header(ws4, 2, len(hs))
    for c in rep["classes"]:
        ws4.append([c["name"], c["size"], c["target"], c["max"]] + [c["gender"].get(k, 0) for k in gkeys])
    if staff:
        fid_sel = {f["id"] for f in feats}
        for it in rep["items"]:
            if it["kind"] == "feature" and it["id"][8:] not in fid_sel:
                continue
            if it["kind"] in ("size", "gender"):
                continue
            ws4.append([])
            ws4.append([f"{it['name']} — 상태: {it['status_label']}" + (" (편성 반영 안 함)" if not it["enabled"] else "")])
            ws4.cell(row=ws4.max_row, column=1).font = BOLD
            hd = ["구분"] + [c["name"] for c in rep["classes"]] + ["합계"]
            ws4.append(hd)
            _style_header(ws4, ws4.max_row, len(hd))
            rows = it["display"] if it["display"] else it["cats"]
            for c in rows:
                ws4.append([c["label"]] + c["counts"] + [c["total"]])
            if it["method"] == "count" and it["cats"]:
                c = it["cats"][0]
                ws4.append([c["label"]] + c["counts"] + [c["total"]])
            if it.get("mean"):
                ws4.append(["평균"] + [m if m is not None else "-" for m in it["mean"]["class_means"]] + [it["mean"]["overall"]])
            if it["kind"] in ("feature", "combo"):
                ws4.append(["미입력"] + it["missing"]["by_class"] + [it["missing"]["total"]])
            if it.get("na"):
                ws4.append(["해당 없음"] + it["na"]["by_class"] + [it["na"]["total"]])
            if it.get("multi_note"):
                ws4.append([it["multi_note"]])
            if it.get("data_note"):
                ws4.append([it["data_note"]])
    _widths(ws4, [34] + [10] * (len(rep["classes"]) + 4))

    if staff and options.get("include_conditions", True):
        ws5 = wb.create_sheet("⑤ 조건 설정 및 충족 현황")
        ws5.append(["조건 설정 및 충족 현황"])
        ws5["A1"].font = TITLE_FONT
        ws5.append(["필수 조건", "✔ 모두 충족" if rep["hard"]["ok"] else f"✖ 위반 {len(rep['hard']['violations'])}건"])
        for v in rep["hard"]["violations"]:
            ws5.append(["", v["message"]])
        ws5.append([])
        hr = ["강도", "조건", "대상 학생", "충족 여부"] + (["사유"] if options.get("include_reasons") else [])
        ws5.append(hr)
        _style_header(ws5, ws5.max_row, len(hr))
        from .evaluate import relation_satisfied
        from .common import REL_KINDS
        for r in project.get("relations", []):
            ok, detail = relation_satisfied(ctx, r, a)
            kind = REL_KINDS.get(r["kind"], r["kind"]) if r["kind"] != "max_per_class" else f"반마다 최대 {r.get('max_n')}명"
            if r["kind"] == "pairs_diff":
                who = "; ".join(f"{ctx.name_of(x)}↔{ctx.name_of(y)}" for x, y in r.get("pairs", []))
            else:
                who = ", ".join(ctx.name_of(k) for k in r.get("members", []))
            row = ["반드시" if r.get("strength") == "must" else "가급적", kind, who, ("✔ 충족" if ok else "✖ 미충족 " + detail)]
            if options.get("include_reasons"):
                row.append(r.get("reason", ""))
            ws5.append(row)
        ws5.append([])
        hb = ["균형 항목", "편성 반영", "중요도", "방식", "상태", "최대 차이(명)"]
        ws5.append(hb)
        _style_header(ws5, ws5.max_row, len(hb))
        for it in rep["items"]:
            ws5.append([it["name"], "반영" if it["enabled"] else "반영 안 함", it["importance_label"], METHODS.get(it["method"], it["method"]),
                        it["status_label"], it["max_dev"]])
        ws5.append([])
        ws5.append(["지정·고정 배정 학생"])
        ws5.cell(row=ws5.max_row, column=1).font = BOLD
        for s in ctx.students:
            if s.get("fixed_class"):
                ws5.append([ctx.name_of(s["key"]), "지정 배정: " + cname.get(s["fixed_class"], "")])
        for k, c in locks.items():
            if k in ctx.idx:
                ws5.append([ctx.name_of(k), "편성안 고정: " + cname.get(c, "")])
        _widths(ws5, [24, 22, 50, 30, 40, 12])
    if staff and options.get("include_excluded", True):
        ws6 = wb.create_sheet("참고 - 편성 제외 학생")
        hx = ["학생 ID", "이름", "현재 반", "현재 번호"]
        ws6.append(hx)
        _style_header(ws6, 1, 4)
        for s in project["students"]:
            if not s.get("eligible", True):
                ws6.append([s.get("sid"), s.get("name"), s.get("cls"), s.get("num")])
    for w in wb.worksheets:
        w.page_setup.orientation = "landscape"
        w.page_setup.fitToWidth = 1
        w.sheet_properties.pageSetUpPr.fitToPage = True
        w.page_setup.fitToHeight = 0
    bio = io.BytesIO()
    wb.save(bio)
    data = bio.getvalue()
    if not staff:
        problems = verify_public(data, project)
        if problems:
            raise ValueError("일반 배부용 파일 안전 검사 실패: " + "; ".join(problems[:5]))
    return data


def verify_public(data, project):
    """일반 배부용 파일에 특성·메모·관계 사유가 (숨김 포함) 들어 있지 않은지 직접 검사한다."""
    wb = load_workbook(io.BytesIO(data))
    bad = []
    forbidden = set()
    for f in project.get("features", []):
        if f.get("name") and len(f["name"]) >= 2:
            forbidden.add(f["name"])
    for s in project["students"]:
        m = (s.get("memo") or "").strip()
        if len(m) >= 4:
            forbidden.add(m)
        for fid, v in (s.get("traits") or {}).items():
            if isinstance(v, str) and len(v) >= 4:
                forbidden.add(v)
    for r in project.get("relations", []):
        if (r.get("reason") or "").strip() and len(r["reason"].strip()) >= 2:
            forbidden.add(r["reason"].strip())
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            bad.append(f"숨김 시트 {ws.title}")
        for k, d in ws.column_dimensions.items():
            if d.hidden:
                bad.append(f"{ws.title} 숨김 열 {k}")
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str):
                    for fb in forbidden:
                        if fb in v:
                            bad.append(f"{ws.title}: ‘{fb[:10]}…’ 포함")
    return bad
