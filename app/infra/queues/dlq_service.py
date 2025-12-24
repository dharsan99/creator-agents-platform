"""Dead Letter Queue service for handling failed tasks.

This service manages tasks that have exhausted all retries:
- Records failed tasks with error details
- Tracks retry attempts
- Provides reprocessing capabilities
- Integrates with metrics for monitoring
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.infra.db.models import DeadLetterQueueEntry
from app.infra.metrics import get_metrics

logger = logging.getLogger(__name__)


class DLQService:
    """Service for managing dead letter queue entries.

    Usage:
        dlq = DLQService(session)
        dlq.add_failed_task(
            queue_name="agents",
            original_job_id="task_123",
            task_name="process_agent_invocations",
            payload={"creator_id": "...", "consumer_id": "..."},
            error_message="Connection timeout after 3 retries"
        )
    """

    def __init__(self, session: Session):
        """Initialize DLQ service.

        Args:
            session: Database session
        """
        self.session = session
        self.metrics = get_metrics()

    def add_failed_task(
        self,
        queue_name: str,
        original_job_id: str,
        task_name: str,
        payload: Dict[str, Any],
        error_message: str,
    ) -> DeadLetterQueueEntry:
        """Add a failed task to the dead letter queue.

        Args:
            queue_name: Name of the queue (agents, actions, default, supervisor_tasks, etc.)
            original_job_id: Original task/job ID
            task_name: Name of the task that failed
            payload: Task payload (parameters)
            error_message: Error message from the failure

        Returns:
            Created DeadLetterQueueEntry
        """
        try:
            entry = DeadLetterQueueEntry(
                queue_name=queue_name,
                original_job_id=original_job_id,
                task_name=task_name,
                payload=payload,
                error_message=error_message,
                failed_at=datetime.utcnow(),
                retry_count=0,
                processed=False,
            )

            self.session.add(entry)
            self.session.commit()
            self.session.refresh(entry)

            # Track DLQ metric
            self.metrics.tasks_completed.labels(
                task_type=task_name,
                status="dlq"
            ).inc()

            logger.warning(
                f"Added task to DLQ: {task_name} (queue: {queue_name}, job: {original_job_id})",
                extra={
                    "dlq_entry_id": str(entry.id),
                    "queue_name": queue_name,
                    "task_name": task_name,
                    "error": error_message[:200]  # Truncate for logging
                }
            )

            return entry

        except Exception as e:
            logger.error(f"Failed to add task to DLQ: {e}", exc_info=True)
            self.session.rollback()
            raise

    def get_unprocessed_entries(
        self,
        queue_name: Optional[str] = None,
        limit: int = 10
    ) -> List[DeadLetterQueueEntry]:
        """Get unprocessed DLQ entries.

        Args:
            queue_name: Optional queue name filter
            limit: Maximum number of entries to return

        Returns:
            List of unprocessed DeadLetterQueueEntry objects
        """
        try:
            stmt = select(DeadLetterQueueEntry).where(
                DeadLetterQueueEntry.processed == False  # noqa: E712
            )

            if queue_name:
                stmt = stmt.where(DeadLetterQueueEntry.queue_name == queue_name)

            stmt = stmt.order_by(DeadLetterQueueEntry.failed_at).limit(limit)

            return list(self.session.exec(stmt).all())

        except Exception as e:
            logger.error(f"Failed to get unprocessed DLQ entries: {e}", exc_info=True)
            return []

    def mark_processed(self, entry_id: UUID) -> bool:
        """Mark a DLQ entry as processed.

        Args:
            entry_id: DLQ entry UUID

        Returns:
            True if marked, False if not found
        """
        try:
            entry = self.session.get(DeadLetterQueueEntry, entry_id)

            if not entry:
                logger.warning(f"DLQ entry not found: {entry_id}")
                return False

            entry.processed = True
            entry.retry_count += 1

            self.session.add(entry)
            self.session.commit()

            logger.info(
                f"Marked DLQ entry {entry_id} as processed (retry #{entry.retry_count})"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to mark DLQ entry as processed: {e}", exc_info=True)
            self.session.rollback()
            return False

    def get_entry(self, entry_id: UUID) -> Optional[DeadLetterQueueEntry]:
        """Get a specific DLQ entry.

        Args:
            entry_id: DLQ entry UUID

        Returns:
            DeadLetterQueueEntry or None
        """
        return self.session.get(DeadLetterQueueEntry, entry_id)

    def get_entries_by_queue(
        self,
        queue_name: str,
        include_processed: bool = False,
        limit: int = 50
    ) -> List[DeadLetterQueueEntry]:
        """Get DLQ entries for a specific queue.

        Args:
            queue_name: Queue name
            include_processed: Whether to include processed entries
            limit: Maximum entries to return

        Returns:
            List of DeadLetterQueueEntry objects
        """
        try:
            stmt = select(DeadLetterQueueEntry).where(
                DeadLetterQueueEntry.queue_name == queue_name
            )

            if not include_processed:
                stmt = stmt.where(DeadLetterQueueEntry.processed == False)  # noqa: E712

            stmt = stmt.order_by(
                DeadLetterQueueEntry.failed_at.desc()
            ).limit(limit)

            return list(self.session.exec(stmt).all())

        except Exception as e:
            logger.error(
                f"Failed to get DLQ entries for queue {queue_name}: {e}",
                exc_info=True
            )
            return []

    def get_entries_by_task(
        self,
        task_name: str,
        include_processed: bool = False,
        limit: int = 50
    ) -> List[DeadLetterQueueEntry]:
        """Get DLQ entries for a specific task.

        Args:
            task_name: Task name
            include_processed: Whether to include processed entries
            limit: Maximum entries to return

        Returns:
            List of DeadLetterQueueEntry objects
        """
        try:
            stmt = select(DeadLetterQueueEntry).where(
                DeadLetterQueueEntry.task_name == task_name
            )

            if not include_processed:
                stmt = stmt.where(DeadLetterQueueEntry.processed == False)  # noqa: E712

            stmt = stmt.order_by(
                DeadLetterQueueEntry.failed_at.desc()
            ).limit(limit)

            return list(self.session.exec(stmt).all())

        except Exception as e:
            logger.error(
                f"Failed to get DLQ entries for task {task_name}: {e}",
                exc_info=True
            )
            return []

    def delete_entry(self, entry_id: UUID) -> bool:
        """Delete a DLQ entry.

        Args:
            entry_id: DLQ entry UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            entry = self.session.get(DeadLetterQueueEntry, entry_id)

            if not entry:
                logger.warning(f"DLQ entry not found for deletion: {entry_id}")
                return False

            self.session.delete(entry)
            self.session.commit()

            logger.info(f"Deleted DLQ entry {entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete DLQ entry: {e}", exc_info=True)
            self.session.rollback()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics.

        Returns:
            Dict with counts by queue and status
        """
        try:
            # Count unprocessed by queue
            unprocessed_stmt = select(
                DeadLetterQueueEntry.queue_name,
                DeadLetterQueueEntry.id
            ).where(
                DeadLetterQueueEntry.processed == False  # noqa: E712
            )

            unprocessed_entries = self.session.exec(unprocessed_stmt).all()

            # Count processed by queue
            processed_stmt = select(
                DeadLetterQueueEntry.queue_name,
                DeadLetterQueueEntry.id
            ).where(
                DeadLetterQueueEntry.processed == True  # noqa: E712
            )

            processed_entries = self.session.exec(processed_stmt).all()

            # Aggregate counts
            unprocessed_by_queue = {}
            for queue_name, _ in unprocessed_entries:
                unprocessed_by_queue[queue_name] = unprocessed_by_queue.get(queue_name, 0) + 1

            processed_by_queue = {}
            for queue_name, _ in processed_entries:
                processed_by_queue[queue_name] = processed_by_queue.get(queue_name, 0) + 1

            return {
                "total_unprocessed": len(unprocessed_entries),
                "total_processed": len(processed_entries),
                "unprocessed_by_queue": unprocessed_by_queue,
                "processed_by_queue": processed_by_queue,
            }

        except Exception as e:
            logger.error(f"Failed to get DLQ stats: {e}", exc_info=True)
            return {
                "total_unprocessed": 0,
                "total_processed": 0,
                "unprocessed_by_queue": {},
                "processed_by_queue": {},
            }


def add_to_dlq(
    session: Session,
    queue_name: str,
    original_job_id: str,
    task_name: str,
    payload: Dict[str, Any],
    error_message: str,
) -> Optional[DeadLetterQueueEntry]:
    """Convenience function to add task to DLQ.

    Args:
        session: Database session
        queue_name: Queue name
        original_job_id: Original job ID
        task_name: Task name
        payload: Task payload
        error_message: Error message

    Returns:
        DeadLetterQueueEntry or None if failed
    """
    try:
        dlq = DLQService(session)
        return dlq.add_failed_task(
            queue_name=queue_name,
            original_job_id=original_job_id,
            task_name=task_name,
            payload=payload,
            error_message=error_message,
        )
    except Exception as e:
        logger.error(f"Failed to add to DLQ: {e}", exc_info=True)
        return None
