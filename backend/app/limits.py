import ipaddress
import time

from fastapi import Request

DAY_SECONDS = 86_400
MICRO = 1_000_000


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def client_ip(request: Request, trusted_hops: int) -> str:
    """Rate-limit identity of the caller.

    X-Forwarded-For is client-controlled at its left end: every proxy *appends*
    the address it saw. Only entries added by proxies we operate/trust are
    reliable, so we count from the RIGHT. With N trusted proxy hops the real
    client is the Nth entry from the right; anything the client prepended sits
    further left and is ignored. trusted_hops=0 disables the header.
    """
    peer = request.client.host if request.client else "unknown"
    if trusted_hops <= 0:
        return peer
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) < trusted_hops:
        return peer
    candidate = parts[-trusted_hops]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


async def check_rate_limit(store, ip: str, limit: int) -> tuple[bool, int]:
    key = f"rl:{ip}:{today()}"
    count = await store.incr(key)
    if count == 1:
        await store.expire(key, DAY_SECONDS)
    return count <= limit, max(0, limit - count)


async def refund_rate_limit(store, ip: str):
    await store.decr(f"rl:{ip}:{today()}")


async def spent_today_usd(store) -> float:
    return int(await store.get(f"budget:{today()}") or 0) / MICRO


async def budget_exhausted(store, budget_usd: float) -> bool:
    return await spent_today_usd(store) >= budget_usd


async def record_spend(store, usd: float):
    key = f"budget:{today()}"
    total = await store.incrby(key, round(usd * MICRO))
    if total == round(usd * MICRO):
        await store.expire(key, 3 * DAY_SECONDS)


async def record_stats(store, verdict: str):
    d = today()
    await store.incr("stats:total")
    await store.incr({"ai": "stats:ai_detected", "human": "stats:not_ai"}.get(verdict, "stats:uncertain"))
    await store.incr(f"stats:daily:{d}")


async def record_error(store):
    key = f"stats:errors:{today()}"
    if await store.incr(key) == 1:
        await store.expire(key, 40 * DAY_SECONDS)
