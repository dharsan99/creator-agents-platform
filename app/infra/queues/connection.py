"""Redis queue connection management."""
import redis
from rq import Queue

from app.config import settings

# Create Redis connection
redis_conn = redis.from_url(settings.redis_url)

# Create queues
default_queue = Queue("default", connection=redis_conn)
agents_queue = Queue("agents", connection=redis_conn)
actions_queue = Queue("actions", connection=redis_conn)
