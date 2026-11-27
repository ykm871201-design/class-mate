"""빌드된 실행 파일이 실제로 동작하는지 확인한다.   실행: python packaging/smoke_test.py <ClassMate 실행 파일 경로>"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}/api/"


def call(method, url, body=None, raw=False):
    req = urllib.request.Request(BASE + url, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if raw else json.loads(data.decode("utf-8"))


def main(exe):
    data_dir = tempfile.mkdtemp(prefix="cm-data-")
    env = dict(os.environ, CLASSPLAN_NO_BROWSER="1", CLASSPLAN_PORT=str(PORT), CLASSPLAN_DATA=data_dir)
    proc = subprocess.Popen([exe], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(90):
            time.sleep(1)
            try:
                info = call("GET", "info")
                break
            except OSError:
                if proc.poll() is not None:
                    raise SystemExit(f"실행 파일이 바로 종료되었습니다 (코드 {proc.returncode})")
        else:
            raise SystemExit("실행 파일이 시작되지 않았습니다")
        print("버전", info["version"], "/ 자료 위치", info["data_dir"])
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=10) as r:
            assert "학급 편성 도우미" in r.read().decode("utf-8")
        print("AI 구성요소 포함:", call("GET", "ai/settings")["anthropic_installed"])
        p = call("POST", "projects/sample")
        job = call("POST", "solve", {"project": p, "options": {"seed": 2027, "alternatives": 3, "effort": "fast"}})
        for _ in range(180):
            time.sleep(1)
            st = call("GET", "jobs/" + job["job_id"])
            if st["status"] != "running":
                break
        res = st["result"]
        assert res["status"] == "ok", res.get("message")
        print("자동 편성:", res["message"])
        a = res["alternatives"][0]["assignment"]
        assert res["alternatives"][0]["report"]["hard"]["ok"]
        p["plans"] = [{"id": "pl1", "name": "확인", "assignment": a, "original": a, "locks": {}, "confirmed": True, "new_numbers": {}}]
        x = call("POST", "export", {"project": p, "options": {"plan_id": "pl1", "mode": "public"}}, raw=True)
        assert x[:2] == b"PK"
        x = call("POST", "template", {"project": p}, raw=True)
        assert x[:2] == b"PK"
        print("엑셀 내보내기·양식 확인 완료")
        call("PUT", "projects/" + p["id"], p)
        assert call("GET", "projects/" + p["id"])["plans"][0]["assignment"] == a
        print("저장·불러오기 확인 완료")
    finally:
        proc.kill()


if __name__ == "__main__":
    main(sys.argv[1])
