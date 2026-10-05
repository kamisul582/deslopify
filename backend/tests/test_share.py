import asyncio
import json
import time

from app.schemas import ShareTicket
from app.share import make_ticket, verify_ticket
from app.store import MemoryStore
from tests.conftest import TEXT, agenda, detection

CLIENT_A = {"X-Forwarded-For": "1.1.1.1"}


def analyze(client, headers=CLIENT_A):
    r = client.post("/analyze", json={"text": TEXT}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def new_share(client, headers=CLIENT_A):
    body = analyze(client, headers)
    r = client.post("/share", json=body["share"], headers=headers)
    assert r.status_code == 201, r.text
    return body, r.json()


# ── tickets ───────────────────────────────────────────────────────────────────


def test_analyze_offers_ticket_only_when_sharing_enabled(build, build_share):
    c, _, _ = build([detection(0.9), agenda()])
    assert c.post("/analyze", json={"text": TEXT}).json()["share"] is None  # no secret, no durable store
    c, _, _, _ = build_share([detection(0.9), agenda()])
    assert analyze(c)["share"]["ticket"]


def test_ticket_tamper_expiry_and_wrong_secret(build_share):
    c, _, _, settings = build_share([detection(0.9), agenda()])
    t = ShareTicket.model_validate(analyze(c)["share"])
    assert verify_ticket(settings, t)

    forged = t.model_copy(deep=True)
    forged.record.ai_probability = 0.99
    assert not verify_ticket(settings, forged)

    forged = t.model_copy(deep=True)
    forged.record.agenda.primary_goal.claim = "Author is a fraud"
    assert not verify_ticket(settings, forged)

    old = ShareTicket(record=t.record, ticket=f"{int(time.time()) - 7200}.{t.ticket.split('.')[1]}")
    assert not verify_ticket(settings, old)

    settings.share_secret = "another-secret"
    assert not verify_ticket(settings, t)
    assert make_ticket(settings, t.record)


def test_forged_record_cannot_be_published(build_share):
    c, _, _, _ = build_share([detection(0.5)])
    share = analyze(c)["share"]
    share["record"]["verdict"] = "ai"
    share["record"]["ai_probability"] = 0.99
    r = c.post("/share", json=share, headers=CLIENT_A)
    assert r.status_code == 400 and r.json()["detail"]["error"] == "invalid_ticket"


# ── create / view ─────────────────────────────────────────────────────────────


def test_share_roundtrip_hides_secrets_and_is_noindex(build_share):
    c, _, store, _ = build_share([detection(0.9), agenda()])
    body, created = new_share(c)
    assert created["path"] == f"/r/{created['id']}" and created["delete_key"]

    r = c.get(f"/r/{created['id']}")
    assert r.status_code == 200
    assert "noindex" in r.headers["x-robots-tag"] and r.headers["cache-control"] == "no-store"
    view = r.json()
    assert view["record"]["verdict"] == "ai"
    assert view["record"]["agenda"]["primary_goal"]["quote"] == "identity does"
    assert "delete" not in json.dumps(view) and created["delete_key"] not in json.dumps(view)

    # what is persisted: no pasted text, no plaintext delete key
    raw = asyncio.run(store.primary.get(f"share:{created['id']}"))
    assert created["delete_key"] not in raw
    assert "wake up at 5am because of who you are" not in raw  # full text sentence not stored
    assert '"text"' not in raw


def test_unknown_and_malformed_ids_404(build_share):
    c, _, _, _ = build_share([])
    assert c.get("/r/" + "a" * 22).status_code == 404
    assert c.get("/r/short").status_code == 404
    assert c.get("/r/..%2Fstats").status_code == 404


def test_share_disabled_without_secret(build):
    c, _, _ = build([])
    assert c.post("/share", json={"record": {}, "ticket": "x"}).status_code in (422, 503)
    assert c.get("/r/" + "a" * 22).status_code == 503


def test_share_rate_limit(build_share):
    c, _, _, _ = build_share([detection(0.1)] * 3, shares_per_day=1, rate_limit_per_day=10)
    body = analyze(c)
    assert c.post("/share", json=body["share"], headers=CLIENT_A).status_code == 201
    body = analyze(c)
    assert c.post("/share", json=body["share"], headers=CLIENT_A).status_code == 429


# ── delete / report / expiry ──────────────────────────────────────────────────


def test_delete_requires_key(build_share):
    c, _, _, _ = build_share([detection(0.1)])
    _, created = new_share(c)
    url = f"/r/{created['id']}"
    assert c.delete(url).status_code == 403
    assert c.delete(url, headers={"X-Delete-Key": "wrong"}).status_code == 403
    assert c.get(url).status_code == 200
    assert c.delete(url, headers={"X-Delete-Key": created["delete_key"]}).status_code == 204
    assert c.get(url).status_code == 404


def test_reports_hide_share_one_vote_per_ip(build_share):
    c, _, _, _ = build_share([detection(0.1)], report_hide_threshold=3)
    _, created = new_share(c)
    url = f"/r/{created['id']}"
    for _ in range(3):  # same IP spamming counts once
        assert c.post(url + "/report", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert c.get(url).status_code == 200
    c.post(url + "/report", headers={"X-Forwarded-For": "3.3.3.3"})
    assert c.get(url).status_code == 200
    c.post(url + "/report", headers={"X-Forwarded-For": "4.4.4.4"})
    assert c.get(url).status_code == 404  # hidden at 3 distinct reporters


def test_cors_allows_delete_header_for_frontend(build_share):
    c, _, _, _ = build_share([], allowed_origins=["https://deslopify.app"])
    r = c.options(
        "/r/" + "a" * 22,
        headers={
            "Origin": "https://deslopify.app",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "x-delete-key",
        },
    )
    assert r.status_code == 200 and "DELETE" in r.headers["access-control-allow-methods"]


def test_memory_store_ttl_and_delete():
    async def go():
        s = MemoryStore()
        await s.set("k", "v", ex=0)
        assert await s.get("k") is None  # expired
        await s.set("k", "v", ex=100)
        assert await s.get("k") == "v"
        assert await s.delete("k") == 1 and await s.get("k") is None

    asyncio.run(go())
