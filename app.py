import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    openai_model: str
    app_env: str


def get_config() -> AppConfig:
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL") or "gpt-4.1-mini",
        app_env=os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development",
    )


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    cfg = get_config()

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
            if cfg.openai_api_key:
                answer = call_openai_responses_api(
                    api_key=cfg.openai_api_key,
                    model=cfg.openai_model,
                    messages=messages,
                    lang=lang,
                )
            else:
                answer = fallback_answer(user_text=user_text, lang=lang)
        except Exception as e:
            # Don't leak internals in production.
            if cfg.app_env.lower() == "development":
                return jsonify({"error": str(e)}), 500
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


def fallback_answer(*, user_text: str, lang: str) -> str:
    t = user_text.strip()
    if lang == "en":
        return (
            "Demo mode: I don't see `OPENAI_API_KEY` set on the server yet.\n"
            f"You said: {t}\n\n"
            "Set `OPENAI_API_KEY` then restart the server to enable real AI replies."
        )
    return (
        "Demo mode: сервер дээр `OPENAI_API_KEY` тохируулаагүй байна.\n"
        f"Таны бичсэн: {t}\n\n"
        "`OPENAI_API_KEY` тохируулаад серверээ restart хийвэл жинхэнэ AI хариулт идэвхжинэ."
    )


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT") or 5000), debug=True)

