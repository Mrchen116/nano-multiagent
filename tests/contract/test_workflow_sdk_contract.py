"""Public Workflow DTOs are immutable and SDK-owned."""

from dataclasses import FrozenInstanceError

import pytest

from agent.sdk import (
    BackgroundReturnInfo,
    SavedWorkflowInfo,
    WorkflowAgentInfo,
    WorkflowControlAction,
    WorkflowPhaseInfo,
    WorkflowRunInfo,
    WorkflowSaveScope,
)


def test_workflow_public_enums_and_dtos_are_available() -> None:
    agent = WorkflowAgentInfo(
        agent_call_id="call_1",
        start_ordinal=1,
        status="completed",
        prompt="review",
        result="done",
        transcript_path="/artifacts/call_1.jsonl",
    )
    run = WorkflowRunInfo(
        run_id="wf_123456",
        task_id="wt_123456",
        parent_session_id="sess_parent",
        revision=3,
        status="completed",
        name="review",
        description="review changes",
        phases=(WorkflowPhaseInfo(title="Review", status="completed"),),
        agents=(agent,),
    )

    assert WorkflowControlAction.RESTART_AGENT == "restart_agent"
    assert WorkflowSaveScope.PERSONAL == "personal"
    assert run.agents == (agent,)
    assert run.agents[0].transcript_path == "/artifacts/call_1.jsonl"
    assert (
        SavedWorkflowInfo(name="review", scope="project", path="/x.py").name == "review"
    )
    assert (
        BackgroundReturnInfo(
            task_id="wt_123456",
            task_type="workflow",
            status="completed",
            description="review",
        ).task_id
        == "wt_123456"
    )
    with pytest.raises(FrozenInstanceError):
        run.status = "failed"  # type: ignore[misc]
