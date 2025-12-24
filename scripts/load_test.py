"""Load testing script for Creator Agents Platform.

This script simulates realistic load patterns for the platform:
- Event ingestion
- Agent invocations
- Workflow management
- API queries

Usage:
    # Install locust first
    pip install locust

    # Run load test
    locust -f scripts/load_test.py --host=http://localhost:8000

    # Then open http://localhost:8089 to configure and start the test
"""

import json
import random
from uuid import uuid4

from locust import HttpUser, task, between, events


class CreatorAgentUser(HttpUser):
    """Simulates a user/service interacting with the Creator Agents Platform."""

    # Wait 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize test data on user start."""
        # Create test creator and consumer
        self.creator_id = str(uuid4())
        self.consumer_id = str(uuid4())
        self.workflow_id = None
        self.agent_id = None

        # Health check
        self.client.get("/health")

    @task(10)
    def ingest_event(self):
        """Simulate event ingestion (most common operation)."""
        event_types = ["page_view", "service_click", "email_opened", "cta_clicked"]
        event_type = random.choice(event_types)

        payload = {
            "consumer_id": self.consumer_id,
            "type": event_type,
            "source": "api",
            "payload": {
                "session_id": str(uuid4()),
                "timestamp": "2025-01-15T10:00:00Z"
            }
        }

        with self.client.post(
            "/events",
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Event ingestion failed: {response.text}")

    @task(5)
    def get_metrics_summary(self):
        """Get performance metrics summary."""
        with self.client.get(
            "/performance/metrics-summary",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics summary failed: {response.text}")

    @task(3)
    def get_health_status(self):
        """Get detailed health status."""
        with self.client.get(
            "/performance/health",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure(f"System unhealthy: {data}")
            else:
                response.failure(f"Health check failed: {response.text}")

    @task(2)
    def get_prometheus_metrics(self):
        """Get Prometheus metrics."""
        with self.client.get(
            "/metrics",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Prometheus metrics failed: {response.text}")

    @task(2)
    def query_agents(self):
        """Query agents."""
        with self.client.get(
            "/agents",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Agent query failed: {response.text}")

    @task(1)
    def get_dlq_stats(self):
        """Get dead letter queue statistics."""
        with self.client.get(
            "/dlq/stats",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"DLQ stats failed: {response.text}")

    @task(1)
    def get_system_stats(self):
        """Get system statistics."""
        with self.client.get(
            "/performance/system-stats",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"System stats failed: {response.text}")


class WorkflowUser(HttpUser):
    """Simulates MainAgent workflow operations (less frequent, heavier)."""

    # Wait 5-15 seconds between tasks (workflows are less frequent)
    wait_time = between(5, 15)

    def on_start(self):
        """Initialize test data."""
        self.creator_id = str(uuid4())
        self.workflow_id = None
        self.execution_id = None

    @task(2)
    def get_workflow_performance(self):
        """Get workflow performance metrics."""
        with self.client.get(
            "/performance/workflow-performance?limit=10",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Workflow performance query failed: {response.text}")

    @task(1)
    def get_slow_queries(self):
        """Get slow operations."""
        with self.client.get(
            "/performance/slow-queries?hours=1&limit=10",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Slow queries failed: {response.text}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("\n" + "="*80)
    print("Starting Creator Agents Platform Load Test")
    print("="*80)
    print(f"Host: {environment.host}")
    print(f"Users will ramp up over time...")
    print("="*80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "="*80)
    print("Load Test Completed")
    print("="*80)
    print("Check the results at http://localhost:8089")
    print("="*80 + "\n")


if __name__ == "__main__":
    """
    Direct execution for quick testing (without Locust web UI).

    Usage:
        python scripts/load_test.py

    For full load testing with web UI, use:
        locust -f scripts/load_test.py --host=http://localhost:8000
    """
    import sys
    sys.exit(
        "Run with: locust -f scripts/load_test.py --host=http://localhost:8000"
    )
