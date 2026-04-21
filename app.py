import os
import time
from dataclasses import dataclass

import requests
from requests import HTTPError
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from lite_nlp import answer_lite, detect_lang


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    gemini_api_keys: list[str]
    gemini_model: str
    openai_api_key: str | None
    openai_model: str
    app_env: str


def get_config() -> AppConfig:
    keys_raw = os.getenv("GEMINI_API_KEYS") or ""
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
    # Backward compatible: single key
    if not keys:
        one = os.getenv("GEMINI_API_KEY") or ""
        if one.strip():
            keys = [one.strip()]
    return AppConfig(
        gemini_api_keys=keys,
        gemini_model=os.getenv("GEMINI_MODEL") or "gemini-2.5-flash",
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL") or "gpt-4.1-mini",
        app_env=os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development",
    )


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    cfg = get_config()
    limiter = SimpleRateLimiter()
    gemini_pool = GeminiKeyPool(cfg.gemini_api_keys)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True) or {}
        messages = data.get("messages") or []
        lang = (data.get("lang") or "mn").lower()

        if not isinstance(messages, list) or len(messages) == 0:
            return jsonify({"error": "Invalid payload: messages[] required"}), 422

        # Basic rate-limit-ish guard (best-effort, stateless demo)
        if len(messages) > 50:
            return jsonify({"error": "Too many messages"}), 413

        user_text = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_text = str(m.get("content") or "")
                break

        if not user_text.strip():
            return jsonify({"error": "Last user message is empty"}), 422

        try:
            # Simple server-side throttle (prevents many devices spamming one key)
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
            if not limiter.allow(ip):
                answer = friendly_rate_limit_message(lang=lang)
                return jsonify({"reply": answer, "ts": int(time.time())}), 200

            if cfg.gemini_api_keys:
                try:
                    answer = call_gemini_with_pool(
                        pool=gemini_pool,
                        model=cfg.gemini_model,
                        messages=messages,
                        lang=lang,
                    )
                except UpstreamRateLimitedError:
                    # Graceful degrade (no raw 429 shown to user)
                    ui_lang = lang if lang in ("mn", "en") else detect_lang(user_text, fallback="mn")
                    answer = (
                        friendly_rate_limit_message(lang=ui_lang)
                        + "\n\n"
                        + answer_lite(user_text=user_text, ui_lang=ui_lang).text
                    )
            elif cfg.openai_api_key:
                answer = call_openai_responses_api(
                    api_key=cfg.openai_api_key,
                    model=cfg.openai_model,
                    messages=messages,
                    lang=lang,
                )
            else:
                # Free mode: lightweight MN/EN "NLP" (no paid APIs)
                ui_lang = lang if lang in ("mn", "en") else None
                if ui_lang is None:
                    ui_lang = detect_lang(user_text, fallback="mn")
                answer = answer_lite(user_text=user_text, ui_lang=ui_lang).text
        except Exception as e:
            # Don't leak internals in production.
            if cfg.app_env.lower() == "development":
                return jsonify({"error": safe_error_message(e)}), 500
            return jsonify({"error": "Server error"}), 500

        return jsonify({"reply": answer, "ts": int(time.time())})

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    return app


def call_openai_responses_api(*, api_key: str, model: str, messages: list, lang: str) -> str:
    """
    Uses OpenAI Responses API over HTTPS via requests (no extra SDK dependency).
    Requires OPENAI_API_KEY in environment.
    """
    system = (
        "You are a helpful AI assistant. "
        "Be concise, production-focused, and friendly. "
        "If the user speaks Mongolian, reply in Mongolian; if English, reply in English. "
        "If lang is provided as 'mn' or 'en', prioritize that."
    )
    if lang == "mn":
        system += " Reply primarily in Mongolian."
    elif lang == "en":
        system += " Reply primarily in English."

    # Normalize to the schema OpenAI expects for chat messages
    normalized = [{"role": "system", "content": system}]
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            normalized.append({"role": role, "content": content})

    payload = {
        "model": model,
        "input": normalized,
    }

    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    # Extract output text (Responses API can return multiple items)
    out = data.get("output") or []
    texts: list[str] = []
    for item in out:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "output_text":
                t = c.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t.strip())
    return "\n\n".join(texts).strip() or "..."


def call_gemini_generate_content(*, api_key: str, model: str, messages: list, lang: str) -> str:
    """
    Gemini API via HTTPS (no SDK). Uses Generative Language API `generateContent`.
    Set `GEMINI_API_KEY` in environment.
    """
    system = (
        "You are a helpful AI assistant. "
        "Be concise, production-focused, and friendly. "
        "If the user speaks Mongolian, reply in Mongolian; if English, reply in English. "
        "If lang is provided as 'mn' or 'en', prioritize that."
    )
    if lang == "mn":
        system += " Reply primarily in Mongolian."
    elif lang == "en":
        system += " Reply primarily in English."

    # Gemini uses `contents[]` with `role` + `parts[]`.
    contents: list[dict] = [{"role": "user", "parts": [{"text": system}]}]
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})

    # Prefer stable v1 and API key via header (avoids key in URL logs).
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 800,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    # Retry on transient upstream throttling.
    data = post_with_backoff(url=url, headers=headers, json=payload, timeout=30)

    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates, list):
        return "..."
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            texts.append(p["text"])
    return "\n".join(texts).strip() or "..."


class UpstreamRateLimitedError(RuntimeError):
    pass


def safe_error_message(e: Exception) -> str:
    """
    Avoid leaking secrets (API keys) in error messages.
    """
    s = str(e) or e.__class__.__name__
    # Redact common API key patterns
    if os.getenv("GEMINI_API_KEY"):
        s = s.replace(os.getenv("GEMINI_API_KEY") or "", "[REDACTED]")
    if os.getenv("GEMINI_API_KEYS"):
        for k in [x.strip() for x in (os.getenv("GEMINI_API_KEYS") or "").split(",") if x.strip()]:
            s = s.replace(k, "[REDACTED]")
    s = s.replace(os.getenv("OPENAI_API_KEY") or "", "[REDACTED]") if os.getenv("OPENAI_API_KEY") else s
    # Remove query params to avoid `?key=...` appearing
    s = s.split("?key=")[0] if "?key=" in s else s
    return s


def friendly_rate_limit_message(*, lang: str) -> str:
    l = (lang or "mn").lower()
    if l == "en":
        return "Nero is temporarily busy (rate limit). Please wait 10–20 seconds and try again."
    return "Nero түр завгүй байна (rate limit). 10–20 секунд хүлээгээд дахин оролдоорой."


class SimpleRateLimiter:
    """
    Very small in-memory limiter: allow ~1 request/sec burst 3 per IP.
    Not perfect, but prevents accidental flooding on a home network.
    """

    def __init__(self):
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        # token bucket: rate=1 token/sec, capacity=3
        rate = 1.0
        cap = 3.0
        tokens, last = self._buckets.get(key, (cap, now))
        tokens = min(cap, tokens + (now - last) * rate)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        tokens -= 1.0
        self._buckets[key] = (tokens, now)
        return True


class GeminiKeyPool:
    """
    Rotate between multiple API keys. If one key gets 429, put it on cooldown
    and try the next one.
    """

    def __init__(self, keys: list[str]):
        self._keys = [k for k in keys if k]
        self._i = 0
        self._cooldown_until: dict[str, float] = {}

    def next_key(self) -> str | None:
        if not self._keys:
            return None
        now = time.time()
        for _ in range(len(self._keys)):
            k = self._keys[self._i % len(self._keys)]
            self._i += 1
            until = self._cooldown_until.get(k, 0.0)
            if until <= now:
                return k
        return None

    def cooldown(self, key: str, seconds: int = 20) -> None:
        self._cooldown_until[key] = time.time() + max(1, seconds)


def call_gemini_with_pool(*, pool: GeminiKeyPool, model: str, messages: list, lang: str) -> str:
    last_err: Exception | None = None
    attempts = max(1, len(pool._keys))
    for _ in range(attempts):
        key = pool.next_key()
        if not key:
            break
        try:
            return call_gemini_generate_content(api_key=key, model=model, messages=messages, lang=lang)
        except UpstreamRateLimitedError as e:
            pool.cooldown(key, seconds=20)
            last_err = e
            continue
    if last_err:
        raise last_err
    raise UpstreamRateLimitedError("Upstream rate limited (all keys)")


def post_with_backoff(*, url: str, headers: dict, json: dict, timeout: int) -> dict:
    delays = [0.5, 1.0, 2.0]
    last_err: Exception | None = None
    for attempt, d in enumerate([0.0, *delays]):
        if d:
            time.sleep(d)
        try:
            r = requests.post(url, headers=headers, json=json, timeout=timeout)
            if r.status_code == 429:
                # Respect Retry-After if present (seconds)
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    time.sleep(min(int(ra), 5))
                raise UpstreamRateLimitedError("Upstream rate limited (429)")
            r.raise_for_status()
            return r.json()
        except UpstreamRateLimitedError as e:
            last_err = e
            # retry next loop; if last attempt -> raise
        except HTTPError as e:
            last_err = e
            # retry only on a couple transient codes
            status = getattr(e.response, "status_code", None)
            if status in (500, 502, 503, 504) and attempt < len(delays):
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < len(delays):
                continue
            raise
    if last_err:
        raise last_err
    raise UpstreamRateLimitedError("Upstream rate limited")


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT") or 5000), debug=True)

