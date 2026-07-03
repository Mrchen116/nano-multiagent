"""Route outbound replies back through the originating channel adapter."""

from __future__ import annotations

from collections.abc import Mapping

from personal_assistant.channels.base import OutboundMessage, ReplyContext
from personal_assistant.gateway.channel_registry import ChannelRegistry


class OutboundRouter:
    """Send normalized replies to the adapter captured in reply context."""

    def __init__(self, registry: ChannelRegistry) -> None:
        self._registry = registry
        self._sent_dedupe_keys: set[str] = set()

    def send_text(
        self, *, text: str, reply_context: ReplyContext
    ) -> OutboundMessage | None:
        """Build and dispatch one outbound text reply.

        Args:
            text: Reply text produced by the kernel execution.
            reply_context: Original target captured from the inbound message.

        Returns:
            The normalized outbound payload sent to the adapter, or ``None`` when
            ``reply_dedupe_key`` identifies a reply already delivered by this router.

        Raises:
            LookupError: When the target channel adapter is not registered.
        """

        channel = self._registry.get(reply_context.channel_name)
        if channel is None:
            raise LookupError(f"unknown channel adapter: {reply_context.channel_name}")
        dedupe_keys = self._dedupe_keys_for(text=text, metadata=reply_context.metadata)
        if any(key in self._sent_dedupe_keys for key in dedupe_keys):
            return None
        outbound = OutboundMessage(
            channel_name=reply_context.channel_name,
            text=text,
            target_chat_id=reply_context.target_chat_id,
            thread_id=reply_context.thread_id,
            metadata=dict(reply_context.metadata),
        )
        channel.send(outbound)
        self._sent_dedupe_keys.update(dedupe_keys)
        return outbound

    @staticmethod
    def _dedupe_keys_for(*, text: str, metadata: object) -> set[str]:
        """Return physical and semantic dedupe keys for one outbound send."""

        if not isinstance(metadata, Mapping):
            return set()
        keys: set[str] = set()
        dedupe_key = metadata.get("reply_dedupe_key")
        if isinstance(dedupe_key, str) and dedupe_key.strip():
            normalized_key = dedupe_key.strip()
            keys.add(normalized_key)
            if metadata.get("reply_phase") == "final":
                run_id, _, _ = normalized_key.partition(":")
                cleaned_text = text.strip()
                if run_id and cleaned_text:
                    keys.add(f"{run_id}:final_text:{cleaned_text}")
        return keys
