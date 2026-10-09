"""
Small in-memory sliding-window rate limiter for the auth endpoints.

State lives in this process, so limits are per worker. That is enough for a
single-instance deployment; behind several workers or instances, move the
buckets to a shared store such as Redis.
"""

import math
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window = window_seconds
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        events = self._events[key]
        while events and events[0] <= now - self.window:
            events.popleft()
        return events

    def retry_after(self, key: str) -> int:
        """Seconds until another event is allowed, or 0 if allowed now."""
        now = time.monotonic()
        with self._lock:
            events = self._prune(key, now)
            if len(events) < self.max_events:
                return 0
            return max(1, math.ceil(events[0] + self.window - now))

    def hit(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


def client_ip(request: Request) -> str:
    # Behind a proxy, run uvicorn with --proxy-headers so this is the real client
    return request.client.host if request.client else "unknown"


def enforce(limiter: SlidingWindowLimiter, key: str, message: str) -> None:
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(wait)})
