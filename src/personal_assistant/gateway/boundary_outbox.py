"""Deliver durable configuration-boundary intents to IM."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from typing import Protocol

from personal_assistant.gateway.session_binder import (
    BoundaryDispatchAcked,
    BoundaryDispatchIdle,
    BoundaryDispatchPermanentlyRejected,
    BoundaryDispatchReady,
    BoundaryDispatchRetryableFailure,
    BoundaryDispatchWait,
    GatewaySessionBinder,
)
from personal_assistant.ws.im_connection import IMFrameRejectedError


class BoundaryConnection(Protocol):
    """Describe the ACK-gated IM operation required by boundary delivery."""

    async def send_json_await_ack(
        self, message_type: str, payload: Mapping[str, object]
    ) -> dict[str, object]: ...


_DETERMINISTIC_REJECTION_CODES = frozenset(
    {
        "gateway_owner_mismatch",
        "anchor_not_found",
        "agent_not_participant",
        "agent_not_found",
        "conversation_not_found",
        "bad_payload",
    }
)


class BoundaryOutboxDispatcher:
    """Drain durable boundary intents through the IM websocket ACK protocol.

    Args:
        binder: Gateway continuity owner for durable boundary transitions.

    Notes:
        Delivery is deliberately sequential. The connection manager also serializes
        ACK-gated frames, and retaining the item until its matching success ACK makes
        process crashes and reconnects safe to replay.
    """

    def __init__(
        self,
        *,
        binder: GatewaySessionBinder,
        sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    ) -> None:
        self._binder = binder
        self._sleep = sleep
        self._drain_task: asyncio.Task[None] | None = None
        self._connection: BoundaryConnection | None = None

    def schedule_drain(self, connection: BoundaryConnection) -> asyncio.Task[None]:
        """Schedule ACK-gated delivery and durable delayed retries after connection."""

        self._connection = connection
        if self._drain_task is not None and not self._drain_task.done():
            self._drain_task.cancel()
        task = self._start_drain(connection)
        return task

    def notify_pending(self) -> asyncio.Task[None] | None:
        """Schedule delivery for a newly durable fact on the registered connection."""

        connection = self._connection
        if connection is None:
            return None
        if self._drain_task is not None and not self._drain_task.done():
            self._drain_task.cancel()
        return self._start_drain(connection)

    def _start_drain(self, connection: BoundaryConnection) -> asyncio.Task[None]:
        """Start one tracked drain task for the current connection epoch."""

        task = asyncio.create_task(self._drain_until_idle(connection))
        self._drain_task = task
        task.add_done_callback(self._report_drain_failure)
        return task

    async def _drain_until_idle(self, connection: BoundaryConnection) -> None:
        """Drain ready work, then wait only for durable retry deadlines."""

        await self.drain(connection)

    @staticmethod
    def _report_drain_failure(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logging.getLogger(__name__).exception("boundary outbox delivery failed")

    async def drain(self, connection: BoundaryConnection) -> None:
        """Attempt every delivery-ready intent without erasing later facts."""

        while True:
            plan = self._binder.next_boundary_dispatch()
            if isinstance(plan, BoundaryDispatchIdle):
                return
            if isinstance(plan, BoundaryDispatchWait):
                await self._sleep(plan.delay_seconds)
                continue
            if not isinstance(plan, BoundaryDispatchReady):  # pragma: no cover
                raise TypeError(f"unsupported boundary dispatch plan: {plan!r}")
            intent = plan.intent
            try:
                ack = await connection.send_json_await_ack(
                    "agent.config.boundary", asdict(intent)
                )
            except IMFrameRejectedError as exc:
                if exc.code in _DETERMINISTIC_REJECTION_CODES:
                    self._binder.complete_boundary_dispatch(
                        intent.boundary_id,
                        BoundaryDispatchPermanentlyRejected(
                            reason=f"{exc.code}: {exc}"
                        ),
                    )
                    continue
                self._binder.complete_boundary_dispatch(
                    intent.boundary_id,
                    BoundaryDispatchRetryableFailure(reason=str(exc)),
                )
                continue
            except Exception as exc:
                self._binder.complete_boundary_dispatch(
                    intent.boundary_id,
                    BoundaryDispatchRetryableFailure(reason=str(exc)),
                )
                continue
            acknowledged_id = ack.get("boundary_id")
            if acknowledged_id != intent.boundary_id:
                self._binder.complete_boundary_dispatch(
                    intent.boundary_id,
                    BoundaryDispatchRetryableFailure(
                        reason="IM boundary ACK did not match durable intent"
                    ),
                )
                continue
            self._binder.complete_boundary_dispatch(
                intent.boundary_id,
                BoundaryDispatchAcked(),
            )
