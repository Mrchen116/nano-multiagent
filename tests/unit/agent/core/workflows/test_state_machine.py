import pytest

from agent.core.workflows import WorkflowStatus, transition_workflow


def test_workflow_state_machine_allows_only_documented_live_transitions() -> None:
    assert (
        transition_workflow(WorkflowStatus.QUEUED, WorkflowStatus.RUNNING) == "running"
    )
    assert (
        transition_workflow(WorkflowStatus.RUNNING, WorkflowStatus.PAUSED) == "paused"
    )
    assert (
        transition_workflow(WorkflowStatus.PAUSED, WorkflowStatus.RUNNING) == "running"
    )
    assert (
        transition_workflow(WorkflowStatus.PAUSED, WorkflowStatus.STOPPED) == "stopped"
    )

    with pytest.raises(ValueError, match="invalid Workflow transition"):
        transition_workflow(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING)
