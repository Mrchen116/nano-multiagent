"""Public control-boundary regressions for managed external channels."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

from personal_assistant.channels.channel_credentials import GatewayChannelKeyStore
from personal_assistant.gateway.channel_manifest_store import ChannelManifestStore
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.managed_channel_control import (
    ChannelStatusDirective,
    ManagedChannelConnectionSender,
    ManagedChannelControl,
)


class _AgentConfigSync:
    def ensure_agent_skill_enabled(self, _agent_id: str, _skill_id: str) -> bool:
        return True


class _Sender(ManagedChannelConnectionSender):
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, object]]] = []
        self.pending_request_ids: set[str] = set()

    async def send_json(self, message_type: str, payload: Mapping[str, object]) -> None:
        self.sent.append((message_type, dict(payload)))

    def has_pending_request(self, request_id: str) -> bool:
        return request_id in self.pending_request_ids


def _control(tmp_path: Path) -> tuple[ManagedChannelControl, ChannelManifestStore]:
    key = GatewayChannelKeyStore(
        tmp_path / "channel-credentials-v1.pem"
    ).load_or_create()
    store = ChannelManifestStore(
        tmp_path / "channel-manifest-v1.json",
        node_id="node-a",
        key_id=key.key_id,
    )
    return (
        ManagedChannelControl(
            node_id="node-a",
            channel_key=key,
            manifest_store=store,
            registry=ChannelRegistry(),
            on_inbound=lambda _message: None,
            agent_config_sync=_AgentConfigSync(),  # type: ignore[arg-type]
            group_context_store=object(),
            permission_decision_callback=None,
        ),
        store,
    )


def _status(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "node_id": "node-a",
        "channel_id": "ch-a",
        "channel_revision": 1,
        "runtime_incarnation": "inc-a",
        "status_sequence": 1,
        "instance_started": True,
        "connection_state": "connecting",
        "diagnostics_state": "unknown",
        "checks": [],
    }


def test_register_ready_replays_durable_state_through_current_sender(
    tmp_path: Path,
) -> None:
    """Reconnect derives channel state from the store, never an old mailbox queue."""
    control, store = _control(tmp_path)
    store.record_channel_status(_status("status-pending"))
    store.record_reconcile_result(
        manifest_revision=3,
        outcome="applied",
        applied_channel_ids=("ch-a",),
        removal_outcomes=(),
        failures=(),
    )
    sender = _Sender()

    asyncio.run(control.connection_bindings().reconcile_after_register(sender))

    assert sender.sent[0] == ("channel.status", _status("status-pending"))
    result_type, result_payload = sender.sent[1]
    assert result_type == "channel.reconcile.result"
    assert result_payload["node_id"] == "node-a"
    assert result_payload["manifest_revision"] == 3
    assert result_payload["applied_channel_ids"] == ["ch-a"]


def test_register_ready_does_not_duplicate_current_fifo_request(tmp_path: Path) -> None:
    """A reconnect cannot enqueue a durable status already owned by this FIFO."""
    control, store = _control(tmp_path)
    store.record_channel_status(_status("status-pending"))
    sender = _Sender()
    sender.pending_request_ids.add("status-pending")

    asyncio.run(control.connection_bindings().reconcile_after_register(sender))

    assert sender.sent == []


def test_fatal_status_ack_returns_receive_stack_close_directive(tmp_path: Path) -> None:
    """The control leaves transport close timing to the IM receive owner."""
    control, store = _control(tmp_path)
    store.record_channel_status(_status("status-fatal"))

    directive = asyncio.run(
        control.connection_bindings().handle_status_result(
            {"request_id": "status-fatal", "outcome": "fatal_owner_mismatch"}
        )
    )

    assert directive is ChannelStatusDirective.CLOSE_CONNECTION


def test_invalid_manifest_returns_wire_ready_failure_without_runtime_mutation(
    tmp_path: Path,
) -> None:
    """The public apply binding preserves existing fail-closed manifest behavior."""
    control, _store = _control(tmp_path)

    result = asyncio.run(control.connection_bindings().apply_manifest({}))

    assert result == {
        "outcome": "retryable_failed",
        "applied_channel_ids": [],
        "removal_outcomes": [],
        "failures": [
            {
                "channel_id": "",
                "error_code": "manifest_invalid",
                "error_message": "Channel manifest is incomplete or invalid.",
            }
        ],
    }
