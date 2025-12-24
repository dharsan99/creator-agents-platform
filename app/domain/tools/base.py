"""
Base tool interface for all tools in the system

Tools are executable capabilities that agents can use during reasoning.
Each tool has a schema, timeout, and availability check.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ToolResult(BaseModel):
    """Standardized result from tool execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float
    tool_name: str
    timestamp: datetime


class BaseTool(ABC):
    """
    Abstract base class for all tools

    Tools are capabilities that agents can call during execution.
    Unlike PlannedActions (which are scheduled for later), tools execute immediately.

    Example tools:
    - Communication: send_email, send_whatsapp, send_sms
    - Data: get_consumer_context, update_consumer_stage
    - Analytics: get_campaign_metrics
    - Content: generate_image, create_video
    - Scheduling: schedule_meeting, create_calendar_event
    """

    # Tool metadata (set by subclass)
    name: str
    description: str
    category: str  # "communication", "data", "analytics", "content", "scheduling"

    # Tool configuration
    timeout_seconds: int = 30  # Default 30-second timeout
    retry_on_timeout: bool = True
    max_retries: int = 2
    is_available: bool = True  # Can be set to False if dependencies missing

    # JSON Schema for parameters (OpenAPI-compatible)
    schema: Dict[str, Any] = {}

    def __init__(self):
        """Initialize tool and check availability"""
        self.is_available = self.check_availability()

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters

        Args:
            **kwargs: Tool-specific parameters (validated against schema)

        Returns:
            ToolResult: Standardized result with success status, data, and metadata

        Raises:
            ValueError: If parameters don't match schema
            TimeoutError: If execution exceeds timeout_seconds
            Exception: Tool-specific errors
        """
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        """
        Check if tool dependencies are available

        Returns:
            bool: True if tool can be used, False if dependencies missing

        Example:
            For SendEmailTool, check if SES credentials are configured
            For GenerateImageTool, check if DALL-E API key exists
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """
        Get JSON Schema for tool parameters

        Returns:
            Dict: JSON Schema compatible with OpenAPI
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.schema,
            "timeout_seconds": self.timeout_seconds,
            "is_available": self.is_available
        }

    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate parameters against schema

        Args:
            **kwargs: Parameters to validate

        Returns:
            bool: True if valid, raises ValueError if invalid
        """
        # Basic validation - check required fields
        if "required" in self.schema:
            for field in self.schema["required"]:
                if field not in kwargs:
                    raise ValueError(f"Missing required parameter: {field}")

        # Type validation would go here
        # For now, we assume parameters are correct
        return True

    def __repr__(self) -> str:
        status = "available" if self.is_available else "unavailable"
        return f"<{self.__class__.__name__} ({status})>"


class ToolCategory:
    """Tool categories for organization"""
    COMMUNICATION = "communication"
    DATA = "data"
    ANALYTICS = "analytics"
    CONTENT = "content"
    SCHEDULING = "scheduling"
    KNOWLEDGE = "knowledge"
    PAYMENT = "payment"
