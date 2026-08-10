"""Binder-owned SQLite compatibility tests."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.channels.base import InboundMessage, ReplyContext
from personal_assistant.gateway.runtime_protocol import (
    RuntimeProtocolFacts,
    ShadowConversationRef,
    attach_runtime_protocol,
)
from personal_assistant.gateway.session_keys import (
    BoundaryIntent,
    _SQLiteSessionBindingStore,
    build_reply_context,
)


def _make_message_with_runtime_protocol() -> InboundMessage:
    return attach_runtime_protocol(
        InboundMessage(
            channel_name="web_relay",
            text="hello",
            external_user_id="user-1",
            external_chat_id="conv-1",
            is_group=False,
            metadata={"message_id": "msg-1"},
        ),
        RuntimeProtocolFacts(
            relay_task_id="relay-1",
            im_message_id="msg-1",
            shadow_ref=ShadowConversationRef(
                conversation_id="conv-1",
                relay_task_id="relay-1",
                im_message_id="msg-1",
            ),
        ),
    )


class TestSQLiteCompatibility:
    """Keep schema, serialization, and atomic-transition compatibility coverage."""

    def test_db_file_created(self, tmp_path: Path) -> None:
        """构造 _SQLiteSessionBindingStore 后 db 文件存在。"""
        db_path = tmp_path / "sb.sqlite3"
        _SQLiteSessionBindingStore(db_path=db_path)
        assert db_path.exists()

    def test_db_parent_created_if_missing(self, tmp_path: Path) -> None:
        """db_path 父目录不存在时自动创建。"""
        db_path = tmp_path / "subdir" / "sb.sqlite3"
        _SQLiteSessionBindingStore(db_path=db_path)
        assert db_path.exists()

    def test_build_reply_context_strips_private_runtime_protocol_metadata(
        self,
    ) -> None:
        """Typed delivery facts are private and excluded from channel contexts."""
        reply_context = build_reply_context(_make_message_with_runtime_protocol())

        assert reply_context.metadata == {"message_id": "msg-1"}

    def test_build_reply_context_excludes_inbound_image_payloads(self) -> None:
        message = InboundMessage(
            channel_name="feishu:agent-a",
            text="[图片]",
            external_user_id="user-1",
            external_chat_id="chat-1",
            is_group=False,
            metadata={
                "message_id": "msg-1",
                "attachments": [{"url": "data:image/png;base64,large"}],
                "kernel_input_parts": [{"type": "image", "attachment_index": 0}],
                "image_resolution_failure": "download",
            },
        )

        assert build_reply_context(message).metadata == {"message_id": "msg-1"}

    def test_bind_strips_existing_private_runtime_protocol_metadata(
        self, tmp_path: Path
    ) -> None:
        """Typed delivery facts stay in memory and do not leak into persisted context."""
        store = _SQLiteSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        message = _make_message_with_runtime_protocol()
        reply_context = ReplyContext(
            channel_name=message.channel_name,
            target_chat_id=message.external_chat_id,
            metadata=dict(message.metadata),
        )

        store.bind(
            session_key="web_relay:conv-1:agent-a",
            kernel_session_id="ksess-1",
            reply_context=reply_context,
        )

        binding = store.get("web_relay:conv-1:agent-a")
        assert binding is not None
        assert binding.reply_context.metadata == {"message_id": "msg-1"}

    def test_quarantined_boundary_remains_serializable_for_compatibility(
        self, tmp_path: Path
    ) -> None:
        """Terminal rejection retains the existing on-disk diagnostic row."""

        store = _SQLiteSessionBindingStore(db_path=tmp_path / "sb.sqlite3")
        reply_context = ReplyContext(
            channel_name="web_relay",
            target_chat_id="conversation-1",
        )
        binding = store.bind(
            session_key="web_relay:conversation-1:agent-1",
            kernel_session_id="session-1",
            reply_context=reply_context,
        )
        intent = BoundaryIntent(
            boundary_id="boundary-1",
            node_id="node-1",
            conversation_id="conversation-1",
            agent_id="agent-1",
            before_message_id="message-1",
            runtime_fingerprint="runtime-b",
            fingerprint_schema="runtime-v1",
            profile_version=7,
            applied_at="2026-08-10T00:00:00Z",
        )
        store.apply_runtime_with_boundary(
            binding,
            runtime_fingerprint="runtime-b",
            fingerprint_schema="runtime-v1",
            profile_version=7,
            boundary=intent,
        )

        store.record_boundary_error("boundary-1", reason="anchor missing")

        assert store.quarantined_boundaries() == (intent,)
