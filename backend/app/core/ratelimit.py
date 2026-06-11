"""In-process token-bucket rate limiter for run creation.

A lightweight abuse guard for the public API. Keyed per caller (principal subject or
client IP). Suitable for a single-instance deployment; a multi-instance deployment
should back this with Redis. Fails open only on internal error, never on limit.
"""

from __future__ import annotations

import time

from fastapi import HTTPException, status

from app.config import settings


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float) -> None:
        self.tokens = tokens
        self.updated = time.monotonic()


class RateLimiter:
    """Refilling token bucket: ``rate`` tokens per 60s, burst = ``rate``."""

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}

    def check(self, key: str) -> None:
        rate = max(1, settings.rate_limit_runs_per_minute)
        refill_per_sec = rate / 60.0
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = _Bucket(tokens=rate - 1)
            return
        elapsed = now - bucket.updated
        bucket.tokens = min(rate, bucket.tokens + elapsed * refill_per_sec)
        bucket.updated = now
        if bucket.tokens < 1:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded ({rate} runs/min). Try again shortly.",
            )
        bucket.tokens -= 1


run_rate_limiter = RateLimiter()
