"""Task API endpoints for dashboard integration.

Provides endpoints to query worker tasks for visualization
in the creator-onboarding-service dashboard.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, and_, or_, func

from app.infra.db.connection import get_session
from app.domain.tasks.models import WorkerTask, TaskStatus
from app.domain.workflow.models import Workflow, WorkflowExecution
from app.infra.db.models import Consumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    creator_id: Optional[str] = Query(None, description="Filter by creator ID"),
    consumer_id: Optional[str] = Query(None, description="Filter by consumer ID"),
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    agent_id: Optional[str] = Query(None, description="Filter by assigned agent ID"),
    status: Optional[str] = Query(None, description="Filter by status: pending|running|completed|failed"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    since: Optional[str] = Query(None, description="Filter tasks created since this ISO timestamp"),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session)
):
    """List worker tasks with optional filtering.

    Query Parameters:
        creator_id: Filter by creator
        consumer_id: Filter by consumer
        workflow_id: Filter by workflow
        agent_id: Filter by assigned agent
        status: Filter by task status
        task_type: Filter by task type
        since: Filter tasks created since timestamp
        limit: Maximum results
    """
    try:
        # Build query
        statement = select(WorkerTask)

        # Apply filters
        if consumer_id:
            statement = statement.where(WorkerTask.consumer_id == UUID(consumer_id))

        if agent_id:
            statement = statement.where(WorkerTask.assigned_agent_id == UUID(agent_id))

        if status:
            statement = statement.where(WorkerTask.status == status)

        if task_type:
            statement = statement.where(WorkerTask.task_type == task_type)

        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                statement = statement.where(WorkerTask.created_at >= since_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid since timestamp format")

        # Filter by creator_id through workflow
        if creator_id:
            # Get workflow execution IDs for this creator
            workflow_ids = session.exec(
                select(Workflow.id).where(Workflow.creator_id == UUID(creator_id))
            ).all()

            execution_ids = session.exec(
                select(WorkflowExecution.id).where(
                    WorkflowExecution.workflow_id.in_(workflow_ids)
                )
            ).all()

            statement = statement.where(
                WorkerTask.workflow_execution_id.in_(execution_ids)
            )

        # Filter by workflow_id
        if workflow_id:
            execution_ids = session.exec(
                select(WorkflowExecution.id).where(
                    WorkflowExecution.workflow_id == UUID(workflow_id)
                )
            ).all()

            statement = statement.where(
                WorkerTask.workflow_execution_id.in_(execution_ids)
            )

        statement = statement.order_by(WorkerTask.created_at.desc()).limit(limit)

        tasks = session.exec(statement).all()

        # Convert to dict with serializable fields
        result = []
        for task in tasks:
            task_dict = task.model_dump()

            # Add consumer name if available
            consumer = session.get(Consumer, task.consumer_id)
            if consumer:
                task_dict["consumer_name"] = consumer.name
                task_dict["consumer_email"] = consumer.email

            # Add workflow info
            execution = session.get(WorkflowExecution, task.workflow_execution_id)
            if execution:
                workflow = session.get(Workflow, execution.workflow_id)
                if workflow:
                    task_dict["workflow"] = {
                        "id": str(workflow.id),
                        "purpose": workflow.purpose,
                        "creator_id": str(workflow.creator_id)
                    }

            result.append(task_dict)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    session: Session = Depends(get_session)
):
    """Get a specific task by ID with full details."""
    try:
        task = session.get(WorkerTask, UUID(task_id))

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        task_dict = task.model_dump()

        # Add consumer details
        consumer = session.get(Consumer, task.consumer_id)
        if consumer:
            task_dict["consumer"] = {
                "id": str(consumer.id),
                "name": consumer.name,
                "email": consumer.email,
                "whatsapp": consumer.whatsapp
            }

        # Add workflow execution details
        execution = session.get(WorkflowExecution, task.workflow_execution_id)
        if execution:
            task_dict["execution"] = {
                "id": str(execution.id),
                "workflow_id": str(execution.workflow_id),
                "status": execution.status,
                "current_stage": execution.current_stage
            }

            # Add workflow details
            workflow = session.get(Workflow, execution.workflow_id)
            if workflow:
                task_dict["workflow"] = {
                    "id": str(workflow.id),
                    "purpose": workflow.purpose,
                    "creator_id": str(workflow.creator_id),
                    "workflow_type": workflow.workflow_type
                }

        return task_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_task_stats(
    creator_id: Optional[str] = Query(None, description="Filter by creator ID"),
    session: Session = Depends(get_session)
):
    """Get aggregate task statistics.

    Returns summary statistics including:
    - Total tasks by status
    - Tasks by type
    - Success rate
    - Average completion time
    """
    try:
        # Build base query
        statement = select(WorkerTask)

        # Filter by creator if specified
        if creator_id:
            workflow_ids = session.exec(
                select(Workflow.id).where(Workflow.creator_id == UUID(creator_id))
            ).all()

            execution_ids = session.exec(
                select(WorkflowExecution.id).where(
                    WorkflowExecution.workflow_id.in_(workflow_ids)
                )
            ).all()

            statement = statement.where(
                WorkerTask.workflow_execution_id.in_(execution_ids)
            )

        tasks = session.exec(statement).all()

        # Calculate statistics
        total_tasks = len(tasks)
        status_counts = {}
        type_counts = {}

        for task in tasks:
            # Count by status
            status_counts[task.status] = status_counts.get(task.status, 0) + 1

            # Count by type
            type_counts[task.task_type] = type_counts.get(task.task_type, 0) + 1

        # Calculate rates
        completed = status_counts.get(TaskStatus.COMPLETED, 0)
        failed = status_counts.get(TaskStatus.FAILED, 0)

        success_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0
        failure_rate = (failed / total_tasks * 100) if total_tasks > 0 else 0

        return {
            "summary": {
                "total_tasks": total_tasks,
                "by_status": status_counts,
                "by_type": type_counts,
                "success_rate": round(success_rate, 2),
                "failure_rate": round(failure_rate, 2)
            },
            "filter": {
                "creator_id": creator_id
            }
        }

    except Exception as e:
        logger.error(f"Error getting task stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consumer/{consumer_id}")
async def get_consumer_tasks(
    consumer_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session)
):
    """Get all tasks for a specific consumer.

    Useful for viewing a consumer's journey through the workflow.
    """
    try:
        statement = select(WorkerTask).where(
            WorkerTask.consumer_id == UUID(consumer_id)
        )

        if status:
            statement = statement.where(WorkerTask.status == status)

        statement = statement.order_by(WorkerTask.created_at.asc()).limit(limit)

        tasks = session.exec(statement).all()

        # Group by workflow execution for better visualization
        executions = {}
        for task in tasks:
            exec_id = str(task.workflow_execution_id)
            if exec_id not in executions:
                execution = session.get(WorkflowExecution, task.workflow_execution_id)
                executions[exec_id] = {
                    "execution_id": exec_id,
                    "workflow_id": str(execution.workflow_id) if execution else None,
                    "current_stage": execution.current_stage if execution else None,
                    "tasks": []
                }
            executions[exec_id]["tasks"].append(task.model_dump())

        return {
            "consumer_id": consumer_id,
            "total_tasks": len(tasks),
            "by_execution": list(executions.values())
        }

    except Exception as e:
        logger.error(f"Error getting consumer tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
