"""AI 보조 기능 (선택 기능, 기본값 꺼짐).

원칙
- AI는 요청 해석·조건 제안·결과 설명·수정 조건 변환에만 쓰고, 실제 배정은 편성 알고리즘이 계산·검증한다.
- 전송 전에 '실제로 보낼 내용'을 그대로 보여주고, 교사가 전송을 누른 경우에만 보낸다 (미리보기 = 실제 전송 내용).
- 이름 대신 임시 ID, 학급별 집계 위주. 자유 메모는 교사가 고른 경우에만, 이름·연락처·날짜를 가린 뒤 보낸다.
- API 키는 이 PC의 data 폴더에만 저장하고 브라우저·프로젝트 파일로 보내지 않는다.
- AI 응답은 정해진 JSON 구조로 받아 검사하며, 잘못되면 아무것도 바꾸지 않는다.
"""
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .common import ALLOWED_METHODS, BUILTIN_ITEMS, IMPORTANCE, IMPORTANCE_LABEL, METHODS, fmt_num, is_missing, level_label, level_steps
from .evaluate import Ctx, evaluate, explain_facts

PROVIDERS = {
    "builtin": {"label": "내장 간이 해석기 (이 PC 안에서만 처리, 외부 전송 없음, 키워드 기반의 단순 해석)", "default_model": "builtin"},
    "anthropic": {"label": "Anthropic Claude API (인터넷으로 외부 전송, 사용량에 따라 비용 발생)", "default_model": "claude-opus-5-5"},
    "openai_compat": {"label": "OpenAI 호환 서버 (예: 이 PC의 Ollama·LM Studio, 또는 학교가 승인한 서버)", "default_model": "llama3.1"},
}
DEFAULT_SETTINGS = {"enabled": False, "provider": "builtin", "model": "", "endpoint": "http://127.0.0.1:11434/v1",
                    "allow_external": False}
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1", "claude-sonnet-5-5"}

SYN = {
    "builtin:gender": ["성별", "남녀", "남학생", "여학생"],
    "builtin:size": ["인원", "학생 수", "학생수"],
    "builtin:origin": ["현재 반", "출신 반", "같은 반이었던", "골고루 섞", "섞어"],
    "f_learn": ["학습 수준", "학력", "성적", "공부", "학업"],
    "f_kor": ["국어"], "f_math": ["수학"],
    "f_basic": ["기초학습", "학습 지원", "학습지원", "기초 학습", "학습 부진", "학습지원 대상"],
    "f_engage": ["과제", "학습 참여"],
    "f_active": ["활동성", "활발", "활동적", "에너지"],
    "f_selfreg": ["자기조절", "자기 조절", "감정 조절"],
    "f_peer": ["또래", "교우", "친구 관계", "교우관계"],
    "f_leader": ["리더", "이끌", "주도", "반장"],
    "f_coop": ["협력", "협동"],
    "f_guide": ["생활지도", "갈등", "중재"],
    "f_iep": ["개별적인 교육", "개별 교육", "개별화", "특수"],
    "f_kolang": ["한국어", "다문화"],
    "f_extra": ["추가 지원", "수업 참여"],
    "f_arts": ["예체능", "음악", "미술", "체육"],
}
CORE_STRIP = ["지원 필요 정도", "필요 정도", "필요 여부", "정도", "여부", "수준", "성향", "관심 분야"]

SYSTEM_COMMON = (
    "당신은 초등학교 교사의 학급 편성을 돕는 보조자입니다. 반드시 지켜야 할 원칙:\n"
    "1) 제공된 항목 ID·학급 ID·선택지만 사용하고, 없는 특성이나 학생 자료를 만들어내지 마세요.\n"
    "2) 학생의 질병·장애·성격·가정환경을 추정하거나 진단하지 마세요. 낙인 표현과 학생 간 우열 평가를 쓰지 마세요.\n"
    "3) 모호한 요청을 필수 조건으로 바꾸지 마세요. 불분명한 점은 unclear 목록에 쓰세요.\n"
    "4) 숫자는 제공된 자료에 있는 값만 사용하세요. 직접 추정한 수치를 만들지 마세요.\n"
    "5) 출력은 설명 문장 없이 지정된 JSON 객체 하나만 출력하세요.\n"
)
SYS = {
    "settings": SYSTEM_COMMON + (
        "과제: 교사의 문장 요청을 현재 프로젝트의 균형 조건 설정 제안으로 바꾸세요.\n"
        "출력 형식: {\"interpretation\": 문자열, \"proposals\": [{\"target\": 항목ID, \"use_in_balance\": true/false, "
        "\"method\": (선택) 허용 방식 중 하나, \"importance\": low|normal|high|very_high, \"count_values\": (선택) 선택지 목록, "
        "\"count_min\": (선택) 숫자, \"reason\": 문자열}], \"new_combos\": [{\"name\": 문자열, \"conds\": [{\"feature_id\": 특성ID, \"values\": [값]}], "
        "\"importance\": low|normal|high|very_high, \"reason\": 문자열}], \"unclear\": [문자열], \"missing\": [문자열]}\n"
        "요청한 특성이 목록에 없으면 missing 에 '필요한 항목과 자료가 없음'을 쓰세요."),
    "explain": SYSTEM_COMMON + (
        "과제: 프로그램이 계산한 사실 목록(facts)만 근거로 교사가 이해하기 쉬운 한국어 설명을 쓰세요. facts 에 없는 숫자는 절대 쓰지 마세요.\n"
        "원인은 단정하지 말고, facts 에서 확인된 것이 아니면 possible_causes 에 '가능성'으로만 쓰세요.\n"
        "출력 형식: {\"summary\": 문자열, \"points\": [문자열], \"possible_causes\": [문자열]}"),
    "fix": SYSTEM_COMMON + (
        "과제: 교사의 수정 요청을 편성 알고리즘이 계산할 '수정 조건'으로 바꾸세요. 실제 학생 이동은 알고리즘이 계산합니다.\n"
        "출력 형식: {\"objective\": {\"focus\": [{\"target\": 항목ID, \"class_id\": 학급ID 또는 null, \"direction\": decrease|increase|balance, "
        "\"category\": 범주key 또는 null}], \"max_moved\": 1~40 정수, \"minimize_moves\": true/false, \"keep_locked\": true}, "
        "\"explanation\": 문자열, \"unclear\": [문자열]}\n고정된 학생과 필수 조건은 항상 유지해야 하므로 keep_locked 는 true 입니다."),
    "memo_tags": SYSTEM_COMMON + (
        "과제: 교사가 고른 메모에서, 제공된 특성 항목의 선택지에 명확히 해당하는 내용만 태그 후보로 제안하세요. 애매하면 제안하지 마세요.\n"
        "출력 형식: {\"suggestions\": [{\"temp_id\": 메모ID, \"feature_id\": 특성ID, \"values\": [선택지], \"basis\": 메모 속 근거 표현(짧게)}]}"),
}


class AIError(Exception):
    pass


class AIService:
    def __init__(self, data_dir):
        self.dir = data_dir
        self.path = os.path.join(data_dir, "ai_settings.json")
        self.key_path = os.path.join(data_dir, "ai_key.secret")
        self.pending = {}
        self.lock = threading.Lock()

    # ----------------------------------------------------------- 설정
    def _load(self):
        s = dict(DEFAULT_SETTINGS)
        try:
            with open(self.path, encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        return s

    def _key(self):
        try:
            with open(self.key_path, encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
        except OSError:
            pass
        s = self._load()
        if s.get("provider") == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY", "")
        return os.environ.get("CLASSPLAN_AI_KEY", "")

    def public_settings(self):
        s = self._load()
        s["has_key"] = bool(self._key())
        s["providers"] = {k: v["label"] for k, v in PROVIDERS.items()}
        s["default_models"] = {k: v["default_model"] for k, v in PROVIDERS.items()}
        s["external"] = self.is_external(s)
        try:
            import anthropic  # noqa: F401
            s["anthropic_installed"] = True
        except ImportError:
            s["anthropic_installed"] = False
        s["key_location"] = self.key_path
        return s

    def update_settings(self, d):
        s = self._load()
        for k in ("enabled", "provider", "model", "endpoint", "allow_external"):
            if k in d:
                s[k] = d[k]
        if s["provider"] not in PROVIDERS:
            s["provider"] = "builtin"
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
        if d.get("api_key"):
            with open(self.key_path, "w", encoding="utf-8") as f:
                f.write(d["api_key"].strip())
        if d.get("clear_key"):
            try:
                os.remove(self.key_path)
            except OSError:
                pass
        return self.public_settings()

    def is_external(self, s=None):
        s = s or self._load()
        if s["provider"] == "builtin":
            return False
        if s["provider"] == "anthropic":
            return True
        host = urllib.parse.urlparse(s.get("endpoint") or "").hostname or ""
        return host not in ("localhost", "127.0.0.1", "::1")

    # ----------------------------------------------------------- 자료 구성
    def _feature_defs(self, project, ctx):
        out = []
        for f in project.get("features", []):
            if not f.get("active") or f["type"] == "text":
                continue
            vals = [s.get("traits", {}).get(f["id"]) for s in ctx.students]
            miss = sum(1 for v in vals if is_missing(f, v))
            d = {"id": "feature:" + f["id"], "feature_id": f["id"], "name": f["name"], "category": f.get("category"),
                 "type": f["type"], "description": f.get("desc", ""), "allowed_methods": ALLOWED_METHODS[f["type"]],
                 "current": {"use_in_balance": bool(f.get("use_in_balance")), "method": f.get("method"), "importance": f.get("importance")},
                 "input_status": {"entered": len(vals) - miss, "missing": miss}}
            if f["type"] in ("single", "multi"):
                d["options"] = f.get("options", [])
            if f["type"] == "level":
                d["steps"] = [level_label(f, x) for x in level_steps(f)][:12]
                d["range"] = [f.get("min"), f.get("max")]
            if f["type"] == "yesno":
                d["options"] = ["예", "아니요"]
            out.append(d)
        return out

    def _builtins(self, project):
        bal = project.get("balance", {})
        return [{"id": k, "name": v, "current": {"use_in_balance": bal.get(k.split(":")[1], {}).get("enabled", True),
                                                 "importance": bal.get(k.split(":")[1], {}).get("importance")}}
                for k, v in BUILTIN_ITEMS.items()]

    def build(self, task, project, args):
        ctx = Ctx(project)
        included, excluded = [], ["학생 이름", "학생 ID", "학교명", "생년월일", "연락처", "교사용 메모", "관계 사유"]
        aux = {}
        if task == "settings":
            text = (args.get("text") or "").strip()
            if not text:
                raise AIError("요청 문장을 입력하세요.")
            payload = {"task": "settings", "request": text, "features": self._feature_defs(project, ctx),
                       "builtin_items": self._builtins(project),
                       "combos": [{"id": "combo:" + c["id"], "name": c.get("name")} for c in project.get("combos", [])],
                       "importance_levels": {k: IMPORTANCE_LABEL[k] for k in IMPORTANCE}, "methods": METHODS}
            included = ["교사의 요청 문장", "특성 항목 정의(이름·형식·선택지)", "항목별 입력 인원·미입력 인원(집계)", "현재 균형 조건 설정"]
            excluded.append("학생별 특성 값")
        elif task == "explain":
            fx = explain_facts(project, args.get("assignment") or {}, args.get("locks") or {})
            payload = {"task": "explain", "class_names": [c["name"] for c in project["classes"]],
                       "facts": [f["text"] for f in fx["facts"]]}
            aux["facts"] = payload["facts"]
            included = ["프로그램이 계산한 학급별 집계 문장(인원·분포·조건 충족 여부)", "학급 이름"]
            excluded.append("학생별 특성 값")
            # 사실 문장에 들어 있는 학생 이름(선호 조건 미충족 안내 등)은 임시 표기로 바꾼다
            payload["facts"] = [self._redact_names(project, t) for t in payload["facts"]]
            aux["facts"] = payload["facts"]
        elif task == "fix":
            text = (args.get("text") or "").strip()
            if not text:
                raise AIError("수정 요청 문장을 입력하세요.")
            rep = evaluate(project, args.get("assignment") or {}, args.get("locks") or {}, ctx)
            items = []
            for it in rep["items"]:
                items.append({"id": it["id"], "name": it["name"], "enabled": it["enabled"], "status": it["status_label"],
                              "categories": [{"key": c["key"], "label": c["label"], "counts_by_class": c["counts"]} for c in it["cats"]],
                              "class_means": it["mean"]["class_means"] if it.get("mean") else None})
            payload = {"task": "fix", "request": text,
                       "classes": [{"id": c["id"], "name": c["name"], "size": c["size"], "target": c["target"], "max": c["max"]} for c in rep["classes"]],
                       "items": items, "locked_student_count": len(args.get("locks") or {}),
                       "hard_constraints_ok": rep["hard"]["ok"]}
            included = ["교사의 수정 요청 문장", "학급별 인원과 항목별 집계(학생 단위 아님)", "고정된 학생 수"]
        elif task == "memo_tags":
            keys = [k for k in (args.get("keys") or []) if k in ctx.by_key]
            if not keys:
                raise AIError("메모를 분석할 학생을 1명 이상 고르세요.")
            memos, idmap = [], {}
            for i, k in enumerate(keys):
                m = (ctx.by_key[k].get("memo") or "").strip()
                if not m:
                    continue
                tid = f"M{i + 1}"
                idmap[tid] = k
                memos.append({"temp_id": tid, "text": self._redact(project, m)})
            if not memos:
                raise AIError("선택한 학생들에게 메모가 없습니다.")
            tf = []
            for f in project.get("features", []):
                if f.get("active") and f["type"] in ("single", "multi", "yesno"):
                    tf.append({"feature_id": f["id"], "name": f["name"], "type": f["type"],
                               "options": f.get("options", []) if f["type"] != "yesno" else ["예", "아니요"]})
            payload = {"task": "memo_tags", "memos": memos, "tag_features": tf}
            aux["idmap"] = idmap
            included = [f"교사가 고른 메모 {len(memos)}건 (이름·연락처·날짜는 가림 처리)", "태그로 쓸 특성 항목과 선택지"]
            excluded = [x for x in excluded if x != "교사용 메모"] + ["선택하지 않은 학생의 메모"]
        else:
            raise AIError("알 수 없는 AI 작업입니다.")
        return payload, included, excluded, aux

    def _redact_names(self, project, text):
        names = sorted({(s.get("name") or "").strip() for s in project["students"] if len((s.get("name") or "").strip()) >= 2}, key=len, reverse=True)
        tmp = {}
        for i, s in enumerate(project["students"]):
            tmp[s.get("sid")] = f"학생{i + 1}"
        # "이름(ID)" 형태를 임시 표기로 교체
        text = re.sub(r"[^\s,·()]+\(([^()]+)\)", lambda m: tmp.get(m.group(1), "학생") if m.group(1) in tmp else m.group(0), text)
        for n in names:
            text = text.replace(n, "○○")
        return text

    def _redact(self, project, text):
        text = self._redact_names(project, text)
        text = re.sub(r"\d{2,4}-\d{3,4}-\d{4}", "[연락처 가림]", text)
        text = re.sub(r"\d{4}[./-]\s?\d{1,2}[./-]\s?\d{1,2}", "[날짜 가림]", text)
        return text

    # ----------------------------------------------------------- 준비 / 전송
    def prepare(self, task, project, args):
        s = self._load()
        if not s.get("enabled"):
            raise AIError("AI 보조 기능이 꺼져 있습니다. ‘AI 연결 설정’에서 켜세요. (AI 없이도 모든 기본 기능은 사용할 수 있습니다)")
        payload, inc, exc, aux = self.build(task, project, args)
        ext = self.is_external(s)
        token = secrets.token_hex(12)
        text = json.dumps(payload, ensure_ascii=False, indent=1)
        model = s.get("model") or PROVIDERS[s["provider"]]["default_model"]
        dest = {"builtin": "이 PC (외부 전송 없음)", "anthropic": "api.anthropic.com (외부 서버)",
                "openai_compat": s.get("endpoint", "")}[s["provider"]]
        with self.lock:
            now = time.time()
            for k in [k for k, v in self.pending.items() if now - v["at"] > 900]:
                del self.pending[k]
            self.pending[token] = {"task": task, "system": SYS[task], "user": text, "at": now, "aux": aux,
                                   "provider": s["provider"], "model": model, "endpoint": s.get("endpoint"), "args": args,
                                   "project": project}
        return {"token": token, "provider": s["provider"], "provider_label": PROVIDERS[s["provider"]]["label"], "model": model,
                "destination": dest, "external": ext, "allow_external": bool(s.get("allow_external")),
                "included": inc, "excluded": exc, "system_text": SYS[task], "payload_text": text,
                "notice": ("이름을 지워도 특성 조합으로 학생을 알아볼 가능성이 있으므로 익명 정보라고 단정할 수 없습니다. "
                           "학교의 개인정보 처리 기준에 따라 전송 여부를 결정하세요.") if ext else "이 작업은 이 PC 안에서만 처리되며 외부로 전송되지 않습니다."}

    def send(self, token):
        with self.lock:
            p = self.pending.pop(token, None)
        if not p:
            raise AIError("전송 준비 정보가 없거나 만료되었습니다. 다시 시도하세요.")
        s = self._load()
        if not s.get("enabled"):
            raise AIError("AI 보조 기능이 꺼져 있습니다.")
        if self.is_external(s) and not s.get("allow_external"):
            raise AIError("외부 전송이 허용되지 않았습니다. ‘AI 연결 설정’에서 ‘외부 AI로 자료 전송 허용’을 직접 켜야 합니다.")
        if p["provider"] != s["provider"]:
            raise AIError("미리보기 이후 연결 설정이 바뀌었습니다. 다시 미리보기를 확인하세요.")
        if p["provider"] == "builtin":
            raw = json.dumps(builtin_answer(p["task"], p["project"], json.loads(p["user"]), p["aux"]), ensure_ascii=False)
        elif p["provider"] == "anthropic":
            raw = self._call_anthropic(p)
        else:
            raw = self._call_openai_compat(p)
        try:
            data = extract_json(raw)
        except ValueError:
            return {"ok": False, "errors": ["AI 응답이 정해진 형식(JSON)이 아니어서 아무것도 변경하지 않았습니다."], "raw": raw[:4000]}
        res = validate(p["task"], p["project"], data, p["aux"], p["args"])
        res["raw"] = raw[:6000]
        res["provider"] = p["provider"]
        res["model"] = p["model"]
        return res

    def _call_anthropic(self, p):
        key = self._key()
        if not key:
            raise AIError("Anthropic API 키가 저장되어 있지 않습니다. ‘AI 연결 설정’에서 입력하세요.")
        try:
            import anthropic
        except ImportError:
            raise AIError("Anthropic 연결 구성요소가 설치되어 있지 않습니다. 프로그램 폴더의 ‘AI구성요소_설치.bat’을 실행하세요.")
        client = anthropic.Anthropic(api_key=key, timeout=120.0, max_retries=2)
        kw = dict(model=p["model"], max_tokens=8000, system=p["system"],
                  messages=[{"role": "user", "content": p["user"]}], output_config={"effort": "low"})
        try:
            if p["model"] in FALLBACK_MODELS:
                resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
            else:
                resp = client.messages.create(**kw)
        except anthropic.AuthenticationError:
            raise AIError("API 키가 올바르지 않습니다.")
        except anthropic.PermissionDeniedError:
            raise AIError("이 API 키로는 해당 모델을 사용할 권한이 없습니다.")
        except anthropic.NotFoundError:
            raise AIError("모델 이름이 올바르지 않습니다. 설정의 모델 이름을 확인하세요.")
        except anthropic.RateLimitError:
            raise AIError("사용 한도를 초과했거나 요청이 너무 많습니다. 잠시 후 다시 시도하세요. (편성 자료는 그대로 유지됩니다)")
        except anthropic.APIStatusError as e:
            raise AIError(f"AI 서버 오류({e.status_code})입니다. 잠시 후 다시 시도하세요.")
        except anthropic.APIConnectionError:
            raise AIError("AI 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요. (편성 자료는 그대로 유지됩니다)")
        if resp.stop_reason == "refusal":
            raise AIError("AI가 이 요청에 응답하지 않았습니다. 요청 문장을 바꿔 다시 시도하세요.")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def _call_openai_compat(self, p):
        ep = (p.get("endpoint") or "").rstrip("/")
        if not ep:
            raise AIError("서버 주소를 입력하세요.")
        url = ep if ep.endswith("/chat/completions") else ep + "/chat/completions"
        body = json.dumps({"model": p["model"], "temperature": 0.2,
                           "messages": [{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        key = self._key()
        if key:
            req.add_header("Authorization", "Bearer " + key)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise AIError(f"AI 서버 오류({e.code})입니다. 서버 주소·모델 이름을 확인하세요.")
        except (urllib.error.URLError, OSError):
            raise AIError("AI 서버에 연결할 수 없습니다. 서버가 실행 중인지, 주소가 맞는지 확인하세요.")
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AIError("AI 서버의 응답 구조를 이해할 수 없습니다.")


def extract_json(raw):
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    if m:
        raw = m.group(1)
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise ValueError("no json")
    return json.loads(raw[a:b + 1])


# ----------------------------------------------------------------------------
# 응답 검증
# ----------------------------------------------------------------------------

def _str_list(x):
    return [str(v) for v in x] if isinstance(x, list) else []


def validate(task, project, data, aux, args):
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["응답이 객체 형식이 아닙니다."]}
    if task == "settings":
        return _validate_settings(project, data)
    if task == "explain":
        return _validate_explain(project, data, aux)
    if task == "fix":
        return _validate_fix(project, data, args)
    if task == "memo_tags":
        return _validate_memo(project, data, aux)
    return {"ok": False, "errors": ["알 수 없는 작업"]}


def _level_ok(f, x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return False
    return any(abs(x - s) < 1e-6 for s in level_steps(f))


def _validate_settings(project, data):
    feats = {"feature:" + f["id"]: f for f in project.get("features", []) if f.get("active") and f["type"] != "text"}
    combos = {"combo:" + c["id"]: c for c in project.get("combos", [])}
    bal = project.get("balance", {})
    errors, changes, new_combos = [], [], []
    props = data.get("proposals", [])
    if not isinstance(props, list):
        errors.append("proposals 가 목록이 아닙니다.")
        props = []
    seen = set()
    for i, pr in enumerate(props):
        if not isinstance(pr, dict):
            errors.append(f"{i + 1}번째 제안 형식 오류")
            continue
        t = pr.get("target")
        if t in seen:
            errors.append(f"같은 항목({t})에 대한 제안이 중복되었습니다.")
            continue
        seen.add(t)
        imp = pr.get("importance")
        if imp is not None and imp not in IMPORTANCE:
            errors.append(f"‘{t}’의 중요도 ‘{imp}’는 허용 범위(낮음·보통·높음·매우 높음)가 아닙니다.")
            continue
        use = pr.get("use_in_balance")
        if use is not None and not isinstance(use, bool):
            errors.append(f"‘{t}’의 반영 여부 값이 올바르지 않습니다.")
            continue
        reason = str(pr.get("reason") or "")
        if t in BUILTIN_ITEMS:
            key = t.split(":")[1]
            cur = bal.get(key, {})
            if pr.get("method") not in (None, "", "distribution"):
                errors.append(f"‘{BUILTIN_ITEMS[t]}’에는 균형 방식을 지정할 수 없습니다.")
                continue
            changes.append({"target": t, "name": BUILTIN_ITEMS[t],
                            "current": {"use_in_balance": cur.get("enabled", True), "importance": cur.get("importance")},
                            "proposed": {"use_in_balance": cur.get("enabled", True) if use is None else use, "importance": imp or cur.get("importance")},
                            "reason": reason})
            continue
        if t in combos:
            c = combos[t]
            changes.append({"target": t, "name": c.get("name"), "current": {"use_in_balance": bool(c.get("use_in_balance")), "importance": c.get("importance")},
                            "proposed": {"use_in_balance": bool(c.get("use_in_balance")) if use is None else use, "importance": imp or c.get("importance")},
                            "reason": reason})
            continue
        f = feats.get(t)
        if not f:
            errors.append(f"‘{t}’은(는) 현재 프로젝트에 없는(또는 꺼져 있는) 특성 항목입니다.")
            continue
        method = pr.get("method") or f.get("method")
        if method not in ALLOWED_METHODS[f["type"]]:
            errors.append(f"‘{f['name']}’에 ‘{method}’ 방식은 사용할 수 없습니다.")
            continue
        prop = {"use_in_balance": bool(f.get("use_in_balance")) if use is None else use, "method": method, "importance": imp or f.get("importance")}
        if method == "count":
            if f.get("count_values"):
                prop["count_values"] = list(f["count_values"])
            if f.get("count_min") is not None:
                prop["count_min"] = f["count_min"]
        if pr.get("count_values") is not None:
            cv = pr.get("count_values")
            opts = f.get("options", []) if f["type"] != "yesno" else ["예", "아니요"]
            if not isinstance(cv, list) or any(v not in opts for v in cv):
                errors.append(f"‘{f['name']}’의 count_values 에 선택지에 없는 값이 있습니다.")
                continue
            prop["count_values"] = cv
        if pr.get("count_min") is not None:
            if f["type"] != "level" or not _level_ok(f, pr["count_min"]):
                errors.append(f"‘{f['name']}’의 기준값이 허용 단계가 아닙니다.")
                continue
            prop["count_min"] = float(pr["count_min"])
        changes.append({"target": t, "name": f["name"], "current": {"use_in_balance": bool(f.get("use_in_balance")), "method": f.get("method"),
                                                                    "importance": f.get("importance"), "count_values": f.get("count_values"),
                                                                    "count_min": f.get("count_min")},
                        "proposed": prop, "reason": reason})
    for i, cb in enumerate(data.get("new_combos", []) or []):
        if not isinstance(cb, dict):
            errors.append("조합 제안 형식 오류")
            continue
        conds = cb.get("conds") or []
        if len(conds) < 2:
            errors.append(f"조합 ‘{cb.get('name')}’은 특성이 2개 이상이어야 합니다.")
            continue
        okc = []
        for c in conds:
            f = feats.get("feature:" + str(c.get("feature_id"))) or feats.get(str(c.get("feature_id")))
            vals = c.get("values") or []
            if not f or not isinstance(vals, list) or not vals:
                errors.append(f"조합 ‘{cb.get('name')}’에 없는 특성 또는 값이 있습니다.")
                okc = None
                break
            if f["type"] == "yesno":
                if any(v not in ("예", "아니요", True, False) for v in vals):
                    errors.append(f"조합 ‘{cb.get('name')}’의 ‘{f['name']}’ 값 오류")
                    okc = None
                    break
                vals = [True if v in ("예", True) else False for v in vals]
            elif f["type"] == "level":
                if any(not _level_ok(f, v) for v in vals):
                    errors.append(f"조합 ‘{cb.get('name')}’의 ‘{f['name']}’ 단계 값 오류")
                    okc = None
                    break
                vals = [float(v) for v in vals]
            elif any(v not in f.get("options", []) for v in vals):
                errors.append(f"조합 ‘{cb.get('name')}’의 ‘{f['name']}’ 선택지 오류")
                okc = None
                break
            okc.append({"feature_id": f["id"], "values": vals})
        if okc is None:
            continue
        imp = cb.get("importance", "normal")
        if imp not in IMPORTANCE:
            errors.append(f"조합 ‘{cb.get('name')}’ 중요도 오류")
            continue
        new_combos.append({"name": str(cb.get("name") or "특성 조합")[:60], "conds": okc, "importance": imp, "reason": str(cb.get("reason") or "")})
    res = {"ok": not errors, "errors": errors, "changes": changes if not errors else [], "new_combos": new_combos if not errors else [],
           "interpretation": str(data.get("interpretation") or ""), "unclear": _str_list(data.get("unclear")), "missing": _str_list(data.get("missing"))}
    if errors:
        res["message"] = "AI 응답에 허용되지 않는 내용이 있어 아무것도 변경하지 않았습니다."
    return res


NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _validate_explain(project, data, aux):
    facts = aux.get("facts", [])
    allowed = set()
    for t in facts + [c["name"] for c in project["classes"]]:
        for n in NUM_RE.findall(t):
            allowed.add(fmt_num(float(n)))
    texts = [str(data.get("summary") or "")] + _str_list(data.get("points")) + _str_list(data.get("possible_causes"))
    bad = sorted({n for t in texts for n in NUM_RE.findall(t) if fmt_num(float(n)) not in allowed})
    causes = []
    for c in _str_list(data.get("possible_causes")):
        causes.append(c if ("가능" in c or "추정" in c) else "[가능성] " + c)
    if bad:
        return {"ok": False, "errors": [f"AI 설명에 프로그램이 계산하지 않은 숫자({', '.join(bad[:10])})가 있어 사용하지 않았습니다. 아래의 프로그램 계산 결과를 확인하세요."],
                "facts": facts}
    return {"ok": True, "summary": str(data.get("summary") or ""), "points": _str_list(data.get("points")), "possible_causes": causes, "facts": facts}


def _validate_fix(project, data, args):
    from .solver import suggest_fix
    ctx = Ctx(project)
    obj = data.get("objective")
    errors, notes = [], []
    if not isinstance(obj, dict):
        return {"ok": False, "errors": ["objective 가 없습니다. 요청을 해석하지 못했습니다."], "unclear": _str_list(data.get("unclear"))}
    item_ids = {it["id"]: it for it in ctx.items}
    focus = []
    for f in obj.get("focus") or []:
        if not isinstance(f, dict) or f.get("target") not in item_ids:
            errors.append(f"‘{(f or {}).get('target') if isinstance(f, dict) else f}’은(는) 현재 프로젝트에 없는 항목입니다.")
            continue
        cid = f.get("class_id")
        if cid not in (None, "") and cid not in ctx.cidx:
            errors.append(f"학급 ID ‘{cid}’가 없습니다.")
            continue
        d = f.get("direction", "balance")
        if d not in ("decrease", "increase", "balance"):
            errors.append(f"방향 ‘{d}’는 허용되지 않습니다.")
            continue
        cat = f.get("category")
        it = item_ids[f["target"]]
        if cat not in (None, "") and cat not in [c["key"] for c in it["cats"]] + [c["label"] for c in it["cats"]]:
            errors.append(f"‘{it['name']}’에 ‘{cat}’ 범주가 없습니다.")
            continue
        focus.append({"target": f["target"], "class_id": cid or None, "direction": d, "category": cat or None})
    if not focus and not errors:
        errors.append("수정 대상 항목을 찾지 못했습니다.")
    mm = obj.get("max_moved", 6)
    if not isinstance(mm, int) or isinstance(mm, bool) or not (1 <= mm <= 40):
        errors.append("이동 학생 수 제한(max_moved)은 1~40 사이 정수여야 합니다.")
    if obj.get("keep_locked") is False:
        notes.append("AI가 고정 해제를 제안했지만 허용되지 않으므로, 고정 배정과 필수 조건은 그대로 유지합니다.")
    if errors:
        return {"ok": False, "errors": errors, "message": "AI 응답에 허용되지 않는 내용이 있어 수정안을 계산하지 않았습니다.", "unclear": _str_list(data.get("unclear"))}
    objective = {"focus": focus, "max_moved": mm, "minimize_moves": bool(obj.get("minimize_moves", True)), "keep_locked": True}
    names = {c["id"]: c["name"] for c in ctx.classes}
    readable = []
    for f in focus:
        dn = {"decrease": "줄이기", "increase": "늘리기", "balance": "고르게 하기"}[f["direction"]]
        readable.append(f"{item_ids[f['target']]['name']}" + (f" — {names[f['class_id']]}" if f["class_id"] else "") + f" {dn}")
    sf = suggest_fix(project, args.get("assignment") or {}, args.get("locks") or {}, objective)
    return {"ok": True, "objective": objective, "objective_text": readable, "explanation": str(data.get("explanation") or ""),
            "unclear": _str_list(data.get("unclear")), "notes": notes, "fix": sf}


def _validate_memo(project, data, aux):
    idmap = aux.get("idmap", {})
    feats = {f["id"]: f for f in project.get("features", []) if f.get("active") and f["type"] in ("single", "multi", "yesno")}
    by_key = {s["key"]: s for s in project["students"]}
    errors, sugg = [], []
    for s in data.get("suggestions") or []:
        if not isinstance(s, dict):
            errors.append("제안 형식 오류")
            continue
        k = idmap.get(s.get("temp_id"))
        f = feats.get(s.get("feature_id"))
        vals = s.get("values")
        if not k or not f or not isinstance(vals, list) or not vals:
            errors.append(f"메모 {s.get('temp_id')}: 없는 메모·항목이거나 값이 없습니다.")
            continue
        opts = f.get("options", []) if f["type"] != "yesno" else ["예", "아니요"]
        if any(v not in opts for v in vals):
            errors.append(f"메모 {s.get('temp_id')}: ‘{f['name']}’ 선택지에 없는 값입니다.")
            continue
        if f["type"] in ("single", "yesno") and len(vals) != 1:
            errors.append(f"메모 {s.get('temp_id')}: ‘{f['name']}’은(는) 하나만 고를 수 있습니다.")
            continue
        st = by_key[k]
        cur = st.get("traits", {}).get(f["id"])
        if f["type"] == "yesno":
            newv = vals[0] == "예"
        elif f["type"] == "single":
            newv = vals[0]
        else:
            base = list(cur) if isinstance(cur, list) else []
            newv = [o for o in f["options"] if o in base or o in vals]
        sugg.append({"key": k, "name": st.get("name"), "sid": st.get("sid"), "feature_id": f["id"], "feature": f["name"],
                     "current": cur, "proposed": newv, "basis": str(s.get("basis") or "")[:80]})
    if errors:
        return {"ok": False, "errors": errors, "message": "AI 응답에 허용되지 않는 내용이 있어 태그 후보를 사용하지 않았습니다."}
    return {"ok": True, "suggestions": sugg}


# ----------------------------------------------------------------------------
# 내장 간이 해석기 (외부 전송 없음) — 같은 검증 과정을 그대로 거친다
# ----------------------------------------------------------------------------

def _match_items(project, text, active_only=True):
    found = []
    for f in project.get("features", []):
        if f["type"] == "text":
            continue
        kws = list(SYN.get(f["id"], []))
        core = f["name"]
        for sfx in CORE_STRIP:
            core = core.replace(sfx, "")
        core = core.strip()
        kws += [f["name"]] + ([core] if len(core) >= 2 else [])
        hit = next((k for k in kws if k and k in text), None)
        if hit:
            found.append(("feature:" + f["id"], f, hit))
    for t in ("builtin:gender", "builtin:size", "builtin:origin"):
        hit = next((k for k in SYN[t] if k in text), None)
        if hit:
            found.append((t, None, hit))
    return found


def builtin_answer(task, project, payload, aux):
    if task == "settings":
        text = payload["request"]
        strong = any(w in text for w in ("매우", "꼭", "특히", "반드시", "무엇보다"))
        props, missing, unclear = [], [], []
        matched = _match_items(project, text)
        actives = []
        for tid, f, hit in matched:
            if f is not None and not f.get("active"):
                missing.append(f"‘{f['name']}’ 항목이 꺼져 있어 학생 자료가 없습니다. 특성 항목 관리에서 켜고 자료를 입력해야 반영할 수 있습니다.")
                continue
            pr = {"target": tid, "use_in_balance": True, "importance": "very_high" if strong else "high",
                  "reason": f"요청 문장의 ‘{hit}’ 표현을 이 항목과 연결했습니다 (키워드 기반 간이 해석이므로 확인이 필요합니다)."}
            if f is not None:
                m = f.get("method")
                if m == "none" or m not in ALLOWED_METHODS[f["type"]]:
                    m = ALLOWED_METHODS[f["type"]][0]
                if f["type"] == "level" and any(w in text for w in ("이끌", "리더", "골고루 배치")) and f["id"] == "f_leader":
                    m = "count"
                pr["method"] = m
                actives.append(f)
            props.append(pr)
        if "반드시" in text:
            unclear.append("‘반드시’라는 표현이 있지만 필수 조건으로 바꾸지 않았습니다. 꼭 지켜야 하는 조건은 ‘관계 및 편성 조건’에서 직접 지정하세요.")
        combos = []
        if any(w in text for w in ("모두 필요", "동시에", "함께 필요", "둘 다", "모두 해당")) and len(actives) >= 2:
            conds = []
            for f in actives[:2]:
                if f["type"] == "yesno":
                    conds.append({"feature_id": f["id"], "values": ["예"]})
                elif f["type"] == "level":
                    conds.append({"feature_id": f["id"], "values": [level_steps(f)[-1]]})
                elif f.get("options"):
                    conds.append({"feature_id": f["id"], "values": [f["options"][0]]})
            combos.append({"name": " + ".join(f["name"] for f in actives[:2]), "conds": conds, "importance": "high",
                           "reason": "두 특성에 모두 해당하는 학생의 분포를 함께 보도록 제안합니다."})
            unclear.append("조합의 기준 값(예: ‘지원 필요 정도 3’)은 자동으로 정했으므로 적용 전에 확인하세요.")
        if not props:
            unclear.append("요청에서 현재 프로젝트의 특성 항목을 찾지 못했습니다. 항목 이름을 포함해 다시 써 주세요.")
        return {"interpretation": "키워드 기반 간이 해석 결과입니다.", "proposals": props, "new_combos": combos, "unclear": unclear, "missing": missing}
    if task == "explain":
        facts = payload["facts"]
        return {"summary": "프로그램이 계산한 편성 결과를 항목별로 정리했습니다.",
                "points": [f for f in facts if not f.startswith("[가능성")],
                "possible_causes": [f for f in facts if f.startswith("[가능성")]}
    if task == "fix":
        text = payload["request"]
        cls = next((c for c in project["classes"] if c["name"] in text), None)
        if cls is None:
            m = re.search(r"(\d+)\s*반", text)
            if m:
                cls = next((c for c in project["classes"] if c["name"] == m.group(1) + "반"), None)
        matched = [(t, f) for t, f, _ in _match_items(project, text) if f is None or f.get("active")]
        direction = "balance"
        if any(w in text for w in ("줄여", "줄이", "낮춰", "덜", "부담")):
            direction = "decrease"
        elif any(w in text for w in ("늘려", "늘리", "더 많이")):
            direction = "increase"
        if cls is None and direction != "balance":
            direction = "balance"
        m = re.search(r"(\d+)\s*명", text)
        mm = int(m.group(1)) if m else 6
        mm = max(1, min(40, mm))
        focus = [{"target": t, "class_id": cls["id"] if cls and direction != "balance" else None, "direction": direction, "category": None}
                 for t, f in matched[:3]]
        unclear = []
        if not focus:
            unclear.append("수정할 항목을 찾지 못했습니다. 항목 이름(예: 활동성, 성별, 인원)을 넣어 다시 요청하세요.")
        return {"objective": {"focus": focus, "max_moved": mm, "minimize_moves": True, "keep_locked": True},
                "explanation": "키워드 기반 간이 해석으로 수정 조건을 만들었습니다.", "unclear": unclear}
    if task == "memo_tags":
        sugg = []
        for m in payload["memos"]:
            for f in payload["tag_features"]:
                if f["type"] == "yesno":
                    continue
                hits = [o for o in f["options"] if len(o) >= 2 and o in m["text"]]
                if hits:
                    sugg.append({"temp_id": m["temp_id"], "feature_id": f["feature_id"], "values": hits if f["type"] == "multi" else hits[:1],
                                 "basis": "메모에 ‘" + hits[0] + "’ 표현이 있음"})
        return {"suggestions": sugg}
    return {}
