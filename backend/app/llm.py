import json
import logging
import re
from dataclasses import dataclass
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from .config import Settings, estimate_cost_usd

log = logging.getLogger("deslopify.llm")
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class. `code` and `status` map directly onto the HTTP error."""

    code = "upstream_error"
    status = 502
    user_message = "The analysis service had a problem. Please try again in a moment."


class LLMTimeout(LLMError):
    code = "upstream_timeout"
    status = 504
    user_message = "The analysis took too long. Please try again, or try a shorter text."


class LLMBusy(LLMError):
    code = "upstream_busy"
    status = 503
    user_message = "The analysis service is busy right now. Please try again in a minute."


class LLMBadOutput(LLMError):
    code = "model_output_invalid"
    status = 502
    user_message = "The model returned an unusable answer. Please try again."


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage"):
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd += other.cost_usd


def extract_json(raw: str) -> dict:
    raw = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(raw[start : end + 1])


class LLMClient:
    """Thin wrapper over the Anthropic async client.

    - timeouts and retries (429/5xx/connection errors) are handled by the SDK
    - the model's JSON is validated against a Pydantic schema; up to two repair turns that
      show the model its own invalid output and the error
    - SDK errors are translated into LLMError subclasses with safe messages
    """

    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None):
        self.settings = settings
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )

    async def complete(self, system: str, user: str, schema: type[T], model: str | None = None) -> tuple[T, Usage]:
        model = model or self.settings.model
        usage = Usage()
        last_err: Exception | None = None
        messages = [{"role": "user", "content": user}]
        for attempt in range(3):
            try:
                resp = await self.client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system,
                    messages=messages,
                )
            except anthropic.APITimeoutError as e:
                raise LLMTimeout() from e
            except anthropic.RateLimitError as e:
                raise LLMBusy() from e
            except anthropic.APIStatusError as e:
                log.error("anthropic_status_error", extra={"status": e.status_code})
                raise (LLMBusy() if e.status_code in (429, 529) else LLMError()) from e
            except anthropic.APIConnectionError as e:
                raise LLMError() from e

            u = Usage(
                resp.usage.input_tokens,
                resp.usage.output_tokens,
            )
            u.cost_usd = estimate_cost_usd(model, u.input_tokens, u.output_tokens)
            usage.add(u)
            try:
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                return schema.model_validate(extract_json(text)), usage
            except (ValueError, ValidationError) as e:
                last_err = e
                log.warning("model_output_invalid", extra={"attempt": attempt})
                # Repair turn: show the model its own invalid output and what was wrong.
                # A plain re-send tends to reproduce the same mistake for the same text.
                problem = str(e).splitlines()[0][:200]
                messages = [
                    *messages[:1],
                    {"role": "assistant", "content": text or "(empty)"},
                    {
                        "role": "user",
                        "content": f"That was not valid ({problem}). Reply again with ONLY the corrected JSON object, "
                        "properly escaping any double quotes inside strings.",
                    },
                ]
        raise LLMBadOutput() from last_err
