"""Application service for IM conversations and messages."""

from IM.application.relay_service import RelayEnqueueResult, RelayService
from IM.domain.models import Conversation, Message
from IM.infra.repositories import ConversationRepository, MessageRepository


class WebIMService:
    """Coordinate conversation and message workflows for Web IM APIs."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
        relay_service: RelayService | None = None,
    ) -> None:
        """Bind service to repositories used by Web IM routes.

        Args:
            conversations: Repository for conversation reads and writes.
            messages: Repository for message reads and writes.
            relay_service: Optional relay task service used by M97 websocket flow.
        """
        self._conversations = conversations
        self._messages = messages
        self._relay_service = relay_service

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

    def enqueue_relay(
        self,
        *,
        message: Message,
        target_node_id: str,
        idempotency_key: str,
        sender_user_id: str,
    ) -> RelayEnqueueResult:
        """Create or reuse one relay task for a persisted IM message.

        Raises:
            RuntimeError: When the app was built without relay support.
        """
        if self._relay_service is None:
            raise RuntimeError("relay_service is not configured")
        return self._relay_service.enqueue_message_relay(
            message=message,
            target_node_id=target_node_id,
            idempotency_key=idempotency_key,
            sender_user_id=sender_user_id,
        )
