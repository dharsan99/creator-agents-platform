"""Conversation domain module for human-in-loop escalations."""

from app.domain.conversations.models import ConversationThread, Message

__all__ = [
    "ConversationThread",
    "Message",
]
