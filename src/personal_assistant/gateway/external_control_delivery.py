"""Recoverable external delivery for Gateway control-command confirmations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.shadow_sync import IMShadowConversationSync


class ExternalControlDeliveryMaterializer:
    """Move committed control outcomes into the existing external shadow saga.

    The session binder commits an intent before this class is called. A restart can
    therefore resume at the same operation and saga identity without relying on the
    provider to redeliver the command.
    """

    def __init__(
        self,
        *,
        session_binder: GatewaySessionBinder,
        outbound_router: OutboundRouter,
        shadow_sync: IMShadowConversationSync,
    ) -> None:
        self._session_binder = session_binder
        self._outbound_router = outbound_router
        self._shadow_sync = shadow_sync

    async def drain(self) -> None:
        """Materialize every committed external control not yet handed to its chat."""

        for delivery in self._session_binder.pending_external_controls():
            outcome = delivery.outcome
            output = self._shadow_sync.prepare_agent_output(
                saga_id=delivery.shadow_saga_id,
                run_id=f"control:{outcome.operation_id}",
                output_kind="final",
                kernel_message_id=outcome.operation_id,
                content=outcome.reply_text,
            )
            self._session_binder.mark_external_control_materialized(
                session_key=outcome.session_key,
                operation_id=outcome.operation_id,
                kind=outcome.kind,
            )
            reply_context = self._shadow_sync.reply_context_for_saga(
                delivery.shadow_saga_id
            )
            self._outbound_router.send_text(
                text=outcome.reply_text,
                reply_context=replace(
                    reply_context,
                    metadata={
                        **reply_context.metadata,
                        "reply_phase": "final",
                        "reply_dedupe_key": (
                            f"control:{outcome.kind}:{outcome.operation_id}"
                        ),
                    },
                ),
            )
            self._session_binder.mark_external_control_handed_off(
                session_key=outcome.session_key,
                operation_id=outcome.operation_id,
                kind=outcome.kind,
            )
            task = asyncio.create_task(
                self._shadow_sync.mirror_prepared_agent_output(output),
                name=(f"external-control-shadow:{outcome.kind}:{outcome.operation_id}"),
            )
            task.add_done_callback(_report_mirror_failure)


def _report_mirror_failure(task: asyncio.Task[None]) -> None:
    """Keep IM shadow retries independent from the external confirmation path."""

    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception(
            "external control shadow mirror deferred for recovery"
        )
