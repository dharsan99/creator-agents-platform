"""
Tool Registry - Central registry for all available tools

Provides dynamic tool discovery and management.
Agents query this registry to find available tools.
"""

from typing import Dict, List, Optional
import logging
from app.domain.tools.base import BaseTool, ToolCategory

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for all tools in the system

    Tools self-register when imported. The registry provides:
    - Dynamic discovery of available tools
    - Filtering by category, availability
    - Schema retrieval for tool calling
    - Missing tool detection

    Usage:
        registry = ToolRegistry()
        email_tool = registry.get_tool("send_email")
        available_tools = registry.get_available_tools()
        missing_tools = registry.get_missing_tools()
    """

    _instance: Optional['ToolRegistry'] = None
    _tools: Dict[str, BaseTool] = {}

    def __new__(cls):
        """Singleton pattern - only one registry instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry and discover tools"""
        if self._initialized:
            return

        self._initialized = True
        self._tools = {}
        self._discover_tools()

    def _discover_tools(self):
        """
        Discover and register all tool implementations

        This method imports tool modules and registers them.
        Tools are automatically discovered from:
        - app.domain.tools.communication
        - app.domain.tools.data
        - app.domain.tools.analytics
        - app.domain.tools.content
        - app.domain.tools.scheduling
        """
        # Import tool modules to trigger registration
        # Tools will self-register via register_tool() calls
        try:
            from app.domain.tools import communication
            logger.info("Discovered communication tools")
        except ImportError as e:
            logger.warning(f"Communication tools not available: {e}")

        try:
            from app.domain.tools import data
            logger.info("Discovered data tools")
        except ImportError as e:
            logger.warning(f"Data tools not available: {e}")

        try:
            from app.domain.tools import knowledge
            logger.info("Discovered knowledge tools")
        except ImportError as e:
            logger.warning(f"Knowledge tools not available: {e}")

        logger.info(f"Tool discovery complete. Registered {len(self._tools)} tools")

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry

        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} (available={tool.is_available})")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool by name

        Args:
            tool_name: Name of the tool

        Returns:
            BaseTool instance or None if not found
        """
        return self._tools.get(tool_name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """
        Get all registered tools

        Returns:
            Dict mapping tool_name → BaseTool
        """
        return self._tools.copy()

    def get_available_tools(self) -> Dict[str, BaseTool]:
        """
        Get only tools that are currently available

        Returns:
            Dict mapping tool_name → BaseTool for available tools
        """
        return {
            name: tool
            for name, tool in self._tools.items()
            if tool.is_available
        }

    def get_tools_by_category(self, category: str) -> Dict[str, BaseTool]:
        """
        Get tools filtered by category

        Args:
            category: Tool category (communication, data, analytics, etc.)

        Returns:
            Dict mapping tool_name → BaseTool for matching category
        """
        return {
            name: tool
            for name, tool in self._tools.items()
            if tool.category == category
        }

    def get_missing_tools(self) -> Dict[str, str]:
        """
        Get tools that are registered but unavailable

        Returns:
            Dict mapping tool_name → reason (why unavailable)
        """
        missing = {}
        for name, tool in self._tools.items():
            if not tool.is_available:
                # Try to get reason from tool
                reason = "Dependencies missing or not configured"
                missing[name] = reason

        return missing

    def get_tool_schemas(self, available_only: bool = True) -> List[Dict]:
        """
        Get schemas for all tools (useful for LLM tool binding)

        Args:
            available_only: If True, only return schemas for available tools

        Returns:
            List of tool schemas in OpenAPI format
        """
        tools = self.get_available_tools() if available_only else self._tools

        return [
            tool.get_schema()
            for tool in tools.values()
        ]

    def tool_exists(self, tool_name: str) -> bool:
        """
        Check if a tool is registered

        Args:
            tool_name: Name of the tool

        Returns:
            bool: True if tool exists (even if unavailable)
        """
        return tool_name in self._tools

    def is_tool_available(self, tool_name: str) -> bool:
        """
        Check if a tool is available for use

        Args:
            tool_name: Name of the tool

        Returns:
            bool: True if tool exists AND is available
        """
        tool = self._tools.get(tool_name)
        return tool is not None and tool.is_available

    def get_statistics(self) -> Dict[str, any]:
        """
        Get registry statistics

        Returns:
            Dict with tool counts by category, availability, etc.
        """
        total_tools = len(self._tools)
        available_tools = len(self.get_available_tools())
        missing_tools = total_tools - available_tools

        # Count by category
        category_counts: Dict[str, int] = {}
        for tool in self._tools.values():
            category = tool.category
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "total_tools": total_tools,
            "available_tools": available_tools,
            "unavailable_tools": missing_tools,
            "tools_by_category": category_counts
        }

    def refresh_availability(self) -> None:
        """
        Refresh availability status for all tools

        Useful after configuration changes (e.g., API keys added)
        """
        for tool in self._tools.values():
            tool.is_available = tool.check_availability()

        logger.info(f"Refreshed tool availability. {len(self.get_available_tools())}/{len(self._tools)} available")


# Global registry instance
_registry_instance: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance
