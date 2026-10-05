"""Opt-in result sharing.

Threat model: a share page is a public, authoritative-looking claim about someone's
writing. So (1) only results this server actually produced can be published (HMAC
ticket), (2) the pasted text is never stored, only the short verified quotes,
(3) links expire, can be deleted by their creator, and can be reported."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from .config import Settings
from .schemas import ShareRecord, ShareTicket
from .store import StoreUnavailable

SCHEMA_VERSION = 1
ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")  # token_urlsafe(16)


def _canonical(record: ShareRecord) -> bytes:
    return json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _mac(secret: str, iat: int, record: ShareRecord) -> str:
    msg = str(iat).encode() + b"." + _canonical(record)
    return base64.urlsafe_b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode().rstrip("=")


def make_ticket(settings: Settings, record: ShareRecord) -> ShareTicket | None:
    if not settings.share_secret:
        return None
    iat = int(time.time())
    return ShareTicket(record=record, ticket=f"{iat}.{_mac(settings.share_secret, iat, record)}")


def verify_ticket(settings: Settings, t: ShareTicket) -> bool:
    if not settings.share_secret:
        return False
    iat_s, _, mac = t.ticket.partition(".")
    if not iat_s.isdigit():
        return False
    iat = int(iat_s)
    now = time.time()
    if iat > now + 60 or now - iat > settings.ticket_ttl_s:
        return False
    return hmac.compare_digest(mac, _mac(settings.share_secret, iat, t.record))


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def key_for(share_id: str) -> str:
    return f"share:{share_id}"


async def create_share(store, settings: Settings, record: ShareRecord) -> dict:
    """Returns {id, delete_key, expires_at}. The delete key is shown once; only its hash is stored."""
    share_id, delete_key = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    now = int(time.time())
    ttl = settings.share_ttl_days * 86_400
    envelope = {
        "v": SCHEMA_VERSION,
        "created_at": now,
        "expires_at": now + ttl,
        "delete_hash": _hash(delete_key),
        "hidden": False,
        "record": record.model_dump(mode="json"),
    }
    await _set(store, key_for(share_id), json.dumps(envelope, ensure_ascii=False), ttl)
    return {"id": share_id, "delete_key": delete_key, "expires_at": envelope["expires_at"]}


async def _set(store, key: str, value: str, ttl: int):
    if store.primary is None:
        raise StoreUnavailable("no durable store configured")
    try:
        await store.primary.set(key, value, ex=ttl)
    except Exception as e:
        raise StoreUnavailable("durable store failed") from e


async def load_share(store, share_id: str) -> dict | None:
    if not ID_RE.match(share_id):
        return None
    raw = await store.durable("get", key_for(share_id))
    return json.loads(raw) if raw else None


def public_view(envelope: dict) -> dict:
    return {
        "schema_version": envelope["v"],
        "created_at": envelope["created_at"],
        "expires_at": envelope["expires_at"],
        "record": envelope["record"],
    }


def delete_key_matches(envelope: dict, supplied: str) -> bool:
    return hmac.compare_digest(_hash(supplied), envelope["delete_hash"])


async def report(store, settings: Settings, share_id: str, ip: str) -> int:
    """Counts one report per IP per share. Hides the share at the threshold. Returns the count."""
    ttl = settings.share_ttl_days * 86_400
    ip_key = f"rep:{share_id}:{_hash(ip)[:16]}"
    seen = await store.durable("incr", ip_key)
    if seen == 1:
        await store.durable("expire", ip_key, ttl)
    else:
        return int(await store.durable("get", f"rep:{share_id}") or 0)
    count = await store.durable("incr", f"rep:{share_id}")
    await store.durable("expire", f"rep:{share_id}", ttl)
    if count >= settings.report_hide_threshold:
        env = await load_share(store, share_id)
        if env and not env["hidden"]:
            env["hidden"] = True
            remaining = max(1, env["expires_at"] - int(time.time()))
            await _set(store, key_for(share_id), json.dumps(env, ensure_ascii=False), remaining)
    return count
