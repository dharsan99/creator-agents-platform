"""Workflow API endpoints for dashboard integration.

Provides endpoints to query workflows, workflow executions, and tasks
for visualization in the creator-onboarding-service dashboard.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, and_, func

from app.infra.db.connection import get_session
from app.domain.workflow.models import Workflow, WorkflowExecution
from app.domain.tasks.models import WorkerTask
from app.infra.db.models import Consumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("")
async def list_workflows(
    creator_id: Optional[str] = Query(None, description="Filter by creator ID"),
    purpose: Optional[str] = Query(None, description="Filter by purpose"),
    status: Optional[str] = Query(None, description="Filter by workflow status"),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session)
):
    """List workflows with optional filtering.

    Query Parameters:
        creator_id: Filter workflows by creator
        purpose: Filter by workflow purpose
        status: Filter by status (from latest execution)
        limit: Maximum results to return
    """
    try:
        # Build query
        statement = select(Workflow)

        if creator_id:
            statement = statement.where(Workflow.creator_id == UUID(creator_id))

        if purpose:
            statement = statement.where(Workflow.purpose == purpose)

        statement = statement.order_by(Workflow.created_at.desc()).limit(limit)

        workflows = session.exec(statement).all()

        # Convert to dict and include execution status
        result = []
        for workflow in workflows:
            workflow_dict = workflow.model_dump()

            # Get latest execution
            latest_exec = session.exec(
                select(WorkflowExecution)
                .where(WorkflowExecution.workflow_id == workflow.id)
                .order_by(WorkflowExecution.created_at.desc())
                .limit(1)
            ).first()

            if latest_exec:
                workflow_dict["latest_execution"] = {
                    "id": str(latest_exec.id),
                    "status": latest_exec.status,
                    "current_stage": latest_exec.current_stage,
                    "created_at": latest_exec.created_at.isoformat(),
                    "updated_at": latest_exec.updated_at.isoformat()
                }

            result.append(workflow_dict)

        return result

    except Exception as e:
        logger.error(f"Error listing workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    session: Session = Depends(get_session)
):
    """Get a specific workflow by ID."""
    try:
        workflow = session.get(Workflow, UUID(workflow_id))

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow_dict = workflow.model_dump()

        # Get all executions
        executions = session.exec(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == UUID(workflow_id))
            .order_by(WorkflowExecution.created_at.desc())
        ).all()

        workflow_dict["executions"] = [
            {
                "id": str(exec.id),
                "status": exec.status,
                "current_stage": exec.current_stage,
                "metrics": exec.metrics,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat()
            }
            for exec in executions
        ]

        return workflow_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/executions")
async def get_workflow_executions(
    workflow_id: str,
    status: Optional[str] = Query(None, description="Filter by execution status"),
    session: Session = Depends(get_session)
):
    """Get all executions for a workflow."""
    try:
        # Build query
        statement = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == UUID(workflow_id)
        )

        if status:
            statement = statement.where(WorkflowExecution.status == status)

        statement = statement.order_by(WorkflowExecution.created_at.desc())

        executions = session.exec(statement).all()

        return [
            {
                "id": str(exec.id),
                "workflow_id": str(exec.workflow_id),
                "status": exec.status,
                "current_stage": exec.current_stage,
                "metrics": exec.metrics,
                "decisions_log": exec.decisions_log,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat()
            }
            for exec in executions
        ]

    except Exception as e:
        logger.error(f"Error getting workflow executions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/tasks")
async def get_workflow_tasks(
    workflow_id: str,
    status: Optional[str] = Query(None, description="Filter by task status"),
    session: Session = Depends(get_session)
):
    """Get all tasks for a workflow across all executions."""
    try:
        # Get all execution IDs for this workflow
        executions = session.exec(
            select(WorkflowExecution.id).where(
                WorkflowExecution.workflow_id == UUID(workflow_id)
            )
        ).all()

        if not executions:
            return []

        # Get tasks for these executions
        statement = select(WorkerTask).where(
            WorkerTask.workflow_execution_id.in_(executions)
        )

        if status:
            statement = statement.where(WorkerTask.status == status)

        statement = statement.order_by(WorkerTask.created_at.desc())

        tasks = session.exec(statement).all()

        return [task.model_dump() for task in tasks]

    except Exception as e:
        logger.error(f"Error getting workflow tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
