"""Upstream reporter, web relay adapter, and relay deduplication store tests."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections import deque
from pathlib import Path

import httpx
import pytest

from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.channels.web_relay_adapter import (
    RelayDeduplicationStore,
    WebRelayAdapter,
)
from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_runtime_capabilities,
)
from personal_assistant.main import _IMShadowConversationSyncClient


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=workspace,
            title="Agent A",
            skills=("plan", "playwright"),
            tool_allowlist=("read", "bash"),
            default_model="codex_oauth:gpt-5.5",
        ),
    )


def _write_skill(
    root: Path, dir_name: str, *, frontmatter_name: str | None = None
) -> None:
    skill_dir = root / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    declared_name = frontmatter_name or dir_name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {declared_name}\ndescription: {declared_name} skill\n---\n",
        encoding="utf-8",
    )


def test_upstream_reporter_builds_register_heartbeat_report_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_skill(tmp_path / ".nanoassistant" / "skills", "plan")
    _write_skill(
        tmp_path / ".claude" / "skills", "playwright", frontmatter_name='"playwright"'
    )
    gstack_target_root = (
        tmp_path / ".gstack" / "repos" / "gstack" / ".agents" / "skills"
    )
    _write_skill(
        gstack_target_root,
        "gstack-plan-design-review",
        frontmatter_name="plan-design-review",
    )
    codex_skills_root = tmp_path / ".codex" / "skills"
    codex_skills_root.mkdir(parents=True, exist_ok=True)
    (codex_skills_root / "gstack-plan-design-review").symlink_to(
        gstack_target_root / "gstack-plan-design-review", target_is_directory=True
    )
    from ._im_connection_helpers import _build_test_kernel

    agents = _agents(tmp_path)
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    reporter = UpstreamReporter(
        node=NodeConfig(node_id="node-1", user_id="user-1"),
        agents=agents,
        send_frame=lambda message_type, payload: frames.append((message_type, payload)),
        capabilities=build_runtime_capabilities(kernel),
        node_name="MacBook",
        version="1.2.3",
    )

    register = reporter.send_register()
    heartbeat = reporter.send_heartbeat(
        status="online", last_error=None, extra={"running_runs": 2}
    )
    report = reporter.send_report(
        run_id="run-1",
        status="completed",
        agent_id="agent-a",
        session_key="web:user:agent-a",
    )
    receipt = reporter.send_delivery_receipt(
        relay_task_id="relay-1", delivery_status="completed", detail="ok"
    )

    assert register["node_id"] == "node-1"
    assert register["agents"] == ["agent-a"]
    assert register["capabilities"] == {
        "relay": True,
        "send_message": True,
        "config_sync": True,
    }
    assert "capabilities" not in heartbeat
    assert heartbeat["running_runs"] == 2
    assert report["run_id"] == "run-1"
    assert receipt["relay_task_id"] == "relay-1"
    assert [item[0] for item in frames] == [
        "node.register",
        "node.heartbeat",
        "node.report",
        "node.delivery_receipt",
    ]


def test_web_relay_adapter_converts_relay_payload_to_inbound_message() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)

    inbound = adapter.accept_relay(
        {
            "relay_task_id": "relay-1",
            "idempotency_key": "idem-1",
            "agent_id": "agent-a",
            "message": {
                "id": "msg-1",
                "sender_user_id": "user-1",
                "conversation_id": "conv-1",
                "content": "hello gateway",
            },
            "metadata": {"conversation_type": "group", "thread_id": "thread-1"},
        }
    )

    assert inbound == seen[0]
    assert inbound.channel_name == "web_relay"
    assert inbound.external_chat_id == "conv-1"
    assert inbound.is_group is True
    assert inbound.metadata["relay_task_id"] == "relay-1"
    assert inbound.metadata["message_id"] == "msg-1"

    adapter.send(
        OutboundMessage(
            channel_name="web_relay",
            text="reply",
            target_chat_id="conv-1",
        )
    )
    assert adapter.sent[0].text == "reply"


def test_external_shadow_sync_uses_authenticated_im_user_not_stale_config_user() -> None:
    """External shadow writes must use the Bearer-token user, not config.node.user_id."""
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = {}
        if request.content:
            payload = dict(json.loads(request.content.decode("utf-8")))
        requests.append({"path": request.url.path, "payload": payload})
        if request.url.path == "/im/v1/me":
            return httpx.Response(
                200,
                json={
                    "id": "actual-user",
                    "user_id": "actual-user",
                    "username": "nano",
                    "display_name": "Nano",
                    "owner_id": "actual-user",
                    "owned_node_ids": [],
                    "default_entry_node_id": None,
                    "locale": "en",
                    "created_at": "2026-07-02T00:00:00Z",
                },
            )
        if request.url.path == "/im/v1/conversations/external/find-or-create":
            assert payload["participant_ids"] == [
                "user:actual-user",
                "agent:agent-a",
            ]
            return httpx.Response(201, json={"id": "conv-shadow"})
        if request.url.path == "/im/v1/conversations/conv-shadow/messages":
            assert payload["sender_user_id"] == "actual-user"
            return httpx.Response(201, json={"id": "msg-shadow"})
        raise AssertionError(f"unexpected request: {request.url.path}")

    client = _IMShadowConversationSyncClient(
        base_url="http://im.local",
        token_getter=lambda: _async_value("token-1"),
        owner_user_id="stale-config-user",
        transport=httpx.MockTransport(handler),
    )
    inbound = InboundMessage(
        channel_name="feishu:agent-a",
        text="hello from lark",
        external_user_id="ou_user",
        external_chat_id="feishu:app:dm:ou_user",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:app:dm:ou_user",
            "sender_display_name": "你",
        },
    )

    conversation_id = asyncio.run(client.sync_user_message(inbound, agent_id="agent-a"))

    assert conversation_id == "conv-shadow"
    assert [item["path"] for item in requests] == [
        "/im/v1/me",
        "/im/v1/conversations/external/find-or-create",
        "/im/v1/conversations/conv-shadow/messages",
    ]


async def _async_value(value: str) -> str:
    return value


def test_relay_dedup_store_contains_after_add(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")

    store.add("idem-1")

    assert store.contains("idem-1") is True


def test_relay_dedup_store_load_from_db_populates_deque(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path)
    store.add("idem-1")

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-1") is True


def test_relay_dedup_store_expired_keys_not_loaded(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=1)
    store.add("idem-expired")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE relay_deduplication_keys SET expires_at = ?", (time.time() - 10,)
        )
        conn.commit()

    reloaded = RelayDeduplicationStore(db_path=db_path)
    reloaded.load_from_db()

    assert reloaded.contains("idem-expired") is False


def test_relay_dedup_store_purge_removes_expired_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    store = RelayDeduplicationStore(db_path=db_path, ttl_seconds=30)
    store.add("idem-expired")
    store.add("idem-live")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE relay_deduplication_keys SET expires_at = ? WHERE idempotency_key = ?",
            (time.time() - 10, "idem-expired"),
        )
        conn.commit()

    deleted = store.purge_expired()

    assert deleted == 1
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT idempotency_key FROM relay_deduplication_keys ORDER BY idempotency_key"
        ).fetchall()
    assert rows == [("idem-live",)]


def test_relay_dedup_store_deque_rolls_over_at_max(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(
        db_path=tmp_path / "relay-dedup.sqlite3", seen_keys=deque(["old"])
    )
    store._seen_idempotency_keys = deque([str(index) for index in range(1000)])  # noqa: SLF001

    store.add("overflow")

    assert store.contains("0") is False
    assert store.contains("overflow") is True
    assert len(store._seen_idempotency_keys) == 1000  # noqa: SLF001


def test_web_relay_adapter_uses_dedup_store_on_accept(tmp_path: Path) -> None:
    store = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    adapter = WebRelayAdapter(dedup_store=store)
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]
    reloaded = RelayDeduplicationStore(db_path=tmp_path / "relay-dedup.sqlite3")
    reloaded.load_from_db()
    assert reloaded.contains("idem-1") is True


def test_web_relay_adapter_loads_store_on_start(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-dedup.sqlite3"
    seeded = RelayDeduplicationStore(db_path=db_path)
    seeded.add("idem-1")
    adapter = WebRelayAdapter(dedup_store=RelayDeduplicationStore(db_path=db_path))

    adapter.start(lambda _message: None)

    assert adapter._seen_idempotency_keys == deque(["idem-1"])  # noqa: SLF001


def test_web_relay_adapter_without_store_uses_in_memory_dedup() -> None:
    adapter = WebRelayAdapter()
    seen: list[InboundMessage] = []
    adapter.start(seen.append)
    payload = {
        "relay_task_id": "relay-1",
        "idempotency_key": "idem-1",
        "message": {
            "id": "msg-1",
            "sender_user_id": "user-1",
            "conversation_id": "conv-1",
            "content": "hello gateway",
        },
        "metadata": {"conversation_type": "direct"},
    }

    adapter.accept_relay(payload)
    adapter.accept_relay(payload)

    assert [item.text for item in seen] == ["hello gateway"]
