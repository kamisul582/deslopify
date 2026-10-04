"""Versioned prompts. Files live in app/prompts/<name>.<version>.md and the
version string is attached to every result, so any output can be traced to the
exact prompt that produced it."""

import os
from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
DEFAULT_VERSIONS = {"detect": "v1", "agenda": "v1"}


def active_versions() -> dict[str, str]:
    return {name: os.getenv(f"PROMPT_{name.upper()}_VERSION", default) for name, default in DEFAULT_VERSIONS.items()}


@cache
def load_prompt(name: str, version: str) -> str:
    path = PROMPT_DIR / f"{name}.{version}.md"
    return path.read_text(encoding="utf-8").strip()


def wrap_untrusted(text: str) -> str:
    """Fence user text as data. A literal closing tag in the text is neutralised so
    the text cannot break out of the fence."""
    safe = text.replace("</untrusted_text", "< /untrusted_text")
    return f"<untrusted_text>\n{safe}\n</untrusted_text>"
