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

    def list_conversations_for_owner(self, *, owner_id: str) -> list[Conversation]:
        """List conversations owned by ``owner_id`` (SQL-level tenant filter)."""
        return self._conversations.list_conversations_for_owner(owner_id=owner_id)

    def get_conversation_for_owner(self, *, conversation_id: str, owner_id: str) -> Conversation | None:
        """Return the conversation iff it belongs to ``owner_id`` (else None)."""
        return self._conversations.get_conversation_for_owner(
            conversation_id=conversation_id, owner_id=owner_id
        )

    def delete_conversation(self, *, conversation_id: str, requester_id: str) -> None:
        """Dissolve a conversation; only the creator may do this.

        Args:
            conversation_id: Conversation to delete.
            requester_id: Caller's user ID; must be the conversation creator.

        Raises:
            ValueError: When conversation does not exist.
            PermissionError: When requester is not the creator.
        """
        self._conversations.delete_conversation(
            conversation_id=conversation_id,
            requester_id=requester_id,
        )

    def remove_participant(self, *, conversation_id: str, user_id: str) -> None:
        """Remove a participant from a conversation (leave-group).

        Args:
            conversation_id: Target conversation identifier.
            user_id: User leaving the conversation.

        Raises:
            ValueError: When conversation or participant does not exist.
        """
        self._conversations.remove_participant(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def create_message(
        self,
        *,
        conversation_id: str,
        sender_user_id: str,
        content: str,
        sender_type: str = "user",
        attachments: list[Attachment] | None = None,
        auto_complete_delivery: bool = True,
    ) -> Message:
        """Create one message inside a conversation.

        Args:
            conversation_id: Target conversation identifier.
            sender_user_id: Sender user identifier.
            content: Plain text body of the message.
            sender_type: Sender kind; must be user, agent, or system.
            attachments: Attachment descriptors stored alongside the message.
            auto_complete_delivery: Whether this write can synchronously close to completed. Relay-backed
                writes pass False so gateway receipts remain the source of truth for final completion.

        Returns:
            Created message snapshot.
        """
        created = self._messages.create_message(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
            sender_type=sender_type,
            attachments=attachments,
            auto_complete_delivery=auto_complete_delivery,
        )
        if self._metrics_service is not None and auto_complete_delivery:
            conversation = self._conversations.get_conversation(conversation_id=conversation_id)
            owner_id = conversation.owner_id if conversation is not None else None
            token_count = len(content.split())
            prompt_tokens = token_count if sender_type == "user" else 0
            completion_tokens = token_count if sender_type != "user" else 0
            self._metrics_service.record_usage(
                owner_id=owner_id,
                conversation_id=None,
                agent_id=None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                turns=1,
            )
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
        mark_as_read: bool = False,
    ) -> list[Message]:
        """List messages for one conversation in storage order."""
        return self._messages.list_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before_message_id,
            mark_as_read=mark_as_read,
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
        conversation = self._conversations.get_conversation(conversation_id=message.conversation_id)
        return self._relay_service.enqueue_message_relay(
            message=message,
            target_node_id=target_node_id,
            idempotency_key=idempotency_key,
            sender_user_id=sender_user_id,
            conversation_type=conversation.type if conversation is not None else None,
        )

    def enqueue_relay_all(
        self,
        *,
        message: Message,
        target_node_id: str,
        idempotency_key_base: str,
        sender_user_id: str,
    ) -> list[RelayEnqueueResult]:
        """Create or reuse relay tasks for all participant agents in a conversation.

        Delegates to ``RelayService.enqueue_message_relay_all``, which creates one
        relay per participant agent for group chats and a single relay for direct chats.

        Args:
            message: Persisted message to relay.
            target_node_id: Gateway node that should receive every relay.
            idempotency_key_base: Base retry key; per-agent key is ``{base}:{agent_id}``.
            sender_user_id: Human sender identifier copied into relay payloads.

        Returns:
            List of RelayEnqueueResult, one per agent.

        Raises:
            RuntimeError: When the app was built without relay support.
        """
        if self._relay_service is None:
            raise RuntimeError("relay_service is not configured")
        conversation = self._conversations.get_conversation(conversation_id=message.conversation_id)
        return self._relay_service.enqueue_message_relay_all(
            message=message,
            target_node_id=target_node_id,
            idempotency_key_base=idempotency_key_base,
            sender_user_id=sender_user_id,
            conversation_type=conversation.type if conversation is not None else None,
        )

    def resolve_target_node_id(self, *, conversation_id: str, content: str) -> str | None:
        """Resolve the concrete gateway node for one outgoing conversation message."""
        if self._relay_service is None:
            return None
        return self._relay_service.resolve_target_node_id(
            conversation_id=conversation_id,
            content=content,
        )
