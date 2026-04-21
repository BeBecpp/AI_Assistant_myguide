# AI_Assistant_myguide

This is an AI assistant (chatbot) for `myguide.ubcircus.com`.

## Minimal AI Assistant (Flask)

Minimalist хар/цагаан загвартай, **draggable popup** чат UI + Flask API.

### Why (Яагаад)
- **Бэлэн ашиглах demo**: `OPENAI_API_KEY` байхгүй үед ч ажиллана (fallback).
- **Production-д ойр**: нэг origin, JSON API, error handling, env тохиргоо.

### How (Хэрхэн ажиллуулах вэ)

#### 1) Virtual env + dependency суулгах (Windows PowerShell)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 2) (Optional) Жинхэнэ AI хариулт асаах
- `.env.example`-ийг `.env` болгож хуулна
- `OPENAI_API_KEY`-гээ тавина

#### 3) Ажиллуулах

```bash
python app.py
```

Дараа нь browser дээр `http://127.0.0.1:5000` нээнэ.

### UI Behavior
- Баруун доод буланд **AI** товч.
- Дарвал popup цонх нээгдэнэ.
- Header-ийг чирээд байрлалыг зөөнө.
- MN/EN хэл сонгоно.
