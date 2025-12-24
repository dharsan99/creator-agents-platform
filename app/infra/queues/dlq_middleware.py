"""Taskiq middleware for dead letter queue handling.

This middleware automatically captures tasks that fail after max retries
and adds them to the dead letter queue for later analysis or reprocessing.
"""

import logging
import traceback
from typing import Any, Dict

from taskiq import TaskiqResult, TaskiqMiddleware
from sqlmodel import Session

from app.infra.db.connection import engine
from app.infra.queues.dlq_service import add_to_dlq

logger = logging.getLogger(__name__)


class DLQMiddleware(TaskiqMiddleware):
    """Middleware to handle failed tasks by adding them to DLQ.

    This middleware intercepts task execution results and sends
    permanently failed tasks (after all retries) to the dead letter queue.
    """

    async def on_error(
        self,
        message: Any,
        result: TaskiqResult,
        exception: BaseException,
    ) -> None:
        """Handle task execution error.

        Args:
            message: Task message
            result: Task execution result
            exception: Exception that occurred
        """
        try:
            # Extract task information
            task_name = message.task_name if hasattr(message, "task_name") else "unknown"
            task_id = message.task_id if hasattr(message, "task_id") else "unknown"

            # Get task args (payload)
            if hasattr(message, "args"):
                payload = {"args": message.args}
            else:
                payload = {}

            # Get labels to check if this is the final retry
            labels = message.labels if hasattr(message, "labels") else {}
            retry_count = labels.get("retry", 0)
            max_retries = labels.get("max_retries", 3)

            # Only add to DLQ if this was the final retry
            if retry_count >= max_retries:
                logger.warning(
                    f"Task {task_name} ({task_id}) failed after {retry_count} retries, "
                    f"adding to DLQ"
                )

                # Determine queue name from task name
                queue_name = self._get_queue_name(task_name)

                # Format error message
                error_message = (
                    f"{exception.__class__.__name__}: {str(exception)}\n\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )

                # Add to DLQ
                with Session(engine) as session:
                    add_to_dlq(
                        session=session,
                        queue_name=queue_name,
                        original_job_id=str(task_id),
                        task_name=task_name,
                        payload=payload,
                        error_message=error_message[:5000],  # Limit to 5000 chars
                    )

                logger.info(f"Added task {task_id} to DLQ: {queue_name}")
            else:
                logger.info(
                    f"Task {task_name} ({task_id}) failed on retry {retry_count}/{max_retries}, "
                    f"will retry"
                )

        except Exception as e:
            logger.error(
                f"Failed to process error in DLQ middleware: {e}",
                exc_info=True
            )

    def _get_queue_name(self, task_name: str) -> str:
        """Determine queue name from task name.

        Args:
            task_name: Task name

        Returns:
            Queue name
        """
        # Map task names to queue names
        if "agent" in task_name.lower():
            return "agents"
        elif "action" in task_name.lower():
            return "actions"
        elif "supervisor" in task_name.lower():
            return "supervisor_tasks"
        elif "worker" in task_name.lower():
            return "worker_tasks"
        else:
            return "default"
