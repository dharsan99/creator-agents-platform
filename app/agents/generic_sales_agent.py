"""Generic sales agent that works with any creator's profile."""
from datetime import datetime, timedelta
from app.domain.agents.base_agent import BaseAgent, PlannedAction


class GenericSalesAgent(BaseAgent):
    """Generic agent for selling any creator's services using their profile."""

    def should_act(self, context, event) -> bool:
        """
        Decide whether to reach out based on consumer behavior.

        Act when:
        - New lead visits the creator's page
        - Lead returns after 24+ hours of inactivity
        - Lead has shown interest but hasn't enrolled
        """
        # Get creator profile from config
        creator_profile = self.config.get("creator_profile")
        if not creator_profile:
            return False

        # Act on first page view (new lead)
        if event.type == "page_view" and self.get_page_views(context) == 1:
            return True

        # Act if lead returned after 24+ hours
        if event.type == "page_view":
            last_seen = context.last_seen_at
            if last_seen:
                hours_since = (datetime.utcnow() - last_seen).total_seconds() / 3600
                if hours_since >= 24 and self.get_page_views(context) > 1:
                    return True

        # Act if lead clicked on service but didn't enroll
        if event.type == "service_click" and not self.has_enrolled(context):
            return True

        return False

    def plan_actions(self, context, event):
        """
        Plan sales outreach using the creator's profile data.

        Uses:
        - sales_pitch: For initial outreach
        - agent_instructions: For tone and approach
        - objection_handling: For follow-ups
        - services: For specific offering details
        """
        actions = []
        creator_profile = self.config.get("creator_profile", {})

        # Extract profile data
        sales_pitch = creator_profile.get("sales_pitch", "")
        services = creator_profile.get("services", [])
        agent_instructions = creator_profile.get("agent_instructions", "")
        creator_name = creator_profile.get("creator_name", "")

        # Get consumer info from context metrics (should be set by context engine)
        consumer_whatsapp = self.get_metric(context, "whatsapp") or self.get_event_payload(event, "whatsapp")
        consumer_email = self.get_metric(context, "email") or self.get_event_payload(event, "email")
        consumer_name = self.get_metric(context, "name") or self.get_event_payload(event, "name") or "there"

        # Scenario 1: New lead - send initial pitch
        if event.type == "page_view" and self.get_page_views(context) == 1:
            # Personalized greeting with sales pitch
            message = self._create_initial_pitch(
                consumer_name=consumer_name,
                creator_name=creator_name,
                sales_pitch=sales_pitch,
                services=services
            )

            if consumer_whatsapp:
                actions.append(
                    self.send_whatsapp(
                        to=consumer_whatsapp,
                        message=message,
                        delay_minutes=5,  # Wait 5 minutes after page view
                        priority=1.0
                    )
                )

        # Scenario 2: Returning lead - send follow-up
        elif event.type == "page_view" and self.get_page_views(context) > 1:
            follow_up_message = self._create_follow_up_message(
                consumer_name=consumer_name,
                creator_name=creator_name,
                services=services,
                agent_instructions=agent_instructions
            )

            if consumer_whatsapp:
                actions.append(
                    self.send_whatsapp(
                        to=consumer_whatsapp,
                        message=follow_up_message,
                        delay_minutes=10,
                        priority=0.8
                    )
                )

        # Scenario 3: Service click - send enrollment link
        elif event.type == "service_click":
            service_id = self.get_event_payload(event, "service_id")
            service = self._find_service_by_id(services, service_id)

            if service:
                enrollment_message = self._create_enrollment_message(
                    consumer_name=consumer_name,
                    creator_name=creator_name,
                    service=service,
                    agent_instructions=agent_instructions
                )

                if consumer_whatsapp:
                    actions.append(
                        self.send_whatsapp(
                            to=consumer_whatsapp,
                            message=enrollment_message,
                            delay_minutes=2,
                            priority=1.5
                        )
                    )

        return actions

    def _create_initial_pitch(self, consumer_name, creator_name, sales_pitch, services):
        """Create personalized initial outreach message."""
        # Get first service for highlighting
        service = services[0] if services else {}
        service_name = service.get("name", "our program")
        service_price = service.get("pricing", {}).get("display_text", "")

        message = f"""Hi {consumer_name}! 👋

I noticed you checked out {creator_name}'s page.

{sales_pitch[:400]}...

{service_name} is available for {service_price}.

Would you like to learn more about how this can help you? I'm here to answer any questions!"""

        return message

    def _create_follow_up_message(self, consumer_name, creator_name, services, agent_instructions):
        """Create follow-up message for returning leads."""
        service = services[0] if services else {}
        service_name = service.get("name", "the program")

        message = f"""Hey {consumer_name},

I saw you came back to check out {service_name}. That's great!

Many people have questions before enrolling. Here are some quick highlights:

"""
        # Add service highlights
        if service:
            schedule = service.get("schedule", "")
            if schedule:
                message += f"📅 Schedule: {schedule[:100]}...\n"

            pricing = service.get("pricing", {})
            if pricing:
                message += f"💰 Investment: {pricing.get('display_text', '')}\n"

            current_enrollment = service.get("current_enrollment", 0)
            if current_enrollment:
                message += f"👥 {current_enrollment} people already enrolled\n"

        message += f"\nWhat questions can I answer for you?"

        return message

    def _create_enrollment_message(self, consumer_name, creator_name, service, agent_instructions):
        """Create message with enrollment details and link."""
        service_name = service.get("name", "the program")
        pricing = service.get("pricing", {})
        price_display = pricing.get("display_text", "")

        message = f"""Perfect timing, {consumer_name}! ✨

{service_name} is exactly what you need. Here's what you get:

"""
        # Add key details
        description = service.get("description", "")
        if description:
            # Clean HTML tags from description
            import re
            clean_desc = re.sub(r'<[^>]+>', '', description)
            message += f"{clean_desc[:200]}...\n\n"

        message += f"""💳 Investment: {price_display}

Ready to enroll? I can share the secure enrollment link right now.

Just reply "YES" and I'll send it over! 🚀"""

        return message

    def _find_service_by_id(self, services, service_id):
        """Find service by ID in the services list."""
        for service in services:
            if str(service.get("id")) == str(service_id):
                return service
        return services[0] if services else None

    def has_enrolled(self, context):
        """Check if consumer has enrolled in any service."""
        return self.get_metric(context, "enrolled", False)
