import logging

from fastapi import FastAPI, HTTPException, Request, Response

from . import limits, share
from .config import Settings
from .schemas import ShareTicket
from .store import StoreUnavailable

log = logging.getLogger("deslopify.share")
NO_INDEX = {"X-Robots-Tag": "noindex, nofollow, noarchive", "Cache-Control": "no-store"}


def sharing_enabled(settings: Settings, store) -> bool:
    return bool(settings.share_secret) and store.persistent


def register(app: FastAPI, settings: Settings, store) -> None:
    def err(status: int, code: str, message: str):
        return HTTPException(status_code=status, detail={"error": code, "message": message})

    def require_enabled():
        if not sharing_enabled(settings, store):
            raise err(503, "sharing_unavailable", "Sharing is not available right now.")

    @app.post("/share", status_code=201)
    async def create(request: Request, body: ShareTicket):
        require_enabled()
        if not share.verify_ticket(settings, body):
            raise err(400, "invalid_ticket", "This result can no longer be shared. Run the analysis again.")
        ip = limits.client_ip(request, settings.trusted_proxy_hops)
        key = f"sharelimit:{ip}:{limits.today()}"
        count = await store.incr(key)
        if count == 1:
            await store.expire(key, limits.DAY_SECONDS)
        if count > settings.shares_per_day:
            raise err(429, "share_limit_exceeded", "You've created too many share links today.")
        try:
            created = await share.create_share(store, settings, body.record)
        except StoreUnavailable as e:
            raise err(503, "sharing_unavailable", "Sharing is not available right now.") from e
        await store.incr("stats:shares")
        log.info("share_created", extra={"share_id": created["id"], "verdict": body.record.verdict})
        return {**created, "path": f"/r/{created['id']}"}

    async def load_visible(share_id: str) -> dict:
        require_enabled()
        try:
            env = await share.load_share(store, share_id)
        except StoreUnavailable as e:
            raise err(503, "sharing_unavailable", "Sharing is not available right now.") from e
        if env is None or env["hidden"]:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "This result doesn't exist, has expired, or was removed."},
                headers=NO_INDEX,
            )
        return env

    @app.get("/r/{share_id}")
    async def view(share_id: str, response: Response):
        env = await load_visible(share_id)
        response.headers.update(NO_INDEX)
        return share.public_view(env)

    @app.delete("/r/{share_id}", status_code=204)
    async def delete(share_id: str, request: Request):
        env = await load_visible(share_id)
        supplied = request.headers.get("x-delete-key", "")
        if not supplied or not share.delete_key_matches(env, supplied):
            raise err(403, "forbidden", "Wrong delete key.")
        await store.durable("delete", share.key_for(share_id))
        log.info("share_deleted", extra={"share_id": share_id})
        return Response(status_code=204)

    @app.post("/r/{share_id}/report")
    async def report(share_id: str, request: Request):
        await load_visible(share_id)
        ip = limits.client_ip(request, settings.trusted_proxy_hops)
        try:
            count = await share.report(store, settings, share_id, ip)
        except StoreUnavailable as e:
            raise err(503, "sharing_unavailable", "Sharing is not available right now.") from e
        log.warning("share_reported", extra={"share_id": share_id, "reports": count})
        return {"ok": True, "message": "Thanks. This result will be hidden once enough people report it."}
