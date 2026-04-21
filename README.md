# AI_Assistant_myguide

This is an AI assistant (chatbot) for `myguide.ubcircus.com`.

## Minimal AI Assistant (Flask)

Minimalist хар/цагаан загвартай, **draggable popup** чат UI + Flask API.

### Why (Яагаад)
- **Бэлэн ашиглах demo**: API key байхгүй үед ч ажиллана (Lite NLP fallback).
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
- **`GEMINI_API_KEY`** (зөвлөмж) эсвэл `OPENAI_API_KEY`-гээ тавина

#### 3) Ажиллуулах

```bash
python app.py
```

Дараа нь browser дээр `http://127.0.0.1:5000` нээнэ.

## Network дээр (LAN) ажиллуулах

Windows дээр production-д ойр, network дээр гаргах хамгийн амар арга нь **Waitress** ашиглах.

```bash
pip install -r requirements.txt
$env:HOST="0.0.0.0"
$env:PORT="5000"
python serve.py
```

Одоо бусад төхөөрөмжөөс `http://<Таны-IP>:5000` гэж орно.

> Firewall: Windows Defender Firewall дээр 5000 портыг inbound зөвшөөрөх хэрэгтэй.

### UI Behavior
- Баруун доод буланд **AI** товч.
- Дарвал popup цонх нээгдэнэ.
- Header-ийг чирээд байрлалыг зөөнө.
- MN/EN хэл сонгоно.
