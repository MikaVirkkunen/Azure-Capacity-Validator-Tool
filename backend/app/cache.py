"""Simple in-memory TTL cache utilities.

Lightweight (no external deps) caching for expensive Azure metadata calls.
Not thread-safe for high concurrency, but adequate for local / low RPS MVP.
If concurrency contention arises, replace dict ops with a threading.Lock or use cachetools.
"""
from __future__ import annotations

import os
import time
from typing import Callable, TypeVar, Dict, Tuple, Any

T = TypeVar("T")

_store: Dict[Tuple[str, Tuple[Any, ...], Tuple[Tuple[str, Any], ...]], tuple[float, Any]] = {}

def _now() -> float:
    return time.time()

def ttl_cache(ttl_seconds: int | None = None):
    """Decorator implementing a naive TTL cache.

    Key is function name + args + sorted kwargs. Stale entries are lazily evicted.
    """
    ttl_env = os.getenv("CACHE_TTL_SECONDS")
    if ttl_env and ttl_seconds is None:
        try:
            ttl_seconds = int(ttl_env)
        except ValueError:
            pass
    if ttl_seconds is None:
        ttl_seconds = 600  # default 10m

    def wrapper(fn: Callable[..., T]) -> Callable[..., T]:
        fname = fn.__name__

        def inner(*args, **kwargs):  # type: ignore
            key = (fname, args, tuple(sorted(kwargs.items())))
            record = _store.get(key)
            now = _now()
            if record:
                expires_at, value = record
                if expires_at > now:
                    return value
                else:
                    # stale
                    _store.pop(key, None)
            value = fn(*args, **kwargs)
            _store[key] = (now + ttl_seconds, value)
            return value

        def invalidate():  # expose invalidation for tests
            to_del = [k for k in _store if k[0] == fname]
            for k in to_del:
                _store.pop(k, None)

        inner.invalidate = invalidate  # type: ignore[attr-defined]
        return inner

    return wrapper

def clear_all_cache():
    _store.clear()
