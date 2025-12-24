"""
Tool Executor - Executes tools with timeout, retry, and policy validation

Handles the actual execution of tools with:
- Timeout enforcement (30 seconds default)
- Retry logic for transient failures
- Policy validation (rate limits, consent)
- Execution logging
"""

import time
import logging
from typing import Optional, Any, Dict
from uuid import UUID
import asyncio
from concurrent.futures import TimeoutError as FuturesTimeoutError
from sqlmodel import Session

from app.domain.tools.base import BaseTool, ToolResult
from app.domain.tools.registry import ToolRegistry
from app.domain.policy.service import PolicyService

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    pass


class ToolExecutor:
    """
    Executes tools with safety checks and monitoring

    Features:
    - Timeout enforcement (configurable per tool)
    - Automatic retry on timeout/transient failures
    - Policy validation before execution
    - Execution time tracking
    - Error handling and logging

    Usage:
        executor = ToolExecutor(session, policy_service)
        result = executor.execute(
            tool_name="send_email",
            creator_id=creator.id,
            consumer_id=consumer.id,
            to="user@example.com",
            subject="Hello",
            body="Welcome!"
        )
    """

    def __init__(
        self,
        session: Session,
        policy_service: Optional[PolicyService] = None,
        registry: Optional[ToolRegistry] = None
    ):
        """
        Initialize tool executor

        Args:
            session: Database session for logging
            policy_service: Optional policy service for validation
            registry: Optional tool registry (uses global if not provided)
        """
        self.session = session
        self.policy_service = policy_service
        self.registry = registry or ToolRegistry()

    def execute(
        self,
        tool_name: str,
        creator_id: Optional[UUID] = None,
        consumer_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute a tool with safety checks

        Args:
            tool_name: Name of the tool to execute
            creator_id: Creator context (for policy validation)
            consumer_id: Consumer context (for policy validation)
            agent_id: Agent making the call (for logging)
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult: Standardized result from tool execution

        Raises:
            ToolExecutionError: If tool not found or execution fails
            TimeoutError: If execution exceeds timeout
            ValueError: If parameters invalid
        """
        start_time = time.time()

        # Get tool from registry
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            raise ToolExecutionError(f"Tool '{tool_name}' not found in registry")

        if not tool.is_available:
            raise ToolExecutionError(
                f"Tool '{tool_name}' is registered but unavailable. "
                f"Check dependencies and configuration."
            )

        # Validate policy if policy service is available
        if self.policy_service and creator_id and consumer_id:
            try:
                policy_result = self.policy_service.validate_tool_call(
                    creator_id=creator_id,
                    consumer_id=consumer_id,
                    tool_name=tool_name,
                    params=kwargs
                )

                if not policy_result.approved:
                    error_msg = f"Policy violation: {', '.join(policy_result.violations)}"
                    logger.warning(
                        f"Tool execution blocked by policy",
                        extra={
                            "tool_name": tool_name,
                            "creator_id": str(creator_id),
                            "consumer_id": str(consumer_id),
                            "violations": policy_result.violations
                        }
                    )
                    return ToolResult(
                        success=False,
                        data=None,
                        error=error_msg,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        tool_name=tool_name,
                        timestamp=policy_result.timestamp if hasattr(policy_result, 'timestamp') else None
                    )
            except Exception as e:
                logger.error(f"Policy validation error: {e}")
                # Continue execution if policy check fails (fail open for now)

        # Validate parameters against tool schema
        try:
            tool.validate_parameters(**kwargs)
        except ValueError as e:
            raise ToolExecutionError(f"Invalid parameters for tool '{tool_name}': {e}")

        # Execute tool with retry logic
        max_retries = tool.max_retries if tool.retry_on_timeout else 0
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                # Execute with timeout
                result = self._execute_with_timeout(
                    tool=tool,
                    timeout_seconds=tool.timeout_seconds,
                    **kwargs
                )

                # Log successful execution
                execution_time_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Tool executed successfully",
                    extra={
                        "tool_name": tool_name,
                        "execution_time_ms": execution_time_ms,
                        "attempt": attempt + 1,
                        "creator_id": str(creator_id) if creator_id else None,
                        "consumer_id": str(consumer_id) if consumer_id else None
                    }
                )

                return result

            except FuturesTimeoutError:
                last_error = f"Tool execution timed out after {tool.timeout_seconds} seconds"
                logger.warning(
                    f"Tool execution timeout (attempt {attempt + 1}/{max_retries + 1})",
                    extra={
                        "tool_name": tool_name,
                        "timeout_seconds": tool.timeout_seconds
                    }
                )
                attempt += 1

            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Tool execution error (attempt {attempt + 1}/{max_retries + 1})",
                    extra={
                        "tool_name": tool_name,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                attempt += 1

        # All retries exhausted
        execution_time_ms = (time.time() - start_time) * 1000
        return ToolResult(
            success=False,
            data=None,
            error=last_error or "Tool execution failed",
            execution_time_ms=execution_time_ms,
            tool_name=tool_name,
            timestamp=None
        )

    def _execute_with_timeout(
        self,
        tool: BaseTool,
        timeout_seconds: int,
        **kwargs
    ) -> ToolResult:
        """
        Execute tool with timeout enforcement

        Args:
            tool: Tool instance to execute
            timeout_seconds: Maximum execution time
            **kwargs: Tool parameters

        Returns:
            ToolResult from tool execution

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool.execute, **kwargs)
            try:
                result = future.result(timeout=timeout_seconds)
                return result
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise FuturesTimeoutError(
                    f"Tool '{tool.name}' execution exceeded {timeout_seconds} seconds"
                )

    def execute_batch(
        self,
        tool_calls: list[Dict[str, Any]],
        creator_id: Optional[UUID] = None,
        consumer_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None
    ) -> list[ToolResult]:
        """
        Execute multiple tools in sequence

        Args:
            tool_calls: List of dicts with {tool_name, **params}
            creator_id: Creator context
            consumer_id: Consumer context
            agent_id: Agent making calls

        Returns:
            List of ToolResult objects
        """
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.pop("tool_name")
            params = tool_call

            try:
                result = self.execute(
                    tool_name=tool_name,
                    creator_id=creator_id,
                    consumer_id=consumer_id,
                    agent_id=agent_id,
                    **params
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch execution error for tool '{tool_name}': {e}")
                results.append(ToolResult(
                    success=False,
                    data=None,
                    error=str(e),
                    execution_time_ms=0,
                    tool_name=tool_name,
                    timestamp=None
                ))

        return results
