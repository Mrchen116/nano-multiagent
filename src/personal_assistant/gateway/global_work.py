"""Persist real global execution events and relay the acknowledged journal to IM."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
import logging
from typing import Any
from uuid import uuid4

_log = logging.getLogger(__name__)


class GlobalWorkRecorder:
    """Observe one Kernel and attribute real Session events to global Agents.

    Args:
        kernel: Public SDK Kernel providing committed ordered observations.
        store: Shared global Inbox/work journal persistence.
        inbox: Inbox service accepting durable content proofs.
    """

    def __init__(self, *, kernel: Any, store: Any, inbox: Any) -> None:
        self.kernel = kernel
        self.store = store
        self.inbox = inbox
        self._subscription: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.on_event: Callable[[Mapping[str, Any]], None] | None = None
        self.on_record: Callable[[], None] | None = None
        self._permissions: dict[str, tuple[str, str]] = {}
        self._run_turns: dict[tuple[str, str], str] = {}
        self._runtime_seen: dict[str, str] = {}
        self._pending_configs: dict[str, dict[str, Any]] = {}
        self._recording_gaps: dict[tuple[str, str], dict[str, Any]] = {}
        self.degraded = False

    def start(self) -> None:
        """Install exactly one synchronous observer before opening producers."""
        self._loop = asyncio.get_running_loop()
        if self._subscription is None:
            self._subscription = self.kernel.observe_events(self._observe)

    def close(self) -> None:
        """Wait for entered callbacks after Kernel execution has been closed."""
        if self._subscription is not None:
            self._subscription.close()
            self._subscription = None

    def register(
        self,
        *,
        agent_id: str,
        session_id: str,
        scope: str,
        parent_session_id: str | None = None,
        **identity: Any,
    ) -> None:
        """Persist observed ownership before accepting any execution events."""
        self.store.register_work_session(
            session_id, agent_id, scope, parent_session_id=parent_session_id, **identity
        )
        self.record(
            agent_id=agent_id,
            session_id=session_id,
            event_type="session_registered",
            event_id=f"work-session:{session_id}",
            payload={
                "scope": scope,
                "parent_session_id": parent_session_id,
                **identity,
            },
        )

    def record(
        self,
        *,
        agent_id: str,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        event_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """Append one PA-owned fact using its stable business identity."""
        session_fact = event_type in {
            "session_registered",
            "control_result",
            "recording_degraded",
            "cron_trigger",
            "cron_delivery",
        }
        self._persist(
            event_id=event_id or str(uuid4()),
            root_agent_id=agent_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            turn_id=turn_id
            or (
                self._run_turns.get((session_id, str(payload.get("run_id") or "")))
                if not session_fact
                else None
            ),
        )
        self._notify_record()

    def _persist(self, **event: Any) -> None:
        try:
            # A recovered disk cannot reconstruct missed facts. Persist that
            # boundary before the next event, without borrowing an old turn.
            for key, gap in list(self._recording_gaps.items()):
                self.store.append_work_event(
                    event_id=gap["event_id"],
                    root_agent_id=key[0],
                    session_id=key[1],
                    event_type="recording_degraded",
                    turn_id=None,
                    payload={
                        **gap["payload"],
                        "recovered_at": datetime.now(timezone.utc).isoformat(),
                        "recording_complete": False,
                    },
                )
                del self._recording_gaps[key]
                self._notify_record()
            self.store.append_work_event(**event)
            self.degraded = False
        except Exception as exc:
            key = (event["root_agent_id"], event["session_id"])
            now = datetime.now(timezone.utc).isoformat()
            gap = self._recording_gaps.setdefault(
                key,
                {
                    "event_id": f"recording-gap:{uuid4()}",
                    "payload": {
                        "first_failed_event_id": event["event_id"],
                        "first_failed_at": now,
                        "failed_write_count": 0,
                    },
                },
            )["payload"]
            gap["failed_write_count"] += 1
            gap["last_failed_event_id"] = event["event_id"]
            gap["last_failed_at"] = now
            gap["error_type"] = type(exc).__name__
            self.degraded = True
            raise

    def runtime_applied(
        self,
        *,
        agent_id: str,
        session_id: str,
        workspace_root: str,
        runtime_fingerprint: str,
        profile_version: int,
        model: str,
    ) -> None:
        """Retain actual applied identity and attach its boundary to the next turn."""
        self.store.save_global_session(
            agent_id,
            session_id,
            workspace_root,
            runtime_fingerprint=runtime_fingerprint,
            profile_version=profile_version,
        )
        if self._runtime_seen.get(session_id) != runtime_fingerprint:
            self._runtime_seen[session_id] = runtime_fingerprint
            self._pending_configs[session_id] = {
                "profile_version": profile_version,
                "model": model,
            }

    def _notify_record(self) -> None:
        if self._loop is not None and self.on_record is not None:
            self._loop.call_soon_threadsafe(self.on_record)

    def _observe(self, event: Mapping[str, Any]) -> None:
        # This callback only commits local facts. Scheduling defers Kernel/network
        # calls until after the publisher releases its admission/event locks.
        try:
            kind = str(event.get("event") or "")
            if kind in {
                "permission_request",
                "permission_resolved",
                "permission_response",
            } and event.get("execution_session_id"):
                # Workflow routes notifications to its parent, while the work
                # journal belongs to the Session that actually requested access.
                event = {**event, "session_id": event["execution_session_id"]}
            session_id = str(event.get("session_id") or "")
            if kind == "session_linked":
                parent_id = str(event.get("parent_session_id") or session_id)
                parent = self.store.get_work_session(parent_id)
                child = event.get("child_session_id")
                if parent is not None and isinstance(child, str):
                    self.register(
                        agent_id=parent["root_agent_id"],
                        session_id=child,
                        scope="workflow"
                        if event.get("workflow_run_id")
                        else "subagent",
                        parent_session_id=parent_id,
                        child_agent_id=event.get("child_agent_id"),
                        workflow_run_id=event.get("workflow_run_id"),
                        description=event.get("description"),
                    )
            if event.get("turn_id"):
                if event.get("run_id"):
                    self._run_turns[(session_id, str(event["run_id"]))] = str(
                        event["turn_id"]
                    )
            owner = self.store.get_work_session(session_id)
            if owner is None:
                return
            self._persist(
                event_id=str(event["event_id"]),
                root_agent_id=owner["root_agent_id"],
                session_id=session_id,
                event_type=kind,
                payload=dict(event),
                turn_id=event.get("turn_id"),
                source_event_id=str(event["event_id"]),
                observed_at=event.get("created_at"),
            )
            if kind == "turn_started" and session_id in self._pending_configs:
                self.record(
                    agent_id=owner["root_agent_id"],
                    session_id=session_id,
                    event_type="runtime_config_applied",
                    turn_id=event.get("turn_id"),
                    event_id=f"config:{session_id}:{event.get('turn_id')}",
                    payload=self._pending_configs[session_id],
                )
                self._pending_configs.pop(session_id)
            if kind == "tool_result_committed" and owner["scope"] == "global_main":
                self.inbox.confirm_committed_read(event)
            request_id = event.get("request_id")
            if kind == "permission_request" and isinstance(request_id, str):
                self._permissions[request_id] = (owner["root_agent_id"], session_id)
            if kind in {"permission_resolved", "permission_response"} and isinstance(
                request_id, str
            ):
                self._permissions.pop(request_id, None)
            self._notify_record()
            if self._loop is not None and self.on_event is not None:
                self._loop.call_soon_threadsafe(self.on_event, dict(event))
        except Exception:
            self.degraded = True
            _log.exception("global work recording degraded")

    def decide_permission(self, payload: Mapping[str, Any]) -> bool:
        """Authorize only an actually observed pending request in this process."""
        request_id = str(payload.get("request_id") or "")
        expected = (payload.get("root_agent_id"), payload.get("session_id"))
        if self._permissions.get(request_id) != expected:
            return False
        accepted = bool(
            self.kernel.submit_permission_decision(
                request_id=request_id,
                decision=str(payload.get("decision") or ""),
                reason=str(payload.get("reason") or ""),
            )
        )
        if accepted:
            self._permissions.pop(request_id, None)
        return accepted


def _wire_value(value: Any) -> Any:
    """Keep actual image locators while omitting model-only base64 payloads."""
    if isinstance(value, Mapping):
        if value.get("type") == "base64" and "data" in value:
            return {
                key: _wire_value(item) for key, item in value.items() if key != "data"
            }
        return {key: _wire_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_wire_value(item) for item in value]
    if isinstance(value, str) and value.startswith("data:image/"):
        return "[image data retained in model context]"
    return value


class GlobalWorkRelay:
    """Send contiguous durable batches; only an IM commit ACK advances progress."""

    def __init__(self, *, store: Any, manager_provider: Callable[[], Any]) -> None:
        self.store = store
        self.manager_provider = manager_provider
        self._task: asyncio.Task | None = None
        self._pending = asyncio.Event()
        self._caught_up = asyncio.Event()
        self._closed = False
        self._replay_from: int | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        """Start the journal sender on the Gateway event loop."""
        self._task = asyncio.create_task(self._run(), name="global-work-relay")
        self.notify()

    def notify(self) -> None:
        """Wake on a new committed event or connection recovery."""
        if self._closed:
            return
        self._caught_up.clear()
        self._pending.set()

    async def wait_caught_up(self) -> None:
        """Wait until recorded Session identities are durably queryable at IM."""
        if self._closed:
            raise ConnectionError("global work relay closed")
        self.notify()
        async with asyncio.timeout(30):
            await self._caught_up.wait()
        if self._closed:
            raise ConnectionError("global work relay closed")

    async def _run(self) -> None:
        while not self._closed:
            await self._pending.wait()
            self._pending.clear()
            manager = self.manager_provider()
            if manager is None or not manager.connected:
                continue
            while not self._closed:
                rows = (
                    self.store.read_work_events(from_seq=self._replay_from, limit=100)
                    if self._replay_from is not None
                    else self.store.read_unacked_events(limit=100)
                )
                if not rows:
                    self._replay_from = None
                    self._caught_up.set()
                    break
                batch = []
                size = 0
                for row in rows:
                    wire = _wire_value(row)
                    item_size = len(json.dumps(wire, ensure_ascii=False).encode())
                    if batch and size + item_size > 256 * 1024:
                        break
                    batch.append(wire)
                    size += item_size
                try:
                    ack = await manager.send_json_await_ack(
                        "agent.work.append",
                        {
                            "journal_id": self.store.journal_id,
                            "from_seq": batch[0]["seq"],
                            "events": batch,
                        },
                    )
                    if ack.get("journal_id") != self.store.journal_id:
                        raise ValueError(
                            "work journal acknowledgement identity mismatch"
                        )
                    through = int(ack["through_seq"])
                    if through < batch[0]["seq"]:
                        expected = ack.get("expected_seq")
                        if (
                            not isinstance(expected, int)
                            or expected <= 0
                            or expected != through + 1
                            or expected >= batch[0]["seq"]
                        ):
                            raise ValueError(f"invalid work journal gap at {expected}")
                        self._replay_from = expected
                        continue
                    self.store.acknowledge_events(through)
                    if self._replay_from is not None:
                        self._replay_from = through + 1
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                    _log.warning("global work sync failed: %s", exc)
                    break

    async def close(self, deadline: float) -> None:
        """Stop transport waits; all unacknowledged records remain durable."""
        manager = self.manager_provider()
        if (
            manager is not None
            and manager.connected
            and self.store.read_unacked_events(limit=1)
        ):
            self.notify()
            try:
                async with asyncio.timeout_at(deadline):
                    await self._caught_up.wait()
            except TimeoutError:
                pass
        self._closed = True
        self._caught_up.set()
        self._pending.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)


class GlobalWorkRuntime:
    """Order global observation, wake admission and journal delivery lifecycles."""

    def __init__(
        self, *, recorder: GlobalWorkRecorder, relay: GlobalWorkRelay, coordinator: Any
    ) -> None:
        self.recorder = recorder
        self.relay = relay
        self.coordinator = coordinator

    def start(self) -> None:
        """Install durable observation before any global run can be admitted."""
        self.recorder.start()
        self.relay.start()

    def ready(self) -> None:
        """Resume pending input only after the tool HTTP listener is accepting."""
        self.coordinator.start()

    def on_connected(self) -> None:
        """Resume journal delivery and any pending input after reconnection."""
        self.relay.notify()
        self.coordinator.start()

    def seal(self) -> None:
        """Close global producers while retaining observation of final events."""
        self.coordinator.seal()

    async def close(self, deadline: float) -> None:
        """Settle observers and transport after the Kernel has closed."""
        await self.coordinator.close(deadline)
        self.recorder.close()
        await self.relay.close(deadline)
