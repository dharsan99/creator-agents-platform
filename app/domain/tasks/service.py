"""Task service for managing worker tasks.

This service provides methods for creating, assigning, and tracking
tasks that MainAgent delegates to worker agents.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.domain.tasks.models import WorkerTask, TaskStatus

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing worker tasks.

    This service handles the lifecycle of tasks that MainAgent delegates
    to worker agents for execution.

    Usage:
        service = TaskService(session)
        task = service.create_task({
            "workflow_execution_id": workflow_exec_id,
            "assigned_agent_id": worker_agent_id,
            "consumer_id": consumer_id,
            "task_type": "create_intro_email",
            "task_payload": {...}
        })
        service.mark_in_progress(task.id)
        service.mark_completed(task.id, {"email_sent": True})
    """

    def __init__(self, session: Session):
        """Initialize task service.

        Args:
            session: Database session
        """
        self.session = session

    def create_task(self, task_data: Dict[str, Any]) -> WorkerTask:
        """Create a new worker task.

        Args:
            task_data: Task data dict with:
                - workflow_execution_id: UUID
                - assigned_agent_id: UUID
                - consumer_id: UUID
                - task_type: str
                - task_payload: Dict
                - timeout_seconds: int (optional, default 300)
                - max_retries: int (optional, default 3)

        Returns:
            Created WorkerTask instance

        Raises:
            ValueError: If required fields missing

        Example:
            task = service.create_task({
                "workflow_execution_id": workflow_exec_id,
                "assigned_agent_id": worker_agent_id,
                "consumer_id": consumer_id,
                "task_type": "create_intro_email",
                "task_payload": {
                    "workflow_id": str(workflow_id),
                    "stage": "intro",
                    "creator_id": str(creator_id),
                    "actions": ["Send introduction email"],
                    "required_tools": ["send_email"],
                }
            })
        """
        required_fields = [
            "workflow_execution_id",
            "assigned_agent_id",
            "consumer_id",
            "task_type",
            "task_payload",
        ]

        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"Missing required field: {field}")

        try:
            task = WorkerTask(
                workflow_execution_id=task_data["workflow_execution_id"],
                assigned_agent_id=task_data["assigned_agent_id"],
                consumer_id=task_data["consumer_id"],
                task_type=task_data["task_type"],
                task_payload=task_data["task_payload"],
                status=TaskStatus.PENDING,
                timeout_seconds=task_data.get("timeout_seconds", 300),
                max_retries=task_data.get("max_retries", 3),
            )

            self.session.add(task)
            self.session.commit()
            self.session.refresh(task)

            logger.info(
                f"Created task {task.id}",
                extra={
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "assigned_agent_id": str(task.assigned_agent_id),
                    "consumer_id": str(task.consumer_id),
                }
            )

            return task

        except Exception as e:
            logger.error(f"Failed to create task: {e}", exc_info=True)
            self.session.rollback()
            raise

    def get_task(self, task_id: UUID) -> Optional[WorkerTask]:
        """Get task by ID.

        Args:
            task_id: Task UUID

        Returns:
            WorkerTask instance or None
        """
        return self.session.get(WorkerTask, task_id)

    def assign_task(self, task_id: UUID, agent_id: UUID) -> WorkerTask:
        """Assign task to a worker agent.

        Args:
            task_id: Task UUID
            agent_id: Worker agent UUID

        Returns:
            Updated WorkerTask instance

        Raises:
            ValueError: If task not found
        """
        task = self.session.get(WorkerTask, task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.assigned_agent_id = agent_id
        task.status = TaskStatus.ASSIGNED

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        logger.info(f"Assigned task {task_id} to agent {agent_id}")

        return task

    def get_pending_tasks(
        self,
        agent_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[WorkerTask]:
        """Get pending tasks, optionally filtered by agent.

        Args:
            agent_id: Optional agent UUID to filter by
            limit: Maximum number of tasks to return

        Returns:
            List of pending WorkerTask instances
        """
        statement = (
            select(WorkerTask)
            .where(WorkerTask.status == TaskStatus.PENDING)
            .order_by(WorkerTask.created_at)
            .limit(limit)
        )

        if agent_id:
            statement = statement.where(WorkerTask.assigned_agent_id == agent_id)

        tasks = list(self.session.exec(statement).all())

        logger.debug(
            f"Found {len(tasks)} pending tasks",
            extra={"agent_id": str(agent_id) if agent_id else None}
        )

        return tasks

    def mark_in_progress(self, task_id: UUID) -> WorkerTask:
        """Mark task as in progress.

        Args:
            task_id: Task UUID

        Returns:
            Updated WorkerTask instance

        Raises:
            ValueError: If task not found
        """
        task = self.session.get(WorkerTask, task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        logger.info(f"Task {task_id} in progress")

        return task

    def mark_completed(
        self,
        task_id: UUID,
        result: Dict[str, Any]
    ) -> WorkerTask:
        """Mark task as completed with result.

        Args:
            task_id: Task UUID
            result: Task execution result dict

        Returns:
            Updated WorkerTask instance

        Raises:
            ValueError: If task not found

        Example:
            service.mark_completed(task_id, {
                "email_sent": True,
                "message_id": "abc123",
                "tools_used": ["send_email", "get_consumer_context"],
                "timestamp": "2024-01-01T12:00:00Z"
            })
        """
        task = self.session.get(WorkerTask, task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.utcnow()

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        logger.info(
            f"Task {task_id} completed",
            extra={
                "task_id": str(task_id),
                "duration_seconds": (
                    (task.completed_at - task.started_at).total_seconds()
                    if task.started_at
                    else None
                ),
            }
        )

        return task

    def mark_failed(
        self,
        task_id: UUID,
        error: str,
        should_retry: bool = True
    ) -> WorkerTask:
        """Mark task as failed with error message.

        Args:
            task_id: Task UUID
            error: Error message
            should_retry: Whether to increment retry count and reset to pending

        Returns:
            Updated WorkerTask instance

        Raises:
            ValueError: If task not found

        Example:
            service.mark_failed(
                task_id,
                "SendEmail tool timed out after 30 seconds",
                should_retry=True
            )
        """
        task = self.session.get(WorkerTask, task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.error = error

        if should_retry and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            task.started_at = None

            logger.warning(
                f"Task {task_id} failed, retrying (attempt {task.retry_count}/{task.max_retries})",
                extra={"error": error}
            )
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()

            logger.error(
                f"Task {task_id} failed permanently",
                extra={
                    "error": error,
                    "retry_count": task.retry_count,
                    "max_retries": task.max_retries,
                }
            )

        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        return task

    def get_tasks_for_workflow(
        self,
        workflow_execution_id: UUID,
        status: Optional[str] = None
    ) -> List[WorkerTask]:
        """Get all tasks for a workflow execution.

        Args:
            workflow_execution_id: Workflow execution UUID
            status: Optional status filter

        Returns:
            List of WorkerTask instances
        """
        statement = (
            select(WorkerTask)
            .where(WorkerTask.workflow_execution_id == workflow_execution_id)
            .order_by(WorkerTask.created_at)
        )

        if status:
            statement = statement.where(WorkerTask.status == status)

        return list(self.session.exec(statement).all())

    def get_tasks_for_consumer(
        self,
        consumer_id: UUID,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkerTask]:
        """Get all tasks for a consumer.

        Args:
            consumer_id: Consumer UUID
            status: Optional status filter
            limit: Maximum number of tasks to return

        Returns:
            List of WorkerTask instances
        """
        statement = (
            select(WorkerTask)
            .where(WorkerTask.consumer_id == consumer_id)
            .order_by(WorkerTask.created_at.desc())
            .limit(limit)
        )

        if status:
            statement = statement.where(WorkerTask.status == status)

        return list(self.session.exec(statement).all())

    def get_task_stats(
        self,
        workflow_execution_id: Optional[UUID] = None
    ) -> Dict[str, int]:
        """Get task statistics.

        Args:
            workflow_execution_id: Optional workflow execution UUID to filter by

        Returns:
            Dict with task counts by status

        Example:
            {
                "pending": 5,
                "in_progress": 3,
                "completed": 42,
                "failed": 2,
                "total": 52
            }
        """
        base_statement = select(WorkerTask)

        if workflow_execution_id:
            base_statement = base_statement.where(
                WorkerTask.workflow_execution_id == workflow_execution_id
            )

        all_tasks = list(self.session.exec(base_statement).all())

        stats = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "total": len(all_tasks),
        }

        for task in all_tasks:
            if task.status in stats:
                stats[task.status] += 1

        return stats
