import pytest
from docx import Document

from app.llm import Usage
from app.pipeline import PipelineResult
from app.schemas import Claim, VerifiedAgenda
from investigate.agent import build_options, build_tools
from investigate.state import Investigation

POSTS = {
    "a": "Wake up at five and own your morning, because discipline is a story you tell yourself.",
    "b": "Discipline is a story you tell yourself; identity decides who gets up at five a.m.",
    "c": "Honestly my bus was late again today and I am cold and tired and going to bed now.",
}


def result(verdict, p):
    ag = VerifiedAgenda(
        primary_goal=Claim(claim="Sell identity mindset", quote="discipline is a story"),
        tldr="t",
        likely_prompt="p",
        context="c",
        persuasion_tactics=[],
        probable_cta=None,
    )
    return PipelineResult(
        verdict,
        p,
        [],
        False,
        ag if verdict == "ai" else None,
        "verified" if verdict == "ai" else "skipped",
        0,
        "",
        "m",
        {},
        Usage(10, 10, 0.01),
    )


def make(posts, verdicts):
    async def runner(text):
        key = next(k for k, v in POSTS.items() if v == text)
        return result(verdicts[key], 0.9 if verdicts[key] == "ai" else 0.1)

    return Investigation({k: POSTS[k] for k in posts}, runner)


async def test_consistent_posts_allow_verified_finding_and_report(tmp_path):
    inv = make(["a", "b"], {"a": "ai", "b": "ai"})
    await inv.analyze_post("a"), await inv.analyze_post("b")
    assert not inv.halted
    ok, _ = inv.record_finding(
        "identity over discipline", {"a": "discipline is a story you tell yourself", "b": "Discipline is a story you tell yourself"}
    )
    assert ok and inv.status == "COMPLETE"
    inv.write_docx(tmp_path / "r.docx")
    text = "\n".join(p.text for p in Document(tmp_path / "r.docx").paragraphs)
    assert "COMPLETE" in text and "identity over discipline" in text


async def test_fabricated_quote_rejected():
    inv = make(["a", "b"], {"a": "ai", "b": "ai"})
    ok, msg = inv.record_finding("x", {"a": "discipline is a story you tell yourself", "b": "buy my course today everyone"})
    assert not ok and "not found" in msg and inv.findings == [] and inv.rejected == ["x"]


async def test_contradiction_detected_by_code_halts_and_blocks_findings(tmp_path):
    inv = make(["a", "c"], {"a": "ai", "c": "human"})
    await inv.analyze_post("a"), await inv.analyze_post("c")
    assert inv.halted and inv.contradictions[0].source == "code"
    ok, msg = inv.record_finding("t", {"a": "discipline is a story you tell yourself", "c": "my bus was late again today"})
    assert not ok and "contradictions" in msg
    assert inv.status.startswith("ESCALATED")
    inv.write_docx(tmp_path / "r.docx")


async def test_single_post_evidence_rejected_and_unknown_post():
    inv = make(["a", "b"], {"a": "ai", "b": "ai"})
    assert not inv.record_finding("t", {"a": "discipline is a story you tell yourself"})[0]
    with pytest.raises(KeyError):
        await inv.analyze_post("zzz")


def test_needs_two_posts():
    with pytest.raises(ValueError):
        Investigation({"a": "x"}, None)


async def test_tool_handlers_and_options_disable_builtin_tools():
    inv = make(["a", "c"], {"a": "ai", "c": "human"})
    tools = {t.name: t for t in build_tools(inv)}
    assert set(tools) == {"list_posts", "analyze_post", "flag_contradiction", "record_finding", "finish"}
    await tools["analyze_post"].handler({"post_id": "a"})
    out = await tools["analyze_post"].handler({"post_id": "c"})
    assert "STOP" in out["content"][0]["text"]
    bad = await tools["record_finding"].handler({"theme": "t", "evidence": {"a": "x", "c": "y"}})
    assert bad["is_error"]
    opts = build_options(inv, "claude-sonnet-5-5", 1.0)
    assert opts.tools == [] and opts.max_budget_usd == 1.0
    assert all(t.startswith("mcp__inv__") for t in opts.allowed_tools)
