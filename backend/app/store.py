"""Counter store: Upstash Redis in production, process-local memory otherwise.

ResilientStore falls back to memory if Redis errors, so rate limiting and the
spend breaker keep working (per-process) instead of silently turning off."""

import logging
import time

log = logging.getLogger("deslopify.store")


class StoreUnavailable(Exception):
    pass


class MemoryStore:
    def __init__(self):
        self._d: dict[str, int] = {}
        self._exp: dict[str, float] = {}

    def _purge(self, key: str):
        if key in self._exp and self._exp[key] <= time.time():
            self._d.pop(key, None)
            self._exp.pop(key, None)

    async def incrby(self, key: str, n: int = 1) -> int:
        self._purge(key)
        self._d[key] = self._d.get(key, 0) + n
        return self._d[key]

    async def incr(self, key: str) -> int:
        return await self.incrby(key, 1)

    async def decr(self, key: str) -> int:
        return await self.incrby(key, -1)

    async def get(self, key: str):
        self._purge(key)
        return self._d.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self._d[key] = value
        if ex is not None:
            self._exp[key] = time.time() + ex
        else:
            self._exp.pop(key, None)
        return True

    async def delete(self, key: str):
        self._exp.pop(key, None)
        return 1 if self._d.pop(key, None) is not None else 0

    async def expire(self, key: str, seconds: int):
        self._exp[key] = time.time() + seconds


class ResilientStore:
    def __init__(self, primary, fallback: MemoryStore | None = None):
        self.primary = primary
        self.fallback = fallback or MemoryStore()

    async def _call(self, name: str, *args):
        if self.primary is not None:
            try:
                return await getattr(self.primary, name)(*args)
            except Exception:
                log.exception("redis_error", extra={"op": name})
        return await getattr(self.fallback, name)(*args)

    async def incrby(self, key, n=1):
        return await self._call("incrby", key, n)

    async def incr(self, key):
        return await self._call("incr", key)

    async def decr(self, key):
        return await self._call("decr", key)

    async def get(self, key):
        return await self._call("get", key)

    async def expire(self, key, seconds):
        return await self._call("expire", key, seconds)

    @property
    def persistent(self) -> bool:
        return self.primary is not None

    # Shared results must live in the durable store. No silent per-process fallback:
    # a share that only exists in one worker's memory would vanish or 404 at random.
    async def durable(self, name: str, *args):
        if self.primary is None:
            raise StoreUnavailable("no durable store configured")
        try:
            return await getattr(self.primary, name)(*args)
        except Exception as e:
            log.exception("redis_error", extra={"op": name})
            raise StoreUnavailable("durable store failed") from e
