"""Protect durable work identity, atomic replay and root isolation."""

import pytest
from IM.infra.db import connect, initialize_schema
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.agent_work import AgentWorkRepository


def test_work_batch_replay_projection_and_root_isolation(tmp_path):
    db = connect(tmp_path / "im.sqlite3")
    initialize_schema(db)
    profiles = AgentProfileRepository(db)
    for agent_id in ["a", "b"]:
        profiles.create_profile(
            agent_id=agent_id,
            owner_id="owner",
            node_id="node",
            display_name=agent_id,
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model=None,
            workspace_root=None,
            work_mode="global",
        )
    work = AgentWorkRepository(db)

    def event(seq, kind, payload, session="main", root="a", turn="turn"):
        return dict(
            seq=seq,
            event_id=f"event-{seq}",
            root_agent_id=root,
            session_id=session,
            turn_id=turn,
            type=kind,
            observed_at="2026-09-09T00:00:00Z",
            payload=payload,
        )

    events = [
        event(1, "session_registered", {"scope": "global_main"}),
        event(2, "turn_started", {"origin": "inbox", "model": "model"}),
        event(
            3,
            "tool_start",
            {"call_id": "call", "name": "bash", "arguments": {"command": "pwd"}},
        ),
        event(
            4,
            "tool_end",
            {
                "call_id": "call",
                "name": "bash",
                "duration_ms": 4,
                "presentation": {"detail": {"stdout": "/tmp"}},
            },
        ),
        event(
            5,
            "turn_end",
            {
                "status": "completed",
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        ),
    ]
    assert (
        work.append(node_id="node", journal_id="journal", from_seq=1, events=events)[
            "through_seq"
        ]
        == 5
    )
    assert (
        work.append(node_id="node", journal_id="journal", from_seq=1, events=events)[
            "through_seq"
        ]
        == 5
    )
    view = work.view("a")
    calls = [i for i in view["turns"][0]["items"] if i["kind"] == "tool"]
    assert len(calls) == 1 and calls[0]["payload"]["arguments"] == {"command": "pwd"}
    assert calls[0]["payload"]["detail"] == {"stdout": "/tmp"}
    assert view["turns"][0]["status"] == "completed"
    assert (
        work.append(
            node_id="node",
            journal_id="journal",
            from_seq=7,
            events=[event(7, "message", {})],
        )["expected_seq"]
        == 6
    )
    with pytest.raises(ValueError):
        work.append(
            node_id="node",
            journal_id="journal",
            from_seq=6,
            events=[event(6, "message", {"text": "wrong"}, root="b")],
        )
    assert work.view("a")["revision"] == 5
    with pytest.raises(ValueError):
        work.turns("b", "main")
    reopened = AgentWorkRepository(db)
    assert reopened.view("a")["turns"][0]["items"] == view["turns"][0]["items"]
    # SDK link events belong to the parent and carry its envelope session_id.
    linked = event(
        6,
        "session_linked",
        {
            "session_id": "main",
            "parent_session_id": "main",
            "child_session_id": "child",
            "child_agent_id": "worker",
        },
    )
    work.append(node_id="node", journal_id="journal", from_seq=6, events=[linked])
    assert work.session("a", "child")["session_id"] == "child"
    assert work.view("a")["other_executions"][0]["session_id"] == "child"


@pytest.mark.parametrize("trigger", ["manual", "scheduled", None])
def test_cron_turn_metadata_and_session_facts_remain_separate_from_main(
    tmp_path, trigger
):
    db = connect(tmp_path / "cron.sqlite3")
    initialize_schema(db)
    AgentProfileRepository(db).create_profile(
        agent_id="a",
        owner_id="owner",
        node_id="node",
        display_name="a",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="ALWAYS",
        default_model=None,
        workspace_root=None,
        work_mode="global",
    )
    work = AgentWorkRepository(db)
    events = []

    def record(session, kind, payload, turn=None):
        seq = len(events) + 1
        events.append(
            dict(
                seq=seq,
                event_id=f"cron-event-{seq}",
                root_agent_id="a",
                session_id=session,
                turn_id=turn,
                type=kind,
                observed_at="2026-09-09T00:00:00Z",
                payload=payload,
            )
        )

    record("main", "session_registered", {"scope": "global_main"})
    record("main", "turn_started", {"origin": "inbox"}, "main-turn")
    record(
        "main",
        "turn_end",
        {"usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        "main-turn",
    )
    metadata = {"scope": "cron", "job_id": "daily-report"}
    if trigger:
        metadata["trigger"] = trigger
    record("cron", "session_registered", metadata)
    record("cron", "cron_trigger", {"job_id": "daily-report", "trigger": trigger})
    record(
        "cron",
        "turn_started",
        {"origin": "model", "run_id": "cron-run", "trigger": None},
        "cron-turn",
    )
    record(
        "cron",
        "turn_end",
        {"usage": {"prompt_tokens": 900, "completion_tokens": 80}},
        "cron-turn",
    )
    delivery = {
        "run_id": "cron-run",
        "conversation_id": "target",
        "message_id": "sent",
        "text": "Actual cron result",
    }
    record("cron", "cron_delivery", delivery)
    work.append(node_id="node", journal_id="journal", from_seq=1, events=events)
    page = AgentWorkRepository(db).turns("a", "cron")
    assert len(page["turns"]) == 1
    turn = page["turns"][0]
    assert turn["scope"] == "cron"
    assert turn["job_id"] == "daily-report"
    assert turn["trigger"] == {"kind": "cron", "source": trigger}
    assert turn["usage"]["context_used"] == 900
    assert [item["kind"] for item in page["control_items"]] == [
        "cron_trigger",
        "cron_delivery",
    ]
    assert all(item["kind"] != "cron_delivery" for item in turn["items"])
    assert page["control_items"][1]["payload"] == delivery
    main = work.view("a")
    assert [item["turn_id"] for item in main["turns"]] == ["main-turn"]
    assert main["latest_main_usage"]["context_used"] == 12
    assert main["control_items"] == []
