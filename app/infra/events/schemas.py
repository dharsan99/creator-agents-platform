"""Event schemas for Redpanda event streaming with priority levels.

This module defines structured event schemas for multi-service communication.
All events inherit from BaseEvent which includes priority levels for queue routing.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventPriority(str, Enum):
    """Priority levels for event processing.

    Used by consumer groups to route events to appropriate queues:
    - CRITICAL: Immediate processing, high-priority queue
    - HIGH: Fast processing, high-priority queue
    - NORMAL: Standard processing, default queue
    - LOW: Delayed processing, batch queue
    - BATCH: Scheduled batch processing
    """
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BATCH = "batch"


class EventSource(str, Enum):
    """Source systems that emit events."""
    ONBOARDING_SERVICE = "onboarding_service"
    CREATOR_ONBOARDING_SERVICE = "creator_onboarding_service"  # Legacy/alternative name
    AGENT_PLATFORM = "agent_platform"
    EXTERNAL = "external"
    SYSTEM = "system"


class BaseEvent(BaseModel):
    """Base event class for all events in the system.

    All events must inherit from this class to ensure consistent structure
    and priority-based routing across consumer groups.

    Attributes:
        event_id: Unique identifier for this event instance
        event_type: Type/name of the event (e.g., "creator_onboarded")
        timestamp: When the event occurred
        priority: Priority level for queue routing
        source: System that emitted this event
        metadata: Optional metadata for tracing, correlation, etc.
    """
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: EventPriority
    source: EventSource
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class CreatorOnboardedEvent(BaseEvent):
    """Event emitted when a creator completes onboarding.

    Emitted by: creator-onboarding-service
    Consumed by: creator-agents-platform (MainAgent)
    Priority: HIGH (requires immediate workflow setup)

    This event triggers the MainAgent to:
    1. Analyze creator purpose and goals
    2. Plan workflow stages dynamically
    3. Delegate initial tasks to worker agents
    4. Start monitoring metrics

    Attributes:
        creator_id: UUID of the onboarded creator
        worker_agent_ids: List of worker agent UUIDs created for this creator
        consumers: List of consumer UUIDs in the cohort
        purpose: Creator's purpose (sales, coaching, content, community, etc.)
        start_date: Campaign/cohort start date
        end_date: Campaign/cohort end date (optional)
        goal: Creator's specific goal (e.g., "convert_max_consumers")
        config: Creator-specific configuration (profile, preferences, etc.)
    """
    event_type: str = "creator_onboarded"
    priority: EventPriority = EventPriority.HIGH
    source: EventSource = EventSource.CREATOR_ONBOARDING_SERVICE  # Accept actual service name

    # Event-specific data
    creator_id: UUID
    worker_agent_ids: List[UUID]
    consumers: List[UUID]
    purpose: str  # Generic: sales, coaching, content, community, etc.
    start_date: datetime
    end_date: Optional[datetime] = None  # Made optional to match onboarding service
    goal: str
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkerTaskEvent(BaseEvent):
    """Event for assigning tasks to worker agents.

    Emitted by: creator-agents-platform (MainAgent)
    Consumed by: creator-agents-platform (Worker Agents)
    Priority: Variable (based on task urgency)

    Topic: supervisor_tasks

    Attributes:
        task_id: UUID of the task
        workflow_execution_id: UUID of the workflow this task belongs to
        agent_id: UUID of the worker agent to execute this task
        consumer_id: UUID of the consumer this task relates to
        task_type: Type of task (e.g., "create_intro_email", "create_followup")
        task_payload: Task-specific parameters and context
        deadline: Optional deadline for task completion
    """
    event_type: str = "worker_task_assigned"
    priority: EventPriority  # Set dynamically based on urgency
    source: EventSource = EventSource.AGENT_PLATFORM

    task_id: UUID
    workflow_execution_id: UUID
    agent_id: UUID
    consumer_id: UUID
    task_type: str
    task_payload: Dict[str, Any]
    deadline: Optional[datetime] = None


class WorkerTaskCompletedEvent(BaseEvent):
    """Event emitted when a worker completes a task.

    Emitted by: creator-agents-platform (Worker Agents)
    Consumed by: creator-agents-platform (MainAgent)
    Priority: NORMAL (result reporting)

    Topic: task_results

    Attributes:
        task_id: UUID of the completed task
        workflow_execution_id: UUID of the workflow
        agent_id: UUID of the worker that completed the task
        consumer_id: UUID of the consumer
        result: Task execution result data
        success: Whether the task completed successfully
        error: Error message if task failed
        execution_time_ms: How long the task took
        missing_tools: List of tools the agent needed but were unavailable
    """
    event_type: str = "worker_task_completed"
    priority: EventPriority = EventPriority.NORMAL
    source: EventSource = EventSource.AGENT_PLATFORM

    task_id: UUID
    workflow_execution_id: UUID
    agent_id: UUID
    consumer_id: UUID
    result: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    execution_time_ms: float
    missing_tools: List[str] = Field(default_factory=list)


class WorkflowMetricUpdateEvent(BaseEvent):
    """Event for updating workflow metrics in real-time.

    Emitted by: creator-agents-platform (Agents, Workers)
    Consumed by: creator-agents-platform (MainAgent, Analytics)
    Priority: BATCH (metrics can be processed in batches)

    Topic: workflow_events

    Attributes:
        workflow_execution_id: UUID of the workflow
        creator_id: UUID of the creator
        metric_type: Type of metric (e.g., "email_opened", "booking_completed")
        metric_value: Numeric value of the metric
        dimensions: Additional dimensions (consumer_id, channel, etc.)
    """
    event_type: str = "workflow_metric_update"
    priority: EventPriority = EventPriority.BATCH
    source: EventSource = EventSource.AGENT_PLATFORM

    workflow_execution_id: UUID
    creator_id: UUID
    metric_type: str
    metric_value: float
    dimensions: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsEvent(BaseEvent):
    """Event for analytics data processing.

    Emitted by: Multiple services
    Consumed by: Analytics service
    Priority: BATCH (can be processed in scheduled batches)

    Topic: analytics_events

    Attributes:
        entity_type: Type of entity (creator, consumer, agent, workflow)
        entity_id: UUID of the entity
        metric_type: Type of metric being tracked
        metric_value: Numeric value
        dimensions: Additional context (tags, attributes)
    """
    event_type: str = "analytics_event"
    priority: EventPriority = EventPriority.BATCH
    source: EventSource

    entity_type: str
    entity_id: UUID
    metric_type: str
    metric_value: float
    dimensions: Dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseEvent):
    """Event for audit logging and compliance.

    Emitted by: All services
    Consumed by: Audit service
    Priority: NORMAL (must be logged reliably)

    Topic: audit_events

    Attributes:
        actor_id: UUID of the user/system that performed the action
        actor_type: Type of actor (user, agent, system)
        action: Action performed (create, update, delete, execute)
        resource_type: Type of resource affected
        resource_id: UUID of the resource
        changes: What changed (before/after for updates)
        ip_address: Optional IP address for security tracking
    """
    event_type: str = "audit_event"
    priority: EventPriority = EventPriority.NORMAL
    source: EventSource

    actor_id: UUID
    actor_type: str
    action: str
    resource_type: str
    resource_id: UUID
    changes: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None


class WorkflowStateChangeEvent(BaseEvent):
    """Event for workflow state transitions.

    Emitted by: creator-agents-platform (MainAgent)
    Consumed by: creator-agents-platform (Dashboard, Analytics)
    Priority: HIGH (state changes are important)

    Topic: workflow_events

    Attributes:
        workflow_execution_id: UUID of the workflow
        workflow_id: UUID of the workflow definition
        creator_id: UUID of the creator
        old_state: Previous state
        new_state: New state (running, paused, completed, failed)
        reason: Reason for state change
    """
    event_type: str = "workflow_state_change"
    priority: EventPriority = EventPriority.HIGH
    source: EventSource = EventSource.AGENT_PLATFORM

    workflow_execution_id: UUID
    workflow_id: UUID
    creator_id: UUID
    old_state: str
    new_state: str
    reason: str


class CriticalAlertEvent(BaseEvent):
    """Event for critical system alerts requiring immediate attention.

    Emitted by: All services
    Consumed by: Monitoring/alerting service
    Priority: CRITICAL (highest priority)

    Topic: critical_alerts

    Attributes:
        alert_type: Type of alert (error, failure, breach, etc.)
        severity: Severity level (critical, error, warning)
        message: Human-readable alert message
        details: Additional diagnostic details
        affected_entities: List of affected entity IDs
    """
    event_type: str = "critical_alert"
    priority: EventPriority = EventPriority.CRITICAL
    source: EventSource

    alert_type: str
    severity: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    affected_entities: List[UUID] = Field(default_factory=list)


class ScheduledTaskEvent(BaseEvent):
    """Event for scheduled/cron-like tasks.

    Emitted by: Scheduler service
    Consumed by: Task execution service
    Priority: NORMAL (scheduled, not urgent)

    Topic: scheduled_tasks

    Attributes:
        schedule_id: UUID of the schedule definition
        task_type: Type of task to execute
        task_payload: Task parameters
        scheduled_time: When this task was scheduled to run
    """
    event_type: str = "scheduled_task"
    priority: EventPriority = EventPriority.NORMAL
    source: EventSource = EventSource.SYSTEM

    schedule_id: UUID
    task_type: str
    task_payload: Dict[str, Any]
    scheduled_time: datetime


# Event type registry for deserialization
EVENT_TYPE_REGISTRY: Dict[str, type[BaseEvent]] = {
    "creator_onboarded": CreatorOnboardedEvent,
    "worker_task_assigned": WorkerTaskEvent,
    "worker_task_completed": WorkerTaskCompletedEvent,
    "workflow_metric_update": WorkflowMetricUpdateEvent,
    "analytics_event": AnalyticsEvent,
    "audit_event": AuditEvent,
    "workflow_state_change": WorkflowStateChangeEvent,
    "critical_alert": CriticalAlertEvent,
    "scheduled_task": ScheduledTaskEvent,
}


def deserialize_event(event_data: Dict[str, Any]) -> BaseEvent:
    """Deserialize event JSON to the appropriate event class.

    Args:
        event_data: Event data as dictionary

    Returns:
        Typed event instance

    Raises:
        ValueError: If event_type is not registered
    """
    event_type = event_data.get("event_type")

    if not event_type:
        raise ValueError("Event data missing 'event_type' field")

    event_class = EVENT_TYPE_REGISTRY.get(event_type)

    if not event_class:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_class(**event_data)
