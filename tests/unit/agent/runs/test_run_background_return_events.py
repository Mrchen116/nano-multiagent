from agent.core.background_tasks.notifications import BackgroundReturnInfo
from agent.core.events.hub import EventStreamHub
from agent.core.runs.registry import RunRecord, RunStatus, RunsRegistry


def test_opening_run_status_carries_background_returns_before_turn_events() -> None:
    hub = EventStreamHub()
    registry = object.__new__(RunsRegistry)
    registry._event_hub = hub  # noqa: SLF001
    background_return = BackgroundReturnInfo(
        task_id="wt_123",
        task_type="workflow",
        status="completed",
        description="review",
        workflow_run_id="wf_123456",
        result={"ok": True},
    )
    record = RunRecord(
        run_id="run_123",
        session_id="session_123",
        status=RunStatus.RUNNING,
        created_at="2026-08-10T00:00:00Z",
        updated_at="2026-08-10T00:00:01Z",
        source_background_returns=(background_return,),
    )

    registry._publish_run_status_event(record)  # noqa: SLF001

    event = next(
        hub.stream(
            session_id="session_123",
            after_sequence=0,
            max_events=1,
            timeout_seconds=0.01,
        )
    )
    assert event.event == "run_status"
    assert event.data["status"] == "running"
    assert event.data["background_returns"] == [background_return.to_dict()]
