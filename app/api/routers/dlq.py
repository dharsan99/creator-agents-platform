"""Dead Letter Queue API endpoints for monitoring and management."""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.infra.db.connection import get_session
from app.infra.db.models import DeadLetterQueueEntry
from app.infra.queues.dlq_service import DLQService
from app.infra.queues.taskiq_tasks import process_dead_letter_queue_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dlq", tags=["Dead Letter Queue"])


@router.get("/entries", response_model=List[DeadLetterQueueEntry])
def list_dlq_entries(
    queue_name: Optional[str] = Query(None, description="Filter by queue name"),
    include_processed: bool = Query(False, description="Include processed entries"),
    limit: int = Query(50, ge=1, le=500, description="Maximum entries to return"),
    session: Session = Depends(get_session),
):
    """List dead letter queue entries.

    Returns a list of DLQ entries, optionally filtered by queue name.
    By default, only unprocessed entries are returned.
    """
    try:
        dlq_service = DLQService(session)

        if queue_name:
            entries = dlq_service.get_entries_by_queue(
                queue_name=queue_name,
                include_processed=include_processed,
                limit=limit
            )
        else:
            if include_processed:
                # Need to get all entries - not implemented in service yet
                # For now, just get unprocessed
                entries = dlq_service.get_unprocessed_entries(limit=limit)
            else:
                entries = dlq_service.get_unprocessed_entries(limit=limit)

        return entries

    except Exception as e:
        logger.error(f"Failed to list DLQ entries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entries/{entry_id}", response_model=DeadLetterQueueEntry)
def get_dlq_entry(
    entry_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a specific DLQ entry by ID."""
    try:
        dlq_service = DLQService(session)
        entry = dlq_service.get_entry(entry_id)

        if not entry:
            raise HTTPException(status_code=404, detail="DLQ entry not found")

        return entry

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get DLQ entry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_dlq_stats(
    session: Session = Depends(get_session),
):
    """Get DLQ statistics.

    Returns counts of unprocessed and processed entries by queue.
    """
    try:
        dlq_service = DLQService(session)
        stats = dlq_service.get_stats()

        return {
            "status": "success",
            "data": stats
        }

    except Exception as e:
        logger.error(f"Failed to get DLQ stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entries/{entry_id}/mark-processed")
def mark_dlq_entry_processed(
    entry_id: UUID,
    session: Session = Depends(get_session),
):
    """Mark a DLQ entry as processed without reprocessing."""
    try:
        dlq_service = DLQService(session)
        success = dlq_service.mark_processed(entry_id)

        if not success:
            raise HTTPException(status_code=404, detail="DLQ entry not found")

        return {
            "status": "success",
            "message": f"DLQ entry {entry_id} marked as processed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark DLQ entry as processed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entries/{entry_id}")
def delete_dlq_entry(
    entry_id: UUID,
    session: Session = Depends(get_session),
):
    """Delete a DLQ entry permanently."""
    try:
        dlq_service = DLQService(session)
        success = dlq_service.delete_entry(entry_id)

        if not success:
            raise HTTPException(status_code=404, detail="DLQ entry not found")

        return {
            "status": "success",
            "message": f"DLQ entry {entry_id} deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete DLQ entry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def trigger_dlq_processing():
    """Trigger manual processing of the dead letter queue.

    This enqueues the DLQ processing task to reprocess failed tasks.
    """
    try:
        # Enqueue the DLQ processing task
        task = await process_dead_letter_queue_task.kiq()

        return {
            "status": "success",
            "message": "DLQ processing task enqueued",
            "task_id": str(task.task_id) if hasattr(task, "task_id") else None
        }

    except Exception as e:
        logger.error(f"Failed to trigger DLQ processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queues/{queue_name}/entries", response_model=List[DeadLetterQueueEntry])
def list_queue_entries(
    queue_name: str,
    include_processed: bool = Query(False, description="Include processed entries"),
    limit: int = Query(50, ge=1, le=500, description="Maximum entries to return"),
    session: Session = Depends(get_session),
):
    """List DLQ entries for a specific queue."""
    try:
        dlq_service = DLQService(session)
        entries = dlq_service.get_entries_by_queue(
            queue_name=queue_name,
            include_processed=include_processed,
            limit=limit
        )

        return entries

    except Exception as e:
        logger.error(f"Failed to list queue entries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
