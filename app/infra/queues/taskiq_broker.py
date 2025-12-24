"""Taskiq broker configuration for async task execution with DLQ support."""
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from app.config import settings
from app.infra.queues.dlq_middleware import DLQMiddleware

# Create Redis list-based broker for Taskiq (reliable queue)
broker = (
    ListQueueBroker(url=settings.redis_url)
    .with_result_backend(RedisAsyncResultBackend(redis_url=settings.redis_url))
    .with_middlewares(DLQMiddleware())
)
