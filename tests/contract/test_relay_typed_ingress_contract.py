"""Cross-module deletion contracts for typed relay ingress."""

from dataclasses import fields
from pathlib import Path
import sqlite3

from personal_assistant.channels.base import (
    IMRelayIngress,
    InboundIngress,
    InboundMessage,
)
from personal_assistant.gateway.session_keys import (
    PersistentSessionBindingStore,
    build_reply_context,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PA_SOURCE = PROJECT_ROOT / "src" / "personal_assistant"


def test_legacy_runtime_protocol_authority_is_deleted() -> None:
    """Only typed ingress/state carriers may own relay and shadow facts."""

    assert not (PA_SOURCE / "gateway" / "runtime_protocol.py").exists()
    assert "external_event_identity" not in {
        field.name for field in fields(InboundMessage)
    }

    legacy_private_key = "__runtime_protocol_facts__"
    offenders = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PA_SOURCE.rglob("*.py")
        if legacy_private_key in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_typed_ingress_is_not_projected_into_reply_or_session_storage(
    tmp_path: Path,
) -> None:
    """Stage-local typed carriers do not become public or durable metadata."""

    message = InboundMessage(
        channel_name="web_relay",
        text="hello",
        external_user_id="user-1",
        external_chat_id="conv-1",
        is_group=False,
        metadata={"message_id": "msg-1"},
        ingress=InboundIngress(
            im_relay=IMRelayIngress(
                relay_task_id="relay-1",
                idempotency_key="idem-1",
                im_message_id="msg-1",
            )
        ),
    )
    reply_context = build_reply_context(message)
    assert reply_context.metadata == {"message_id": "msg-1"}

    db_path = tmp_path / "session-bindings.sqlite3"
    store = PersistentSessionBindingStore(db_path=db_path)
    store.bind(
        session_key="web_relay:conv-1:agent-a",
        kernel_session_id="session-1",
        reply_context=reply_context,
    )

    with sqlite3.connect(db_path) as connection:
        stored_json = connection.execute(
            "SELECT reply_context_json FROM session_bindings"
        ).fetchone()[0]
    assert "InboundIngress" not in stored_json
    assert "im_relay" not in stored_json
    assert "__runtime_protocol_facts__" not in stored_json
