"""새 버전 확인과 자동 업데이트.

- 확인: GitHub 공개 API에서 최신 릴리스의 '버전 정보'만 받아온다 (학생 자료는 보내지 않음).
- 설치판(설치 파일로 설치한 경우): 새 설치 파일을 내려받아 크기·SHA-256을 확인한 뒤
  조용히(진행 창만 보이게) 설치하고 프로그램을 다시 실행한다.
- 휴대용(zip)·소스 실행: 스스로 교체할 수 없으므로 내려받기 페이지만 안내한다.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = "ykm871201-design/class-mate"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
UA = "ClassMate-Updater"  # 일반 이름만 보냄 (개인 정보 없음)
SETUP_RE = re.compile(r"^ClassMate-Setup-(\d+\.\d+\.\d+)\.exe$")


class UpdateError(Exception):
    pass


def parse_version(s):
    nums = [int(x) for x in re.findall(r"\d+", str(s or ""))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def install_mode(frozen=None, exe=None):
    """installer: 설치 파일로 설치됨 / portable: 휴대용 zip / source: 파이썬 소스로 실행"""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not frozen:
        return "source"
    exe_dir = os.path.dirname(os.path.abspath(exe or sys.executable))
    if any(n.lower().startswith("unins") and n.lower().endswith(".exe") for n in os.listdir(exe_dir)):
        return "installer"
    return "portable"


def _get_json(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("아직 공개된 릴리스가 없습니다.")
        if e.code in (403, 429):
            raise UpdateError("GitHub 확인 횟수 제한에 걸렸습니다. 잠시 후 다시 시도하세요.")
        raise UpdateError(f"업데이트 정보를 받지 못했습니다 (오류 {e.code}).")
    except (urllib.error.URLError, OSError, ValueError):
        raise UpdateError("인터넷에 연결할 수 없어 새 버전을 확인하지 못했습니다. 프로그램 사용에는 문제가 없습니다.")


def check(current, timeout=8, fetch=None):
    data = (fetch or _get_json)(LATEST_API, timeout)
    tag = data.get("tag_name") or ""
    latest = ".".join(str(x) for x in parse_version(tag))
    setup = None
    portable = None
    for a in data.get("assets") or []:
        name = a.get("name") or ""
        if SETUP_RE.match(name):
            setup = {"name": name, "size": a.get("size"), "url": a.get("browser_download_url"), "digest": a.get("digest")}
        elif name.startswith("ClassMate-Portable-") and name.endswith(".zip"):
            portable = {"name": name, "size": a.get("size"), "url": a.get("browser_download_url")}
    return {
        "current": current,
        "latest": latest,
        "tag": tag,
        "newer": parse_version(latest) > parse_version(current),
        "notes": (data.get("body") or "")[:6000],
        "published_at": data.get("published_at"),
        "page": data.get("html_url") or RELEASES_PAGE,
        "setup": setup,
        "portable": portable,
    }


def download(asset, dest_dir=None, timeout=60, opener=None):
    """설치 파일을 내려받고 크기와 SHA-256(릴리스에 기록된 값)을 확인한다."""
    url = asset.get("url") or ""
    if not url.startswith(f"https://github.com/{REPO}/releases/download/") or not SETUP_RE.match(asset.get("name") or ""):
        raise UpdateError("업데이트 파일 주소가 올바르지 않아 내려받지 않았습니다.")
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="classmate-update-")
    path = os.path.join(dest_dir, asset["name"])
    h = hashlib.sha256()
    size = 0
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r, open(path, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)
    except (urllib.error.URLError, OSError):
        raise UpdateError("업데이트 파일을 내려받지 못했습니다. 인터넷 연결을 확인하세요.")
    if asset.get("size") and size != asset["size"]:
        raise UpdateError("내려받은 파일 크기가 맞지 않아 설치하지 않았습니다. 다시 시도하세요.")
    dg = asset.get("digest") or ""
    if dg.startswith("sha256:") and dg.split(":", 1)[1].lower() != h.hexdigest():
        raise UpdateError("내려받은 파일의 검증값(SHA-256)이 맞지 않아 설치하지 않았습니다.")
    return path


UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{8E3C5B2A-7D41-4F7B-9C2E-3A1D6B0F9E21}_is1"  # installer.iss 의 AppId


def _norm(p):
    # realpath: Windows 의 짧은 이름(RUNNER~1 등)을 긴 이름으로 바꿔 같은 폴더를 같게 비교
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def install_scope(exe=None, use_registry=True):
    """'user'(사용자별 설치) 또는 'all'(모든 사용자 설치). 설치 프로그램이 남긴 제거 정보를 먼저 보고, 없으면 경로로 판단."""
    if use_registry and os.name == "nt":
        try:
            import winreg
            for hive, scope in ((winreg.HKEY_CURRENT_USER, "user"), (winreg.HKEY_LOCAL_MACHINE, "all")):
                for view in (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | view):
                            return scope
                    except OSError:
                        continue
        except ImportError:
            pass
    local = os.environ.get("LOCALAPPDATA") or ""
    if not local:
        return "all"
    exe_dir, local = _norm(os.path.dirname(exe or sys.executable)), _norm(local)
    try:
        return "user" if os.path.commonpath([exe_dir, local]) == local else "all"
    except ValueError:  # 서로 다른 드라이브
        return "all"


def installer_args(exe=None, use_registry=True):
    """현재 설치 위치(사용자별/모든 사용자)에 그대로 덮어쓰도록 설치 옵션을 정한다."""
    scope = "/CURRENTUSER" if install_scope(exe, use_registry) == "user" else "/ALLUSERS"
    return ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/SP-", scope]


def launch_installer(path):
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — 이 프로그램이 꺼져도 설치는 계속
    subprocess.Popen([path] + installer_args(), creationflags=flags, close_fds=True)
