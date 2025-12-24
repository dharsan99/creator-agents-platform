#!/usr/bin/env python3
"""Initialize Redpanda topics using REST API."""
import requests
import time
import sys

REDPANDA_ADMIN = "http://redpanda:9644"
TOPICS = [
    {
        "name": "events",
        "num_partitions": 3,
        "replication_factor": 1,
    },
    {
        "name": "agent-invocations",
        "num_partitions": 3,
        "replication_factor": 1,
    },
    {
        "name": "actions",
        "num_partitions": 3,
        "replication_factor": 1,
    },
    {
        "name": "dlq-agents",
        "num_partitions": 1,
        "replication_factor": 1,
    },
    {
        "name": "dlq-actions",
        "num_partitions": 1,
        "replication_factor": 1,
    },
]


def wait_for_redpanda(timeout=60):
    """Wait for Redpanda to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{REDPANDA_ADMIN}/v1/status/ready", timeout=5)
            if response.status_code == 200:
                print("✅ Redpanda is ready")
                return True
        except Exception as e:
            print(f"⏳ Waiting for Redpanda... ({e})")
            time.sleep(2)
    print("❌ Timeout waiting for Redpanda")
    return False


def get_existing_topics():
    """Get list of existing topics."""
    try:
        response = requests.get(f"{REDPANDA_ADMIN}/v1/metadata/topics", timeout=10)
        if response.status_code == 200:
            topics = response.json()
            return [t["name"] for t in topics]
    except Exception as e:
        print(f"Error getting topics: {e}")
    return []


def create_topic(topic):
    """Create a single topic."""
    try:
        payload = {
            "topic": topic["name"],
            "num_partitions": topic["num_partitions"],
            "replication_factor": topic["replication_factor"],
        }

        response = requests.post(
            f"{REDPANDA_ADMIN}/v1/topics",
            json=payload,
            timeout=10,
        )

        if response.status_code == 200:
            print(f"✅ Topic '{topic['name']}' created successfully")
            return True
        elif response.status_code == 409:
            print(f"ℹ️  Topic '{topic['name']}' already exists")
            return True
        else:
            print(f"❌ Failed to create topic '{topic['name']}': {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating topic '{topic['name']}': {e}")
        return False


def main():
    """Main entry point."""
    print("🚀 Initializing Redpanda topics via REST API...")
    print(f"Admin API: {REDPANDA_ADMIN}")

    if not wait_for_redpanda():
        return False

    # Get existing topics
    print("\n📋 Checking existing topics...")
    existing = get_existing_topics()
    print(f"Found {len(existing)} existing topics")

    # Create new topics
    print("\n📝 Creating topics...")
    all_success = True

    for topic in TOPICS:
        if topic["name"] in existing:
            print(f"ℹ️  Topic '{topic['name']}' already exists")
        else:
            if not create_topic(topic):
                all_success = False

    if all_success:
        print("\n✅ All Redpanda topics initialized successfully!")
        print("\n📊 Topics summary:")
        for topic in TOPICS:
            print(f"  - {topic['name']}: {topic['num_partitions']} partitions")
        return True
    else:
        print("\n❌ Some topics failed to create")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
