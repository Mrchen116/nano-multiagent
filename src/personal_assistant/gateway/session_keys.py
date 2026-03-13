"""Session-key generation and local kernel-session binding storage."""

from __future__ import annotations

from dataclasses import dataclass

from personal_assistant.channels.base import InboundMessage, ReplyContext


@dataclass(frozen=True, slots=True)
class SessionBinding:
    """Persist the kernel session id and reply target for one gateway session key.

    Args:
        session_key: Stable gateway-local session key.
        kernel_session_id: Kernel session id created for this binding.
        reply_context: Original reply target used for outbound routing.
    """

    session_key: str
    kernel_session_id: str
    reply_context: ReplyContext


class SessionBindingStore:
    """Store gateway session bindings in local process memory for v1 pipeline flows."""

    def __init__(self) -> None:
        self._bindings: dict[str, SessionBinding] = {}

    def get(self, session_key: str) -> SessionBinding | None:
        """Return one binding by session key."""

        return self._bindings.get(session_key)

    def bind(self, *, session_key: str, kernel_session_id: str, reply_context: ReplyContext) -> SessionBinding:
        """Create or replace the binding for one session key."""

        binding = SessionBinding(
            session_key=session_key,
            kernel_session_id=kernel_session_id,
            reply_context=reply_context,
        )
        self._bindings[session_key] = binding
        return binding

    def drop_agent(self, agent_id: str) -> None:
        """Remove all session bindings that belong to one routed agent id."""

        suffix = f":{agent_id}"
        for session_key in tuple(self._bindings):
            if session_key.endswith(suffix):
                self._bindings.pop(session_key, None)


session_binding_store = SessionBindingStore()


def build_session_key(message: InboundMessage, *, agent_id: str) -> str:
    """Build the canonical gateway session key for one inbound message.

    Args:
        message: Normalized inbound message produced by a channel adapter.
        agent_id: Routed agent id chosen in pipeline step 1.

    Returns:
        Group-chat key ``{channel}:{external_chat_id}:{agent_id}`` or private-chat
        key ``{channel}:{external_user_id}:{agent_id}`` per NodeGateway-SPEC §4.2.
    """

    if message.is_group:
        return f"{message.channel_name}:{message.external_chat_id}:{agent_id}"
    return f"{message.channel_name}:{message.external_user_id}:{agent_id}"


def build_reply_context(message: InboundMessage) -> ReplyContext:
    """Capture the outbound reply target from one inbound message."""

    return ReplyContext(
        channel_name=message.channel_name,
        target_chat_id=message.external_chat_id,
        thread_id=message.thread_id,
        metadata=dict(message.metadata),
    )
