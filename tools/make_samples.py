"""samples 폴더의 엑셀 입력 양식과 가상 학생 예시 자료를 만든다.   실행: python tools/make_samples.py"""
import io
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "vendor"))
sys.path.insert(0, BASE)

from openpyxl import load_workbook  # noqa: E402

from app import excel_io  # noqa: E402
from app.defaults import new_project, sample_project  # noqa: E402

OUT = os.path.join(BASE, "samples")


def main():
    os.makedirs(OUT, exist_ok=True)
    # 1) 빈 입력 양식 (기본 예시 특성 항목을 모두 켠 상태 — 필요 없는 열은 지우거나 비워 두면 됨)
    p = new_project()
    for f in p["features"]:
        f["active"] = True
    with open(os.path.join(OUT, "엑셀_입력_양식(기본 특성 전체).xlsx"), "wb") as fh:
        fh.write(excel_io.make_template(p))
    # 2) 가상 학생 120명 예시 자료 (가상 예시 프로젝트와 같은 내용)
    s = sample_project()
    wb = load_workbook(io.BytesIO(excel_io.make_template(s)))
    ws = wb["학생 명단"]
    feats = [f for f in s["features"] if f.get("active")]
    for st in s["students"]:
        row = [st["sid"], st["name"], st["grade"], st["cls"], st["num"], st["gender"], "예" if st["eligible"] else "아니요",
               "예" if st["transfer_in"] else "", next((c["name"] for c in s["classes"] if c["id"] == st.get("fixed_class")), ""), st["memo"]]
        for f in feats:
            v = st["traits"].get(f["id"])
            if v is None:
                row.append("")
            elif f["type"] == "multi":
                row.append(", ".join(v) if v else "해당 없음")
            elif f["type"] == "yesno":
                row.append("예" if v else "아니요")
            else:
                row.append(v)
        ws.append(row)
    rs = wb["학생 간 관계"]
    sid = {x["key"]: x["sid"] for x in s["students"]}
    kind = {"same": "같은 반", "all_diff": "모두 다른 반", "pairs_diff": "쌍끼리 다른 반", "max_per_class": "반마다 최대 N명"}
    imp = {"low": "낮음", "normal": "보통", "high": "높음", "very_high": "매우 높음"}
    for r in s["relations"]:
        rs.append(["반드시" if r["strength"] == "must" else "가급적", kind[r["kind"]], ", ".join(sid[k] for k in r["members"]),
                   "; ".join(f"{sid[a]}-{sid[b]}" for a, b in r.get("pairs", [])), r.get("max_n") or "",
                   imp.get(r.get("importance"), "") if r["strength"] == "prefer" else "", r.get("reason", "")])
    path = os.path.join(OUT, "가상학생_120명_예시자료.xlsx")
    wb.save(path)
    # 3) 만든 예시 자료가 오류 없이 다시 불러와지는지 확인
    data = open(path, "rb").read()
    parsed = excel_io.parse_upload(data, path)
    target = new_project()
    for f in target["features"]:
        f["active"] = f["id"] in {x["id"] for x in feats}
        if f["id"] == "f_tags":
            f["options"] = ["또래 도우미", "학급 행사 참여", "방과후 연계"]
    sh = next(x for x in parsed["sheets"] if x["name"] == "학생 명단")
    res = excel_io.validate_students(target, sh, excel_io.guess_mapping(target, sh["headers"]))
    rsh = next(x for x in parsed["sheets"] if x["name"] == "학생 간 관계")
    rr = excel_io.validate_relations(target, rsh, excel_io.guess_mapping(target, rsh["headers"], "relations"), [x["sid"] for x in res["students"]])
    print("학생", res["summary"], "오류", len(res["errors"]), "/ 관계", len(rr["relations"]), "오류", len(rr["errors"]))
    assert res["ok"] and rr["ok"]
    print("만든 파일:", os.listdir(OUT))


if __name__ == "__main__":
    main()
