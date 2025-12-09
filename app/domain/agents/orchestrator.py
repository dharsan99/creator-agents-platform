"""Orchestrator for agent invocation and action execution."""
import logging
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Session

from app.infra.db.models import AgentInvocation, Action, Event, ConsumerContext
from app.domain.agents.service import AgentService
from app.domain.context.service import ConsumerContextService
from app.domain.policy.service import PolicyService
from app.domain.channels.registry import ChannelRegistry
from app.domain.schemas import AgentInput, EventResponse, ConsumerContextResponse
from app.domain.types import EventType, ActionStatus, InvocationStatus, Channel

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central orchestrator for agent execution and action management."""

    def __init__(self, session: Session):
        self.session = session
        self.agent_service = AgentService(session)
        self.context_service = ConsumerContextService(session)
        self.policy_service = PolicyService(session)
        self.channel_registry = ChannelRegistry(session)

    def process_event_agents(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        event_id: UUID,
    ) -> list[UUID]:
        """Process agents for an event and return invocation IDs.

        This is called asynchronously by background workers.
        """
        # Get event
        event = self.session.get(Event, event_id)
        if not event:
            logger.error(f"Event {event_id} not found")
            return []

        # Get context
        context = self.context_service.get_context(creator_id, consumer_id)
        if not context:
            logger.error(f"Context not found for creator {creator_id}, consumer {consumer_id}")
            return []

        # Find matching agents
        event_type = EventType(event.type)
        agents = self.agent_service.get_agents_for_event(creator_id, event_type)

        if not agents:
            logger.info(f"No agents found for event type {event_type}")
            return []

        logger.info(f"Found {len(agents)} agents for event {event_id}")

        invocation_ids = []

        for agent in agents:
            try:
                # Create invocation record
                invocation = AgentInvocation(
                    id=uuid4(),
                    agent_id=agent.id,
                    creator_id=creator_id,
                    consumer_id=consumer_id,
                    trigger_event_id=event_id,
                    status=InvocationStatus.PENDING.value,
                )
                self.session.add(invocation)
                self.session.commit()
                self.session.refresh(invocation)

                # Execute agent
                agent_input = self._build_agent_input(event, context)
                agent_output = self.agent_service.execute_agent(
                    agent, agent_input, invocation.id
                )

                # Process planned actions
                self._process_actions(
                    invocation.id,
                    creator_id,
                    consumer_id,
                    agent_output.actions,
                )

                invocation_ids.append(invocation.id)

            except Exception as e:
                logger.error(f"Failed to process agent {agent.id}: {str(e)}")
                continue

        return invocation_ids

    def _build_agent_input(
        self,
        event: Event,
        context: ConsumerContext,
    ) -> AgentInput:
        """Build agent input from event and context."""
        # Convert to response schemas
        event_response = EventResponse.model_validate(event)
        context_response = ConsumerContextResponse.model_validate(context)

        # Available tools (channels)
        tools = [channel.value for channel in Channel]

        return AgentInput(
            creator_id=event.creator_id,
            consumer_id=event.consumer_id,
            event=event_response,
            context=context_response,
            tools=tools,
        )

    def _process_actions(
        self,
        invocation_id: UUID,
        creator_id: UUID,
        consumer_id: UUID,
        planned_actions: list,
    ) -> None:
        """Process planned actions through policy and execution."""
        logger.info(f"Processing {len(planned_actions)} planned actions for invocation {invocation_id}")

        for planned_action in planned_actions:
            try:
                # Create action record
                action = Action(
                    id=uuid4(),
                    agent_invocation_id=invocation_id,
                    creator_id=creator_id,
                    consumer_id=consumer_id,
                    action_type=planned_action.action_type.value,
                    channel=planned_action.channel.value,
                    payload=planned_action.payload,
                    send_at=planned_action.send_at,
                    priority=planned_action.priority,
                    status=ActionStatus.PLANNED.value,
                )
                self.session.add(action)
                self.session.commit()
                self.session.refresh(action)

                # Validate through policy engine
                policy_decision = self.policy_service.validate_action(
                    creator_id, consumer_id, planned_action
                )

                action.policy_decision = policy_decision.model_dump()

                if policy_decision.approved:
                    action.status = ActionStatus.APPROVED.value
                    self.session.add(action)
                    self.session.commit()

                    # Execute immediately if send time has passed
                    if action.send_at <= datetime.utcnow():
                        self._execute_action(action)
                    else:
                        logger.info(f"Action {action.id} scheduled for {action.send_at}")
                else:
                    action.status = ActionStatus.DENIED.value
                    self.session.add(action)
                    self.session.commit()
                    logger.info(
                        f"Action {action.id} denied by policy: {policy_decision.reason}"
                    )

            except Exception as e:
                logger.error(f"Failed to process action: {str(e)}")
                continue

    def _execute_action(self, action: Action) -> None:
        """Execute an approved action through the channel registry."""
        logger.info(f"Executing action {action.id} via {action.channel}")

        try:
            action.status = ActionStatus.EXECUTING.value
            self.session.add(action)
            self.session.commit()

            channel = Channel(action.channel)
            result = self.channel_registry.execute(
                channel,
                action.creator_id,
                action.consumer_id,
                action.payload,
            )

            action.status = ActionStatus.EXECUTED.value
            action.updated_at = datetime.utcnow()

            # Store execution result in payload
            action.payload["execution_result"] = result

            self.session.add(action)
            self.session.commit()

            logger.info(f"Action {action.id} executed successfully")

        except Exception as e:
            logger.error(f"Action {action.id} execution failed: {str(e)}")
            action.status = ActionStatus.FAILED.value
            action.payload["error"] = str(e)
            self.session.add(action)
            self.session.commit()

    def execute_pending_actions(self) -> int:
        """Execute all pending actions whose send_at time has passed.

        This can be called periodically by a scheduler.
        Returns the number of actions executed.
        """
        from sqlmodel import select

        statement = (
            select(Action)
            .where(Action.status == ActionStatus.APPROVED.value)
            .where(Action.send_at <= datetime.utcnow())
        )

        pending_actions = self.session.exec(statement).all()

        executed_count = 0
        for action in pending_actions:
            try:
                self._execute_action(action)
                executed_count += 1
            except Exception as e:
                logger.error(f"Failed to execute action {action.id}: {str(e)}")
                continue

        logger.info(f"Executed {executed_count} pending actions")
        return executed_count
