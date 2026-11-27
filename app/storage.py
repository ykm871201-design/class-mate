"""프로젝트 저장소: 이 PC의 data 폴더에 JSON 파일로 저장한다 (외부 전송 없음)."""
import glob
import json
import os
import re
import shutil
import threading
import time

from .common import new_id, now_iso
from .defaults import normalize_project

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Storage:
    def __init__(self, data_dir):
        self.dir = os.path.abspath(data_dir)
        self.pdir = os.path.join(self.dir, "projects")
        self.bdir = os.path.join(self.dir, "backups")
        os.makedirs(self.pdir, exist_ok=True)
        os.makedirs(self.bdir, exist_ok=True)
        self.lock = threading.Lock()
        self.last_backup = {}

    def path(self, pid):
        if not ID_RE.match(pid or ""):
            raise ValueError("잘못된 프로젝트 ID")
        return os.path.join(self.pdir, pid + ".json")

    def list(self):
        out = []
        for fp in glob.glob(os.path.join(self.pdir, "*.json")):
            try:
                with open(fp, encoding="utf-8") as f:
                    p = json.load(f)
                out.append({"id": p["id"], "name": p.get("name"), "updated_at": p.get("updated_at"), "created_at": p.get("created_at"),
                            "school_year": p.get("settings", {}).get("school_year"), "next_grade": p.get("settings", {}).get("next_grade"),
                            "n_students": len(p.get("students", [])), "n_plans": len(p.get("plans", [])), "path": fp})
            except (OSError, ValueError, KeyError):
                continue
        out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return out

    def load(self, pid):
        with open(self.path(pid), encoding="utf-8") as f:
            return normalize_project(json.load(f))

    def save(self, p):
        with self.lock:
            p["updated_at"] = now_iso()
            fp = self.path(p["id"])
            tmp = fp + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, fp)
            # 10분마다 백업본을 하나씩 남긴다 (최근 10개 유지)
            now = time.time()
            if now - self.last_backup.get(p["id"], 0) > 600:
                self.last_backup[p["id"]] = now
                bd = os.path.join(self.bdir, p["id"])
                os.makedirs(bd, exist_ok=True)
                shutil.copy2(fp, os.path.join(bd, time.strftime("%Y%m%d-%H%M%S") + ".json"))
                files = sorted(glob.glob(os.path.join(bd, "*.json")))
                for old in files[:-10]:
                    try:
                        os.remove(old)
                    except OSError:
                        pass
            return {"saved_at": p["updated_at"], "path": fp}

    def create(self, p):
        if not p.get("id") or os.path.exists(self.path(p["id"])):
            p["id"] = new_id("p")
        self.save(p)
        return p

    def delete(self, pid):
        with self.lock:
            fp = self.path(pid)
            if os.path.exists(fp):
                os.remove(fp)
            bd = os.path.join(self.bdir, pid)
            if os.path.isdir(bd):
                shutil.rmtree(bd, ignore_errors=True)

    def delete_all(self):
        with self.lock:
            for d in (self.pdir, self.bdir):
                shutil.rmtree(d, ignore_errors=True)
                os.makedirs(d, exist_ok=True)
            for name in ("ai_settings.json", "ai_key.secret"):
                try:
                    os.remove(os.path.join(self.dir, name))
                except OSError:
                    pass
