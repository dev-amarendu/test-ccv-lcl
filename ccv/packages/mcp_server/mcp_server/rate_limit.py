"""Simple in-memory rate limiter (swap to Redis for production)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_CALLS_PER_WINDOW = 100
WINDOW_SECONDS = 60


# ── In-memory sliding window counter ─────────────────────────────────────────
# Key: (caller, tool_name) -> list of timestamps

_buckets: dict[tuple[str, str], list[float]] = defaultdict(list)


class RateLimitBackend:
    """Abstract interface — implement Redis-backed version for production."""

    def check(self, caller: str, tool_name: str) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class InMemoryRateLimiter(RateLimitBackend):
    def __init__(self, max_calls: int = MAX_CALLS_PER_WINDOW, window: int = WINDOW_SECONDS):
        self.max_calls = max_calls
        self.window = window

    def check(self, caller: str, tool_name: str) -> None:
        key = (caller, tool_name)
        now = time.monotonic()
        cutoff = now - self.window

        # Prune old entries
        _buckets[key] = [t for t in _buckets[key] if t > cutoff]

        if len(_buckets[key]) >= self.max_calls:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {caller}/{tool_name}: {self.max_calls}/{self.window}s",
            )

        _buckets[key].append(now)

    def reset(self) -> None:
        _buckets.clear()


_limiter = InMemoryRateLimiter()


def check_rate_limit(caller: str, tool_name: str) -> None:
    """Check rate limit for caller+tool — raises HTTPException(429) if exceeded."""
    _limiter.check(caller, tool_name)


def reset_rate_limits() -> None:
    """Reset all rate limit counters (useful in tests)."""
    _limiter.reset()
