# Creating Custom Agents - Simple Guide

This guide shows you how to create custom agents using the simple `BaseAgent` interface. No complex framework knowledge required!

## Quick Start

Creating an agent is as simple as:

1. **Inherit from `BaseAgent`**
2. **Implement `should_act()`** - Decide when to act
3. **Implement `plan_actions()`** - Decide what to do

That's it! Here's a minimal example:

```python
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext

class MyFirstAgent(BaseAgent):
    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Decide if this agent should take action."""
        return event.type == "page_view" and context.stage == "new"

    def plan_actions(self, context: ConsumerContext, event: Event) -> list[PlannedAction]:
        """Decide what actions to take."""
        return [
            self.send_email(
                to="user@example.com",
                subject="Welcome!",
                body="<html>Thanks for visiting!</html>"
            )
        ]
```

## Step-by-Step Tutorial

### 1. Create Your Agent File

Create a new file in `app/agents/`:

```bash
touch app/agents/my_agent.py
```

### 2. Import Required Classes

```python
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext
```

### 3. Define Your Agent Class

```python
class MyAgent(BaseAgent):
    """Your agent description here."""
    pass
```

### 4. Implement `should_act()`

This method decides **when** your agent should act. It receives:
- `context`: Consumer's current state (stage, metrics, history)
- `event`: The event that triggered this agent

Return `True` to act, `False` to skip.

```python
def should_act(self, context: ConsumerContext, event: Event) -> bool:
    """Your filtering logic."""

    # Example 1: Act on first page view
    if event.type == "page_view" and self.get_page_views(context) == 1:
        return True

    # Example 2: Act on engaged leads who opened emails
    if event.type == "email_opened" and self.is_engaged(context):
        return True

    # Example 3: Act on WhatsApp replies from non-converted leads
    if event.type == "whatsapp_message_received" and not self.is_converted(context):
        return True

    return False
```

### 5. Implement `plan_actions()`

This method decides **what** actions to take. Return a list of actions using the helper methods.

```python
def plan_actions(self, context: ConsumerContext, event: Event) -> list[PlannedAction]:
    """Your action logic."""

    actions = []

    # Send an email
    actions.append(
        self.send_email(
            to="user@example.com",
            subject="Hello!",
            body="<html><body><h1>Welcome!</h1></body></html>",
            delay_minutes=5,  # Optional delay
            priority=1.0,  # Optional priority
        )
    )

    # Send a WhatsApp message
    actions.append(
        self.send_whatsapp(
            to="+1234567890",
            message="Hey! Thanks for your interest.",
            delay_minutes=0,
        )
    )

    # Send a payment link
    actions.append(
        self.send_payment_link(
            product_id="your-product-uuid",
            message="Ready to join? Here's the payment link!",
        )
    )

    # Schedule a call
    from datetime import datetime, timedelta
    actions.append(
        self.schedule_call(
            phone="+1234567890",
            scheduled_time=datetime.utcnow() + timedelta(days=1),
        )
    )

    return actions
```

## Helper Methods

### Context Helpers

Get information about the consumer:

```python
# Check stage
self.is_new_lead(context)       # Is this a new lead?
self.is_engaged(context)         # Is consumer engaged?
self.is_converted(context)       # Has consumer purchased?
self.get_stage(context)          # Get current stage string

# Get metrics
self.get_page_views(context)     # Number of page views
self.get_emails_sent(context)    # Emails sent to consumer
self.get_emails_opened(context)  # Emails opened by consumer
self.get_total_revenue(context)  # Total revenue in cents

# Get any custom metric
self.get_metric(context, "custom_metric_name", default=0)
```

### Event Helpers

Get information from the event:

```python
# Check event type
self.is_event_type(event, "page_view")

# Get event data
self.get_event_payload(event, "email")
self.get_event_payload(event, "whatsapp")
self.get_event_payload(event, "page_url", default="")
```

### Action Helpers

Create actions easily:

```python
# Email
self.send_email(
    to="user@example.com",
    subject="Subject",
    body="<html>...</html>",
    from_email="optional@example.com",  # Optional
    delay_minutes=0,  # Optional delay
    priority=1.0,  # Optional priority (higher = more important)
)

# WhatsApp
self.send_whatsapp(
    to="+1234567890",  # Or "whatsapp:+1234567890"
    message="Your message",
    template="optional_template_name",  # For WhatsApp Business API
    delay_minutes=0,
    priority=1.0,
)

# Payment Link
self.send_payment_link(
    product_id="uuid-of-product",
    custom_amount_cents=50000,  # Optional override
    message="Optional message",
    delay_minutes=0,
    priority=1.0,
)

# Call
from datetime import datetime, timedelta
self.schedule_call(
    phone="+1234567890",
    scheduled_time=datetime.utcnow() + timedelta(hours=24),
    call_type="scheduled",  # or "immediate"
    priority=1.0,
)
```

## Complete Example

Here's a complete agent that welcomes new leads:

```python
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext


class WelcomeAgent(BaseAgent):
    """Welcomes new leads on their first visit."""

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        # Only act on first page view
        return (
            event.type == "page_view" and
            self.get_page_views(context) == 1 and
            self.is_new_lead(context)
        )

    def plan_actions(self, context: ConsumerContext, event: Event) -> list[PlannedAction]:
        actions = []

        # Get contact info from event
        whatsapp = self.get_event_payload(event, "whatsapp")
        email = self.get_event_payload(event, "email")

        # Send WhatsApp welcome
        if whatsapp:
            actions.append(
                self.send_whatsapp(
                    to=whatsapp,
                    message="Hey! 👋 Welcome to our site. I'm here if you have questions!",
                    delay_minutes=2,
                )
            )

        # Send email welcome
        if email:
            actions.append(
                self.send_email(
                    to=email,
                    subject="Welcome! 🎉",
                    body="""
                    <html>
                    <body>
                        <h2>Thanks for visiting!</h2>
                        <p>We're excited to have you here.</p>
                    </body>
                    </html>
                    """,
                    delay_minutes=5,
                )
            )

        return actions
```

## Registering Your Agent

Once your agent is created, register it via the API:

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: your-creator-id" \
  -d '{
    "name": "My Welcome Agent",
    "implementation": "simple",
    "config": {
      "agent_class": "app.agents.my_agent:MyAgent",
      "custom_setting": "value"
    },
    "enabled": true,
    "triggers": [
      {
        "event_type": "page_view",
        "filter": {}
      }
    ]
  }'
```

**Key Points:**
- `implementation`: Must be `"simple"`
- `agent_class`: Path to your agent in format `"module.path:ClassName"`
- `triggers`: List of event types that trigger this agent
- `config`: Any custom settings (accessible via `self.config` in your agent)

## Advanced: Custom Analysis

Override the `analyze()` method to perform custom analysis:

```python
def analyze(self, context: ConsumerContext, event: Event) -> dict:
    """Optional custom analysis."""
    engagement_score = (
        self.get_page_views(context) * 1 +
        self.get_emails_opened(context) * 2
    )

    return {
        "engagement_score": engagement_score,
        "is_hot_lead": engagement_score >= 10,
    }
```

This data is stored in the action metadata for tracking.

## Event Types Reference

Common event types you can filter on:

- `page_view` - Consumer viewed a page
- `email_sent` - Email was sent to consumer
- `email_opened` - Consumer opened an email
- `email_clicked` - Consumer clicked link in email
- `email_replied` - Consumer replied to email
- `whatsapp_message_sent` - WhatsApp sent to consumer
- `whatsapp_message_received` - Consumer replied via WhatsApp
- `booking_created` - Consumer booked a call/session
- `payment_success` - Consumer completed payment
- `payment_failed` - Payment failed

## Consumer Stages

Possible consumer stages:

- `new` - First time visitor
- `interested` - Showed some interest signals
- `engaged` - Multiple touchpoints, high engagement
- `converted` - Made a purchase
- `churned` - Lost interest/inactive

## Tips & Best Practices

### 1. Keep It Simple
Start with simple logic. You can always make it more sophisticated later.

### 2. Don't Over-Communicate
Check how many times you've contacted the consumer:
```python
if self.get_emails_sent(context) >= 3:
    return False  # Don't act
```

### 3. Respect Stage Transitions
Don't send sales messages to already converted customers:
```python
if self.is_converted(context):
    return False
```

### 4. Use Delays Wisely
Add small delays to make communication feel natural:
```python
self.send_whatsapp(..., delay_minutes=2)  # Wait 2 minutes
```

### 5. Leverage Configuration
Use `self.config` for flexibility:
```python
max_emails = self.config.get("max_emails", 3)
if self.get_emails_sent(context) >= max_emails:
    return False
```

### 6. Test Your Logic
Before enabling, test your `should_act()` logic thoroughly:
```python
def should_act(self, context, event):
    # Log your decision-making
    print(f"Event: {event.type}, Stage: {context.stage}")
    print(f"Page views: {self.get_page_views(context)}")

    # Your logic here
    ...
```

## Examples in the Codebase

Check these example agents for inspiration:

1. **`welcome_agent.py`** - Welcome new leads
2. **`followup_agent.py`** - Follow up with engaged leads
3. **`payment_reminder_agent.py`** - Send payment links to ready buyers

## Need Help?

- Check the `BaseAgent` docstrings for all available methods
- Look at example agents for patterns
- The policy engine will automatically enforce rate limits and quiet hours
- Actions are automatically validated before execution

Happy agent building! 🚀
