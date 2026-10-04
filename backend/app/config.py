import os
from dataclasses import dataclass, field

# USD per 1M tokens (input, output). Used only for the spend circuit breaker;
# unknown models fall back to the most expensive known entry (fail safe).
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}

MAX_TEXT_CHARS = 10_000
MIN_TEXT_CHARS = 50


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = MODEL_PRICING.get(model, max(MODEL_PRICING.values()))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


@dataclass
class Settings:
    anthropic_api_key: str | None = None
    model: str = "claude-haiku-4-5-20251001"
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2
    rate_limit_per_day: int = 5
    daily_budget_usd: float = 5.0
    # Number of reverse proxies between the internet and this app that append to
    # X-Forwarded-For. 0 = ignore the header entirely (use the socket peer).
    trusted_proxy_hops: int = 1
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    stats_secret: str | None = None
    upstash_url: str | None = None
    upstash_token: str | None = None
    sentry_dsn: str | None = None
    # Verdict thresholds on ai_probability: <= human_max -> human, >= ai_min -> ai,
    # in between -> "uncertain" (we refuse to force a verdict).
    human_max: float = 0.35
    ai_min: float = 0.65

    @classmethod
    def from_env(cls) -> "Settings":
        g = os.getenv
        return cls(
            anthropic_api_key=g("ANTHROPIC_API_KEY"),
            model=g("MODEL", cls.model),
            llm_timeout_s=float(g("LLM_TIMEOUT_S", cls.llm_timeout_s)),
            llm_max_retries=int(g("LLM_MAX_RETRIES", cls.llm_max_retries)),
            rate_limit_per_day=int(g("RATE_LIMIT_PER_DAY", cls.rate_limit_per_day)),
            daily_budget_usd=float(g("DAILY_BUDGET_USD", cls.daily_budget_usd)),
            trusted_proxy_hops=int(g("TRUSTED_PROXY_HOPS", cls.trusted_proxy_hops)),
            allowed_origins=[o.strip() for o in g("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
            stats_secret=g("STATS_SECRET") or None,
            upstash_url=g("UPSTASH_REDIS_REST_URL"),
            upstash_token=g("UPSTASH_REDIS_REST_TOKEN"),
            sentry_dsn=g("SENTRY_DSN") or None,
        )
