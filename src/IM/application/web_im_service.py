"""Application service for IM conversations and messages."""

from IM.domain.models import Conversation, Message
from IM.infra.repositories import ConversationRepository, MessageRepository


class WebIMService:
    """Coordinate conversation and message workflows for Web IM APIs."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        """Bind service to repositories used by Web IM routes.

        Args:
            conversations: Repository for conversation reads and writes.
            messages: Repository for message reads and writes.
        """
        self._conversations = conversations
        self._messages = messages

    def create_conversation(self, *, title: str, participant_ids: list[str]) -> Conversation:
        """Create one conversation with validated participants."""
        return self._conversations.create_conversation(title=title, participant_ids=participant_ids)

    def list_conversations(self) -> list[Conversation]:
        """List conversations visible in the current storage scope."""
        return self._conversations.list_conversations()

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
    ) -> Message:
        """Create one message inside a conversation."""
        return self._messages.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
        )

    def list_messages(self, *, conversation_id: str) -> list[Message]:
        """List messages for one conversation in storage order."""
        return self._messages.list_messages(conversation_id=conversation_id)
