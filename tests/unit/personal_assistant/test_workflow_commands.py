from agent.sdk import WorkflowAgentInfo, WorkflowPhaseInfo, WorkflowRunInfo

from personal_assistant.gateway.workflow_commands import (
    format_workflow_run,
    parse_workflow_command,
)
from personal_assistant.gateway.effort_commands import parse_effort_command


def test_parse_workflow_list_detail_controls_save_and_config() -> None:
    assert parse_workflow_command("/workflows", named_workflows=()).kind == "list"
    assert (
        parse_workflow_command("/workflows wf_123", named_workflows=()).kind == "detail"
    )
    paused = parse_workflow_command("/workflows wf_123 pause", named_workflows=())
    assert (paused.kind, paused.run_id, paused.action) == (
        "control",
        "wf_123",
        "pause",
    )
    restarted = parse_workflow_command(
        "/workflows wf_123 restart call_2", named_workflows=()
    )
    assert (restarted.action, restarted.agent_call_id) == ("restart_agent", "call_2")
    saved = parse_workflow_command(
        "/workflows wf_123 save project review", named_workflows=()
    )
    assert (saved.kind, saved.scope, saved.name) == ("save", "project", "review")
    configured = parse_workflow_command(
        "/config workflowSizeGuideline large", named_workflows=()
    )
    assert (configured.kind, configured.guideline) == ("config", "large")
    assert parse_workflow_command("/effort ultracode", named_workflows=()) is None


def test_parse_effort_command_keeps_level_validation_model_derived() -> None:
    assert parse_effort_command("/effort custom-level").value == "custom-level"
    assert parse_effort_command("/effort").value is None
    assert parse_effort_command("/effort low extra").value is None
    assert parse_effort_command("/workflows") is None


def test_parse_named_workflow_keeps_user_arguments() -> None:
    parsed = parse_workflow_command(
        "/review-changes focus on API compatibility",
        named_workflows=("review-changes",),
    )

    assert parsed.kind == "invoke"
    assert parsed.name == "review-changes"
    assert parsed.arguments == "focus on API compatibility"

    namespaced = parse_workflow_command(
        "/quality:review focus on tests",
        named_workflows=("quality:review",),
    )
    assert namespaced.name == "quality:review"


def test_parse_unknown_or_invalid_command() -> None:
    assert parse_workflow_command("/unknown", named_workflows=("known",)) is None
    invalid = parse_workflow_command(
        "/config workflowSizeGuideline enormous", named_workflows=()
    )
    assert invalid.kind == "error"
    assert "unrestricted" in (invalid.error or "")


def test_format_workflow_run_exposes_raw_result_and_diagnostics() -> None:
    rendered = format_workflow_run(
        WorkflowRunInfo(
            run_id="wf_123",
            task_id="wt_456",
            parent_session_id="sess_1",
            revision=4,
            status="completed",
            name="review",
            description="Review changes",
            current_phase="verify",
            phases=(
                WorkflowPhaseInfo(
                    title="verify",
                    detail="Verify findings",
                    status="completed",
                    usage={"total_tokens": 21},
                    duration_ms=1500,
                ),
            ),
            agents=(
                WorkflowAgentInfo(
                    agent_call_id="wa_1",
                    start_ordinal=0,
                    status="completed",
                    prompt="Verify the API contract",
                    label="verify-api",
                    phase="verify",
                    result="contract is valid",
                    usage={"total_tokens": 21},
                    duration_ms=1200,
                    session_id="child-1",
                    transcript_path="/artifacts/child-1.jsonl",
                    worktree_path="/retained/wa_1",
                ),
            ),
            result="2 findings",
            usage={"input_tokens": 120, "output_tokens": 30},
            duration_ms=2400,
            script_path="/tmp/review.py",
            transcript_dir="/tmp/wf_123",
        )
    )

    assert "wf_123 · review · completed" in rendered
    assert "阶段: verify" in rendered
    assert "结果: 2 findings" in rendered
    assert "诊断: /tmp/wf_123" in rendered
    assert "input_tokens=120" in rendered
    assert "[completed] verify" in rendered
    assert "Verify findings" in rendered
    assert "任务: Verify the API contract" in rendered
    assert "结果: contract is valid" in rendered
    assert "Session: child-1" in rendered
    assert "Transcript: /artifacts/child-1.jsonl" in rendered
    assert "保留 worktree: /retained/wa_1" in rendered
