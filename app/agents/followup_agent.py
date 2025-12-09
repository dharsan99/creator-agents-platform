"""Follow-up Agent - Follows up with engaged leads who showed interest.

This agent demonstrates conditional logic based on consumer engagement.
"""
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext


class FollowUpAgent(BaseAgent):
    """Follows up with engaged leads after they show interest.

    Triggers when:
    - Consumer opened an email or replied to WhatsApp
    - Consumer hasn't been contacted recently
    - Consumer is in interested or engaged stage
    """

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Act on email opens or WhatsApp replies from interested leads."""
        # Check if this is an engagement event
        engagement_events = ["email_opened", "whatsapp_message_received", "email_replied"]
        if event.type not in engagement_events:
            return False

        # Don't act on converted customers
        if self.is_converted(context):
            return False

        # Check if lead is interested or engaged
        if context.stage not in ["interested", "engaged"]:
            return False

        # Don't over-communicate - check how many emails sent
        emails_sent = self.get_emails_sent(context)
        if emails_sent >= 3:
            return False

        return True

    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> list[PlannedAction]:
        """Send personalized follow-up based on engagement level."""
        actions = []

        # Get contact info from event
        email = self.get_event_payload(event, "email")

        # Calculate engagement score
        engagement_score = (
            self.get_page_views(context) * 1 +
            self.get_emails_opened(context) * 2
        )

        # High engagement - send value content + soft pitch
        if engagement_score >= 5:
            subject = "Thought you'd find this helpful"
            body = """
            <html>
            <body>
                <p>Hey!</p>
                <p>Since you've been exploring our program, I put together a quick resource
                that breaks down exactly what you'll learn and how it applies to real-world
                scenarios.</p>
                <p>I've also included some success stories from recent graduates - they were
                in similar positions before starting.</p>
                <p>Want to hop on a quick call to discuss if this is the right fit for you?
                No pressure, just want to make sure you have all the info you need.</p>
                <p>Let me know!</p>
                <p>Best,<br>The Team</p>
            </body>
            </html>
            """
            priority = 1.0

        # Medium engagement - share value
        elif engagement_score >= 3:
            subject = "Quick question about your goals"
            body = """
            <html>
            <body>
                <p>Hey!</p>
                <p>I noticed you've been checking out our program. I'd love to understand
                what you're hoping to achieve.</p>
                <p>Are you looking to:</p>
                <ul>
                    <li>Level up your current skills?</li>
                    <li>Make a career switch?</li>
                    <li>Start your own project?</li>
                </ul>
                <p>Just reply to this email and let me know - I can send over some
                resources tailored to your goals.</p>
                <p>Best,<br>The Team</p>
            </body>
            </html>
            """
            priority = 0.8

        # Low engagement - gentle nudge
        else:
            subject = "Still interested?"
            body = """
            <html>
            <body>
                <p>Hey!</p>
                <p>I saw you opened our email earlier. Just wanted to check in and see
                if you have any questions about the program.</p>
                <p>No pressure at all - I know deciding on a program is a big decision.
                Happy to answer anything that would help.</p>
                <p>Best,<br>The Team</p>
            </body>
            </html>
            """
            priority = 0.6

        if email:
            actions.append(
                self.send_email(
                    to=email,
                    subject=subject,
                    body=body,
                    delay_minutes=30,  # Give them time
                    priority=priority,
                )
            )

        return actions

    def analyze(self, context: ConsumerContext, event: Event) -> dict:
        """Analyze engagement level for metadata."""
        engagement_score = (
            self.get_page_views(context) * 1 +
            self.get_emails_opened(context) * 2
        )

        return {
            "engagement_score": engagement_score,
            "engagement_level": (
                "high" if engagement_score >= 5
                else "medium" if engagement_score >= 3
                else "low"
            ),
            "emails_sent": self.get_emails_sent(context),
            "stage": context.stage,
        }
