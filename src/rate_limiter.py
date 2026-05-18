"""
rate_limiter.py — Rate limiter async token bucket.
Garantit MAX_RPS requetes/seconde, compatible multi-workers async.
"""
import asyncio
import time

class RateLimiter:
    def __init__(self, max_rps: float) -> None:
        self.max_rps = max_rps
        self._min_interval = 1.0 / max_rps
        self._lock = asyncio.Lock()
        self._last_call: float = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def __aenter__(self) -> "RateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *_) -> None:
        pass
