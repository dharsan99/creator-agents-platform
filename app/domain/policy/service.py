"""Policy engine for enforcing guardrails."""
from datetime import datetime, timedelta, time
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select, func
import pytz

from app.infra.db.models import Consumer, Event, PolicyRule, Action
from app.domain.schemas import PlannedAction, PolicyDecision
from app.domain.types import Channel, ConsentType, EventType, PolicyKey


class PolicyService:
    """Service for enforcing policy guardrails."""

    # Default policy values
    DEFAULT_POLICIES = {
        PolicyKey.RATE_LIMIT_EMAIL_WEEKLY.value: 3,
        PolicyKey.RATE_LIMIT_EMAIL_DAILY.value: 1,
        PolicyKey.RATE_LIMIT_WHATSAPP_DAILY.value: 2,
        PolicyKey.RATE_LIMIT_WHATSAPP_WEEKLY.value: 5,
        PolicyKey.RATE_LIMIT_CALL_WEEKLY.value: 1,
        PolicyKey.QUIET_HOURS_START.value: 21,  # 9 PM
        PolicyKey.QUIET_HOURS_END.value: 9,     # 9 AM
        PolicyKey.REQUIRE_CONSENT.value: True,
    }

    def __init__(self, session: Session):
        self.session = session

    def get_policy_value(self, creator_id: UUID, key: PolicyKey):
        """Get policy value for creator, falling back to default."""
        statement = (
            select(PolicyRule)
            .where(PolicyRule.creator_id == creator_id)
            .where(PolicyRule.key == key.value)
        )
        rule = self.session.exec(statement).first()

        if rule:
            return rule.value.get("value")

        return self.DEFAULT_POLICIES.get(key.value)

    def set_policy_value(self, creator_id: UUID, key: PolicyKey, value) -> PolicyRule:
        """Set policy value for creator."""
        statement = (
            select(PolicyRule)
            .where(PolicyRule.creator_id == creator_id)
            .where(PolicyRule.key == key.value)
        )
        rule = self.session.exec(statement).first()

        if rule:
            rule.value = {"value": value}
        else:
            rule = PolicyRule(
                creator_id=creator_id,
                key=key.value,
                value={"value": value},
            )

        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def validate_action(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        action: PlannedAction,
    ) -> PolicyDecision:
        """Validate if an action should be approved."""
        violations = []

        # Check consent
        consent_check = self._check_consent(creator_id, consumer_id, action.channel)
        if not consent_check:
            violations.append(f"No consent for {action.channel.value}")

        # Check rate limits
        rate_limit_check = self._check_rate_limits(creator_id, consumer_id, action)
        if rate_limit_check:
            violations.append(rate_limit_check)

        # Check quiet hours
        quiet_hours_check = self._check_quiet_hours(creator_id, consumer_id, action)
        if quiet_hours_check:
            violations.append(quiet_hours_check)

        approved = len(violations) == 0
        return PolicyDecision(
            approved=approved,
            reason=None if approved else "; ".join(violations),
            violations=violations,
        )

    def _check_consent(
        self, creator_id: UUID, consumer_id: UUID, channel: Channel
    ) -> bool:
        """Check if consumer has given consent for channel."""
        require_consent = self.get_policy_value(creator_id, PolicyKey.REQUIRE_CONSENT)
        if not require_consent:
            return True

        consumer = self.session.get(Consumer, consumer_id)
        if not consumer:
            return False

        # Map channel to consent type
        consent_map = {
            Channel.EMAIL: ConsentType.EMAIL,
            Channel.WHATSAPP: ConsentType.WHATSAPP,
            Channel.CALL: ConsentType.CALL,
        }

        consent_type = consent_map.get(channel)
        if not consent_type:
            return True  # No consent required for payment links

        return consumer.consent.get(consent_type.value, False)

    def _check_rate_limits(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        action: PlannedAction,
    ) -> Optional[str]:
        """Check if action violates rate limits."""
        now = datetime.utcnow()
        channel = action.channel

        # Count recent actions of the same type
        if channel == Channel.EMAIL:
            # Check daily limit
            daily_limit = self.get_policy_value(creator_id, PolicyKey.RATE_LIMIT_EMAIL_DAILY)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_count = self._count_recent_actions(
                creator_id, consumer_id, channel, day_start
            )
            if daily_count >= daily_limit:
                return f"Email daily limit ({daily_limit}) exceeded"

            # Check weekly limit
            weekly_limit = self.get_policy_value(creator_id, PolicyKey.RATE_LIMIT_EMAIL_WEEKLY)
            week_start = now - timedelta(days=7)
            weekly_count = self._count_recent_actions(
                creator_id, consumer_id, channel, week_start
            )
            if weekly_count >= weekly_limit:
                return f"Email weekly limit ({weekly_limit}) exceeded"

        elif channel == Channel.WHATSAPP:
            # Check daily limit
            daily_limit = self.get_policy_value(creator_id, PolicyKey.RATE_LIMIT_WHATSAPP_DAILY)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_count = self._count_recent_actions(
                creator_id, consumer_id, channel, day_start
            )
            if daily_count >= daily_limit:
                return f"WhatsApp daily limit ({daily_limit}) exceeded"

            # Check weekly limit
            weekly_limit = self.get_policy_value(
                creator_id, PolicyKey.RATE_LIMIT_WHATSAPP_WEEKLY
            )
            week_start = now - timedelta(days=7)
            weekly_count = self._count_recent_actions(
                creator_id, consumer_id, channel, week_start
            )
            if weekly_count >= weekly_limit:
                return f"WhatsApp weekly limit ({weekly_limit}) exceeded"

        elif channel == Channel.CALL:
            # Check weekly limit
            weekly_limit = self.get_policy_value(creator_id, PolicyKey.RATE_LIMIT_CALL_WEEKLY)
            week_start = now - timedelta(days=7)
            weekly_count = self._count_recent_actions(
                creator_id, consumer_id, channel, week_start
            )
            if weekly_count >= weekly_limit:
                return f"Call weekly limit ({weekly_limit}) exceeded"

        return None

    def _count_recent_actions(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        channel: Channel,
        since: datetime,
    ) -> int:
        """Count actions sent to consumer since a given time."""
        statement = (
            select(func.count(Action.id))
            .where(Action.creator_id == creator_id)
            .where(Action.consumer_id == consumer_id)
            .where(Action.channel == channel.value)
            .where(Action.status == "executed")
            .where(Action.created_at >= since)
        )
        return self.session.exec(statement).one()

    def _check_quiet_hours(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        action: PlannedAction,
    ) -> Optional[str]:
        """Check if action falls during quiet hours."""
        consumer = self.session.get(Consumer, consumer_id)
        if not consumer or not consumer.timezone:
            # If no timezone, skip quiet hours check
            return None

        try:
            tz = pytz.timezone(consumer.timezone)
        except:
            # Invalid timezone, skip check
            return None

        # Get scheduled time in consumer's timezone
        local_time = action.send_at.astimezone(tz)

        quiet_start_hour = self.get_policy_value(creator_id, PolicyKey.QUIET_HOURS_START)
        quiet_end_hour = self.get_policy_value(creator_id, PolicyKey.QUIET_HOURS_END)

        current_hour = local_time.hour

        # Quiet hours can span midnight
        if quiet_start_hour > quiet_end_hour:
            # e.g., 21:00 to 09:00
            is_quiet = current_hour >= quiet_start_hour or current_hour < quiet_end_hour
        else:
            # e.g., 22:00 to 23:00 (unusual but possible)
            is_quiet = quiet_start_hour <= current_hour < quiet_end_hour

        if is_quiet:
            return f"Action scheduled during quiet hours ({quiet_start_hour}:00 - {quiet_end_hour}:00 in consumer timezone)"

        return None
