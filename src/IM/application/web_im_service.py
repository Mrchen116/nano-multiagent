"""Application service for IM conversations and messages."""

from IM.domain.models import Attachment, Conversation, Message
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

    def get_conversation(self, *, conversation_id: str) -> Conversation | None:
        """Load one conversation snapshot by identifier."""
        return self._conversations.get_conversation(conversation_id=conversation_id)

    def update_conversation(
        self,
        *,
        conversation_id: str,
        title: str | None,
        is_pinned: bool | None,
        is_muted: bool | None,
    ) -> Conversation:
        """Update mutable conversation metadata."""
        return self._conversations.update_conversation(
            conversation_id=conversation_id,
            title=title,
            is_pinned=is_pinned,
            is_muted=is_muted,
        )

    def list_conversations(self) -> list[Conversation]:
        """List conversations visible in the current storage scope."""
        return self._conversations.list_conversations()

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
        sender_type: str = "user",
        attachments: list[Attachment] | None = None,
    ) -> Message:
        """Create one message inside a conversation."""
        return self._messages.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
            sender_type=sender_type,
            attachments=attachments,
        )

    def list_messages(
        self,
        *,
        conversation_id: str,
        limit: int = 50,
        before_message_id: str | None = None,
    ) -> list[Message]:
        """List messages for one conversation in storage order."""
        return self._messages.list_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before_message_id,
        )
