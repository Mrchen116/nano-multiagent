"""Application service for IM conversations and messages."""

from IM.application.metrics_service import MetricsService
from IM.application.relay_service import RelayEnqueueResult, RelayService
from IM.domain.models import Attachment, Conversation, Message
from IM.infra.repositories import ConversationRepository, MessageRepository


class WebIMService:
    """Coordinate conversation and message workflows for Web IM APIs."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
        relay_service: RelayService | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Bind service to repositories used by Web IM routes.

        Args:
            conversations: Repository for conversation reads and writes.
            messages: Repository for message reads and writes.
            relay_service: Optional relay task service used by M97 websocket flow.
            metrics_service: Optional usage metrics service used by M99 statistics APIs.
        """
        self._conversations = conversations
        self._messages = messages
        self._relay_service = relay_service
        self._metrics_service = metrics_service

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
        created = self._messages.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
            sender_type=sender_type,
            attachments=attachments,
        )
        if self._metrics_service is not None:
            conversation = self._conversations.get_conversation(conversation_id=conversation_id)
            owner_id = conversation.owner_id if conversation is not None else None
            prompt_tokens = max(1, len(content.split()))
            completion_tokens = 0 if sender_type == "user" else max(1, len(content.split()))
            self._metrics_service.record_usage(
                owner_id=owner_id,
                conversation_id=conversation_id,
                agent_id=sender_user_id if sender_type == "agent" else None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                turns=1,
            )
        return created

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
