"""RQ worker script.

Run this script to start a worker that processes background jobs:
    python -m app.infra.queues.worker
"""
import logging

from rq import Worker

from app.infra.queues.connection import redis_conn, agents_queue, actions_queue, default_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Start RQ worker."""
    logger.info("Starting RQ worker...")

    # Listen on multiple queues
    queues = [agents_queue, actions_queue, default_queue]

    worker = Worker(
        queues,
        connection=redis_conn,
        name="creator-agents-worker",
    )

    logger.info(f"Worker listening on queues: {[q.name for q in queues]}")
    worker.work()


if __name__ == "__main__":
    main()
