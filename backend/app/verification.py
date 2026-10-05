"""Deterministic checks of model output against the source text.

The model may only make claims about the author's agenda if it can quote the
pasted text. This module verifies the quotes with plain string matching, so a
hallucinated or injected claim cannot survive.
"""

import re
import unicodedata

from .schemas import AgendaOut, Claim, VerifiedAgenda

MIN_QUOTE_CHARS = 12
_PUNCT_MAP = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "..."})


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_PUNCT_MAP).casefold()
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str) -> bool:
    q = normalize(quote).strip(" .…\"'")
    if len(q) < MIN_QUOTE_CHARS:
        return False
    return q in normalize(text)


def verify_agenda(agenda: AgendaOut, text: str) -> tuple[VerifiedAgenda | None, str, int]:
    """Returns (verified_agenda | None, status, dropped_claims).

    status: "verified" (nothing dropped), "partial" (some supporting claims
    dropped), "rejected" (the core claim is unsupported, so nothing is shown).
    """
    if not quote_in_text(agenda.primary_goal.quote, text):
        total = 1 + len(agenda.persuasion_tactics) + (1 if agenda.probable_cta else 0)
        return None, "rejected", total

    dropped = 0
    tactics: list[Claim] = []
    for t in agenda.persuasion_tactics:
        if quote_in_text(t.quote, text):
            tactics.append(t)
        else:
            dropped += 1

    cta = agenda.probable_cta
    if cta and not quote_in_text(cta.quote, text):
        cta = None
        dropped += 1

    verified = VerifiedAgenda(
        tldr=agenda.tldr,
        likely_prompt=agenda.likely_prompt,
        primary_goal=agenda.primary_goal,
        persuasion_tactics=tactics,
        probable_cta=cta,
        context=agenda.context,
    )
    return verified, ("partial" if dropped else "verified"), dropped
