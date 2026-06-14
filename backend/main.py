import os
import json
import time
from contextlib import asynccontextmanager

import anthropic
import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

load_dotenv()

RATE_LIMIT_PER_DAY = int(os.getenv("RATE_LIMIT_PER_DAY", "5"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if upstash_url and upstash_token and upstash_url.startswith(("redis://", "rediss://")):
        redis_client = aioredis.from_url(
            upstash_url,
            password=upstash_token,
            decode_responses=True,
        )
    yield
    if redis_client:
        await redis_client.aclose()


app = FastAPI(title="Deslopify API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Prompts ──────────────────────────────────────────────────────────────────

DETECTION_SYSTEM = """You are an expert at identifying AI-generated text, specifically text produced by LLMs and posted on social media or blogs.

Analyze the text for structural hallmarks of LLM output — NOT surface features like specific details or emotional language, which LLMs routinely mimic.

Real AI-generation signals (structural, not surface):
- Perfect narrative arc: every scene, detail, and line of dialogue serves the ending. Nothing is irrelevant or random.
- Evenly distributed quotable one-liners / aphorisms — spaced too regularly, like someone seeded them every 200 words
- Karmically symmetrical endings where earlier props return as punchlines (e.g. the same card, the same word, the same place used to "close the loop")
- Binary contrasts that are too clean (victim/villain, luxury/poverty, ignorant masses/enlightened narrator)
- Technical vocabulary deployed at uniform density rather than in natural bursts
- Zero digressions, typos, tangents, or irrelevant memories — human writing is messier
- Hashtag walls or SEO-optimized closings
- "Us vs. them" framing with a narrator who is always right and the crowd who is always wrong
- Emotional beats that follow a scripted arc (wounded → transformation moment → cold revenge), each telegraphed clearly

Return a JSON object with:
- "is_ai": boolean — true if structural AI signals are present
- "ai_probability": float 0.0–1.0 — probability the text was AI-generated (not your confidence in the answer — the actual probability it is AI)
- "signals": list of up to 4 short strings naming the specific structural signals you found

Return ONLY valid JSON, no prose."""

ANALYSIS_SYSTEM = """You are an expert media analyst who reverse-engineers the strategic intent behind AI-generated content.

Given a text, identify what the human author actually wanted to achieve when they prompted an AI to write it.
Focus on the AGENDA (the why), not the surface content (the what).

Return a JSON object with exactly these fields:
- "primary_goal": string — the author's main objective in 1–2 sentences
- "content_type": string — e.g. "Myth-busting social post", "Emotional narrative", "Investigative commentary"
- "target_platform": string — most likely platform/context
- "target_audience": string — who this is aimed at
- "persuasion_tactics": list of strings — techniques used (max 5)
- "probable_cta": string — what the author wants the reader to do or feel next
- "summary": string — one plain-language paragraph a non-expert can understand

Return ONLY valid JSON, no prose."""

# ── Models ────────────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 50:
            raise ValueError("Text is too short (minimum 50 characters)")
        if len(v) > 20_000:
            raise ValueError("Text is too long (maximum 20,000 characters)")
        return v


# ── Rate limiting ─────────────────────────────────────────────────────────────


async def check_rate_limit(ip: str) -> tuple[bool, int]:
    """Returns (allowed, remaining)."""
    if not redis_client:
        return True, RATE_LIMIT_PER_DAY

    key = f"rl:{ip}:{time.strftime('%Y-%m-%d')}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 86400)

    remaining = max(0, RATE_LIMIT_PER_DAY - count)
    return count <= RATE_LIMIT_PER_DAY, remaining


# ── LLM helpers ───────────────────────────────────────────────────────────────


def _call_haiku(system: str, user_text: str) -> dict:
    response = ai_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


def detect_ai(text: str) -> dict:
    return _call_haiku(DETECTION_SYSTEM, text)


def analyze_agenda(text: str) -> dict:
    return _call_haiku(ANALYSIS_SYSTEM, text)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(request: Request, body: AnalyzeRequest):
    ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    allowed, remaining = await check_rate_limit(ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"You've used your {RATE_LIMIT_PER_DAY} free analyses for today. Come back tomorrow.",
                "remaining": 0,
            },
        )

    detection = detect_ai(body.text)
    ai_probability = detection.get("ai_probability", 0.0)
    # Use probability as the source of truth; is_ai flag is a secondary signal
    is_ai = ai_probability >= 0.5 or detection.get("is_ai", False)

    if not is_ai:
        return {
            "is_ai": False,
            "confidence": ai_probability,
            "signals": detection.get("signals", []),
            "message": "This text doesn't show strong AI-generation signals. No agenda analysis performed.",
            "remaining_today": remaining,
        }

    agenda = analyze_agenda(body.text)

    return {
        "is_ai": True,
        "confidence": ai_probability,
        "signals": detection.get("signals", []),
        "agenda": agenda,
        "remaining_today": remaining,
    }
