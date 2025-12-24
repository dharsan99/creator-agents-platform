#!/usr/bin/env python3
"""Initialize Redpanda topics for event streaming."""
import time
import logging
from confluent_kafka.admin import AdminClient, NewTopic, ConfigResource, ConfigSource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TOPICS = {
    "events": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {
            "retention.ms": "604800000",  # 7 days
            "segment.ms": "86400000",  # 1 day
        },
    },
    "agent-invocations": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {
            "retention.ms": "604800000",  # 7 days
        },
    },
    "actions": {
        "partitions": 3,
        "replication_factor": 1,
        "config": {
            "retention.ms": "604800000",  # 7 days
        },
    },
    "dlq-agents": {
        "partitions": 1,
        "replication_factor": 1,
        "config": {
            "retention.ms": "2592000000",  # 30 days
        },
    },
    "dlq-actions": {
        "partitions": 1,
        "replication_factor": 1,
        "config": {
            "retention.ms": "2592000000",  # 30 days
        },
    },
}


def wait_for_redpanda(bootstrap_servers: str, timeout: int = 60) -> bool:
    """Wait for Redpanda to be ready.

    Args:
        bootstrap_servers: Redpanda bootstrap servers
        timeout: Timeout in seconds

    Returns:
        True if Redpanda is ready, False otherwise
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            admin = AdminClient({"bootstrap.servers": bootstrap_servers})
            # Try to get metadata
            md = admin.list_topics(timeout=5)
            logger.info("✅ Redpanda is ready")
            return True
        except Exception as e:
            logger.debug(f"Redpanda not ready yet: {e}")
            time.sleep(2)

    logger.error("❌ Timeout waiting for Redpanda")
    return False


def create_topics(bootstrap_servers: str = "redpanda:9092"):
    """Create all required topics in Redpanda.

    Args:
        bootstrap_servers: Redpanda bootstrap servers
    """
    logger.info("🚀 Initializing Redpanda topics...")
    logger.info(f"Bootstrap servers: {bootstrap_servers}")

    # Wait for Redpanda to be ready
    if not wait_for_redpanda(bootstrap_servers):
        logger.error("Redpanda failed to start")
        return False

    # Create admin client
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    # List existing topics
    md = admin.list_topics(timeout=10)
    existing_topics = set(md.topics.keys())
    logger.info(f"Existing topics: {existing_topics}")

    # Create new topics
    new_topics = []

    for topic_name, config in TOPICS.items():
        if topic_name in existing_topics:
            logger.info(f"✅ Topic '{topic_name}' already exists")
            continue

        logger.info(f"📝 Creating topic: {topic_name}")
        logger.info(f"   Partitions: {config['partitions']}")
        logger.info(f"   Replication: {config['replication_factor']}")

        new_topic = NewTopic(
            topic_name,
            num_partitions=config["partitions"],
            replication_factor=config["replication_factor"],
            config=config.get("config", {}),
        )
        new_topics.append(new_topic)

    if not new_topics:
        logger.info("✅ All topics already exist")
        return True

    # Create topics
    try:
        fs = admin.create_topics(new_topics, validate_only=False)

        # Wait for operation to complete
        for topic, f in fs.items():
            try:
                f.result(timeout=30)
                logger.info(f"✅ Topic '{topic}' created successfully")
            except Exception as e:
                logger.error(f"❌ Failed to create topic '{topic}': {e}")
                return False

        logger.info("✅ All Redpanda topics initialized successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Error creating topics: {e}")
        return False


if __name__ == "__main__":
    import sys

    bootstrap_servers = sys.argv[1] if len(sys.argv) > 1 else "redpanda:9092"

    success = create_topics(bootstrap_servers)
    sys.exit(0 if success else 1)
