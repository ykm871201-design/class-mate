"""Windows 에서 설치 → 프로그램 실행 → [업데이트] → 자동 재실행 과정을 실제로 확인한다 (CI 전용).
실행:  python packaging/update_test.py <ClassMate-Setup-x.y.z.exe 경로>
업데이트 파일로는 같은 설치 파일을 쓴다 (CLASSPLAN_UPDATE_TEST_FILE) — 내려받기·검증은 단위 테스트에서 확인.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/api/"


def call(method, url, body=None):
    req = urllib.request.Request(BASE + url, data=json.dumps(body).encode("utf-8") if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def info():
    try:
        return call("GET", "info")
    except OSError:
        return None


def wait_up(timeout, not_pid=None):
    end = time.time() + timeout
    while time.time() < end:
        i = info()
        if i and i.get("pid") != not_pid:
            return i
        time.sleep(1)
    raise SystemExit("프로그램이 시작되지 않았습니다")


def main(setup):
    setup = os.path.abspath(setup)
    data = tempfile.mkdtemp(prefix="cm-upd-")
    os.environ.update(CLASSPLAN_NO_BROWSER="1", CLASSPLAN_PORT=str(PORT), CLASSPLAN_DATA=data, CLASSPLAN_UPDATE_TEST_FILE=setup)
    # 1) 조용히 설치 → 설치 프로그램이 학급 편성 도우미를 자동 실행
    subprocess.run([setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/SP-"], check=True, timeout=300)
    first = wait_up(90)
    st = call("GET", "update/status")
    print("설치 후 실행:", first["version"], st["mode_label"], "pid", first["pid"])
    assert st["mode"] == "installer", st
    assert st["scope"] == "user", st  # 사용자별 설치로 인식해야 업데이트가 관리자 권한 없이 같은 위치에 덮어씀
    p = call("POST", "projects/sample")
    p["name"] = "업데이트 전 저장한 프로젝트"
    call("PUT", "projects/" + p["id"], p)
    # 2) 업데이트 버튼과 같은 동작
    r = call("POST", "update/install", {})
    print("업데이트 시작:", r["message"])
    end = time.time() + 60
    while info() and time.time() < end:
        time.sleep(0.5)
    print("이전 프로그램 종료 확인")
    second = wait_up(240, not_pid=first["pid"])
    print("업데이트 후 자동 재실행:", second["version"], "pid", second["pid"])
    back = call("GET", "projects/" + p["id"])
    assert back["name"] == "업데이트 전 저장한 프로젝트" and len(back["students"]) == len(p["students"])
    assert not os.path.exists(os.path.join(data, ".update_restart")), "재실행 표시 파일이 남아 있음"
    print("업데이트 후에도 학생 자료 유지 확인 완료")
    subprocess.run(["taskkill", "/F", "/PID", str(second["pid"])], check=False)


if __name__ == "__main__":
    main(sys.argv[1])
