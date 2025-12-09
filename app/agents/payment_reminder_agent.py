"""Payment Reminder Agent - Sends payment links to engaged leads.

This agent shows how to interact with products and generate payment links.
"""
from datetime import datetime, timedelta
from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext


class PaymentReminderAgent(BaseAgent):
    """Sends payment links to highly engaged leads who are ready to buy.

    Triggers when:
    - Consumer is in engaged stage
    - Consumer replied to WhatsApp or email
    - Consumer has shown strong interest signals
    - No payment link sent yet
    """

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Act when engaged lead shows buying signals."""
        # Check if this is a reply/engagement event
        buying_signals = [
            "whatsapp_message_received",
            "email_replied",
            "booking_created"  # Scheduled a call = buying signal
        ]

        if event.type not in buying_signals:
            return False

        # Must be in engaged stage
        if not self.is_engaged(context):
            return False

        # Don't send to already converted
        if self.is_converted(context):
            return False

        # Check if we've already sent a payment link
        # (You'd need to track this in context metrics)
        payment_links_sent = self.get_metric(context, "payment_links_sent", 0)
        if payment_links_sent > 0:
            return False

        # Strong engagement signals
        page_views = self.get_page_views(context)
        emails_opened = self.get_emails_opened(context)

        # Need at least some engagement
        if page_views < 2 or emails_opened < 1:
            return False

        return True

    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> list[PlannedAction]:
        """Send payment link with personalized message."""
        actions = []

        # Get contact info and product ID
        whatsapp = self.get_event_payload(event, "whatsapp")
        email = self.get_event_payload(event, "email")
        product_id = self.config.get("product_id")  # Set in agent config

        if not product_id:
            # No product configured, skip
            return actions

        # Check if they replied with interest keywords
        message_content = self.get_event_payload(event, "message", "").lower()
        shows_interest = any(
            keyword in message_content
            for keyword in ["interested", "price", "cost", "sign up", "join", "yes"]
        )

        # Send payment link via WhatsApp if they showed interest
        if whatsapp and shows_interest:
            # First send the payment link
            actions.append(
                self.send_payment_link(
                    product_id=product_id,
                    message="Here's the payment link for the cohort program. "
                            "Excited to have you join us! 🎉",
                    priority=1.0,
                )
            )

            # Then send a WhatsApp message with details
            whatsapp_message = (
                "Perfect timing! 🎯\n\n"
                "I'm sending over the payment link now. "
                "Once you're in, you'll get immediate access to:\n\n"
                "✅ All course materials\n"
                "✅ Private community\n"
                "✅ Weekly live sessions\n"
                "✅ 1:1 support\n\n"
                "The next batch starts in 5 days. "
                "Let me know if you have any questions!"
            )

            actions.append(
                self.send_whatsapp(
                    to=whatsapp,
                    message=whatsapp_message,
                    delay_minutes=1,  # Send right after payment link
                    priority=1.0,
                )
            )

        # Also send email with payment link
        elif email:
            subject = "Ready to join? Here's your payment link 🚀"
            body = f"""
            <html>
            <body>
                <h2>You're one step away!</h2>

                <p>Based on our conversation, I think you'd be a great fit for the program.</p>

                <p>Here's what happens after you join:</p>
                <ul>
                    <li><strong>Immediate access</strong> to all course materials</li>
                    <li><strong>Join the private community</strong> with 100+ members</li>
                    <li><strong>Weekly live sessions</strong> starting next week</li>
                    <li><strong>1:1 support</strong> whenever you need it</li>
                </ul>

                <p>The next cohort starts in 5 days, and we're limiting it to 50 people
                to keep the experience intimate and effective.</p>

                <p><strong>Ready to join?</strong> Click below to secure your spot:</p>

                <p style="text-align: center; margin: 30px 0;">
                    <a href="#" style="background: #4F46E5; color: white; padding: 15px 40px;
                    text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Join the Cohort →
                    </a>
                </p>

                <p>Have questions? Just reply to this email.</p>

                <p>See you inside!<br>The Team</p>
            </body>
            </html>
            """

            actions.append(
                self.send_payment_link(
                    product_id=product_id,
                    priority=1.0,
                )
            )

            actions.append(
                self.send_email(
                    to=email,
                    subject=subject,
                    body=body,
                    delay_minutes=2,
                    priority=1.0,
                )
            )

        return actions

    def analyze(self, context: ConsumerContext, event: Event) -> dict:
        """Analyze buying readiness."""
        engagement_score = (
            self.get_page_views(context) * 1 +
            self.get_emails_opened(context) * 3 +
            self.get_metric(context, "whatsapp_messages_received", 0) * 5
        )

        return {
            "engagement_score": engagement_score,
            "ready_to_buy": engagement_score >= 10,
            "page_views": self.get_page_views(context),
            "emails_opened": self.get_emails_opened(context),
            "stage": context.stage,
        }
