# Agent Quick Reference Card

## Minimal Agent Template

```python
from app.domain.agents.base_agent import BaseAgent
from app.infra.db.models import Event, ConsumerContext

class MyAgent(BaseAgent):
    def should_act(self, context, event) -> bool:
        # Your filtering logic
        return True

    def plan_actions(self, context, event):
        # Your action logic
        return []
```

## Context Helpers

```python
# Stage checks
self.is_new_lead(context)
self.is_engaged(context)
self.is_converted(context)
self.get_stage(context)  # Returns: "new", "interested", "engaged", "converted", "churned"

# Metrics
self.get_page_views(context)
self.get_emails_sent(context)
self.get_emails_opened(context)
self.get_total_revenue(context)  # In cents
self.get_metric(context, "metric_name", default=0)
```

## Event Helpers

```python
# Check event type
self.is_event_type(event, "page_view")

# Get event data
self.get_event_payload(event, "email")
self.get_event_payload(event, "whatsapp")
self.get_event_payload(event, "page_url", default="")
```

## Action Helpers

### Send Email
```python
self.send_email(
    to="user@example.com",
    subject="Subject",
    body="<html>...</html>",
    from_email="sender@example.com",  # Optional
    delay_minutes=0,
    priority=1.0,
)
```

### Send WhatsApp
```python
self.send_whatsapp(
    to="+1234567890",
    message="Your message",
    template="template_name",  # Optional
    delay_minutes=0,
    priority=1.0,
)
```

### Send Payment Link
```python
self.send_payment_link(
    product_id="uuid",
    custom_amount_cents=50000,  # Optional
    message="Optional message",
    delay_minutes=0,
    priority=1.0,
)
```

### Schedule Call
```python
from datetime import datetime, timedelta
self.schedule_call(
    phone="+1234567890",
    scheduled_time=datetime.utcnow() + timedelta(days=1),
    call_type="scheduled",  # or "immediate"
    priority=1.0,
)
```

## Event Types

```python
"page_view"                    # Page visited
"email_sent"                   # Email sent
"email_opened"                 # Email opened
"email_clicked"                # Email link clicked
"email_replied"                # Email replied to
"whatsapp_message_sent"        # WhatsApp sent
"whatsapp_message_received"    # WhatsApp received
"booking_created"              # Call/session booked
"booking_cancelled"            # Booking cancelled
"payment_success"              # Payment completed
"payment_failed"               # Payment failed
```

## Common Patterns

### First-time Visitor
```python
def should_act(self, context, event):
    return (
        event.type == "page_view" and
        self.get_page_views(context) == 1 and
        self.is_new_lead(context)
    )
```

### Engaged Lead
```python
def should_act(self, context, event):
    return (
        event.type in ["email_opened", "whatsapp_message_received"] and
        self.is_engaged(context) and
        not self.is_converted(context)
    )
```

### Rate Limiting
```python
def should_act(self, context, event):
    # Don't send more than 3 emails
    if self.get_emails_sent(context) >= 3:
        return False
    return True
```

### Engagement Score
```python
engagement_score = (
    self.get_page_views(context) * 1 +
    self.get_emails_opened(context) * 2 +
    self.get_metric(context, "whatsapp_messages_received", 0) * 3
)

if engagement_score >= 10:
    # High engagement - send payment link
```

## Registration via API

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: your-creator-id" \
  -d '{
    "name": "Agent Name",
    "implementation": "simple",
    "config": {
      "agent_class": "app.agents.my_agent:MyAgent",
      "custom_key": "custom_value"
    },
    "enabled": true,
    "triggers": [
      {"event_type": "page_view", "filter": {}},
      {"event_type": "email_opened", "filter": {}}
    ]
  }'
```

## Access Config in Agent

```python
class MyAgent(BaseAgent):
    def should_act(self, context, event):
        max_emails = self.config.get("max_emails", 3)
        return self.get_emails_sent(context) < max_emails
```

## Debugging Tips

```python
def should_act(self, context, event):
    # Log to see what's happening
    print(f"Event: {event.type}")
    print(f"Stage: {context.stage}")
    print(f"Page views: {self.get_page_views(context)}")

    # Your logic
    return True
```

## Full Example

```python
from app.domain.agents.base_agent import BaseAgent
from app.infra.db.models import Event, ConsumerContext

class FollowUpAgent(BaseAgent):
    """Follows up with engaged leads."""

    def should_act(self, context, event):
        return (
            event.type == "email_opened" and
            self.is_engaged(context) and
            self.get_emails_sent(context) < 3
        )

    def plan_actions(self, context, event):
        email = self.get_event_payload(event, "email")

        engagement = (
            self.get_page_views(context) * 1 +
            self.get_emails_opened(context) * 2
        )

        if engagement >= 5:
            message = "Let's schedule a call to discuss!"
        else:
            message = "Have questions? Reply to this email."

        return [
            self.send_email(
                to=email,
                subject="Quick follow-up",
                body=f"<html><body><p>{message}</p></body></html>",
                delay_minutes=30,
            )
        ]
```

---

📖 **Full Guide:** [AGENT_GUIDE.md](./AGENT_GUIDE.md)
📚 **Main README:** [README.md](./README.md)
