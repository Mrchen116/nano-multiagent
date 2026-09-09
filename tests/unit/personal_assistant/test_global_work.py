"""Verify journal replay and recording failures through observable boundaries."""

import asyncio

import pytest

from personal_assistant.gateway.global_inbox import GlobalInboxService, GlobalInboxStore
from personal_assistant.gateway.global_work import GlobalWorkRecorder, GlobalWorkRelay


def append_events(store, count):
    return [
        store.append_work_event(
            event_id=f"event-{number}",
            root_agent_id="a",
            session_id="main",
            event_type="text_delta",
            payload={"text": str(number)},
        )
        for number in range(1, count + 1)
    ]


class IMJournal:
    connected = True

    def __init__(self, store):
        self.store = store
        self.events = {}
        self.starts = []
        self.local_pending = []
        self.fail_after_commit = False

    async def send_json_await_ack(self, kind, payload):
        assert kind == "agent.work.append"
        self.starts.append(payload["from_seq"])
        self.local_pending.append(self.store.read_unacked_events(limit=1))
        through = max(self.events, default=0)
        if payload["from_seq"] > through + 1:
            return {
                "journal_id": payload["journal_id"],
                "through_seq": through,
                "expected_seq": through + 1,
            }
        for event in payload["events"]:
            previous = self.events.setdefault(event["seq"], event)
            assert previous == event
        if self.fail_after_commit:
            self.connected = False
            raise ConnectionError("ACK lost")
        return {
            "journal_id": payload["journal_id"],
            "through_seq": max(self.events),
        }


@pytest.mark.asyncio
async def test_gap_replays_acknowledged_prefix_without_regressing_local_ack(tmp_path):
    store = GlobalInboxStore(tmp_path / "journal.sqlite3")
    original = append_events(store, 205)
    store.acknowledge_events(200)
    manager = IMJournal(store)
    relay = GlobalWorkRelay(store=store, manager_provider=lambda: manager)
    relay.start()
    try:
        await asyncio.wait_for(relay.wait_caught_up(), 1)
        assert manager.starts == [201, 1, 101, 201]
        assert all(rows[0]["seq"] == 201 for rows in manager.local_pending)
        assert list(manager.events.values()) == original
        assert store.read_unacked_events() == []
        assert store.read_work_events(from_seq=1, limit=205) == original
        assert store.get_work_event("event-1") == original[0]
    finally:
        await relay.close(asyncio.get_running_loop().time())
        store.close()


@pytest.mark.asyncio
async def test_lost_ack_and_offline_close_preserve_exact_replay_after_reopen(tmp_path):
    path = tmp_path / "journal.sqlite3"
    store = GlobalInboxStore(path)
    original = append_events(store, 3)
    manager = IMJournal(store)
    manager.fail_after_commit = True
    relay = GlobalWorkRelay(store=store, manager_provider=lambda: manager)
    relay.start()
    # The manager finishes in one event-loop step and simulates a dropped ACK.
    await asyncio.sleep(0)
    await relay.close(asyncio.get_running_loop().time())
    assert relay.last_error == "ACK lost"
    store.close()
    reopened = GlobalInboxStore(path)
    assert reopened.read_unacked_events() == original
    manager.store = reopened
    manager.fail_after_commit = False
    manager.connected = True
    relay = GlobalWorkRelay(store=reopened, manager_provider=lambda: manager)
    relay.start()
    try:
        await asyncio.wait_for(relay.wait_caught_up(), 1)
        assert manager.starts == [1, 1]
        assert list(manager.events.values()) == original
        assert reopened.read_unacked_events() == []
    finally:
        await relay.close(asyncio.get_running_loop().time())
        reopened.close()


@pytest.mark.asyncio
async def test_close_cancels_transport_and_releases_readiness_waiter(tmp_path):
    store = GlobalInboxStore(tmp_path / "journal.sqlite3")
    original = append_events(store, 1)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class WaitingIM:
        connected = True

        async def send_json_await_ack(self, kind, payload):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

    manager = WaitingIM()
    relay = GlobalWorkRelay(store=store, manager_provider=lambda: manager)
    relay.start()
    waiter = asyncio.create_task(relay.wait_caught_up())
    await entered.wait()
    await relay.close(asyncio.get_running_loop().time())
    assert cancelled.is_set()
    with pytest.raises(ConnectionError, match="closed"):
        await asyncio.wait_for(waiter, 1)
    assert store.read_unacked_events() == original
    store.close()


class ObservedKernel:
    def observe_events(self, listener):
        self.listener = listener
        return self

    def close(self):
        self.listener = None

    def publish(self, kind, event_id, **payload):
        self.listener(
            {"event": kind, "event_id": event_id, "session_id": "main", **payload}
        )


class FailingStore(GlobalInboxStore):
    fail_writes = False

    def append_work_event(self, **kwargs):
        if self.fail_writes:
            raise OSError("disk unavailable")
        return super().append_work_event(**kwargs)


def make_recorder(tmp_path):
    store = FailingStore(tmp_path / "journal.sqlite3")
    kernel = ObservedKernel()
    recorder = GlobalWorkRecorder(
        kernel=kernel, store=store, inbox=GlobalInboxService(store)
    )
    recorder.register(agent_id="a", session_id="main", scope="global_main")
    recorder.start()
    return recorder, kernel, store


@pytest.mark.asyncio
async def test_workflow_permission_follows_execution_session_not_delivery_parent(
    tmp_path,
):
    recorder, kernel, store = make_recorder(tmp_path)
    try:
        recorder.register(
            agent_id="a", session_id="child", scope="workflow", parent_session_id="main"
        )
        decisions = []
        kernel.submit_permission_decision = lambda **p: decisions.append(p) or True
        kernel.publish(
            "permission_request",
            "ask",
            execution_session_id="child",
            turn_id="child-turn",
            request_id="p",
        )
        event = store.get_work_event("ask")
        assert event["session_id"] == event["payload"]["session_id"] == "child"
        assert event["turn_id"] == "child-turn"
        assert not recorder.decide_permission(
            {
                "root_agent_id": "a",
                "session_id": "main",
                "request_id": "p",
                "decision": "allow_once",
            }
        )
        assert recorder.decide_permission(
            {
                "root_agent_id": "a",
                "session_id": "child",
                "request_id": "p",
                "decision": "deny",
            }
        )
        assert decisions == [{"request_id": "p", "decision": "deny", "reason": ""}]
        kernel.publish(
            "permission_resolved",
            "resolved",
            execution_session_id="child",
            turn_id="child-turn",
            request_id="p",
        )
        assert store.get_work_event("resolved")["session_id"] == "child"
    finally:
        recorder.close()
        store.close()


@pytest.mark.asyncio
async def test_session_facts_do_not_inherit_ended_turn_but_run_facts_keep_identity(
    tmp_path,
):
    recorder, kernel, store = make_recorder(tmp_path)
    try:
        kernel.publish("turn_started", "start", turn_id="turn-1", run_id="run-1")
        kernel.publish("turn_end", "end", turn_id="turn-1", run_id="run-1")
        for kind in ("control_result", "cron_trigger", "cron_delivery"):
            recorder.record(
                agent_id="a",
                session_id="main",
                event_type=kind,
                event_id=kind,
                payload={"run_id": "run-1"},
            )
            assert store.get_work_event(kind)["turn_id"] is None
        recorder.record(
            agent_id="a",
            session_id="main",
            event_type="dispatch_confirmed",
            event_id="dispatch",
            payload={"run_id": "run-1"},
        )
        assert store.get_work_event("dispatch")["turn_id"] == "turn-1"
    finally:
        recorder.close()
        store.close()


@pytest.mark.asyncio
async def test_recording_recovers_with_durable_session_level_gap_fact(tmp_path):
    recorder, kernel, store = make_recorder(tmp_path)
    try:
        kernel.publish("turn_started", "start", turn_id="turn-1", run_id="run-1")
        store.fail_writes = True
        kernel.publish("tool_start", "lost-tool", turn_id="turn-1", run_id="run-1")
        kernel.publish("turn_end", "lost-end", turn_id="turn-1", run_id="run-1")
        assert recorder.degraded
        store.fail_writes = False
        kernel.publish("session_idle", "recovered")
        rows = store.read_unacked_events()
        gap = next(row for row in rows if row["type"] == "recording_degraded")
        assert gap["turn_id"] is None
        assert gap["payload"]["failed_write_count"] == 2
        assert gap["payload"]["first_failed_event_id"] == "lost-tool"
        assert gap["payload"]["last_failed_event_id"] == "lost-end"
        assert gap["payload"]["recording_complete"] is False
        assert gap["seq"] < store.get_work_event("recovered")["seq"]
        assert store.get_work_event("lost-tool") is None
        assert store.get_work_event("lost-end") is None
        assert not recorder.degraded
        kernel.publish("session_idle", "again")
        assert (
            sum(
                row["type"] == "recording_degraded"
                for row in store.read_unacked_events()
            )
            == 1
        )
    finally:
        recorder.close()
        store.close()


@pytest.mark.asyncio
async def test_public_record_failure_also_leaves_recovery_fact(tmp_path):
    recorder, _, store = make_recorder(tmp_path)
    fact = dict(
        agent_id="a",
        session_id="main",
        event_type="control_result",
        event_id="control",
        payload={"status": "applied"},
    )
    try:
        store.fail_writes = True
        with pytest.raises(OSError, match="disk unavailable"):
            recorder.record(**fact)
        store.fail_writes = False
        recorder.record(**fact)
        rows = store.read_unacked_events()
        gap = next(row for row in rows if row["type"] == "recording_degraded")
        assert gap["payload"]["failed_write_count"] == 1
        assert store.get_work_event("control")["payload"] == fact["payload"]
    finally:
        recorder.close()
        store.close()
