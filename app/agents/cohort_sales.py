"""Cohort Sales Agent using LangGraph.

This agent focuses on converting leads into $500 cohort sales through
multi-channel outreach.
"""
from datetime import datetime, timedelta
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.config import settings
from app.domain.types import ActionType, Channel, ConsumerStage


# Define the state
class AgentState(TypedDict):
    """State for the cohort sales agent."""
    creator_id: str
    consumer_id: str
    event: dict
    context: dict
    tools: list[str]
    actions: list[dict]
    reasoning: str
    metadata: dict
    messages: Annotated[list, add_messages]


# Initialize LLM
llm = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key,
    temperature=0.7,
)


def analyze_consumer(state: AgentState) -> AgentState:
    """Analyze consumer context and decide on actions."""
    context = state["context"]
    event = state["event"]

    stage = context.get("stage", "new")
    metrics = context.get("metrics", {})
    event_type = event.get("type")

    # Build analysis prompt
    system_prompt = """You are a sales assistant helping creators convert leads into cohort purchases.

Your goal is to nurture leads through personalized, value-driven outreach across email and WhatsApp.

Guidelines:
- Focus on $500 cohort offerings
- Use multi-channel approach (email + WhatsApp)
- Provide value before asking for the sale
- Be conversational and authentic
- Respect engagement signals - don't oversell to uninterested leads

Return your analysis in JSON format with:
- should_take_action: boolean
- recommended_channel: "email" or "whatsapp" or "both"
- message_tone: "introduction", "value", "nudge", or "close"
- reasoning: explanation of your decision
"""

    user_prompt = f"""
Consumer Context:
- Stage: {stage}
- Page Views: {metrics.get('page_views', 0)}
- Emails Sent: {metrics.get('emails_sent', 0)}
- Emails Opened: {metrics.get('emails_opened', 0)}
- WhatsApp Messages: {metrics.get('whatsapp_messages_sent', 0)}
- Last Seen: {context.get('last_seen_at', 'Never')}

Recent Event: {event_type}
Event Payload: {event.get('payload', {})}

Should we take action? If yes, what channel and tone should we use?
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    response = llm.invoke(messages)

    state["messages"] = messages + [response]
    state["reasoning"] = response.content

    return state


def plan_actions(state: AgentState) -> AgentState:
    """Plan specific actions based on analysis."""
    context = state["context"]
    event = state["event"]
    reasoning = state["reasoning"]

    stage = context.get("stage", "new")
    metrics = context.get("metrics", {})
    event_type = event.get("type")

    actions = []

    # Simple heuristic-based action planning
    # In production, this could be more sophisticated or LLM-driven

    page_views = metrics.get("page_views", 0)
    emails_sent = metrics.get("emails_sent", 0)
    whatsapp_sent = metrics.get("whatsapp_messages_sent", 0)

    now = datetime.utcnow()
    send_time = now + timedelta(minutes=5)  # Small delay

    # New lead - send initial WhatsApp
    if stage == "new" and event_type == "page_view" and whatsapp_sent == 0:
        actions.append({
            "action_type": ActionType.SEND_WHATSAPP.value,
            "channel": Channel.WHATSAPP.value,
            "payload": {
                "to_number": event.get("payload", {}).get("whatsapp", ""),
                "message": f"Hey! 👋 Noticed you checked out our cohort. "
                           f"It's designed for folks looking to level up. "
                           f"Any questions? Happy to help!",
            },
            "send_at": send_time.isoformat(),
            "priority": 1.0,
        })

    # Interested lead - send email with value
    elif stage == "interested" and emails_sent < 2:
        actions.append({
            "action_type": ActionType.SEND_EMAIL.value,
            "channel": Channel.EMAIL.value,
            "payload": {
                "to_email": event.get("payload", {}).get("email", ""),
                "subject": "What you'll learn in the cohort",
                "body": """<html><body>
<p>Hi there,</p>

<p>Since you've been exploring our cohort, I wanted to share what makes it special:</p>

<ul>
<li>Live sessions every week with hands-on practice</li>
<li>Private community for networking and support</li>
<li>Real-world projects you can add to your portfolio</li>
</ul>

<p>The next batch starts soon. Would love to see you there!</p>

<p>Any questions? Just reply to this email.</p>

<p>Best,<br>The Team</p>
</body></html>""",
            },
            "send_at": send_time.isoformat(),
            "priority": 0.8,
        })

    # Engaged lead - send payment link
    elif stage == "engaged" and "whatsapp_message_received" in event_type:
        # Get cohort product (would need to query DB in real implementation)
        actions.append({
            "action_type": ActionType.SEND_PAYMENT_LINK.value,
            "channel": Channel.PAYMENT.value,
            "payload": {
                "product_id": event.get("payload", {}).get("product_id", ""),
                "message": "Here's the payment link for the cohort. "
                          "Excited to have you join us!",
            },
            "send_at": now.isoformat(),
            "priority": 1.0,
        })

    state["actions"] = actions
    state["metadata"] = {
        "agent_type": "cohort_sales",
        "version": "1.0",
        "stage": stage,
        "actions_planned": len(actions),
    }

    return state


def should_continue(state: AgentState) -> str:
    """Determine if we should continue processing."""
    # Simple check - if we have actions, we're done
    if state.get("actions"):
        return "end"
    return "end"


# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze", analyze_consumer)
workflow.add_node("plan", plan_actions)

# Add edges
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "plan")
workflow.add_edge("plan", END)

# Compile the graph
graph = workflow.compile()
