"""
Tools domain - Runtime tool execution for agents

This module provides a dynamic tool system that allows agents to:
- Execute tools during reasoning (not just plan actions)
- Discover available tools dynamically
- Handle missing tools gracefully
- Log tool needs for future implementation

Key components:
- BaseTool: Abstract interface for all tools
- ToolRegistry: Central registry with dynamic discovery
- ToolExecutor: Executes tools with timeout, retry, and policy validation
- MissingToolLogger: Tracks requests for tools that don't exist yet
"""

from app.domain.tools.base import BaseTool, ToolResult
from app.domain.tools.registry import ToolRegistry
from app.domain.tools.executor import ToolExecutor, ToolExecutionError
from app.domain.tools.missing_tools import MissingToolLogger, MissingToolRequest

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolRegistry",
    "ToolExecutor",
    "ToolExecutionError",
    "MissingToolLogger",
    "MissingToolRequest",
]
