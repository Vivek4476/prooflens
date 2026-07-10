"""In-memory fixed-window rate limiting for the /v1/* surface.

Single-instance only: counters live in this process. A multi-instance deploy
needs a shared store (Redis) — deferred; see BACKEND_REQUIREMENTS.md. Bucketed
by the API key (hashed) when present, else client IP. Two tiers: a general cap
on all /v1/*, a tighter cap on the compute routes (/v1/score, /v1/bulk-score).
A limit of 0 means unlimited (disables the tier)."""

from __future__ import annotations

import time
from hashlib import sha256

from fastapi import Request, Response

# Paths under /v1/ that get the stricter "compute" tier.
_COMPUTE_PATHS = ("/v1/score", "/v1/bulk-score")


class RateLimiter:
    """Fixed 60s window per (bucket_key, tier). check() returns
    (allowed, retry_after_seconds). Thread-safety is not required: the ASGI
    event loop is single-threaded and check() does no awaits."""

    def __init__(self, limits: dict[str, int], window_seconds: int = 60) -> None:
        self._limits = limits
        self._window = window_seconds
        # (bucket_key, tier) -> (window_start_epoch, count)
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def check(self, bucket_key: str, tier: str, now: float | None = None) -> tuple[bool, int]:
        limit = self._limits.get(tier, 0)
        if limit <= 0:
            return True, 0  # 0/absent => unlimited
        t = time.time() if now is None else now
        key = (bucket_key, tier)
        start, count = self._buckets.get(key, (t, 0))
        if t - start >= self._window:
            start, count = t, 0  # new window
        count += 1
        self._buckets[key] = (start, count)
        if count > limit:
            retry = int(self._window - (t - start)) + 1
            return False, max(1, min(retry, self._window))
        return True, 0

    def prune(self, now: float | None = None) -> None:
        """Drop windows older than one full window (opportunistic GC)."""
        t = time.time() if now is None else now
        stale = [k for k, (start, _) in self._buckets.items() if t - start >= self._window]
        for k in stale:
            del self._buckets[k]


def _bucket_key(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
        if raw:
            return "k:" + sha256(raw.encode("utf-8")).hexdigest()[:32]
    # First hop of X-Forwarded-For (Render/Vercel proxy), else the socket peer.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return "ip:" + ip


def make_rate_limit_middleware(limiter: RateLimiter):
    """A Starlette http middleware enforcing `limiter` on /v1/* only."""

    async def middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if not path.startswith("/v1/"):
            return await call_next(request)
        bkey = _bucket_key(request)
        # A compute request counts against BOTH tiers; the stricter one wins.
        tiers = ["general"]
        if path in _COMPUTE_PATHS:
            tiers.append("compute")
        for tier in tiers:
            allowed, retry = limiter.check(bkey, tier)
            if not allowed:
                return Response(
                    status_code=429,
                    content='{"detail":"rate limit exceeded"}',
                    media_type="application/json",
                    headers={"Retry-After": str(retry)},
                )
        return await call_next(request)

    return middleware
