from types import SimpleNamespace

from app.llm import extract_json
from app.verification import normalize, quote_in_text


def req(xff=None, peer="10.0.0.1"):
    from app.limits import client_ip  # noqa: F401

    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_client_ip_variants():
    from app.limits import client_ip

    assert client_ip(req("1.1.1.1", "10.0.0.1"), 0) == "10.0.0.1"
    assert client_ip(req("1.1.1.1"), 1) == "1.1.1.1"
    assert client_ip(req("6.6.6.6, 1.1.1.1"), 1) == "1.1.1.1"
    assert client_ip(req("6.6.6.6, 1.1.1.1, 10.1.1.1"), 2) == "1.1.1.1"
    assert client_ip(req(None), 1) == "10.0.0.1"  # no header -> socket peer
    assert client_ip(req("not-an-ip"), 1) == "10.0.0.1"
    assert client_ip(req("1.1.1.1"), 2) == "10.0.0.1"  # fewer entries than trusted hops


def test_quote_matching_is_tolerant_to_whitespace_and_typography_only():
    text = "Discipline is a story you tell yourself —  after the habit is formed."
    assert quote_in_text("Discipline is a story you tell yourself - after the habit", text)
    assert not quote_in_text("Discipline is a lie you tell yourself", text)
    assert not quote_in_text("story", text)  # too short to count as evidence


def test_normalize_polish():
    assert normalize("  Ząb   „Test”  ") == normalize('ząb "test"')


def test_extract_json():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 1} hope that helps') == {"a": 1}
