"""학생 특성 기반 학급 편성 프로그램 — 로컬 서버

이 PC(127.0.0.1)에서만 접속할 수 있으며, 학생 정보를 외부로 보내지 않습니다.
(AI 보조 기능을 교사가 직접 켜고 전송을 승인한 경우만 예외)
"""
import base64
import json
import os
import time
import socket
import sys
import threading
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse

FROZEN = getattr(sys, "frozen", False)  # 설치 파일(exe)로 실행 중인지
BASE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "vendor"))
sys.path.insert(0, BASE)


def default_data_dir():
    """소스 실행: 프로그램 폴더의 data / 설치판(exe): 사용자별 쓰기 가능한 폴더 (Program Files 는 쓸 수 없음)."""
    if not FROZEN:
        return os.path.join(BASE, "data")
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(root, "ClassMate", "data")
    return os.path.join(os.path.expanduser("~"), ".classmate", "data")


from app import ai as ai_mod  # noqa: E402
from app import defaults, evaluate, excel_io, precheck, solver, updater  # noqa: E402
from app.storage import Storage  # noqa: E402

VERSION = "1.0.2"
DATA_DIR = os.environ.get("CLASSPLAN_DATA") or default_data_dir()
STATIC = os.path.join(BASE, "static")
store = Storage(DATA_DIR)
aisvc = ai_mod.AIService(DATA_DIR)
UPDATE_MARKER = os.path.join(DATA_DIR, ".update_restart")
APP_SETTINGS = os.path.join(DATA_DIR, "app_settings.json")


def app_settings():
    s = {"auto_update_check": True}
    try:
        with open(APP_SETTINGS, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save_app_settings(d):
    s = app_settings()
    if "auto_update_check" in d:
        s["auto_update_check"] = bool(d["auto_update_check"])
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(APP_SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)
    return s


def update_status():
    mode = updater.install_mode()
    return {"version": VERSION, "mode": mode, "auto_check": app_settings()["auto_update_check"],
            "mode_label": {"installer": "설치판", "portable": "휴대용(zip)", "source": "소스 실행"}[mode],
            "page": updater.RELEASES_PAGE, "scope": updater.install_scope() if mode == "installer" else None}


def start_update():
    """새 설치 파일을 내려받아 검증하고, 설치 프로그램을 띄운 뒤 이 프로그램을 종료한다.
    설치가 끝나면 설치 프로그램이 학급 편성 도우미를 다시 실행한다."""
    test_file = os.environ.get("CLASSPLAN_UPDATE_TEST_FILE")  # 자동 테스트 전용 (실제 사용자는 쓰지 않음)
    if updater.install_mode() != "installer" and not test_file:
        raise updater.UpdateError("설치 파일로 설치한 경우에만 자동 업데이트할 수 있습니다. 내려받기 페이지에서 새 버전을 받으세요.")
    if test_file:
        path, latest = test_file, "테스트"
    else:
        info = updater.check(VERSION)
        if not info["newer"]:
            raise updater.UpdateError("이미 최신 버전입니다.")
        if not info["setup"]:
            raise updater.UpdateError("새 버전의 설치 파일이 아직 준비되지 않았습니다. 몇 분 뒤 다시 시도하세요.")
        path, latest = updater.download(info["setup"]), info["latest"]
    with open(UPDATE_MARKER, "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    updater.launch_installer(path)
    threading.Timer(1.5, lambda: os._exit(0)).start()  # 설치가 파일을 바꿀 수 있도록 곧 종료
    return {"ok": True, "latest": latest,
            "message": "업데이트를 설치하고 있습니다. 프로그램이 잠시 꺼졌다가 자동으로 다시 열립니다. 이 화면은 그대로 두세요."}


JOBS = {}
JOBS_LOCK = threading.Lock()
PORT = 8765

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def run_job(job_id, project, options, locks):
    job = JOBS[job_id]

    def progress(f, msg=""):
        job["frac"] = max(job.get("frac", 0.0), min(1.0, max(0.0, float(f))))
        job["progress"] = round(job["frac"] * 100, 1)
        if msg:
            job["message"] = msg

    try:
        res = solver.solve(project, options, locks, progress=progress, cancel=lambda: job["cancel"].is_set())
        job["result"] = res
        job["status"] = "cancelled" if res["status"] == "cancelled" else "done"
    except Exception:
        traceback.print_exc()  # 오류 내용에는 학생 정보가 포함되지 않도록 메시지만 출력
        job["status"] = "error"
        job["result"] = {"status": "error", "message": "편성 계산 중 예기치 않은 오류가 발생했습니다. 자료는 그대로 유지됩니다."}


class Handler(BaseHTTPRequestHandler):
    server_version = "ClassPlanner"

    def log_message(self, fmt, *args):  # 요청 경로만 간단히 (학생 정보는 기록하지 않음)
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, data, filename, ctype):
        self._send(200, data, ctype, {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 80 * 1024 * 1024:
            raise ApiError("파일이 너무 큽니다.")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            raise ApiError("요청 형식이 올바르지 않습니다.")

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method):
        if not self._host_ok():
            return self._send(403, {"error": "이 프로그램은 이 PC에서만 사용할 수 있습니다."})
        path = urlparse(self.path).path
        try:
            if not path.startswith("/api/"):
                if method != "GET":
                    raise ApiError("not found", 404)
                return self._static(path)
            if method != "GET":
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
                    raise ApiError("허용되지 않은 요청입니다.", 403)
            return self._api(method, path[5:].strip("/").split("/"))
        except ApiError as e:
            self._send(e.code, {"error": str(e)})
        except (ai_mod.AIError, ValueError) as e:
            self._send(400, {"error": str(e)})
        except FileNotFoundError:
            self._send(404, {"error": "자료를 찾을 수 없습니다."})
        except Exception:
            traceback.print_exc()
            self._send(500, {"error": "처리 중 오류가 발생했습니다. 자료는 그대로 유지됩니다."})

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, unquote(path).lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        with open(fp, "rb") as f:
            data = f.read()
        self._send(200, data, MIME.get(os.path.splitext(fp)[1], "application/octet-stream"))

    # ------------------------------------------------------------------ API
    def _api(self, method, parts):
        p0 = parts[0]
        if p0 == "update":
            sub = parts[1] if len(parts) > 1 else ""
            if sub == "status" and method == "GET":
                return self._send(200, update_status())
            if method == "POST" and sub == "settings":
                save_app_settings(self._body())
                return self._send(200, update_status())
            if method == "POST" and sub == "check":
                try:
                    return self._send(200, dict(updater.check(VERSION), ok=True, mode=updater.install_mode()))
                except updater.UpdateError as e:
                    return self._send(200, {"ok": False, "error": str(e), "current": VERSION})
            if method == "POST" and sub == "install":
                try:
                    return self._send(200, start_update())
                except updater.UpdateError as e:
                    return self._send(400, {"error": str(e)})
            raise ApiError("not found", 404)
        if p0 == "info" and method == "GET":
            return self._send(200, {"version": VERSION, "pid": os.getpid(), "data_dir": store.dir, "projects_dir": store.pdir, "backups_dir": store.bdir,
                                    "ai": {"enabled": aisvc.public_settings()["enabled"]}})
        if p0 == "projects":
            return self._projects(method, parts[1:])
        if p0 == "defaults" and method == "GET":
            from app import common
            return self._send(200, {"features": defaults.default_features(), "balance": defaults.default_balance(),
                                    "number_rules": evaluate.NUMBER_RULES, "methods": common.METHODS, "allowed_methods": common.ALLOWED_METHODS,
                                    "feature_types": common.FEATURE_TYPES, "rel_kinds": common.REL_KINDS, "importance": common.IMPORTANCE_LABEL,
                                    "builtin_items": common.BUILTIN_ITEMS, "public_columns": excel_io.PUBLIC_COLUMNS,
                                    "default_public": excel_io.DEFAULT_PUBLIC})
        if p0 == "ai" and method == "GET" and len(parts) > 1 and parts[1] == "settings":
            return self._send(200, aisvc.public_settings())
        if p0 == "delete-all" and method == "POST":
            b = self._body()
            if b.get("confirm") != "전체 삭제":
                raise ApiError("확인 문구가 일치하지 않습니다.")
            store.delete_all()
            return self._send(200, {"ok": True})
        if method != "POST" and p0 not in ("jobs",):
            raise ApiError("not found", 404)
        if p0 == "precheck":
            b = self._body()
            return self._send(200, precheck.precheck(b["project"], b.get("locks") or {}))
        if p0 == "evaluate":
            b = self._body()
            return self._send(200, evaluate.evaluate(b["project"], b.get("assignment") or {}, b.get("locks") or {}))
        if p0 == "preview":
            b = self._body()
            return self._send(200, evaluate.preview_change(b["project"], b.get("assignment") or {}, b.get("locks") or {}, b.get("changes") or []))
        if p0 == "compare":
            b = self._body()
            return self._send(200, evaluate.compare(b["project"], b["a"], b["b"], b.get("label_a", "A"), b.get("label_b", "B")))
        if p0 == "numbering":
            b = self._body()
            return self._send(200, {"numbers": evaluate.assign_numbers(b["project"], b["assignment"], b.get("rule", "name"))})
        if p0 == "facts":
            b = self._body()
            fx = evaluate.explain_facts(b["project"], b.get("assignment") or {}, b.get("locks") or {})
            return self._send(200, {"facts": fx["facts"]})
        if p0 == "analyze-item":
            b = self._body()
            return self._send(200, solver.analyze_item(b["project"], b.get("assignment") or {}, b.get("locks") or {}, b["item_id"]))
        if p0 == "suggest-fix":
            b = self._body()
            return self._send(200, solver.suggest_fix(b["project"], b.get("assignment") or {}, b.get("locks") or {}, b["objective"]))
        if p0 == "solve":
            b = self._body()
            jid = uuid.uuid4().hex[:12]
            with JOBS_LOCK:
                JOBS[jid] = {"status": "running", "progress": 0.0, "message": "시작하는 중", "result": None, "cancel": threading.Event()}
            threading.Thread(target=run_job, args=(jid, b["project"], b.get("options") or {}, b.get("locks") or {}), daemon=True).start()
            return self._send(200, {"job_id": jid})
        if p0 == "jobs":
            job = JOBS.get(parts[1] if len(parts) > 1 else "")
            if not job:
                raise ApiError("작업을 찾을 수 없습니다.", 404)
            if len(parts) > 2 and parts[2] == "cancel" and method == "POST":
                job["cancel"].set()
                return self._send(200, {"ok": True})
            out = {k: v for k, v in job.items() if k not in ("cancel", "frac")}
            if job["status"] != "running":
                with JOBS_LOCK:
                    JOBS.pop(parts[1], None)
            return self._send(200, out)
        if p0 == "template":
            b = self._body()
            return self._file(excel_io.make_template(b["project"]), "학급편성_입력양식.xlsx", XLSX)
        if p0 == "import":
            b = self._body()
            sub = parts[1] if len(parts) > 1 else ""
            if sub == "parse":
                data = base64.b64decode(b["data"])
                res = excel_io.parse_upload(data, b.get("filename", ""))
                proj = b.get("project") or {}
                res["seen_before"] = res["hash"] in (proj.get("import_hashes") or [])
                for sh in res["sheets"]:
                    sh["guess_students"] = excel_io.guess_mapping(proj, sh["headers"], "students") if proj else {}
                    sh["guess_relations"] = excel_io.guess_mapping(proj, sh["headers"], "relations") if proj else {}
                return self._send(200, res)
            if sub == "students":
                return self._send(200, excel_io.validate_students(b["project"], b["sheet"], b["mapping"], b.get("existing_policy", "skip")))
            if sub == "relations":
                return self._send(200, excel_io.validate_relations(b["project"], b["sheet"], b["mapping"], b.get("extra_sids")))
            raise ApiError("not found", 404)
        if p0 == "export":
            b = self._body()
            if len(parts) > 1 and parts[1] == "preview":
                return self._send(200, excel_io.export_preview(b["project"], b["options"]))
            data = excel_io.export_excel(b["project"], b["options"])
            kind = "담당교사용" if b["options"].get("mode") == "staff" else "일반배부용"
            return self._file(data, f"학급편성결과_{kind}.xlsx", XLSX)
        if p0 == "ai":
            sub = parts[1] if len(parts) > 1 else ""
            b = self._body()
            if sub == "settings":
                if b.get("_get"):
                    return self._send(200, aisvc.public_settings())
                return self._send(200, aisvc.update_settings(b))
            if sub == "prepare":
                return self._send(200, aisvc.prepare(b["task"], b["project"], b.get("args") or {}))
            if sub == "send":
                return self._send(200, aisvc.send(b["token"]))
            raise ApiError("not found", 404)
        raise ApiError("not found", 404)

    def _projects(self, method, parts):
        if not parts or parts[0] == "":
            if method == "GET":
                return self._send(200, {"projects": store.list(), "dir": store.pdir})
            if method == "POST":
                b = self._body()
                p = defaults.new_project(b.get("name") or "새 편성 프로젝트", int(b.get("school_year") or 2027), int(b.get("current_grade") or 3),
                                         int(b.get("next_grade") or 4), int(b.get("n_classes") or 5), b.get("pattern", "ga"),
                                         int(b.get("target") or 24), int(b.get("max") or 26))
                store.create(p)
                return self._send(200, p)
        pid = parts[0]
        if pid == "sample" and method == "POST":
            p = defaults.sample_project()
            store.create(p)
            return self._send(200, p)
        if pid == "import-backup" and method == "POST":
            b = self._body()
            p = b.get("project")
            if not isinstance(p, dict) or "students" not in p or "classes" not in p:
                raise ApiError("프로젝트 백업 파일이 아닙니다.")
            p = defaults.normalize_project(p)
            p["id"] = None
            p["name"] = (p.get("name") or "불러온 프로젝트") + " (백업에서 복원)"
            store.create(p)
            return self._send(200, p)
        if method == "GET" and len(parts) > 1 and parts[1] == "backup":
            p = store.load(pid)
            data = json.dumps({"format": "class-planner-backup", "version": VERSION, "project": p}, ensure_ascii=False, indent=1).encode("utf-8")
            return self._file(data, f"학급편성_백업_{p.get('name', '')[:20]}.json", "application/json")
        if method == "GET":
            return self._send(200, store.load(pid))
        if method == "PUT":
            b = self._body()
            if b.get("id") != pid:
                raise ApiError("프로젝트 ID가 일치하지 않습니다.")
            info = store.save(b)
            return self._send(200, info)
        if method == "DELETE":
            store.delete(pid)
            return self._send(200, {"ok": True})
        raise ApiError("not found", 404)


def find_port(start):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("사용할 수 있는 포트가 없습니다.")


def already_running(port):
    """이미 실행 중이면 새로 켜지 않고 브라우저만 연다 (바로 가기를 두 번 눌렀을 때)."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8")).get("version") is not None
    except Exception:
        return False


def main():
    for stream in (sys.stdout, sys.stderr):
        try:  # 한글 안내문이 어떤 콘솔에서도 깨지거나 오류를 내지 않도록
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
    want = int(os.environ.get("CLASSPLAN_PORT", PORT))
    if already_running(want):
        print("학급 편성 도우미가 이미 실행 중입니다. 브라우저를 엽니다.")
        if not os.environ.get("CLASSPLAN_NO_BROWSER"):
            webbrowser.open(f"http://127.0.0.1:{want}/")
        return
    port = find_port(want)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 60)
    print(" 학생 특성 기반 학급 편성 프로그램", VERSION)
    print(" 브라우저 주소:", url)
    print(" 자료 저장 위치:", store.dir)
    print(" 이 창을 닫으면 프로그램이 종료됩니다. (자료는 자동 저장됨)")
    print("=" * 60)
    reopened = False
    try:  # 업데이트 직후 다시 켜진 경우: 열려 있던 브라우저 화면이 스스로 다시 연결되므로 새 창을 열지 않음
        if os.path.exists(UPDATE_MARKER):
            reopened = time.time() - os.path.getmtime(UPDATE_MARKER) < 900
            os.remove(UPDATE_MARKER)
    except OSError:
        pass
    if reopened:
        print(" 업데이트가 끝나 다시 실행되었습니다.")
    if not os.environ.get("CLASSPLAN_NO_BROWSER") and not reopened:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
