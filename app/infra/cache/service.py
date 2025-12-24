"""Redis cache service for performance optimization.

This service provides caching capabilities with:
- TTL-based expiration
- JSON serialization
- Cache hit/miss metrics
- Namespace support for key organization
"""

import json
import logging
from typing import Any, Optional
from uuid import UUID

from app.infra.queues.connection import redis_conn
from app.infra.metrics import get_metrics

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching data in Redis with metrics tracking.

    Usage:
        cache = get_cache()
        cache.set("workflow_exec", execution_id, execution_dict, ttl=300)
        cached = cache.get("workflow_exec", execution_id)
    """

    def __init__(self, redis_client):
        """Initialize cache service.

        Args:
            redis_client: Redis connection instance
        """
        self.redis = redis_client
        self.metrics = get_metrics()

    def _make_key(self, namespace: str, key: Any) -> str:
        """Generate cache key with namespace.

        Args:
            namespace: Cache namespace (e.g., "workflow_exec", "creator_profile")
            key: Key within namespace (will be converted to string)

        Returns:
            Namespaced key string
        """
        # Convert UUID to string if needed
        if isinstance(key, UUID):
            key = str(key)

        return f"cache:{namespace}:{key}"

    def get(self, namespace: str, key: Any) -> Optional[Any]:
        """Get value from cache.

        Args:
            namespace: Cache namespace
            key: Key to retrieve

        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        cache_key = self._make_key(namespace, key)

        try:
            cached = self.redis.get(cache_key)

            if cached:
                # Cache hit
                self.metrics.cache_hits.labels(cache_type=namespace).inc()
                logger.debug(
                    f"Cache hit: {namespace}:{key}",
                    extra={"namespace": namespace, "key": str(key)}
                )
                return json.loads(cached)
            else:
                # Cache miss
                self.metrics.cache_misses.labels(cache_type=namespace).inc()
                logger.debug(
                    f"Cache miss: {namespace}:{key}",
                    extra={"namespace": namespace, "key": str(key)}
                )
                return None

        except Exception as e:
            logger.warning(
                f"Cache get failed for {namespace}:{key}: {e}",
                extra={"namespace": namespace, "key": str(key)}
            )
            self.metrics.cache_misses.labels(cache_type=namespace).inc()
            return None

    def set(
        self,
        namespace: str,
        key: Any,
        value: Any,
        ttl: int = 300
    ) -> bool:
        """Set value in cache with TTL.

        Args:
            namespace: Cache namespace
            key: Key to store
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 300 = 5 minutes)

        Returns:
            True if successful, False otherwise
        """
        cache_key = self._make_key(namespace, key)

        try:
            # Serialize to JSON
            serialized = json.dumps(value, default=str)

            # Set with expiration
            self.redis.setex(cache_key, ttl, serialized)

            logger.debug(
                f"Cache set: {namespace}:{key} (TTL: {ttl}s)",
                extra={
                    "namespace": namespace,
                    "key": str(key),
                    "ttl": ttl
                }
            )

            return True

        except Exception as e:
            logger.warning(
                f"Cache set failed for {namespace}:{key}: {e}",
                extra={"namespace": namespace, "key": str(key)}
            )
            return False

    def delete(self, namespace: str, key: Any) -> bool:
        """Delete value from cache.

        Args:
            namespace: Cache namespace
            key: Key to delete

        Returns:
            True if deleted, False if not found or error
        """
        cache_key = self._make_key(namespace, key)

        try:
            deleted = self.redis.delete(cache_key)

            if deleted:
                logger.debug(
                    f"Cache delete: {namespace}:{key}",
                    extra={"namespace": namespace, "key": str(key)}
                )

            return deleted > 0

        except Exception as e:
            logger.warning(
                f"Cache delete failed for {namespace}:{key}: {e}",
                extra={"namespace": namespace, "key": str(key)}
            )
            return False

    def delete_pattern(self, namespace: str, pattern: str = "*") -> int:
        """Delete all keys matching pattern in namespace.

        Args:
            namespace: Cache namespace
            pattern: Pattern to match (default: "*" = all)

        Returns:
            Number of keys deleted
        """
        try:
            search_pattern = f"cache:{namespace}:{pattern}"
            keys = self.redis.keys(search_pattern)

            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(
                    f"Deleted {deleted} keys from cache namespace {namespace}",
                    extra={"namespace": namespace, "count": deleted}
                )
                return deleted

            return 0

        except Exception as e:
            logger.warning(
                f"Cache pattern delete failed for {namespace}:{pattern}: {e}",
                extra={"namespace": namespace, "pattern": pattern}
            )
            return 0

    def flush_namespace(self, namespace: str) -> int:
        """Flush all keys in a namespace.

        Args:
            namespace: Cache namespace to flush

        Returns:
            Number of keys deleted
        """
        return self.delete_pattern(namespace, "*")

    def exists(self, namespace: str, key: Any) -> bool:
        """Check if key exists in cache.

        Args:
            namespace: Cache namespace
            key: Key to check

        Returns:
            True if key exists, False otherwise
        """
        cache_key = self._make_key(namespace, key)

        try:
            return self.redis.exists(cache_key) > 0
        except Exception as e:
            logger.warning(
                f"Cache exists check failed for {namespace}:{key}: {e}",
                extra={"namespace": namespace, "key": str(key)}
            )
            return False

    def get_ttl(self, namespace: str, key: Any) -> Optional[int]:
        """Get remaining TTL for a key.

        Args:
            namespace: Cache namespace
            key: Key to check

        Returns:
            TTL in seconds, or None if key doesn't exist or no expiration
        """
        cache_key = self._make_key(namespace, key)

        try:
            ttl = self.redis.ttl(cache_key)

            # ttl returns:
            # -2 if key doesn't exist
            # -1 if key exists but has no expiration
            # positive value = seconds until expiration
            if ttl == -2:
                return None  # Key doesn't exist
            elif ttl == -1:
                return None  # No expiration set
            else:
                return ttl

        except Exception as e:
            logger.warning(
                f"Cache TTL check failed for {namespace}:{key}: {e}",
                extra={"namespace": namespace, "key": str(key)}
            )
            return None


# Global cache instance
_cache_instance: Optional[CacheService] = None


def get_cache() -> CacheService:
    """Get global cache service instance.

    Returns:
        CacheService singleton
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = CacheService(redis_conn)
        logger.info("CacheService initialized")

    return _cache_instance
