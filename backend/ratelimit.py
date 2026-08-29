"""In-process sliding-window rate limiter.

Protects quota-limited provider keys (Gemini especially) without Redis.
State is per-process and resets on restart — that is intentional for a laptop demo.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from flask import request

from api.errors import ApiError
from config import settings

logger = logging.getLogger(__name__)

_MINUTE = 60.0
_DAY = 86_400.0
_PRUNE_EVERY = 60.0


class RateLimiter:
    """Thread-safe sliding windows plus optional per-key cooldown."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._cooldowns: dict[str, float] = {}
        self._last_prune = 0.0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._cooldowns.clear()
            self._last_prune = 0.0

    def trip_cooldown(self, key: str, seconds: float) -> None:
        if seconds <= 0:
            return
        until = time.monotonic() + seconds
        with self._lock:
            self._cooldowns[key] = max(self._cooldowns.get(key, 0.0), until)

    def consume(self, key: str, limits: list[tuple[int, float]]) -> tuple[bool, int]:
        """Take one slot in every window, or take none.

        ``limits`` is ``[(max_events, window_seconds), ...]``. A non-positive
        ``max_events`` means that window is not enforced.
        Returns ``(allowed, retry_after_seconds)``.
        """
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            cooldown = self._cooldowns.get(key, 0.0)
            if now < cooldown:
                return False, _retry_after(cooldown - now)

            windows: list[tuple[str, deque[float], int, float]] = []
            retry = 0
            for index, (max_events, window_s) in enumerate(limits):
                if max_events <= 0 or window_s <= 0:
                    continue
                window_key = f"{key}:{index}:{int(window_s)}"
                queue = self._events[window_key]
                cutoff = now - window_s
                while queue and queue[0] <= cutoff:
                    queue.popleft()
                if len(queue) >= max_events:
                    wait = queue[0] + window_s - now if queue else window_s
                    retry = max(retry, _retry_after(wait))
                else:
                    windows.append((window_key, queue, max_events, window_s))

            if retry:
                return False, retry

            for window_key, queue, _max_events, _window_s in windows:
                queue.append(now)
            return True, 0

    def _prune_locked(self, now: float) -> None:
        if now - self._last_prune < _PRUNE_EVERY:
            return
        self._last_prune = now
        stale_events = [
            name
            for name, queue in self._events.items()
            if not queue or queue[-1] < now - _DAY
        ]
        for name in stale_events:
            del self._events[name]
        stale_cooldowns = [name for name, until in self._cooldowns.items() if until <= now]
        for name in stale_cooldowns:
            del self._cooldowns[name]


def _retry_after(wait: float) -> int:
    return max(1, int(wait + 0.999))


limiter = RateLimiter()

_CLIENT_LIMITS = {
    "extract": lambda: (settings.extract_ip_per_minute, settings.extract_ip_per_day),
    "geocode": lambda: (settings.geocode_ip_per_minute, settings.geocode_ip_per_day),
    "detect": lambda: (settings.detect_ip_per_minute, settings.detect_ip_per_day),
}

_CLIENT_MESSAGES = {
    "extract": (
        "Too many extraction requests. Wait a moment and try again, "
        "or fill the search-area fields by hand."
    ),
    "geocode": "Too many geocode requests. Wait a moment and try again.",
    "detect": "Too many detection requests. Wait a moment and try again.",
}


def client_identity() -> str:
    """Use the TCP peer. Do not trust X-Forwarded-For — it is trivial to spoof."""
    return (request.remote_addr or "unknown").strip() or "unknown"


def enforce_client_limit(bucket: str) -> None:
    per_minute, per_day = _CLIENT_LIMITS[bucket]()
    identity = client_identity()
    allowed, retry_after = limiter.consume(
        f"client:{bucket}:{identity}",
        [(per_minute, _MINUTE), (per_day, _DAY)],
    )
    if allowed:
        return
    logger.warning(
        "rate_limited bucket=%s retry_after=%s",
        bucket,
        retry_after,
    )
    raise ApiError(429, "RATE_LIMITED", _CLIENT_MESSAGES[bucket], retry_after=retry_after)


def acquire_gemini() -> tuple[bool, int]:
    return limiter.consume(
        "provider:gemini",
        [(settings.gemini_max_rpm, _MINUTE), (settings.gemini_max_rpd, _DAY)],
    )


def acquire_groq() -> tuple[bool, int]:
    return limiter.consume(
        "provider:groq",
        [(settings.groq_max_rpm, _MINUTE), (settings.groq_max_rpd, _DAY)],
    )


def acquire_geocode() -> tuple[bool, int]:
    return limiter.consume(
        "provider:geocode",
        [(settings.geocode_max_rpm, _MINUTE), (settings.geocode_max_rpd, _DAY)],
    )


def trip_gemini_cooldown() -> None:
    limiter.trip_cooldown("provider:gemini", settings.gemini_cooldown_seconds)


def trip_groq_cooldown() -> None:
    limiter.trip_cooldown("provider:groq", settings.groq_cooldown_seconds)


def trip_geocode_cooldown() -> None:
    limiter.trip_cooldown("provider:geocode", settings.geocode_cooldown_seconds)
