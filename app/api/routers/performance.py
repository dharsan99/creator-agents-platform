"""Performance monitoring and diagnostics API endpoints."""
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func

from app.infra.db.connection import get_session
from app.infra.db.models import (
    AgentInvocation,
    DeadLetterQueueEntry,
)
from app.domain.tasks.models import WorkerTask
from app.domain.workflow.models import Workflow, WorkflowExecution
from app.infra.metrics import get_metrics
from app.infra.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance Monitoring"])


@router.get("/health")
def detailed_health_check(
    session: Session = Depends(get_session),
):
    """Detailed health check with performance metrics.

    Returns system health status including database, cache, and queue health.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check database
    try:
        start = time.time()
        session.exec(select(func.count()).select_from(AgentInvocation)).one()
        db_latency = (time.time() - start) * 1000  # ms

        health_status["checks"]["database"] = {
            "status": "healthy",
            "latency_ms": round(db_latency, 2)
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check Redis cache
    try:
        cache = get_cache()
        start = time.time()
        cache.set("health_check", "test", "test_value", ttl=10)
        cache.get("health_check", "test")
        cache_latency = (time.time() - start) * 1000  # ms

        health_status["checks"]["cache"] = {
            "status": "healthy",
            "latency_ms": round(cache_latency, 2)
        }
    except Exception as e:
        health_status["checks"]["cache"] = {
            "status": "degraded",
            "error": str(e)
        }

    return health_status


@router.get("/metrics-summary")
def get_metrics_summary(
    session: Session = Depends(get_session),
):
    """Get summary of key performance metrics.

    Returns:
        - Agent invocation stats
        - Workflow execution stats
        - Task stats
        - DLQ stats
        - Cache hit rate
    """
    try:
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {},
            "workflows": {},
            "tasks": {},
            "dlq": {},
        }

        # Agent invocations (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)

        invocation_stats = session.exec(
            select(
                AgentInvocation.status,
                func.count(AgentInvocation.id).label("count")
            )
            .where(AgentInvocation.created_at >= yesterday)
            .group_by(AgentInvocation.status)
        ).all()

        summary["agents"]["invocations_24h"] = {
            status: count for status, count in invocation_stats
        }

        # Workflow executions
        workflow_stats = session.exec(
            select(
                WorkflowExecution.status,
                func.count(WorkflowExecution.id).label("count")
            )
            .group_by(WorkflowExecution.status)
        ).all()

        summary["workflows"]["executions_by_status"] = {
            status: count for status, count in workflow_stats
        }

        # Worker tasks
        task_stats = session.exec(
            select(
                WorkerTask.status,
                func.count(WorkerTask.id).label("count")
            )
            .where(WorkerTask.created_at >= yesterday)
            .group_by(WorkerTask.status)
        ).all()

        summary["tasks"]["tasks_24h"] = {
            status: count for status, count in task_stats
        }

        # DLQ entries
        dlq_stats = session.exec(
            select(
                DeadLetterQueueEntry.processed,
                func.count(DeadLetterQueueEntry.id).label("count")
            )
            .group_by(DeadLetterQueueEntry.processed)
        ).all()

        summary["dlq"]["entries"] = {
            "unprocessed" if not processed else "processed": count
            for processed, count in dlq_stats
        }

        return {
            "status": "success",
            "data": summary
        }

    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slow-queries")
def get_slow_operations(
    hours: int = Query(1, ge=1, le=24, description="Hours to look back"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    session: Session = Depends(get_session),
):
    """Get slow agent invocations and task executions.

    Identifies operations that took longer than expected for optimization.
    """
    try:
        since = datetime.utcnow() - timedelta(hours=hours)

        # Get agent invocations with results containing execution time
        slow_invocations = session.exec(
            select(AgentInvocation)
            .where(AgentInvocation.created_at >= since)
            .where(AgentInvocation.status == "completed")
            .order_by(AgentInvocation.updated_at.desc())
            .limit(limit)
        ).all()

        # Filter for slow ones (> 10 seconds)
        slow_ops = []
        for inv in slow_invocations:
            if inv.result and isinstance(inv.result, dict):
                exec_time = inv.result.get("execution_time_ms", 0)
                if exec_time > 10000:  # 10+ seconds
                    slow_ops.append({
                        "type": "agent_invocation",
                        "id": str(inv.id),
                        "agent_id": str(inv.agent_id),
                        "execution_time_ms": exec_time,
                        "created_at": inv.created_at.isoformat()
                    })

        # Get slow worker tasks
        slow_tasks = session.exec(
            select(WorkerTask)
            .where(WorkerTask.created_at >= since)
            .where(WorkerTask.status == "completed")
            .where(WorkerTask.completed_at.isnot(None))
            .order_by(WorkerTask.completed_at.desc())
            .limit(limit)
        ).all()

        for task in slow_tasks:
            if task.completed_at:
                duration = (task.completed_at - task.created_at).total_seconds()
                if duration > 30:  # 30+ seconds
                    slow_ops.append({
                        "type": "worker_task",
                        "id": str(task.id),
                        "task_type": task.task_type,
                        "duration_seconds": round(duration, 2),
                        "created_at": task.created_at.isoformat()
                    })

        # Sort by duration/time
        slow_ops.sort(
            key=lambda x: x.get("execution_time_ms", 0) + x.get("duration_seconds", 0) * 1000,
            reverse=True
        )

        return {
            "status": "success",
            "data": {
                "slow_operations": slow_ops[:limit],
                "total_found": len(slow_ops),
                "threshold": {
                    "agent_invocations": "10 seconds",
                    "worker_tasks": "30 seconds"
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get slow operations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow-performance")
def get_workflow_performance(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Get workflow execution performance metrics.

    Returns execution times, decision counts, and tool usage for workflows.
    """
    try:
        stmt = select(WorkflowExecution).order_by(
            WorkflowExecution.created_at.desc()
        ).limit(limit)

        if workflow_id:
            from uuid import UUID
            stmt = stmt.where(WorkflowExecution.workflow_id == UUID(workflow_id))

        executions = session.exec(stmt).all()

        performance_data = []
        for exec in executions:
            duration = None
            if exec.completed_at:
                duration = (exec.completed_at - exec.created_at).total_seconds()

            performance_data.append({
                "execution_id": str(exec.id),
                "workflow_id": str(exec.workflow_id),
                "status": exec.status,
                "duration_seconds": round(duration, 2) if duration else None,
                "decisions_count": len(exec.decisions_log),
                "tools_used": len(exec.tool_usage_log),
                "current_stage": exec.current_stage,
                "created_at": exec.created_at.isoformat(),
                "completed_at": exec.completed_at.isoformat() if exec.completed_at else None
            })

        return {
            "status": "success",
            "data": performance_data
        }

    except Exception as e:
        logger.error(f"Failed to get workflow performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize/cache-warmup")
def cache_warmup(
    workflow_ids: List[str] = Query([], description="Workflow IDs to cache"),
    session: Session = Depends(get_session),
):
    """Warm up cache with frequently accessed workflow executions.

    Preloads workflow execution data into Redis cache for better performance.
    """
    try:
        from uuid import UUID
        from app.domain.workflow.service import WorkflowService

        workflow_service = WorkflowService(session, enable_cache=True)
        cached_count = 0

        # If no IDs provided, get recent active workflows
        if not workflow_ids:
            recent = session.exec(
                select(WorkflowExecution)
                .where(WorkflowExecution.status.in_(["running", "paused"]))
                .order_by(WorkflowExecution.updated_at.desc())
                .limit(50)
            ).all()
            workflow_ids = [str(exec.id) for exec in recent]

        # Cache each execution
        for exec_id_str in workflow_ids:
            try:
                exec_id = UUID(exec_id_str)
                # This will cache it as a side effect
                workflow_service.get_execution(exec_id)
                cached_count += 1
            except Exception as e:
                logger.warning(f"Failed to cache execution {exec_id_str}: {e}")

        return {
            "status": "success",
            "message": f"Cached {cached_count} workflow executions",
            "cached_count": cached_count
        }

    except Exception as e:
        logger.error(f"Failed to warm up cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-stats")
def get_system_stats(
    session: Session = Depends(get_session),
):
    """Get overall system statistics for monitoring.

    Returns counts of active entities and resource usage indicators.
    """
    try:
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "entities": {},
            "activity": {}
        }

        # Count active entities
        workflow_count = session.exec(
            select(func.count()).select_from(Workflow)
        ).one()
        stats["entities"]["workflows"] = workflow_count

        active_executions = session.exec(
            select(func.count())
            .select_from(WorkflowExecution)
            .where(WorkflowExecution.status.in_(["running", "paused"]))
        ).one()
        stats["entities"]["active_executions"] = active_executions

        # Recent activity (last hour)
        last_hour = datetime.utcnow() - timedelta(hours=1)

        recent_invocations = session.exec(
            select(func.count())
            .select_from(AgentInvocation)
            .where(AgentInvocation.created_at >= last_hour)
        ).one()
        stats["activity"]["invocations_last_hour"] = recent_invocations

        recent_tasks = session.exec(
            select(func.count())
            .select_from(WorkerTask)
            .where(WorkerTask.created_at >= last_hour)
        ).one()
        stats["activity"]["tasks_last_hour"] = recent_tasks

        return {
            "status": "success",
            "data": stats
        }

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
