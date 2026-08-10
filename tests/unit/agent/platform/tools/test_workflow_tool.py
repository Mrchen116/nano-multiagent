from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from agent.core.errors import ToolError
from agent.core.session.types import INTERNAL_RUNTIME_KEY
from agent.core.workflows import compile_workflow
from agent.platform.permissions.broker import PermissionDecision
from agent.platform.tools.builtins.workflow import WorkflowTool, workflow_description


SCRIPT = '''
meta = {"name": "demo", "description": "Run a demo"}
async def main():
    return "ok"
'''


class _Manager:
    def __init__(self) -> None:
        self.calls = []

    def launch(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="async_launched",
            task_id="wt_123456",
            run_id="wf_123456",
            name="demo",
            script_path="/tmp/demo.py",
            diagnostics="/tmp/run",
        )


def _context(tmp_path: Path):  # noqa: ANN202
    return SimpleNamespace(
        session_id="sess_parent",
        cwd=tmp_path,
        repo_root=tmp_path,
        tool_call_id="call_parent",
        session_metadata={"run_id": "run_parent"},
        subagent_control=None,
    )


def test_workflow_exact_schema_and_launch_correlation(tmp_path: Path) -> None:
    manager = _Manager()
    tool = WorkflowTool(manager=manager)

    output = tool.run(
        {"script": SCRIPT, "description": "ignored", "title": "ignored"},
        _context(tmp_path),
    )

    assert tool.name == "Workflow"
    assert set(tool.input_schema["properties"]) == {
        "script",
        "scriptPath",
        "name",
        "args",
        "resumeFromRunId",
        "description",
        "title",
    }
    assert output["status"] == "async_launched"
    assert output["guideline"] == "medium"
    assert manager.calls[-1]["size_guideline"] == "medium"
    assert tool.result_event_metadata(output) == {
        "parent_session_id": "sess_parent",
        "parent_run_id": "run_parent",
        "parent_tool_call_id": "call_parent",
        "workflow_run_id": "wf_123456",
    }


def test_source_precedence_and_launch_validation(tmp_path: Path) -> None:
    manager = _Manager()
    tool = WorkflowTool(manager=manager)
    script_path = tmp_path / "saved.py"
    script_path.write_text(SCRIPT.replace('"demo"', '"path"', 1), encoding="utf-8")

    tool.run(
        {"scriptPath": str(script_path), "script": "not valid", "name": "missing"},
        _context(tmp_path),
    )
    assert manager.calls[-1]["source"].startswith('\nmeta = {"name": "path"')

    with pytest.raises(ToolError, match="scriptPath, script, or name"):
        tool.run({}, _context(tmp_path))
    assert len(manager.calls) == 1


def test_session_guideline_projects_description_and_launch_snapshot(
    tmp_path: Path,
) -> None:
    manager = _Manager()
    tool = WorkflowTool(manager=manager)
    context = _context(tmp_path)
    context.session_metadata = {
        "run_id": "run_parent",
        INTERNAL_RUNTIME_KEY: {"workflow_size_guideline": "small"},
    }

    spec = tool.spec_for_session(context.session_metadata)
    output = tool.run({"script": SCRIPT}, context)

    assert "small — keep workflows under 5 agents" in spec.description
    assert spec.input_schema == tool.input_schema
    assert manager.calls[-1]["size_guideline"] == "small"
    assert output["guideline"] == "small"


def test_permission_check_validates_before_asking(tmp_path: Path) -> None:
    tool = WorkflowTool(manager=_Manager())

    decision = tool.check_permissions({"script": SCRIPT}, _context(tmp_path))

    assert isinstance(decision, PermissionDecision)
    assert decision.behavior == "ask"
    assert decision.decision_reason == {"type": "workflow_launch", "identity": "demo"}
    with pytest.raises(ToolError, match="async def main"):
        tool.check_permissions({"script": "meta = {}"}, _context(tmp_path))


def test_prompt_preserves_captured_clause_inventory_as_python() -> None:
    description = workflow_description("large")

    for clause in (
        "ONLY call this tool when the user has explicitly opted",
        "the right move is often **hybrid**",
        "**Ultracode.**",
        "DEFAULT TO `pipeline()`",
        "This is a BARRIER",
        "Quality patterns",
        "The token target is a HARD ceiling",
        "longest unchanged chained-v2 prefix",
        "Use `isolation=\"worktree\"` ONLY",
        "validated structured value",
        "Agent model and reasoning effort inherit",
        "A plan above 25 Agents or an estimated 1.5 million tokens",
        "max(1, min(16, cpu_count - 2))",
        "capped at 1000",
        "at most 4096 items",
        "large — keep workflows under 50 agents",
    ):
        assert clause in description
    assert len(description) > 19_000
    assert not re.search(r"JavaScript|TypeScript|export const|=>|plain JS", description)

    example = description.split("<!-- executable-example:start -->", 1)[1]
    example = example.split("<!-- executable-example:end -->", 1)[0]
    source = example.split("```python", 1)[1].split("```", 1)[0].strip()
    assert compile_workflow(source).meta.name == "review-changes"
