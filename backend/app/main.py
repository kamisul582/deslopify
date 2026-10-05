import hmac
import logging
import time
import uuid

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from upstash_redis.asyncio import Redis as UpstashRedis

from . import limits, share, share_routes
from .config import Settings
from .llm import LLMClient, LLMError
from .logging_setup import request_id_var, setup_logging
from .pipeline import run_pipeline
from .schemas import AnalyzeRequest, AnalyzeResponse, ShareRecord
from .store import ResilientStore

log = logging.getLogger("deslopify.api")
MAX_BODY_BYTES = 64 * 1024


def create_app(settings: Settings | None = None, llm: LLMClient | None = None, store=None) -> FastAPI:
    load_dotenv()
    settings = settings or Settings.from_env()
    setup_logging()

    if settings.sentry_dsn:
        # No PII, no request bodies: pasted text must never leave the server.
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=False,
            max_request_body_size="never",
            traces_sample_rate=0.0,
        )

    if store is None:
        primary = None
        if settings.upstash_url and settings.upstash_token:
            primary = UpstashRedis(url=settings.upstash_url, token=settings.upstash_token)
        store = ResilientStore(primary)
    llm = llm or LLMClient(settings)

    app = FastAPI(title="Deslopify API", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Delete-Key"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        start = time.perf_counter()
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            resp = JSONResponse(
                status_code=413,
                content={"detail": {"error": "payload_too_large", "message": "That request is too large."}},
            )
        else:
            try:
                resp = await call_next(request)
            except Exception:
                log.exception("unhandled_error", extra={"path": request.url.path})
                await limits.record_error(store)
                resp = JSONResponse(
                    status_code=500,
                    content={"detail": {"error": "internal_error", "message": "Something went wrong on our side."}},
                )
        resp.headers["X-Request-ID"] = rid
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": resp.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000),
            },
        )
        return resp

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Never echo the submitted text back (pydantic's default error includes `input`).
        msgs = [str(e.get("msg", "invalid")).removeprefix("Value error, ") for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": {"error": "invalid_request", "message": "; ".join(msgs)}},
        )

    share_routes.register(app, settings, store)

    @app.get("/health")
    async def health():
        return {"status": "ok", "persistent_store": store.persistent}

    @app.get("/stats")
    async def stats(request: Request, days: int = 14):
        # Fail closed: without a configured secret the endpoint does not exist.
        if not settings.stats_secret:
            raise HTTPException(status_code=404)
        supplied = request.headers.get("x-stats-secret", "")
        if not hmac.compare_digest(supplied.encode(), settings.stats_secret.encode()):
            raise HTTPException(status_code=403)

        async def n(key: str) -> int:
            return int(await store.get(key) or 0)

        days = max(1, min(days, 60))
        daily = []
        for i in range(days):
            d = time.strftime("%Y-%m-%d", time.gmtime(time.time() - i * 86_400))
            daily.append(
                {
                    "date": d,
                    "analyses": await n(f"stats:daily:{d}"),
                    "cost_usd": round(await n(f"budget:{d}") / limits.MICRO, 4),
                    "errors": await n(f"stats:errors:{d}"),
                }
            )
        total = await n("stats:total")
        ai = await n("stats:ai_detected")
        return {
            "total_analyses": total,
            "ai_detected": ai,
            "not_ai": await n("stats:not_ai"),
            "uncertain": await n("stats:uncertain"),
            "shares": await n("stats:shares"),
            "today": daily[0]["analyses"],
            "ai_detection_rate_pct": round(ai / max(total, 1) * 100, 1),
            "daily": daily,
        }

    @app.post("/analyze", response_model=AnalyzeResponse)
    async def analyze(request: Request, body: AnalyzeRequest):
        # Global spend breaker first: independent of any per-IP limit.
        if await limits.budget_exhausted(store, settings.daily_budget_usd):
            log.warning("daily_budget_exhausted")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "daily_budget_exhausted",
                    "message": "The free daily capacity of this demo is used up. Please come back tomorrow.",
                },
            )

        ip = limits.client_ip(request, settings.trusted_proxy_hops)
        allowed, remaining = await limits.check_rate_limit(store, ip, settings.rate_limit_per_day)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"You've used your {settings.rate_limit_per_day} free analyses for today. Come back tomorrow.",
                    "remaining": 0,
                },
            )

        try:
            result = await run_pipeline(body.text, llm, settings)
        except LLMError as e:
            await limits.refund_rate_limit(store, ip)  # don't charge users for our failures
            await limits.record_error(store)
            log.error("llm_failure", extra={"code": e.code})
            raise HTTPException(status_code=e.status, detail={"error": e.code, "message": e.user_message}) from e

        await limits.record_spend(store, result.usage.cost_usd)
        await limits.record_stats(store, result.verdict)
        log.info(
            "analysis_done",
            extra={
                "verdict": result.verdict,
                "agenda_status": result.agenda_status,
                "dropped_claims": result.dropped_claims,
                "injection": result.injection_detected,
                "model": result.model,
                "prompt_versions": result.prompt_versions,
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cost_usd": round(result.usage.cost_usd, 6),
            },
        )
        ticket = None
        if share_routes.sharing_enabled(settings, store):
            try:
                ticket = share.make_ticket(
                    settings,
                    ShareRecord(
                        verdict=result.verdict,
                        ai_probability=result.ai_probability,
                        signals=result.signals,
                        injection_detected=result.injection_detected,
                        agenda=result.agenda,
                        agenda_status=result.agenda_status,
                        dropped_claims=result.dropped_claims,
                        model=result.model,
                        prompt_versions=result.prompt_versions,
                    ),
                )
            except ValueError:
                log.warning("share_record_invalid")  # analysis still succeeds, just not shareable
        return AnalyzeResponse(
            request_id=request_id_var.get(),
            verdict=result.verdict,
            ai_probability=result.ai_probability,
            signals=result.signals,
            injection_detected=result.injection_detected,
            agenda=result.agenda,
            agenda_status=result.agenda_status,
            dropped_claims=result.dropped_claims,
            message=result.message,
            remaining_today=remaining,
            model=result.model,
            prompt_versions=result.prompt_versions,
            share=ticket,
        )

    return app


app = create_app()
