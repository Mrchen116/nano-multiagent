"""Workflow background-task notification and stop contracts."""

from agent.core.background_tasks.models import (
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from agent.core.background_tasks.notifications import (
    build_background_notification,
)
from agent.core.background_tasks.registry import BackgroundTaskRegistry


def _workflow_registry() -> tuple[BackgroundTaskRegistry, str]:
    registry = BackgroundTaskRegistry()
    task_id = "wt_123456"
    registry.register_workflow(
        task_id=task_id,
        parent_session_id="sess_parent",
        workflow_run_id="wf_123456",
        description="review changes",
        output_file="/tmp/workflow/journal.jsonl",
        diagnostics="/tmp/workflow",
        resume_hint="/workflows wf_123456 resume",
        workspace_root="/workspace",
    )
    registry.mark_running(task_id)
    return registry, task_id


def test_workflow_stop_is_distinct_from_existing_killed_status() -> None:
    registry, task_id = _workflow_registry()

    stopped = registry.stop(
        task_id,
        result_text="partial result",
        usage={"total_tokens": 42},
        duration_ms=1200,
        tool_use_count=3,
    )
    late = registry.complete(task_id, result_text="late complete")

    assert stopped.task_type is BackgroundTaskType.WORKFLOW
    assert stopped.status is BackgroundTaskStatus.STOPPED
    assert stopped.result_text == "partial result"
    assert late == stopped


def test_notification_projection_renders_workflow_xml_and_sidecar_from_same_record() -> None:
    registry, task_id = _workflow_registry()
    terminal = registry.complete(
        task_id,
        result_text="two findings",
        usage={"total_tokens": 42},
        duration_ms=1200,
        tool_use_count=3,
    )

    notification = build_background_notification(terminal)

    assert "<workflow-run-id>wf_123456</workflow-run-id>" in notification.xml
    assert "<result>two findings</result>" in notification.xml
    assert notification.background_return is not None
    assert notification.background_return.task_id == task_id
    assert notification.background_return.task_type == "workflow"
    assert notification.background_return.workflow_run_id == "wf_123456"
    assert notification.background_return.status == "completed"
    assert notification.background_return.result == "two findings"
    assert notification.background_return.usage == {"total_tokens": 42}
    assert notification.background_return.diagnostics == "/tmp/workflow"
    assert notification.background_return.resume_hint == "/workflows wf_123456 resume"


def test_bash_notification_keeps_xml_but_has_no_ui_sidecar() -> None:
    registry = BackgroundTaskRegistry()
    registry.register_bash(
        task_id="b1",
        parent_session_id="sess_parent",
        description="tests",
        command="pytest",
        output_file="/tmp/bash.out",
    )
    terminal = registry.complete("b1", result_text="ok")

    notification = build_background_notification(terminal)

    assert "<task-id>b1</task-id>" in notification.xml
    assert notification.background_return is None


def test_notification_claim_has_one_winner() -> None:
    registry, task_id = _workflow_registry()
    registry.complete(task_id, result_text="done")

    first = registry.claim_notification(task_id)
    second = registry.claim_notification(task_id)

    assert first is not None
    assert first.notified is True
    assert second is None
