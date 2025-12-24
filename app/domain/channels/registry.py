"""Channel registry for managing all channel tools."""
from sqlmodel import Session

from app.domain.channels.base import ChannelTool
from app.domain.channels.email import EmailChannel
from app.domain.channels.whatsapp import WhatsAppChannel
from app.domain.channels.call import CallChannel
from app.domain.channels.payment import PaymentChannel
from app.domain.channels.redpanda import RedpandaChannel
from app.domain.types import Channel
from app.infra.external.ses_client import SESClient
from app.infra.external.twilio_client import TwilioClient
from app.infra.events.producer import get_producer


class ChannelRegistry:
    """Registry for all channel tools."""

    def __init__(self, session: Session):
        self.session = session
        self._channels: dict[Channel, ChannelTool] = {}
        self._initialize_channels()

    def _initialize_channels(self):
        """Initialize all channel tools."""
        # Email channel
        ses_client = SESClient()
        self._channels[Channel.EMAIL] = EmailChannel(ses_client)

        # WhatsApp channel
        twilio_client = TwilioClient()
        self._channels[Channel.WHATSAPP] = WhatsAppChannel(twilio_client)

        # Call channel
        self._channels[Channel.CALL] = CallChannel()

        # Payment channel
        self._channels[Channel.PAYMENT] = PaymentChannel(self.session)

        # Redpanda channel
        producer = get_producer()
        self._channels[Channel.REDPANDA] = RedpandaChannel(producer)

    def get_channel(self, channel: Channel) -> ChannelTool:
        """Get channel tool by type."""
        if channel not in self._channels:
            raise ValueError(f"Channel {channel} not supported")
        return self._channels[channel]

    def execute(self, channel: Channel, creator_id, consumer_id, payload) -> dict:
        """Execute action on a channel."""
        tool = self.get_channel(channel)
        return tool.execute(creator_id, consumer_id, payload)
