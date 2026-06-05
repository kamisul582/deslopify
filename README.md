# Deslopify

Paste AI-generated text. Find out what the author actually wanted.

Most AI detection tools stop at "85% AI-generated." Deslopify goes further: it reconstructs the **author's agenda** — what goal they had when they prompted the AI.

## Project structure

```
backend/   FastAPI + Claude Haiku
frontend/  React + Vite
```

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Environment variables

### Backend (`backend/.env`)
| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `UPSTASH_REDIS_REST_URL` | No | Upstash Redis URL for IP rate limiting |
| `UPSTASH_REDIS_REST_TOKEN` | No | Upstash Redis token |
| `RATE_LIMIT_PER_DAY` | No | Analyses per IP per day (default: 5) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (default: localhost:5173) |

### Frontend (`frontend/.env`)
| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | No | Backend URL (default: http://localhost:8000) |

## Deployment

- **Backend**: Railway (`railway up` from `backend/`)
- **Frontend**: Vercel (connect repo, set root to `frontend/`)

## Monetization

- Google AdSense — replace the `.ad-placeholder` div in `App.jsx` with the AdSense script
- Ko-fi — update the Ko-fi link in the footer with your actual Ko-fi URL
- Rate limiting via Upstash Redis prevents cost overruns (5 analyses/IP/day by default)
