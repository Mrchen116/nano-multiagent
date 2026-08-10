"""Test-only subprocess launcher for Gateway continuity partial recovery."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

from personal_assistant.channels.base import (
    ExternalInboundEventIdentity,
    InboundMessage,
    OutboundMessage,
)
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.boundary_outbox import BoundaryOutboxDispatcher
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.external_control_delivery import (
    ExternalControlDeliveryMaterializer,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.runtime_protocol import (
    ExternalConversationIdentity,
    RuntimeProtocolFacts,
    attach_runtime_protocol,
)
from personal_assistant.gateway.session_binder import (
    GatewaySessionBinder,
    SessionBindingRequest,
)
from personal_assistant.gateway.session_keys import (
    PendingBoundaryIntent,
    SessionBinding,
    build_reply_context,
    build_session_key,
)
from personal_assistant.gateway.shadow_saga import ExternalShadowSagaStore
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync
from tests.e2e.critical_paths._session_continuity_im import (
    initialize as initialize_im,
    serve as serve_im,
)

_AGENT_ID = "agent-a"
_CHANNEL_NAME = "feishu:agent-a"
_CONFIRMATION = "已开始新会话。"


class _Kernel:
    """Create deterministic process-local Kernel session identities."""

    def __init__(self, *, prefix: str) -> None:
        self._prefix = prefix
        self._created = 0

    async def create_session(self, **_kwargs: Any) -> SimpleNamespace:
        self._created += 1
        return SimpleNamespace(session_id=f"{self._prefix}-{self._created}")


@dataclass(frozen=True)
class _Owners:
    catalog: LiveAgentCatalog
    binder: GatewaySessionBinder
    saga_store: ExternalShadowSagaStore
    shadow_sync: IMShadowConversationSync


class _FileChannel:
    name = _CHANNEL_NAME

    def __init__(self, runtime: Path) -> None:
        self._runtime = runtime

    def start(self, _on_inbound) -> None:  # noqa: ANN001
        return None

    def send(self, outbound: OutboundMessage) -> None:
        state = _read_state(self._runtime)
        if not state.get("allow_remote_delivery"):
            _write_state(self._runtime, {**state, "external_send_blocked": True})
            while not _read_state(self._runtime).get("allow_remote_delivery"):
                time.sleep(0.05)
        _append_ledger(
            self._runtime,
            {
                "type": "control_confirmation",
                "target_chat_id": outbound.target_chat_id,
                "text": outbound.text,
            },
        )

    def stop(self) -> None:
        return None


class _FileBoundaryConnection:
    def __init__(self, runtime: Path) -> None:
        self._runtime = runtime

    async def send_json_await_ack(
        self, message_type: str, payload: dict[str, object]
    ) -> dict[str, object]:
        assert message_type == "agent.config.boundary"
        _append_ledger(
            self._runtime,
            {
                "type": "boundary_applied",
                "boundary_id": payload["boundary_id"],
                "conversation_id": payload["conversation_id"],
            },
        )
        return {"boundary_id": payload["boundary_id"]}


def _message(*, chat_id: str, event_id: str, text: str) -> InboundMessage:
    return attach_runtime_protocol(
        InboundMessage(
            channel_name=_CHANNEL_NAME,
            text=text,
            external_user_id="external-owner",
            external_chat_id=chat_id,
            is_group=False,
            agent_id=_AGENT_ID,
            external_event_identity=ExternalInboundEventIdentity(
                connector_account_id="fake-account",
                provider_event_id=event_id,
            ),
        ),
        RuntimeProtocolFacts(
            external_identity=ExternalConversationIdentity(
                external_source="feishu",
                external_chat_id=chat_id,
                agent_id=_AGENT_ID,
                trigger_source="feishu",
            )
        ),
    )


def _owners(args: argparse.Namespace, *, kernel_prefix: str) -> _Owners:
    runtime = Path(args.runtime)
    workspace = runtime / "workspace"
    workspace.mkdir(exist_ok=True)
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id=_AGENT_ID,
                workspace_root=workspace,
                title="Agent A",
            ),
        )
    )
    binder = GatewaySessionBinder(
        catalog=catalog,
        kernel=_Kernel(prefix=kernel_prefix),
        db_path=runtime / "session_bindings.sqlite3",
        boundary_retry_initial_seconds=0,
    )
    saga_store = ExternalShadowSagaStore(
        db_path=runtime / "external_shadow_sagas.sqlite3"
    )

    async def token_getter() -> str:
        return str(args.token)

    shadow_sync = IMShadowConversationSync(
        base_url=str(args.im_url),
        token_getter=token_getter,
        owner_user_id=str(args.owner_id),
        node_id="node-1",
        saga_store=saga_store,
        promote_pending_boundary=binder.promote_pending_shadow_boundary,
    )
    return _Owners(catalog, binder, saga_store, shadow_sync)


async def _resolve(
    owners: _Owners, message: InboundMessage
) -> tuple[SessionBindingRequest, SessionBinding]:
    request = SessionBindingRequest(
        session_key=build_session_key(message, agent_id=_AGENT_ID),
        reply_context=build_reply_context(message),
        message=message,
    )
    binding = await owners.binder.resolve(
        request,
        owners.catalog.require(_AGENT_ID),
    )
    return request, binding


async def _stage_a(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime)
    owners = _owners(args, kernel_prefix="gateway-a-session")
    agent = owners.catalog.require(_AGENT_ID)

    boundary_message = _message(
        chat_id="shadow-boundary-chat",
        event_id="boundary-event-1",
        text="boundary user message",
    )
    boundary_saga = owners.saga_store.prepare(
        message=boundary_message,
        agent_id=_AGENT_ID,
        owner_id=str(args.owner_id),
    )
    assert boundary_saga is not None
    _boundary_request, boundary_binding = await _resolve(owners, boundary_message)
    owners.binder.persist_applied_runtime_with_pending_boundary(
        boundary_binding,
        runtime_fingerprint="runtime-v2",
        fingerprint_schema="runtime-v1",
        profile_version=2,
        boundary=PendingBoundaryIntent(
            boundary_id="boundary-1",
            node_id="node-1",
            agent_id=_AGENT_ID,
            runtime_fingerprint="runtime-v2",
            fingerprint_schema="runtime-v1",
            profile_version=2,
            applied_at="2026-08-10T00:00:00+00:00",
            shadow_saga_id=boundary_saga.saga_id,
        ),
        agent=agent,
    )

    control_message = _message(
        chat_id="control-chat",
        event_id="control-event-1",
        text="/new",
    )
    control_saga = owners.saga_store.prepare(
        message=control_message,
        agent_id=_AGENT_ID,
        owner_id=str(args.owner_id),
    )
    assert control_saga is not None
    control_request, old_binding = await _resolve(owners, control_message)
    candidate = await owners.binder.prepare_reset(control_request, agent)
    published = owners.binder.publish_reset(
        candidate,
        operation_id="external:new-1",
        superseded_run_id=None,
        reply_text=_CONFIRMATION,
        external_saga_id=control_saga.saga_id,
    )
    _write_state(
        runtime,
        {
            "durable_commit_reached": True,
            "shadow_anchor_blocked": True,
            "allow_remote_delivery": False,
            "old_control_session_id": old_binding.kernel_session_id,
            "new_control_session_id": published.kernel_session_id,
        },
    )

    channel = _FileChannel(runtime)
    materializer = ExternalControlDeliveryMaterializer(
        session_binder=owners.binder,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        shadow_sync=owners.shadow_sync,
    )
    await materializer.drain()


async def _recover_b(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime)
    owners = _owners(args, kernel_prefix="gateway-b-session")
    materializer = ExternalControlDeliveryMaterializer(
        session_binder=owners.binder,
        outbound_router=OutboundRouter(ChannelRegistry((_FileChannel(runtime),))),
        shadow_sync=owners.shadow_sync,
    )
    await materializer.drain()
    await asyncio.sleep(0)
    await owners.shadow_sync.recover_pending()
    await BoundaryOutboxDispatcher(binder=owners.binder).drain(
        _FileBoundaryConnection(runtime)
    )

    # Re-run every recovery owner to prove stable idempotency after success.
    await materializer.drain()
    await owners.shadow_sync.recover_pending()
    await BoundaryOutboxDispatcher(binder=owners.binder).drain(
        _FileBoundaryConnection(runtime)
    )
    next_message = _message(
        chat_id="control-chat",
        event_id="control-event-2",
        text="message after reset",
    )
    _request, next_binding = await _resolve(owners, next_message)
    print(
        json.dumps(
            {
                "current_control_session_id": next_binding.kernel_session_id,
                "next_message_session_id": next_binding.kernel_session_id,
            }
        )
    )


def _state_path(runtime: Path) -> Path:
    return runtime / "barrier-state.json"


def _read_state(runtime: Path) -> dict[str, object]:
    path = _state_path(runtime)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(runtime: Path, state: dict[str, object]) -> None:
    _state_path(runtime).write_text(json.dumps(state), encoding="utf-8")


def _append_ledger(runtime: Path, event: dict[str, object]) -> None:
    with (runtime / "fake-external-chat.jsonl").open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(event, ensure_ascii=False) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("initialize-im", "serve-im", "stage-a", "recover-b")
    )
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--port", type=int)
    parser.add_argument("--im-url")
    parser.add_argument("--token")
    parser.add_argument("--owner-id")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.mode == "initialize-im":
        initialize_im(Path(args.runtime))
    elif args.mode == "serve-im":
        serve_im(Path(args.runtime), port=int(args.port))
    elif args.mode == "stage-a":
        asyncio.run(_stage_a(args))
    else:
        asyncio.run(_recover_b(args))


if __name__ == "__main__":
    main()
