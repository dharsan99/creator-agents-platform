"""Worker task models for MainAgent → Worker delegation.

These models represent tasks that MainAgent delegates to worker agents
for execution. Each task contains the context and instructions needed
for a worker to complete a specific action.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, Field, JSON, SQLModel


class WorkerTask(SQLModel, table=True):
    """Task delegated from MainAgent to a worker agent.

    Workflow:
    1. MainAgent creates WorkerTask with task_type and payload
    2. Task published to Redpanda supervisor_tasks topic
    3. Worker agent consumes task from topic
    4. Worker agent executes task using tools
    5. Worker agent reports completion/failure
    6. MainAgent receives result and updates workflow

    Attributes:
        id: Task UUID
        workflow_execution_id: Which workflow execution this belongs to
        assigned_agent_id: Worker agent UUID (from onboarding service)
        consumer_id: Which consumer this task is for
        task_type: Type of task (e.g., "create_intro_email", "send_followup")
        task_payload: Task-specific context and instructions
        status: Current task status
        result: Task execution result (populated by worker)
        error: Error message if task failed
        created_at: When task was created
        started_at: When worker started execution
        completed_at: When worker completed execution
        retry_count: Number of retries attempted
        max_retries: Maximum retries allowed
        timeout_seconds: Task timeout in seconds
    """

    __tablename__ = "worker_tasks"

    # Identity
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workflow_execution_id: UUID = Field(
        foreign_key="workflow_executions.id",
        index=True,
        description="Workflow execution this task belongs to"
    )
    assigned_agent_id: UUID = Field(
        index=True,
        description="Worker agent UUID from onboarding service"
    )
    consumer_id: UUID = Field(
        foreign_key="consumers.id",
        index=True,
        description="Consumer this task is for"
    )

    # Task Definition
    task_type: str = Field(
        index=True,
        description="Task type identifier (e.g., create_intro_email, send_followup)"
    )
    task_payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Task-specific context: workflow_id, stage, creator_profile, etc."
    )

    # Task Status
    status: str = Field(
        default="pending",
        index=True,
        description="pending, assigned, in_progress, completed, failed"
    )

    # Execution Results
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Task execution result from worker agent"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if task failed"
    )

    # Retry Configuration
    retry_count: int = Field(
        default=0,
        description="Number of retries attempted"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retries allowed"
    )
    timeout_seconds: int = Field(
        default=300,
        description="Task timeout in seconds (5 minutes default)"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When task was created by MainAgent"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="When worker started execution"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When worker completed execution"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "workflow_execution_id": "789e0123-e89b-12d3-a456-426614174000",
                "assigned_agent_id": "456e7890-e89b-12d3-a456-426614174000",
                "consumer_id": "321e6543-e89b-12d3-a456-426614174000",
                "task_type": "create_intro_email",
                "task_payload": {
                    "workflow_id": "789e0123-e89b-12d3-a456-426614174000",
                    "stage": "intro",
                    "creator_id": "111e1111-e89b-12d3-a456-426614174000",
                    "creator_profile": {
                        "name": "John Doe",
                        "sales_pitch": "Transform your business..."
                    },
                    "actions": ["Send personalized introduction email"],
                    "required_tools": ["send_email", "get_consumer_context"],
                    "fallback_actions": ["Log attempt for manual follow-up"]
                },
                "status": "pending",
                "retry_count": 0,
                "max_retries": 3,
                "timeout_seconds": 300
            }
        }


class TaskStatus:
    """Task status constants."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType:
    """Common task type constants.

    Worker agents can define custom task types - these are just examples.
    """
    # Email tasks
    CREATE_INTRO_EMAIL = "create_intro_email"
    CREATE_FOLLOWUP_EMAIL = "create_followup_email"
    SEND_EMAIL = "send_email"

    # WhatsApp tasks
    CREATE_WHATSAPP_MESSAGE = "create_whatsapp_message"
    SEND_WHATSAPP = "send_whatsapp"

    # SMS tasks
    CREATE_SMS = "create_sms"
    SEND_SMS = "send_sms"

    # Engagement tasks
    CHECK_ENGAGEMENT = "check_engagement"
    UPDATE_CONSUMER_STAGE = "update_consumer_stage"

    # Analytics tasks
    COLLECT_METRICS = "collect_metrics"
    GENERATE_REPORT = "generate_report"

    # Content tasks
    GENERATE_CONTENT = "generate_content"
    SCHEDULE_POST = "schedule_post"
