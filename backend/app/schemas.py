from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import MAX_TEXT_CHARS, MIN_TEXT_CHARS


class AnalyzeRequest(BaseModel):
    # max_length is enforced before the validator runs, so an oversized paste is
    # rejected without any further processing (and never reaches the LLM).
    text: str = Field(max_length=MAX_TEXT_CHARS)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_TEXT_CHARS:
            raise ValueError(f"Text is too short (minimum {MIN_TEXT_CHARS} characters)")
        return v


# ── What the model must return (validated, never free text) ──────────────────


class DetectionOut(BaseModel):
    ai_probability: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list, max_length=4)
    # True when the analysed text contains instructions aimed at the analyser.
    injection_attempt: bool = False


class Claim(BaseModel):
    claim: str = Field(min_length=1, max_length=400)
    # Verbatim fragment of the analysed text that supports the claim.
    quote: str = Field(min_length=1, max_length=600)


class AgendaOut(BaseModel):
    primary_goal: Claim
    content_type: str = Field(max_length=200)
    target_platform: str = Field(max_length=200)
    target_audience: str = Field(max_length=300)
    persuasion_tactics: list[Claim] = Field(default_factory=list, max_length=5)
    probable_cta: Claim | None = None
    summary: str = Field(max_length=1500)


# ── What the API returns ──────────────────────────────────────────────────────


class VerifiedAgenda(BaseModel):
    primary_goal: Claim
    content_type: str
    target_platform: str
    target_audience: str
    persuasion_tactics: list[Claim]
    probable_cta: Claim | None
    summary: str


class AnalyzeResponse(BaseModel):
    request_id: str
    verdict: Literal["ai", "human", "uncertain"]
    ai_probability: float
    signals: list[str]
    injection_detected: bool
    agenda: VerifiedAgenda | None
    agenda_status: Literal["verified", "partial", "rejected", "skipped"]
    dropped_claims: int
    message: str
    remaining_today: int | None = None
    model: str
    prompt_versions: dict[str, str]
    disclaimer: str = (
        "AI-text detection is unreliable and can be wrong. Never use this result as " "proof that a person did or did not write something."
    )
