"""The analysis pipeline, independent of HTTP: detect -> decide -> (agenda -> verify).

Used by the API, the eval suite and the investigation agent so all three
exercise exactly the same logic."""

from dataclasses import dataclass

from .config import Settings
from .llm import LLMClient, Usage
from .prompts import active_versions, load_prompt, wrap_untrusted
from .schemas import AgendaOut, DetectionOut, VerifiedAgenda
from .verification import verify_agenda


@dataclass
class PipelineResult:
    verdict: str
    ai_probability: float
    signals: list[str]
    injection_detected: bool
    agenda: VerifiedAgenda | None
    agenda_status: str
    dropped_claims: int
    message: str
    model: str
    prompt_versions: dict[str, str]
    usage: Usage


def decide(p: float, settings: Settings) -> str:
    """Verdict is decided by code from the model's probability, not by the model."""
    if p >= settings.ai_min:
        return "ai"
    if p <= settings.human_max:
        return "human"
    return "uncertain"


async def run_pipeline(text: str, llm: LLMClient, settings: Settings, model: str | None = None) -> PipelineResult:
    model = model or settings.model
    versions = active_versions()
    usage = Usage()
    user = wrap_untrusted(text)

    det, u = await llm.complete(load_prompt("detect", versions["detect"]), user, DetectionOut, model)
    usage.add(u)
    verdict = decide(det.ai_probability, settings)

    agenda, status, dropped = None, "skipped", 0
    if verdict == "ai":
        raw, u = await llm.complete(load_prompt("agenda", versions["agenda"]), user, AgendaOut, model)
        usage.add(u)
        agenda, status, dropped = verify_agenda(raw, text)

    if verdict == "ai":
        if status == "rejected":
            message = (
                "Signs of AI generation were found, but the model's agenda claims could not be "
                "verified against your text, so they are not shown."
            )
        else:
            message = "Structural signs of AI generation were found. Detection is unreliable; treat this as a hint, not proof."
    elif verdict == "human":
        message = "No strong signs of AI generation. This does not prove a human wrote it."
    else:
        message = "Can't tell. The evidence is mixed or too thin for a verdict, and we prefer saying so over guessing."

    return PipelineResult(
        verdict=verdict,
        ai_probability=det.ai_probability,
        signals=det.signals,
        injection_detected=det.injection_attempt,
        agenda=agenda,
        agenda_status=status,
        dropped_claims=dropped,
        message=message,
        model=model,
        prompt_versions=versions,
        usage=usage,
    )
