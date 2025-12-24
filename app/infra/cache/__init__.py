"""Cache module for Redis-based caching."""

from app.infra.cache.service import CacheService, get_cache

__all__ = [
    "CacheService",
    "get_cache",
]
