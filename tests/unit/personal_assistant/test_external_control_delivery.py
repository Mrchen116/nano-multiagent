"""Durable external control-confirmation handoff tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from personal_assistant.channels.base import OutboundMessage, ReplyContext
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.external_control_delivery import (
    ExternalControlDeliveryMaterializer,
)
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_keys import (
    ControlOperation,
    PendingExternalControlDelivery,
    PersistentSessionBindingStore,
)
from personal_assistant.gateway.shadow_saga import ExternalShadowOutput


class _Channel:
    name = "feishu:agent-a"

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    def start(self, _on_inbound) -> None:  # noqa: ANN001
        return None

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        return None


class _Binder:
    def __init__(self, delivery: PendingExternalControlDelivery) -> None:
        self._delivery = delivery
        self.materialized: list[tuple[str, str, str]] = []
        self.handed_off: list[tuple[str, str, str]] = []

    def pending_external_controls(self) -> tuple[PendingExternalControlDelivery, ...]:
        return (self._delivery,)

    def mark_external_control_materialized(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None:
        self.materialized.append((session_key, operation_id, kind))

    def mark_external_control_handed_off(
        self, *, session_key: str, operation_id: str, kind: str
    ) -> None:
        self.handed_off.append((session_key, operation_id, kind))


class _ShadowSync:
    def __init__(self) -> None:
        self.prepared: list[ExternalShadowOutput] = []
        self.mirrored: list[ExternalShadowOutput] = []

    def prepare_agent_output(
        self,
        *,
        saga_id: str,
        run_id: str,
        output_kind: str,
        kernel_message_id: str | None,
        content: str,
    ) -> ExternalShadowOutput:
        output = ExternalShadowOutput(
            saga_id=saga_id,
            run_id=run_id,
            output_kind=output_kind,
            kernel_message_id=kernel_message_id,
            ordinal=0,
            content=content,
            im_message_id=None,
        )
        self.prepared.append(output)
        return output

    def reply_context_for_saga(self, saga_id: str) -> ReplyContext:
        assert saga_id == "saga-1"
        return ReplyContext(
            channel_name="feishu:agent-a",
            target_chat_id="oc-1",
            metadata={"feishu_message_id": "om-1"},
        )

    async def mirror_prepared_agent_output(self, output: ExternalShadowOutput) -> None:
        self.mirrored.append(output)


def _delivery() -> PendingExternalControlDelivery:
    return PendingExternalControlDelivery(
        outcome=ControlOperation(
            session_key="feishu:oc-1:agent-a",
            operation_id="shadow:saga-1",
            kind="new",
            status="completed",
            kernel_session_id="kernel-2",
            reply_text="已开始新会话。",
        ),
        shadow_saga_id="saga-1",
        state="pending_materialization",
    )


@pytest.mark.asyncio
async def test_control_materializer_persists_saga_output_before_external_handoff() -> (
    None
):
    delivery = _delivery()
    binder = _Binder(delivery)
    channel = _Channel()
    shadow_sync = _ShadowSync()
    materializer = ExternalControlDeliveryMaterializer(
        session_binder=binder,  # type: ignore[arg-type]
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        shadow_sync=shadow_sync,  # type: ignore[arg-type]
    )

    await materializer.drain()
    await asyncio.sleep(0)

    assert [output.run_id for output in shadow_sync.prepared] == [
        "control:shadow:saga-1"
    ]
    assert shadow_sync.prepared[0].content == "已开始新会话。"
    assert [message.text for message in channel.sent] == ["已开始新会话。"]
    assert channel.sent[0].metadata["reply_dedupe_key"] == "control:new:shadow:saga-1"
    assert binder.materialized == [
        (delivery.outcome.session_key, "shadow:saga-1", "new")
    ]
    assert binder.handed_off == [(delivery.outcome.session_key, "shadow:saga-1", "new")]
    assert shadow_sync.mirrored == shadow_sync.prepared


def test_persistent_control_intent_survives_before_saga_materialization(
    tmp_path: Path,
) -> None:
    store = PersistentSessionBindingStore(db_path=tmp_path / "bindings.sqlite3")
    outcome = _delivery().outcome

    store.record_control_operation(outcome, external_saga_id="saga-1")

    pending = store.pending_external_controls()
    assert pending == (
        PendingExternalControlDelivery(
            outcome=outcome,
            shadow_saga_id="saga-1",
            state="pending_materialization",
        ),
    )
    store.mark_external_control_materialized(
        session_key=outcome.session_key,
        operation_id=outcome.operation_id,
        kind=outcome.kind,
    )
    assert store.pending_external_controls()[0].state == "materialized"
    store.mark_external_control_handed_off(
        session_key=outcome.session_key,
        operation_id=outcome.operation_id,
        kind=outcome.kind,
    )
    assert store.pending_external_controls() == ()
