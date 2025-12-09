"""Agent runtime for executing agent logic."""
import importlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from uuid import UUID

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from sqlmodel import Session

from app.domain.schemas import AgentInput, AgentOutput, PlannedAction
from app.domain.types import AgentImplementation
from app.domain.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentRuntime(ABC):
    """Abstract base class for agent runtimes."""

    @abstractmethod
    def execute(self, agent_config: dict, input_data: AgentInput) -> AgentOutput:
        """Execute agent and return planned actions."""
        pass


class LangGraphRuntime(AgentRuntime):
    """Runtime for LangGraph-based agents."""

    def __init__(self):
        self.graphs_cache: Dict[str, StateGraph] = {}

    def execute(self, agent_config: dict, input_data: AgentInput) -> AgentOutput:
        """Execute LangGraph agent.

        Args:
            agent_config: Agent configuration with 'graph_path' key
            input_data: Input data for the agent

        Returns:
            AgentOutput with planned actions
        """
        graph_path = agent_config.get("graph_path")
        if not graph_path:
            raise ValueError("LangGraph agent requires 'graph_path' in config")

        # Load the graph
        graph = self._load_graph(graph_path)

        # Prepare input state
        state = {
            "creator_id": str(input_data.creator_id),
            "consumer_id": str(input_data.consumer_id),
            "event": input_data.event.model_dump(),
            "context": input_data.context.model_dump(),
            "tools": input_data.tools,
            "actions": [],
            "reasoning": "",
        }

        try:
            # Execute the graph
            result = graph.invoke(state)

            # Extract actions from result
            actions = []
            for action_dict in result.get("actions", []):
                actions.append(PlannedAction(**action_dict))

            return AgentOutput(
                actions=actions,
                reasoning=result.get("reasoning", ""),
                metadata=result.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"LangGraph execution failed: {str(e)}")
            raise

    def _load_graph(self, graph_path: str) -> Any:
        """Load LangGraph from module path.

        Args:
            graph_path: Module path like 'app.agents.cohort_sales:graph'

        Returns:
            Compiled LangGraph
        """
        if graph_path in self.graphs_cache:
            return self.graphs_cache[graph_path]

        try:
            module_path, graph_name = graph_path.split(":")
            module = importlib.import_module(module_path)
            graph = getattr(module, graph_name)

            # Cache the compiled graph
            self.graphs_cache[graph_path] = graph
            return graph

        except Exception as e:
            logger.error(f"Failed to load graph from {graph_path}: {str(e)}")
            raise ValueError(f"Invalid graph_path: {graph_path}")


class ExternalHttpRuntime(AgentRuntime):
    """Runtime for external HTTP-based agents."""

    def __init__(self):
        self.http_client = httpx.Client(timeout=30.0)

    def execute(self, agent_config: dict, input_data: AgentInput) -> AgentOutput:
        """Execute external HTTP agent.

        Args:
            agent_config: Agent configuration with 'endpoint' key
            input_data: Input data for the agent

        Returns:
            AgentOutput with planned actions
        """
        endpoint = agent_config.get("endpoint")
        if not endpoint:
            raise ValueError("External HTTP agent requires 'endpoint' in config")

        # Prepare request payload
        payload = {
            "creator_id": str(input_data.creator_id),
            "consumer_id": str(input_data.consumer_id),
            "event": input_data.event.model_dump(),
            "context": input_data.context.model_dump(),
            "tools": input_data.tools,
        }

        try:
            response = self.http_client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

            # Parse response
            actions = []
            for action_dict in result.get("actions", []):
                actions.append(PlannedAction(**action_dict))

            return AgentOutput(
                actions=actions,
                reasoning=result.get("reasoning", ""),
                metadata=result.get("metadata", {}),
            )

        except httpx.HTTPError as e:
            logger.error(f"External HTTP agent call failed: {str(e)}")
            raise

    def __del__(self):
        """Close HTTP client on cleanup."""
        self.http_client.close()


class SimpleAgentRuntime(AgentRuntime):
    """Runtime for simple BaseAgent implementations.

    This runtime makes it easy for users to create agents by just
    implementing a Python class with should_act() and plan_actions() methods.
    """

    def __init__(self, session: Session):
        self.session = session
        self.agents_cache: Dict[str, type] = {}

    def execute(self, agent_config: dict, input_data: AgentInput) -> AgentOutput:
        """Execute simple BaseAgent.

        Args:
            agent_config: Agent configuration with 'agent_class' key
            input_data: Input data for the agent

        Returns:
            AgentOutput with planned actions
        """
        agent_class_path = agent_config.get("agent_class")
        if not agent_class_path:
            raise ValueError("Simple agent requires 'agent_class' in config")

        # Load the agent class
        agent_class = self._load_agent_class(agent_class_path)

        # Instantiate the agent
        agent_instance = agent_class(agent_config)

        # Get the actual database models from IDs
        from app.infra.db.models import Event, ConsumerContext

        event = self.session.get(Event, input_data.event.id)
        context = self.session.get(
            ConsumerContext,
            (input_data.creator_id, input_data.consumer_id)
        )

        if not event or not context:
            logger.error(f"Event or context not found for agent execution")
            return AgentOutput(actions=[], reasoning="Event or context not found")

        try:
            # Check if agent should act
            should_act = agent_instance.should_act(context, event)

            if not should_act:
                logger.info(f"Agent {agent_instance.name} decided not to act")
                return AgentOutput(
                    actions=[],
                    reasoning="Agent decided not to act based on context and event",
                    metadata={"should_act": False}
                )

            # Perform optional analysis
            analysis = agent_instance.analyze(context, event)

            # Plan actions
            actions = agent_instance.plan_actions(context, event)

            logger.info(
                f"Agent {agent_instance.name} generated {len(actions)} actions"
            )

            return AgentOutput(
                actions=actions,
                reasoning=f"Agent {agent_instance.name} decided to act",
                metadata={
                    "should_act": True,
                    "analysis": analysis,
                    "agent_class": agent_class_path,
                }
            )

        except Exception as e:
            logger.error(f"Simple agent execution failed: {str(e)}", exc_info=True)
            raise

    def _load_agent_class(self, class_path: str) -> type:
        """Load agent class from module path.

        Args:
            class_path: Module path like 'app.agents.my_agent:MyAgent'

        Returns:
            Agent class (subclass of BaseAgent)
        """
        if class_path in self.agents_cache:
            return self.agents_cache[class_path]

        try:
            module_path, class_name = class_path.split(":")
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)

            # Validate that it's a BaseAgent subclass
            if not issubclass(agent_class, BaseAgent):
                raise ValueError(
                    f"{class_name} must inherit from BaseAgent"
                )

            # Cache the class
            self.agents_cache[class_path] = agent_class
            return agent_class

        except Exception as e:
            logger.error(f"Failed to load agent class from {class_path}: {str(e)}")
            raise ValueError(f"Invalid agent_class: {class_path}")


class AgentRuntimeFactory:
    """Factory for creating agent runtimes."""

    @staticmethod
    def create(implementation: AgentImplementation, session: Session = None) -> AgentRuntime:
        """Create appropriate runtime based on implementation type.

        Args:
            implementation: Type of agent implementation
            session: Database session (required for simple agents)

        Returns:
            AgentRuntime instance
        """
        if implementation == AgentImplementation.LANGGRAPH:
            return LangGraphRuntime()
        elif implementation == AgentImplementation.EXTERNAL_HTTP:
            return ExternalHttpRuntime()
        elif implementation == AgentImplementation.SIMPLE:
            if not session:
                raise ValueError("SimpleAgentRuntime requires a database session")
            return SimpleAgentRuntime(session)
        else:
            raise ValueError(f"Unsupported agent implementation: {implementation}")
