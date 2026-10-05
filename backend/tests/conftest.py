import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LLMClient
from app.main import create_app
from app.store import MemoryStore, ResilientStore

TEXT = (
    "Most people think discipline builds habits. Here's what nobody tells you: "
    "identity does. You wake up at 5am because of who you are, not what you force."
)


def detection(p=0.9, signals=("uniform aphorisms",), injection=False):
    return json.dumps({"ai_probability": p, "signals": list(signals), "injection_attempt": injection})


def agenda(goal_quote="identity does", tactics=(("Identity framing", "because of who you are"),), cta=None):
    return json.dumps(
        {
            "tldr": "Wants readers to adopt an identity-first mindset.",
            "likely_prompt": "Write a motivational LinkedIn post arguing that identity, not discipline, builds habits.",
            "context": "Motivational LinkedIn post for professionals",
            "primary_goal": {"claim": "Sell an identity-first mindset", "quote": goal_quote},
            "persuasion_tactics": [{"claim": c, "quote": q} for c, q in tactics],
            "probable_cta": ({"claim": cta[0], "quote": cta[1]} if cta else None),
        }
    )


class FakeMessages:
    """Stands in for AsyncAnthropic().messages: returns queued responses/exceptions."""

    def __init__(self, queue):
        self.queue = list(queue)
        self.calls = []

    async def create(self, **kw):
        self.calls.append(kw)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=item)],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        )


def make_client(responses, **settings_kw):
    settings = Settings(**settings_kw)
    fake = SimpleNamespace(messages=FakeMessages(responses))
    return settings, LLMClient(settings, client=fake), fake.messages


@pytest.fixture
def build():
    def _build(responses, **settings_kw):
        settings, llm, msgs = make_client(responses, **settings_kw)
        store = ResilientStore(None, MemoryStore())
        app = create_app(settings, llm, store)
        return TestClient(app), msgs, store

    return _build


@pytest.fixture
def build_share():
    """Like `build`, but with sharing enabled: a signing secret and a durable (in-memory) store."""

    def _build(responses, **settings_kw):
        settings_kw.setdefault("share_secret", "test-signing-secret")
        settings_kw.setdefault("trusted_proxy_hops", 1)
        settings, llm, msgs = make_client(responses, **settings_kw)
        store = ResilientStore(MemoryStore())
        return TestClient(create_app(settings, llm, store)), msgs, store, settings

    return _build
