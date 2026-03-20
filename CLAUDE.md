# CLAUDE.md — AarogyaAI Codebase Guide

This file provides AI assistants (Claude Code and similar) with the essential context needed to understand, navigate, and contribute to this codebase effectively.

---

## Project Overview

**AarogyaAI** is a multilingual health-triage chatbot for the Indian healthcare market. It guides users through a structured consultation workflow: consent → demographics → symptom triage → doctor escalation → payment. It is built with regulatory compliance in mind (Telemedicine Practice Guidelines 2020, DPDP Act 2023).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| AI Engine | OpenAI GPT-4 (`chat_engine.py`) |
| Database | MongoDB Atlas via async Motor driver |
| Session Store | Redis (in-memory fallback) |
| Payment | Razorpay |
| Frontend | Single-page HTML5 (vanilla JS, no build step) |
| Containerization | Docker |
| Hosting | Render |
| Language Detection | langdetect |
| Data Validation | Pydantic |

---

## Repository Structure

```
arogya_ai/
├── main.py              # FastAPI app init, CORS, health check, static serving
├── routes.py            # All API route handlers (6 endpoints)
├── chat_engine.py       # OpenAI GPT-4 async wrapper + system prompt logic
├── db.py                # All MongoDB async CRUD operations
├── schemas.py           # Pydantic request/response models
├── utils.py             # Input validation, language detection, timestamps
├── razorpay_utils.py    # Payment link creation and webhook verification
├── session_store.py     # Hybrid Redis/in-memory session management
├── frontend/
│   └── index.html       # Complete self-contained web UI (consent, chat, payment)
├── tests/
│   └── test_app.py      # pytest test suite (currently minimal)
├── .env.example         # All required environment variables documented here
├── Dockerfile           # Python 3.11 slim image, exposes port 8000
├── requirements.txt     # Python dependencies
├── README.md            # User-facing project documentation
├── PROMPT.md            # Original system prompt / product specification
└── agents.md            # Agent components documentation
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serve `frontend/index.html` |
| GET | `/health` | Health check — returns `{"status": "ok"}` |
| POST | `/start` | Initialize session: capture consent + user demographics |
| POST | `/triage` | Process symptom input and begin triage |
| POST | `/consult` | Generate Razorpay payment link (₹99 audio / ₹249 video) |
| POST | `/chat` | Main stateful multi-turn chat endpoint |
| POST | `/summary` | Store consultation summary for doctor handoff |
| POST | `/payment-webhook` | Handle Razorpay webhook events; verifies HMAC signature |

---

## Data Models (`schemas.py`)

- **Consent** — `phone`, `consent_given` (bool)
- **UserInfo** — `name`, `age`, `gender`, `location`, `language`
- **SymptomData** — `session_id`, `symptoms` (str)
- **ConsultRequest** — `session_id`, `consult_type` (`audio` | `video`)
- **Summary** — `session_id`, `summary_text`
- **WebChatPayload** — `session_id`, `message`, `language` (optional)

---

## MongoDB Collections

| Collection | Key Fields |
|---|---|
| `users` | `phone` (unique), `name`, `age`, `gender`, `location`, `language`, `consent_time`, `payments[]`, `chats[]` |
| `chats` | `session_id`, `input`, `output`, `time`, `event` |
| `summaries` | `session_id`, `summary_text`, `time` |

All DB operations are in `db.py` using Motor (async). Never use the synchronous PyMongo driver.

---

## Session Management (`session_store.py`)

- Primary store: **Redis** (key: `session:<session_id>`, value: serialized chat history)
- Fallback: **in-memory dict** (used automatically if Redis is unavailable)
- Sessions hold the full `messages` list passed to GPT-4 for context
- Session TTL and cleanup are not currently implemented — be cautious adding state here

---

## Chat Engine (`chat_engine.py`)

- Uses `AsyncOpenAI` client (non-streaming, `await` pattern)
- 12-second timeout on completions
- System prompt is defined inline; it encodes the full triage workflow, escalation logic, and payment placeholder instructions
- Payment link placeholder: when GPT-4 output contains `<PAYMENT_LINK>`, `routes.py` replaces it with an actual Razorpay URL
- Returning user context (name, age, gender, PIN) is injected into the system prompt on each `/chat` call

---

## Payment Flow (`razorpay_utils.py`)

1. `/consult` calls `create_payment_link()` → returns a Razorpay short URL
2. URL is stored in the `users` collection under `payments`
3. GPT-4 includes `<PAYMENT_LINK>` in its response; `routes.py` substitutes the real URL
4. Razorpay sends webhook to `/payment-webhook`
5. Webhook handler verifies HMAC-SHA256 signature before processing
6. On `payment.captured` event, payment status in MongoDB is updated to `paid`

---

## Language Support (`utils.py`)

Supported languages (auto-detected via `langdetect`):
- English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi

`DetectorFactory.seed = 0` is set globally for deterministic detection. Language is stored per user in MongoDB and used to adapt GPT-4 system prompt language.

---

## Input Validation Rules

- **Age:** integer, range 1–120
- **PIN:** exactly 6 digits
- **Phone:** validated at consent step (format enforced by Pydantic)
- **Language:** must be in supported language list

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before running.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | GPT-4 API authentication |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `MONGODB_ALLOW_INVALID_CERTS` | Set `true` for dev if TLS cert issues occur |
| `RAZORPAY_KEY_ID` | Razorpay public key |
| `RAZORPAY_KEY_SECRET` | Razorpay secret key |
| `RAZORPAY_WEBHOOK_SECRET` | Used for HMAC webhook verification |
| `BOT_NAME` | Display name in UI (default: `AarogyaAI`) |
| `LOG_LEVEL` | Python logging level (default: `INFO`) |
| `PORT` | Server port (default: `8000`) |
| `REDIS_URL` | Redis connection URL (optional; falls back to in-memory) |

---

## Development Workflow

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the server
uvicorn main:app --reload --port 8000
```

The app will be available at `http://localhost:8000`. The frontend is served at `/`.

### Running with Docker

```bash
docker build -t arogya_ai .
docker run -p 8000:8000 --env-file .env arogya_ai
```

### Running Tests

```bash
pytest tests/
```

Currently only `tests/test_app.py` exists with a basic smoke test (hits `/docs`). When adding features, add corresponding tests here.

---

## Coding Conventions

1. **Async everywhere** — All I/O (DB, OpenAI, Redis) must use `async/await`. Never use synchronous equivalents.
2. **Pydantic for validation** — All request bodies must have a corresponding Pydantic model in `schemas.py`.
3. **DB operations in `db.py`** — Do not inline MongoDB queries in routes. Add a function to `db.py` and call it from `routes.py`.
4. **No direct `print()`** — Use Python's `logging` module. The log level is controlled via the `LOG_LEVEL` env var.
5. **Secrets via env** — Never hardcode API keys, secrets, or connection strings. Always use `os.getenv()` or `python-dotenv`.
6. **Error handling** — Return FastAPI `HTTPException` with appropriate status codes. Do not let unhandled exceptions reach the client.
7. **No AI prescribing** — GPT-4 must not recommend medications. The system prompt enforces this. Do not modify the prompt in ways that could bypass this constraint.

---

## Compliance Requirements

This is a **health application** — the following constraints are non-negotiable:

- **Telemedicine Practice Guidelines 2020 (India):** Only Registered Medical Practitioners (RMPs) may give medical advice. The AI performs triage only.
- **DPDP Act 2023:** Explicit consent must be captured before collecting any personal data. The `/start` endpoint enforces this.
- **No prescriptions from AI:** The GPT-4 system prompt strictly prohibits medication recommendations.
- **Webhook security:** All Razorpay webhooks must verify HMAC-SHA256 signatures before processing.

---

## Key Files to Read Before Making Changes

| If you're changing... | Read these first |
|---|---|
| Chat behavior / AI response | `chat_engine.py`, `PROMPT.md` |
| API endpoints | `routes.py`, `schemas.py` |
| Database schema or queries | `db.py`, `schemas.py` |
| Payment flow | `razorpay_utils.py`, `routes.py` (`/consult`, `/payment-webhook`) |
| Session or conversation state | `session_store.py`, `chat_engine.py` |
| Frontend UI | `frontend/index.html` |
| Validation logic | `utils.py`, `schemas.py` |

---

## Known Limitations / Areas for Improvement

- Test coverage is minimal — only a basic smoke test exists
- No GitHub Actions CI/CD pipeline configured
- Session TTL/cleanup not implemented in `session_store.py`
- Frontend is a single HTML file — no component system or build tooling
- No structured logging format (currently plain text)
- `MONGODB_ALLOW_INVALID_CERTS` should never be `true` in production
