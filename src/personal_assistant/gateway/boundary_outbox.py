"""Deliver durable configuration-boundary intents to IM."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from typing import Protocol

from personal_assistant.gateway.session_keys import BoundaryIntent
from personal_assistant.ws.im_connection import IMFrameRejectedError


class BoundaryOutboxStore(Protocol):
    """Describe persistent boundary operations owned by the Gateway."""

    def delivery_ready_boundaries(self) -> tuple[BoundaryIntent, ...]: ...

    def acknowledge_boundary(self, boundary_id: str) -> None: ...

    def record_boundary_error(self, boundary_id: str, *, reason: str) -> None: ...

    def defer_boundary_retry(
        self,
        boundary_id: str,
        *,
        reason: str,
        retry_initial_seconds: float,
        retry_max_seconds: float,
    ) -> None: ...

    def next_boundary_retry_delay(self) -> float | None: ...


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
        store: Gateway-local durable source of actual-applied boundary facts.

    Notes:
        Delivery is deliberately sequential. The connection manager also serializes
        ACK-gated frames, and retaining the item until its matching success ACK makes
        process crashes and reconnects safe to replay.
    """

    def __init__(
        self,
        *,
        store: BoundaryOutboxStore,
        retry_initial_seconds: float = 1.0,
        retry_max_seconds: float = 60.0,
        sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    ) -> None:
        if retry_initial_seconds < 0:
            raise ValueError("boundary retry initial delay must not be negative")
        if retry_max_seconds < retry_initial_seconds:
            raise ValueError("boundary retry maximum delay must cover initial delay")
        self._store = store
        self._retry_initial_seconds = retry_initial_seconds
        self._retry_max_seconds = retry_max_seconds
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

        while True:
            await self.drain(connection)
            retry_delay = self._store.next_boundary_retry_delay()
            if retry_delay is None:
                return
            await self._sleep(retry_delay)

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

        for intent in self._store.delivery_ready_boundaries():
            try:
                ack = await connection.send_json_await_ack(
                    "agent.config.boundary", asdict(intent)
                )
            except IMFrameRejectedError as exc:
                if exc.code in _DETERMINISTIC_REJECTION_CODES:
                    self._store.record_boundary_error(
                        intent.boundary_id,
                        reason=f"{exc.code}: {exc}",
                    )
                    continue
                self._defer_retry(intent, exc)
                continue
            except Exception as exc:
                self._defer_retry(intent, exc)
                continue
            acknowledged_id = ack.get("boundary_id")
            if acknowledged_id != intent.boundary_id:
                self._defer_retry(
                    intent,
                    RuntimeError("IM boundary ACK did not match durable intent"),
                )
                continue
            self._store.acknowledge_boundary(intent.boundary_id)

    def _defer_retry(self, intent: BoundaryIntent, error: Exception) -> None:
        """Retain one retryable wire failure with bounded exponential backoff."""

        self._store.defer_boundary_retry(
            intent.boundary_id,
            reason=str(error),
            retry_initial_seconds=self._retry_initial_seconds,
            retry_max_seconds=self._retry_max_seconds,
        )
