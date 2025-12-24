"""Workflow models with versioning support.

This module defines the workflow system that enables purpose-agnostic,
dynamic workflow planning and execution with full version control.

Key Concepts:
- Workflow: Definition of a workflow (purpose, stages, tools)
- WorkflowVersion: Historical versions with change tracking
- WorkflowExecution: Runtime state of a workflow instance

Architecture:
- MainAgent creates workflows based on creator purpose
- Workflows are versioned - every change creates a new version
- Executions track runtime state and metrics
- Missing tools are logged but don't block workflow creation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class Workflow(SQLModel, table=True):
    """Purpose-agnostic workflow definition.

    Workflows are NOT limited to sales - they support any creator purpose:
    - Sales/conversion campaigns
    - Cohort-based programs
    - Content creation schedules
    - Community engagement
    - Coaching programs
    - Event management

    Attributes:
        id: Workflow UUID
        creator_id: Creator who owns this workflow
        worker_agent_ids: List of worker agent UUIDs for task execution
        purpose: Generic purpose (sales, coaching, content, community, etc.)
        workflow_type: Type (sequential, parallel, conditional, event_driven)
        start_date: Workflow start date
        end_date: Workflow end date
        goal: Creator's specific goal
        version: Current version number
        stages: List of workflow stages with actions and conditions
        metrics_thresholds: Decision rules based on metrics
        available_tools: Tools available when created
        missing_tools: Tools needed but unavailable (logged for future)
        created_at: Creation timestamp
        created_by: Who/what created this workflow (MainAgent, Human, System)
    """
    __tablename__ = "workflows"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(index=True)
    worker_agent_ids: List[UUID] = Field(sa_column=Column(JSON))

    # Purpose-agnostic fields
    purpose: str = Field(index=True)  # sales, coaching, content, community, etc.
    workflow_type: str  # sequential, parallel, conditional, event_driven
    start_date: datetime
    end_date: datetime
    goal: str  # Creator's goal description

    # Versioning
    version: int = Field(default=1)

    # Workflow definition
    stages: Dict[str, Any] = Field(sa_column=Column(JSON))
    # Example stages structure:
    # {
    #     "intro": {
    #         "day": 1,
    #         "actions": ["send_intro_email", "send_whatsapp_welcome"],
    #         "conditions": {"page_views": ">= 1"},
    #         "required_tools": ["send_email", "send_whatsapp"],
    #         "fallback_actions": ["log_missing_tool"]
    #     },
    #     "engagement": {
    #         "day": 3,
    #         "actions": ["send_value_content"],
    #         "conditions": {"emails_opened": ">= 1"},
    #         "required_tools": ["send_email"]
    #     }
    # }

    metrics_thresholds: Dict[str, Any] = Field(sa_column=Column(JSON))
    # Example thresholds:
    # {
    #     "email_open_rate": {"threshold": 0.2, "action": "adjust_subject_lines"},
    #     "click_through_rate": {"threshold": 0.1, "action": "improve_cta"},
    #     "conversion_rate": {"threshold": 0.05, "action": "escalate_to_human"}
    # }

    # Tool availability tracking
    available_tools: List[str] = Field(sa_column=Column(JSON))
    missing_tools: List[Dict[str, Any]] = Field(sa_column=Column(JSON), default=[])
    # Example missing_tools:
    # [
    #     {
    #         "name": "send_telegram",
    #         "reason": "Tool not implemented",
    #         "alternative_action": "send_whatsapp",
    #         "priority": "medium"
    #     }
    # ]

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "MainAgent"  # MainAgent, Human, System
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    versions: List["WorkflowVersion"] = Relationship(back_populates="workflow")
    executions: List["WorkflowExecution"] = Relationship(back_populates="workflow")


class WorkflowVersion(SQLModel, table=True):
    """Historical version of a workflow with change tracking.

    Every workflow modification creates a new version with:
    - Full snapshot of changes
    - Reasoning for the change
    - Diff showing what changed
    - Who/what made the change

    Attributes:
        id: Version UUID
        workflow_id: Parent workflow
        version: Version number
        previous_version: Previous version number (if any)
        changes: What changed (JSON description)
        reason: Why the change was made
        changed_by: Who made the change (MainAgent, Human, System)
        diff: JSON diff of the changes
        created_at: When this version was created
        workflow: Relationship to parent workflow
    """
    __tablename__ = "workflow_versions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workflow_id: UUID = Field(foreign_key="workflows.id", index=True)
    version: int = Field(index=True)
    previous_version: Optional[int] = None

    # Change tracking
    changes: Dict[str, Any] = Field(sa_column=Column(JSON))
    # Example changes:
    # {
    #     "stages_added": ["followup"],
    #     "stages_modified": ["intro"],
    #     "metrics_thresholds_updated": ["email_open_rate"],
    #     "tools_added": ["send_sms"]
    # }

    reason: str  # Why this change was made
    changed_by: str  # MainAgent, Human, System

    diff: Dict[str, Any] = Field(sa_column=Column(JSON))
    # Example diff:
    # {
    #     "stages.intro.actions": {
    #         "old": ["send_intro_email"],
    #         "new": ["send_intro_email", "send_whatsapp_welcome"]
    #     },
    #     "metrics_thresholds.email_open_rate.threshold": {
    #         "old": 0.2,
    #         "new": 0.15
    #     }
    # }

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    workflow: Workflow = Relationship(back_populates="versions")


class WorkflowExecution(SQLModel, table=True):
    """Runtime state of a workflow execution.

    Tracks the execution of a workflow for a specific cohort/campaign:
    - Current stage and status
    - Real-time metrics
    - Decision log (what MainAgent decided and why)
    - Tool usage tracking
    - Missing tool impact analysis

    Attributes:
        id: Execution UUID
        workflow_id: Workflow definition being executed
        workflow_version: Version of workflow being executed
        creator_id: Creator who owns this execution
        consumer_ids: List of consumer UUIDs in this execution
        current_stage: Current workflow stage
        status: Execution status (running, paused, completed, failed)
        metrics: Real-time metrics (generic, purpose-agnostic)
        decisions_log: Log of MainAgent decisions with reasoning
        tool_usage_log: Log of tool calls (success, latency, errors)
        missing_tool_attempts: Attempts to use unavailable tools
        created_at: When execution started
        updated_at: Last update time
        completed_at: When execution completed (if finished)
        workflow: Relationship to workflow definition
    """
    __tablename__ = "workflow_executions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workflow_id: UUID = Field(foreign_key="workflows.id", index=True)
    workflow_version: int  # Which version is executing

    creator_id: UUID = Field(index=True)
    consumer_ids: List[UUID] = Field(sa_column=Column(JSON))

    # Runtime state
    current_stage: str
    status: str = Field(index=True)  # running, paused, completed, failed

    # Generic metrics (purpose-agnostic)
    metrics: Dict[str, Any] = Field(sa_column=Column(JSON), default={})
    # Example metrics (varies by purpose):
    # Sales: {"emails_sent": 100, "emails_opened": 30, "bookings": 5}
    # Coaching: {"sessions_scheduled": 20, "attendance_rate": 0.9}
    # Content: {"posts_created": 10, "engagement_rate": 0.15}
    # Community: {"members_active": 500, "posts_per_member": 2.5}

    # Decision tracking
    decisions_log: List[Dict[str, Any]] = Field(sa_column=Column(JSON), default=[])
    # Example decision:
    # {
    #     "timestamp": "2025-12-17T10:30:00Z",
    #     "decision": "trigger_followup_stage",
    #     "reasoning": "Only 20% opened intro email, below 30% threshold",
    #     "metrics_snapshot": {"emails_opened": 20, "emails_sent": 100}
    # }

    # Tool usage tracking
    tool_usage_log: List[Dict[str, Any]] = Field(sa_column=Column(JSON), default=[])
    # Example tool usage:
    # {
    #     "tool": "send_email",
    #     "timestamp": "2025-12-17T10:30:00Z",
    #     "success": true,
    #     "latency_ms": 250,
    #     "consumer_id": "uuid-here"
    # }

    missing_tool_attempts: List[Dict[str, Any]] = Field(sa_column=Column(JSON), default=[])
    # Example missing tool attempt:
    # {
    #     "tool": "send_telegram",
    #     "timestamp": "2025-12-17T10:30:00Z",
    #     "alternative_used": "send_whatsapp",
    #     "impact": "Used fallback successfully",
    #     "consumer_id": "uuid-here"
    # }

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Relationship
    workflow: Workflow = Relationship(back_populates="executions")


class WorkflowStage(BaseModel):
    """Helper model for defining workflow stages (not a DB model).

    Used by MainAgent when creating workflows.
    """
    name: str
    day: int
    actions: List[str]
    conditions: Dict[str, str]
    required_tools: List[str]
    fallback_actions: List[str] = []
    metadata: Dict[str, Any] = {}


class WorkflowMetricsThreshold(BaseModel):
    """Helper model for metric thresholds (not a DB model).

    Used by MainAgent for decision rules.
    """
    metric_name: str
    threshold: float
    comparison: str  # ">=", "<=", "==", ">", "<"
    action: str
    priority: str = "normal"  # critical, high, normal, low
