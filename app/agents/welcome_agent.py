"""Welcome Agent - Simple agent that welcomes new leads.

This is an example of how simple it is to create a new agent using the BaseAgent interface.
"""
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext


class WelcomeAgent(BaseAgent):
    """Welcomes new leads when they first visit the site.

    This agent:
    - Triggers on the first page view
    - Sends a friendly WhatsApp message
    - Optionally sends a welcome email
    """

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Act only on first page view for new leads."""
        # Check if this is a page view event
        if event.type != "page_view":
            return False

        # Check if this is their first page view
        if self.get_page_views(context) != 1:
            return False

        # Check if lead is new
        if not self.is_new_lead(context):
            return False

        return True

    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> list[PlannedAction]:
        """Send welcome message via WhatsApp."""
        actions = []

        # Get contact info from event payload
        whatsapp = self.get_event_payload(event, "whatsapp")
        email = self.get_event_payload(event, "email")
        page_url = self.get_event_payload(event, "page_url", "our site")

        # Send WhatsApp welcome if available
        if whatsapp:
            message = (
                f"Hey! 👋 Thanks for checking out {page_url}. "
                f"I'm here if you have any questions. "
                f"What brought you here today?"
            )
            actions.append(
                self.send_whatsapp(
                    to=whatsapp,
                    message=message,
                    delay_minutes=2,  # Small delay to seem natural
                    priority=1.0,
                )
            )

        # Optionally send email
        if email and self.config.get("send_welcome_email", False):
            subject = "Welcome! 🎉"
            body = f"""
            <html>
            <body>
                <h2>Hey there!</h2>
                <p>Thanks for stopping by. We're excited to have you here.</p>
                <p>Feel free to explore, and reach out if you have any questions!</p>
                <p>Best,<br>The Team</p>
            </body>
            </html>
            """
            actions.append(
                self.send_email(
                    to=email,
                    subject=subject,
                    body=body,
                    delay_minutes=5,
                    priority=0.8,
                )
            )

        return actions
