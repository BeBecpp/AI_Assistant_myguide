from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u0400-\u04FF]+")


def detect_lang(text: str, fallback: str = "mn") -> str:
    """
    Very lightweight MN/EN guess:
    - If Cyrillic exists -> mn
    - else -> en
    """
    t = text or ""
    return "mn" if _CYRILLIC_RE.search(t) else fallback if fallback in ("mn", "en") else "mn"


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = _WS_RE.sub(" ", t)
    return t


@dataclass(frozen=True)
class LiteAnswer:
    text: str
    confidence: float
    intent: str


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(a=a, b=b).ratio()


def _contains_any(t: str, needles: list[str]) -> bool:
    return any(n in t for n in needles)

def _tokens(t: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(t or "")}

def _contains_token_any(token_set: set[str], needles: list[str]) -> bool:
    return any(n in token_set for n in needles)


def answer_lite(*, user_text: str, ui_lang: str | None = None) -> LiteAnswer:
    """
    A tiny, CPU/RAM-friendly "NLP" assistant:
    - intent routing via keywords
    - fuzzy matching for small talk / help
    - safe fallback asks clarifying question
    """
    raw = user_text or ""
    t = _norm(raw)
    tok = _tokens(t)

    lang = (ui_lang or "").lower()
    if lang not in ("mn", "en"):
        lang = detect_lang(raw, fallback="mn")

    # 1) Greetings / smalltalk
    if (
        _contains_any(t, ["sain uu", "sainuu", "sn uu", "сайн уу", "сайнуу", "сайн байна уу"])
        or _contains_token_any(tok, ["hi", "hello", "hey"])
    ):
        if lang == "en":
            return LiteAnswer("Hi! Tell me what you want to do (CV, study plan, code, etc.).", 0.9, "greet")
        return LiteAnswer("Сайн байна уу! Та яг юу хиймээр байна (CV, суралцах төлөвлөгөө, код, гэх мэт)?", 0.9, "greet")

    # 2) Time/date
    if _contains_any(t, ["time", "date", "цаг", "он сар", "өнөөдөр", "өдөр"]):
        now = _dt.datetime.now()
        if lang == "en":
            return LiteAnswer(f"Now: {now:%Y-%m-%d %H:%M}", 0.85, "datetime")
        return LiteAnswer(f"Одоо: {now:%Y-%m-%d %H:%M}", 0.85, "datetime")

    # 3) CV help
    if _contains_any(t, ["cv", "resume", "curriculum", "анкет", "намтар", "өөрийн тухай"]):
        if lang == "en":
            return LiteAnswer(
                "I can help. What role are you applying for (Flutter / Backend / QA), and do you want 1-page or 2-page CV?",
                0.8,
                "cv",
            )
        return LiteAnswer(
            "Тусалъя. Та ямар role (Flutter / Backend / QA) руу өргөдөл өгөх вэ? CV 1 хуудас уу 2 хуудас уу?",
            0.8,
            "cv",
        )

    # 4) Learning plan / NLP/ML guidance
    if _contains_any(t, ["nlp", "machine learning", "ml", "deep learning", "ai", "model", "сургалт", "машин сургалт", "nlp гэж"]):
        if lang == "en":
            return LiteAnswer(
                "For a free, lightweight start: learn basics (text cleaning, tokenization), then TF-IDF + cosine, then simple classifiers. Tell me your goal: chatbot, CV parser, or text classification?",
                0.75,
                "ml_nlp",
            )
        return LiteAnswer(
            "Үнэгүй, хөнгөн эхлэл: text cleaning → tokenization → TF‑IDF + cosine similarity → simple classifier. Таны зорилго яг юу вэ: chatbot уу, CV parser уу, эсвэл text classification уу?",
            0.75,
            "ml_nlp",
        )

    # 5) "Do something quick" (task-like)
    if _contains_any(t, ["хийгээд өг", "хийж өг", "help me", "can you", "please", "болгоод өг"]):
        if lang == "en":
            return LiteAnswer("Sure. Paste the exact text / requirements and I’ll do it step-by-step.", 0.65, "assist")
        return LiteAnswer("За. Яг хийх ёстой текст/шаардлагаа энд paste хийгээрэй — алхам алхмаар хийж өгье.", 0.65, "assist")

    # 6) Fuzzy help (cheap)
    examples = [
        ("what can you do", "capabilities"),
        ("чи юу хийж чадна", "capabilities"),
        ("help", "capabilities"),
        ("туслаач", "capabilities"),
    ]
    best = 0.0
    best_intent = ""
    for ex, intent in examples:
        best = max(best, _similarity(t, ex))
        if best == _similarity(t, ex):
            best_intent = intent
    if best >= 0.78 and best_intent == "capabilities":
        if lang == "en":
            return LiteAnswer(
                "I can help with: CV, study plans (NLP/ML basics), coding tasks, and Q/A. Tell me your goal in one sentence.",
                best,
                "capabilities",
            )
        return LiteAnswer(
            "Би: CV бэлдэх, NLP/ML сурах төлөвлөгөө, жижиг кодын ажил, асуулт/хариулт дээр тусалж чадна. Зорилгоо 1 өгүүлбэрээр хэлээрэй.",
            best,
            "capabilities",
        )

    # Safe fallback
    if lang == "en":
        return LiteAnswer("I’m not fully sure. What exactly do you want: CV, learning plan, or a coding fix?", 0.35, "clarify")
    return LiteAnswer("Яг сайн ойлгосонгүй. Та CV юу, суралцах төлөвлөгөө юу, эсвэл код засуулах уу?", 0.35, "clarify")

