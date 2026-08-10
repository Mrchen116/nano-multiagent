"""Test-only subprocess launcher for Gateway continuity partial recovery."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import time

from personal_assistant.channels.base import (
    ExternalInboundEventIdentity,
    InboundMessage,
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
    ShadowConversationRef,
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
from tests.e2e.critical_paths._session_continuity_recovery_support import (
    FileBoundaryConnection,
    FileChannel,
    Kernel,
    read_state,
    write_state,
)

_AGENT_ID = "agent-a"
_CHANNEL_NAME = "feishu:agent-a"
_CONFIRMATION = "已开始新会话。"


@dataclass(frozen=True)
class _Owners:
    catalog: LiveAgentCatalog
    binder: GatewaySessionBinder
    saga_store: ExternalShadowSagaStore
    shadow_sync: IMShadowConversationSync


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


def _owners(
    args: argparse.Namespace,
    *,
    kernel_prefix: str,
    block_after_boundary_promotion: bool = False,
) -> _Owners:
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
        kernel=Kernel(prefix=kernel_prefix),
        db_path=runtime / "session_bindings.sqlite3",
        boundary_retry_initial_seconds=0,
    )
    saga_store = ExternalShadowSagaStore(
        db_path=runtime / "external_shadow_sagas.sqlite3"
    )

    async def token_getter() -> str:
        return str(args.token)

    def promote_boundary(saga_id: str, shadow_ref: ShadowConversationRef) -> object:
        promoted = binder.promote_pending_shadow_boundary(saga_id, shadow_ref)
        if block_after_boundary_promotion and promoted is not None:
            state = read_state(runtime)
            write_state(
                runtime,
                {
                    **state,
                    "promotion_committed": True,
                    "promoted_boundary_id": promoted.boundary_id,
                    "promoted_saga_id": saga_id,
                    "saga_anchor_absent": (
                        saga_store.require(saga_id).shadow_ref is None
                    ),
                },
            )
            while not read_state(runtime).get("allow_remote_delivery"):
                time.sleep(0.05)
        return promoted

    shadow_sync = IMShadowConversationSync(
        base_url=str(args.im_url),
        token_getter=token_getter,
        owner_user_id=str(args.owner_id),
        node_id="node-1",
        saga_store=saga_store,
        promote_pending_boundary=promote_boundary,
        pending_shadow_boundary_saga_ids=binder.pending_shadow_boundary_saga_ids,
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
    owners = _owners(
        args,
        kernel_prefix="gateway-a-session",
        block_after_boundary_promotion=True,
    )
    agent = owners.catalog.require(_AGENT_ID)

    legacy_message = _message(
        chat_id="legacy-anchored-boundary-chat",
        event_id="legacy-boundary-event-1",
        text="legacy anchored boundary user message",
    )
    legacy_saga = owners.saga_store.prepare(
        message=legacy_message,
        agent_id=_AGENT_ID,
        owner_id=str(args.owner_id),
    )
    assert legacy_saga is not None
    _legacy_request, legacy_binding = await _resolve(owners, legacy_message)
    owners.binder.persist_applied_runtime_with_pending_boundary(
        legacy_binding,
        runtime_fingerprint="runtime-legacy",
        fingerprint_schema="runtime-v1",
        profile_version=2,
        boundary=PendingBoundaryIntent(
            boundary_id="boundary-legacy",
            node_id="node-1",
            agent_id=_AGENT_ID,
            runtime_fingerprint="runtime-legacy",
            fingerprint_schema="runtime-v1",
            profile_version=2,
            applied_at="2026-08-10T00:00:00+00:00",
            shadow_saga_id=legacy_saga.saga_id,
        ),
        agent=agent,
    )

    async def token_getter() -> str:
        return str(args.token)

    legacy_sync = IMShadowConversationSync(
        base_url=str(args.im_url),
        token_getter=token_getter,
        owner_user_id=str(args.owner_id),
        node_id="node-1",
        saga_store=owners.saga_store,
    )
    legacy_ref = await legacy_sync.sync_user_message(
        legacy_message,
        agent_id=_AGENT_ID,
    )
    assert legacy_ref is not None
    assert owners.saga_store.require(legacy_saga.saga_id).shadow_ref == legacy_ref

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
    write_state(
        runtime,
        {
            "durable_commit_reached": True,
            "saga_anchor_blocked": True,
            "allow_remote_delivery": False,
            "old_control_session_id": old_binding.kernel_session_id,
            "new_control_session_id": published.kernel_session_id,
            "legacy_saga_id": legacy_saga.saga_id,
            "legacy_boundary_id": "boundary-legacy",
        },
    )
    await owners.shadow_sync.sync_user_message(
        boundary_message,
        agent_id=_AGENT_ID,
    )


async def _recover_b(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime)
    owners = _owners(args, kernel_prefix="gateway-b-session")
    materializer = ExternalControlDeliveryMaterializer(
        session_binder=owners.binder,
        outbound_router=OutboundRouter(ChannelRegistry((FileChannel(runtime),))),
        shadow_sync=owners.shadow_sync,
    )
    await materializer.drain()
    await asyncio.sleep(0)
    await owners.shadow_sync.recover_pending()
    await BoundaryOutboxDispatcher(binder=owners.binder).drain(
        FileBoundaryConnection(runtime)
    )

    # Re-run every recovery owner to prove stable idempotency after success.
    await materializer.drain()
    await owners.shadow_sync.recover_pending()
    await BoundaryOutboxDispatcher(binder=owners.binder).drain(
        FileBoundaryConnection(runtime)
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
                "remaining_pending_shadow_sagas": (
                    owners.binder.pending_shadow_boundary_saga_ids()
                ),
            }
        )
    )


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
