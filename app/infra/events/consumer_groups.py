"""Redpanda consumer group configurations for priority-based event processing.

This module defines consumer groups that process events based on priority levels:
- High-Priority Group: CRITICAL and HIGH priority events (immediate processing)
- Batch Processing Group: BATCH priority events (scheduled batches)
- Scheduled Tasks Group: Scheduled/cron tasks
- Analytics Group: Analytics and metrics events
- Audit Group: Audit logging and compliance

Each consumer group runs independently with its own concurrency settings.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ConsumerGroupConfig:
    """Configuration for a Redpanda consumer group.

    Attributes:
        group_id: Unique identifier for this consumer group
        topics: List of Redpanda topics to consume from
        concurrency: Number of concurrent consumers/workers
        description: Human-readable description
        priority_filter: Optional priority levels this group handles
        max_poll_records: Maximum records to fetch per poll
        session_timeout_ms: Consumer session timeout
        heartbeat_interval_ms: Heartbeat interval
    """
    group_id: str
    topics: List[str]
    concurrency: int
    description: str
    priority_filter: List[str] = None
    max_poll_records: int = 10
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000


# =========================================================================
# HIGH-PRIORITY CONSUMER GROUP
# =========================================================================
# Processes CRITICAL and HIGH priority events immediately
# Use cases:
# - Creator onboarded (needs immediate workflow setup)
# - Workflow state changes (important transitions)
# - Critical system alerts (require immediate attention)

HIGH_PRIORITY_GROUP = ConsumerGroupConfig(
    group_id="high-priority-consumer-group",
    topics=[
        "creator_onboarded",     # New creator needs immediate setup
        "critical_alerts",       # System alerts
        "workflow_events",       # Workflow state changes
    ],
    concurrency=10,  # 10 concurrent workers for high throughput
    description="High-priority event processing (CRITICAL, HIGH)",
    priority_filter=["critical", "high"],
    max_poll_records=5,  # Smaller batches for faster processing
    session_timeout_ms=30000,
    heartbeat_interval_ms=3000,
)


# =========================================================================
# BATCH PROCESSING CONSUMER GROUP
# =========================================================================
# Processes BATCH and LOW priority events in scheduled batches
# Use cases:
# - Analytics events (can be batched)
# - Metric updates (aggregate in batches)
# - Low-priority notifications

BATCH_PROCESSING_GROUP = ConsumerGroupConfig(
    group_id="batch-processing-group",
    topics=[
        "analytics_events",      # Analytics data
        "workflow_events",       # Metric updates
    ],
    concurrency=2,  # Lower priority, fewer workers
    description="Batch processing for analytics and metrics (BATCH, LOW)",
    priority_filter=["batch", "low"],
    max_poll_records=100,  # Larger batches for efficiency
    session_timeout_ms=60000,
    heartbeat_interval_ms=10000,
)


# =========================================================================
# SCHEDULED TASKS CONSUMER GROUP
# =========================================================================
# Processes scheduled/cron-like tasks
# Use cases:
# - Periodic workflow checks
# - Scheduled reports
# - Cleanup tasks
# - Workflow timers

SCHEDULED_TASKS_GROUP = ConsumerGroupConfig(
    group_id="scheduled-tasks-group",
    topics=[
        "scheduled_tasks",       # Cron-like scheduled tasks
        "workflow_timers",       # Workflow delay/timer events
    ],
    concurrency=5,
    description="Scheduled task execution (cron, timers)",
    priority_filter=["normal"],
    max_poll_records=10,
    session_timeout_ms=45000,
    heartbeat_interval_ms=5000,
)


# =========================================================================
# ANALYTICS CONSUMER GROUP
# =========================================================================
# Processes analytics and metrics events
# Use cases:
# - Real-time dashboards
# - Metric aggregation
# - Performance tracking
# - Business intelligence

ANALYTICS_GROUP = ConsumerGroupConfig(
    group_id="analytics-consumer-group",
    topics=[
        "analytics_events",      # Analytics data points
        "workflow_events",       # Workflow metrics
    ],
    concurrency=3,
    description="Real-time analytics processing",
    priority_filter=None,  # Process all priorities for analytics
    max_poll_records=50,
    session_timeout_ms=60000,
    heartbeat_interval_ms=10000,
)


# =========================================================================
# AUDIT CONSUMER GROUP
# =========================================================================
# Processes audit logs and compliance events
# Use cases:
# - Audit trail logging
# - Compliance tracking
# - Security monitoring
# - Access logs

AUDIT_GROUP = ConsumerGroupConfig(
    group_id="audit-consumer-group",
    topics=[
        "audit_events",          # Audit logs
        "compliance_logs",       # Compliance tracking
    ],
    concurrency=2,
    description="Audit logging and compliance",
    priority_filter=None,  # Log all audit events regardless of priority
    max_poll_records=20,
    session_timeout_ms=60000,
    heartbeat_interval_ms=10000,
)


# =========================================================================
# WORKER TASK CONSUMER GROUP
# =========================================================================
# Processes tasks delegated by MainAgent to worker agents
# Use cases:
# - Worker agent task execution
# - Task result reporting

WORKER_TASK_GROUP = ConsumerGroupConfig(
    group_id="worker-task-consumer-group",
    topics=[
        "supervisor_tasks",      # Tasks from MainAgent to workers
        "task_results",          # Task completion results
    ],
    concurrency=8,  # High concurrency for worker tasks
    description="Worker agent task processing",
    priority_filter=None,  # Handle all task priorities
    max_poll_records=10,
    session_timeout_ms=45000,
    heartbeat_interval_ms=5000,
)


# =========================================================================
# ALL CONSUMER GROUPS
# =========================================================================

ALL_CONSUMER_GROUPS = [
    HIGH_PRIORITY_GROUP,
    BATCH_PROCESSING_GROUP,
    SCHEDULED_TASKS_GROUP,
    ANALYTICS_GROUP,
    AUDIT_GROUP,
    WORKER_TASK_GROUP,
]


def get_consumer_group(group_id: str) -> ConsumerGroupConfig:
    """Get consumer group configuration by ID.

    Args:
        group_id: Consumer group identifier

    Returns:
        Consumer group configuration

    Raises:
        ValueError: If group_id not found
    """
    for group in ALL_CONSUMER_GROUPS:
        if group.group_id == group_id:
            return group

    raise ValueError(f"Consumer group not found: {group_id}")


def get_consumer_groups_for_topic(topic: str) -> List[ConsumerGroupConfig]:
    """Get all consumer groups that subscribe to a topic.

    Args:
        topic: Redpanda topic name

    Returns:
        List of consumer group configurations
    """
    return [
        group for group in ALL_CONSUMER_GROUPS
        if topic in group.topics
    ]


def get_high_priority_groups() -> List[ConsumerGroupConfig]:
    """Get consumer groups that handle high-priority events.

    Returns:
        List of high-priority consumer groups
    """
    return [
        group for group in ALL_CONSUMER_GROUPS
        if group.priority_filter and "high" in group.priority_filter
    ]


def get_batch_processing_groups() -> List[ConsumerGroupConfig]:
    """Get consumer groups that handle batch processing.

    Returns:
        List of batch processing consumer groups
    """
    return [
        group for group in ALL_CONSUMER_GROUPS
        if group.priority_filter and "batch" in group.priority_filter
    ]
