"""Base interface for channel tools."""
from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID


class ChannelTool(ABC):
    """Abstract base class for channel execution."""

    @abstractmethod
    def execute(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the channel action.

        Args:
            creator_id: ID of the creator
            consumer_id: ID of the consumer
            payload: Action-specific payload

        Returns:
            Result dictionary with execution details

        Raises:
            Exception if execution fails
        """
        pass

    @abstractmethod
    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate that payload has required fields."""
        pass
