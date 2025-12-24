"""Metrics collection service using Prometheus.

This service tracks key metrics for the supervisor-worker architecture:
- Agent execution metrics (MainAgent, WorkerAgent)
- Tool execution metrics
- Workflow metrics
- Task metrics
- Conversation metrics
- System health metrics
"""

import logging
import time
from typing import Optional
from functools import wraps

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    generate_latest,
    CollectorRegistry,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and exposing Prometheus metrics.

    Usage:
        metrics = get_metrics()
        metrics.agent_executions.labels(agent_name="MainAgent", status="success").inc()
        metrics.tool_execution_time.labels(tool_name="send_email").observe(1.5)
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics service.

        Args:
            registry: Optional Prometheus registry (default: global registry)
        """
        self.registry = registry

        # Agent Execution Metrics
        self.agent_executions = Counter(
            "agent_executions_total",
            "Total number of agent executions",
            ["agent_name", "status"],
            registry=registry
        )

        self.agent_execution_time = Histogram(
            "agent_execution_seconds",
            "Agent execution time in seconds",
            ["agent_name"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=registry
        )

        self.agent_decision_time = Histogram(
            "agent_decision_seconds",
            "Agent decision-making time (should_act + plan_actions)",
            ["agent_name"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
            registry=registry
        )

        # Tool Execution Metrics
        self.tool_executions = Counter(
            "tool_executions_total",
            "Total number of tool executions",
            ["tool_name", "status"],
            registry=registry
        )

        self.tool_execution_time = Histogram(
            "tool_execution_seconds",
            "Tool execution time in seconds",
            ["tool_name"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=registry
        )

        self.tool_timeouts = Counter(
            "tool_timeouts_total",
            "Total number of tool timeouts",
            ["tool_name"],
            registry=registry
        )

        self.tool_retries = Counter(
            "tool_retries_total",
            "Total number of tool retries",
            ["tool_name"],
            registry=registry
        )

        self.missing_tool_requests = Counter(
            "missing_tool_requests_total",
            "Total number of missing tool requests logged",
            ["tool_name", "category"],
            registry=registry
        )

        # Workflow Metrics
        self.workflows_created = Counter(
            "workflows_created_total",
            "Total number of workflows created",
            ["purpose", "workflow_type"],
            registry=registry
        )

        self.workflow_versions = Counter(
            "workflow_versions_total",
            "Total number of workflow versions created",
            ["workflow_id"],
            registry=registry
        )

        self.workflow_executions = Gauge(
            "workflow_executions_active",
            "Number of active workflow executions",
            ["status"],
            registry=registry
        )

        self.workflow_execution_time = Histogram(
            "workflow_execution_seconds",
            "Workflow execution time from start to completion",
            ["purpose"],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800],  # 1m to 8h
            registry=registry
        )

        self.workflow_stages_completed = Counter(
            "workflow_stages_completed_total",
            "Total number of workflow stages completed",
            ["purpose", "stage"],
            registry=registry
        )

        # Task Metrics
        self.tasks_created = Counter(
            "tasks_created_total",
            "Total number of worker tasks created",
            ["task_type"],
            registry=registry
        )

        self.tasks_completed = Counter(
            "tasks_completed_total",
            "Total number of tasks completed",
            ["task_type", "status"],
            registry=registry
        )

        self.task_execution_time = Histogram(
            "task_execution_seconds",
            "Task execution time in seconds",
            ["task_type"],
            buckets=[1, 5, 10, 30, 60, 120, 300],
            registry=registry
        )

        self.task_retries = Counter(
            "task_retries_total",
            "Total number of task retries",
            ["task_type"],
            registry=registry
        )

        self.tasks_in_queue = Gauge(
            "tasks_in_queue",
            "Number of tasks in queue by status",
            ["status"],
            registry=registry
        )

        # Conversation/Escalation Metrics
        self.escalations = Counter(
            "escalations_total",
            "Total number of escalations to human",
            ["reason"],
            registry=registry
        )

        self.conversations_active = Gauge(
            "conversations_active",
            "Number of active conversations",
            ["status"],
            registry=registry
        )

        self.conversation_resolution_time = Histogram(
            "conversation_resolution_seconds",
            "Time to resolve conversations",
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400],  # 1m to 4h
            registry=registry
        )

        self.messages_sent = Counter(
            "messages_sent_total",
            "Total number of messages sent",
            ["sender_type"],
            registry=registry
        )

        # Event Processing Metrics
        self.events_processed = Counter(
            "events_processed_total",
            "Total number of events processed",
            ["event_type", "consumer_group"],
            registry=registry
        )

        self.event_processing_time = Histogram(
            "event_processing_seconds",
            "Event processing time in seconds",
            ["event_type", "consumer_group"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=registry
        )

        self.event_processing_errors = Counter(
            "event_processing_errors_total",
            "Total number of event processing errors",
            ["event_type", "consumer_group", "error_type"],
            registry=registry
        )

        # System Health Metrics
        self.http_requests = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=registry
        )

        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=registry
        )

        self.database_query_time = Summary(
            "database_query_seconds",
            "Database query execution time",
            ["query_type"],
            registry=registry
        )

        self.cache_hits = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=registry
        )

        self.cache_misses = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=registry
        )

        # LLM Metrics
        self.llm_requests = Counter(
            "llm_requests_total",
            "Total LLM API requests",
            ["model", "purpose"],
            registry=registry
        )

        self.llm_request_time = Histogram(
            "llm_request_seconds",
            "LLM API request time",
            ["model"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
            registry=registry
        )

        self.llm_tokens = Counter(
            "llm_tokens_total",
            "Total LLM tokens used",
            ["model", "token_type"],
            registry=registry
        )

        logger.info("MetricsService initialized with Prometheus metrics")

    def track_agent_execution(self, agent_name: str):
        """Context manager for tracking agent execution.

        Usage:
            with metrics.track_agent_execution("MainAgent"):
                # Execute agent logic
                pass
        """
        return _ExecutionTracker(
            self.agent_execution_time.labels(agent_name=agent_name),
            self.agent_executions.labels(agent_name=agent_name)
        )

    def track_tool_execution(self, tool_name: str):
        """Context manager for tracking tool execution.

        Usage:
            with metrics.track_tool_execution("send_email"):
                # Execute tool
                pass
        """
        return _ExecutionTracker(
            self.tool_execution_time.labels(tool_name=tool_name),
            self.tool_executions.labels(tool_name=tool_name)
        )

    def track_task_execution(self, task_type: str):
        """Context manager for tracking task execution.

        Usage:
            with metrics.track_task_execution("create_intro_email"):
                # Execute task
                pass
        """
        return _ExecutionTracker(
            self.task_execution_time.labels(task_type=task_type),
            self.tasks_completed.labels(task_type=task_type)
        )

    def track_event_processing(self, event_type: str, consumer_group: str):
        """Context manager for tracking event processing.

        Usage:
            with metrics.track_event_processing("creator_onboarded", "high-priority"):
                # Process event
                pass
        """
        return _ExecutionTracker(
            self.event_processing_time.labels(
                event_type=event_type,
                consumer_group=consumer_group
            ),
            self.events_processed.labels(
                event_type=event_type,
                consumer_group=consumer_group
            )
        )

    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get content type for metrics endpoint.

        Returns:
            Content type string
        """
        return CONTENT_TYPE_LATEST


class _ExecutionTracker:
    """Context manager for tracking execution time and status."""

    def __init__(self, timer, counter):
        self.timer = timer
        self.counter = counter
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.timer.observe(duration)

        if exc_type is None:
            self.counter.labels(status="success").inc()
        else:
            self.counter.labels(status="error").inc()

        return False  # Don't suppress exceptions


# Global metrics instance
_metrics_instance: Optional[MetricsService] = None


def get_metrics() -> MetricsService:
    """Get global metrics service instance.

    Returns:
        MetricsService singleton
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsService()
    return _metrics_instance


def track_execution(metric_name: str):
    """Decorator for tracking function execution time and status.

    Usage:
        @track_execution("agent_execution")
        def execute_agent(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success
                if hasattr(metrics, f"{metric_name}_time"):
                    getattr(metrics, f"{metric_name}_time").observe(duration)

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record failure
                if hasattr(metrics, f"{metric_name}_errors"):
                    getattr(metrics, f"{metric_name}_errors").inc()

                raise

        return wrapper
    return decorator
