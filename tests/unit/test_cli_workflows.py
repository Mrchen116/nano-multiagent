from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.sdk import PromptSlots, SessionRuntimeConfig, WorkflowSaveScope
from coding_cli.commands import (
    _format_workflow_run,
    _handle_repl_command_async,
    _resolve_workflow_permission_event,
    _run_workflow_tty_controls,
    _send_message_async,
)
from coding_cli.events.background_runs import BackgroundRunEventProcessor
from coding_cli.product import (
    DEFAULT_ENABLED_TOOLS,
    load_cli_workflow_config,
    open_cli_session,
    save_cli_workflow_size_guideline,
)


class _RuntimeKernel:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.reconfigured: list[SessionRuntimeConfig] = []
        self.runtime = SessionRuntimeConfig(
            model="test:model",
            prompt=PromptSlots(),
            skills=None,
            enabled_tools=list(DEFAULT_ENABLED_TOOLS),
            features={},
            reasoning_effort="high",
            workflow_size_guideline="medium",
        )
        self.controls: list[dict[str, object]] = []

    def get_llm_config(self):
        return SimpleNamespace(model="test:model")

    async def create_session(self, **kwargs):
        self.created.append(dict(kwargs))
        return SimpleNamespace(session_id="sess-1")

    async def get_session_runtime(self, **_kwargs):
        return SimpleNamespace(runtime=self.runtime)

    async def reconfigure_session(self, *, runtime, **_kwargs):
        self.runtime = runtime
        self.reconfigured.append(runtime)
        return SimpleNamespace(state=SimpleNamespace(runtime=runtime))

    def list_workflow_runs(self, **_kwargs):
        return (
            SimpleNamespace(
                run_id="wf_1",
                name="review",
                status="running",
                current_phase=None,
                agents=(),
                result=None,
                error=None,
                usage=None,
                duration_ms=None,
                transcript_dir="/tmp/wf_1",
                script_path="/tmp/wf_1.py",
                warnings=(),
            ),
        )

    def list_session_tools(self, *_args, **_kwargs):
        return {"tools": [{"name": "Workflow"}]}

    def get_workflow_run(self, *, run_id, **_kwargs):
        return self.list_workflow_runs()[0] if run_id == "wf_1" else None

    def control_workflow(self, **kwargs):
        self.controls.append(dict(kwargs))
        return self.list_workflow_runs()[0]

    def save_workflow(self, **_kwargs):
        return SimpleNamespace(
            name="saved-review", path="/project/.nanocode/workflows/saved-review.py"
        )

    def list_named_workflows(self, **_kwargs):
        return (SimpleNamespace(name="deep-research", namespace=None),)


def test_cli_workflow_config_merges_global_workspace_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "repo" / "nested"
    (home / ".nanocode").mkdir(parents=True)
    (workspace / ".nanocode").mkdir(parents=True)
    (home / ".nanocode" / "config.yaml").write_text(
        "workflows:\n  disabled: true\n  size_guideline: small\n",
        encoding="utf-8",
    )
    (workspace / ".nanocode" / "config.yaml").write_text(
        "workflows:\n  disabled: false\n  size_guideline: large\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    config = load_cli_workflow_config(workspace)

    assert config.disabled is False
    assert config.size_guideline == "large"

    monkeypatch.setenv("NANOCODE_DISABLE_WORKFLOWS", "1")
    assert load_cli_workflow_config(workspace).disabled is True


def test_cli_workflow_config_uses_nearest_file_and_saves_back_to_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    workspace = repo / "packages" / "api" / "src"
    workspace.mkdir(parents=True)
    (repo / ".git").mkdir()
    (home / ".nanocode").mkdir(parents=True)
    (home / ".nanocode" / "config.yaml").write_text(
        "workflows:\n  size_guideline: small\n", encoding="utf-8"
    )
    repo_config = repo / ".nanocode" / "config.yaml"
    repo_config.parent.mkdir()
    repo_config.write_text(
        "workflows:\n  disabled: true\n  size_guideline: large\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    config = load_cli_workflow_config(workspace)
    save_cli_workflow_size_guideline(workspace, "medium")

    assert config.disabled is True
    assert config.size_guideline == "large"
    assert "size_guideline: medium" in repo_config.read_text(encoding="utf-8")
    assert not (workspace / ".nanocode" / "config.yaml").exists()


def test_cli_workflow_config_prefers_nearest_nested_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = repo / "packages" / "api"
    workspace.mkdir(parents=True)
    (repo / ".git").mkdir()
    repo_config = repo / ".nanocode" / "config.yaml"
    repo_config.parent.mkdir()
    repo_config.write_text("workflows:\n  size_guideline: small\n", encoding="utf-8")
    package_config = repo / "packages" / ".nanocode" / "config.yaml"
    package_config.parent.mkdir()
    package_config.write_text("workflows:\n  size_guideline: large\n", encoding="utf-8")

    config = load_cli_workflow_config(workspace)

    assert config.size_guideline == "large"


@pytest.mark.asyncio
async def test_open_cli_session_defaults_workflow_and_projects_guideline(
    tmp_path: Path,
) -> None:
    kernel = _RuntimeKernel()
    (tmp_path / ".nanocode").mkdir()
    (tmp_path / ".nanocode" / "config.yaml").write_text(
        "workflows:\n  size_guideline: large\n", encoding="utf-8"
    )

    await open_cli_session(kernel, workspace_root=tmp_path)

    runtime = kernel.created[-1]["runtime"]
    assert isinstance(runtime, SessionRuntimeConfig)
    assert "Workflow" in runtime.enabled_tools
    assert runtime.workflow_size_guideline == "large"


@pytest.mark.asyncio
async def test_open_cli_session_preserves_default_guideline_as_implicit(
    tmp_path: Path,
) -> None:
    kernel = _RuntimeKernel()

    await open_cli_session(kernel, workspace_root=tmp_path)

    runtime = kernel.created[-1]["runtime"]
    assert isinstance(runtime, SessionRuntimeConfig)
    assert runtime.workflow_size_guideline is None


@pytest.mark.asyncio
async def test_cli_workflow_commands_use_sdk_and_reconfigure_runtime(
    tmp_path: Path,
) -> None:
    kernel = _RuntimeKernel()
    output = io.StringIO()

    for line in (
        "/workflows",
        "/workflows wf_1 pause",
        "/workflows wf_1 save project saved-review",
        "/config workflowSizeGuideline small",
        "/effort ultracode",
    ):
        result = await _handle_repl_command_async(
            line=line,
            out=output,
            kernel=kernel,
            active_session_id="sess-1",
            history_by_session={},
            workspace_root=tmp_path,
        )
        assert result.handled is True

    assert kernel.controls[-1]["action"] == "pause"
    assert kernel.reconfigured[-2].workflow_size_guideline == "small"
    assert kernel.reconfigured[-1].workflow_ultracode is True
    assert kernel.reconfigured[-1].reasoning_effort == "xhigh"
    assert "wf_1 · review · running" in output.getvalue()
    assert "已保存 Workflow /saved-review" in output.getvalue()


def test_cli_workflow_detail_renders_phase_and_agent_observability() -> None:
    run = SimpleNamespace(
        run_id="wf_1",
        name="review",
        status="completed",
        current_phase="Verify",
        phases=(
            SimpleNamespace(
                title="Verify",
                detail="Verify findings",
                status="completed",
                usage={"total_tokens": 21},
                duration_ms=1500,
            ),
        ),
        agents=(
            SimpleNamespace(
                agent_call_id="wa_1",
                label="verify-api",
                phase="Verify",
                status="completed",
                prompt="Verify the API contract",
                result="contract is valid",
                error=None,
                usage={"total_tokens": 21},
                duration_ms=1200,
                session_id="child-1",
                transcript_path="/artifacts/child-1.jsonl",
                worktree_path="/retained/wa_1",
            ),
        ),
        result="done",
        error=None,
        usage={"total_tokens": 21},
        duration_ms=1600,
        transcript_dir="/diagnostics/wf_1",
        script_path="/diagnostics/wf_1.py",
        warnings=(),
    )

    rendered = _format_workflow_run(run)

    assert "[completed] Verify" in rendered
    assert "Verify findings" in rendered
    assert "任务: Verify the API contract" in rendered
    assert "结果: contract is valid" in rendered
    assert "total_tokens=21" in rendered
    assert "Session: child-1" in rendered
    assert "Transcript: /artifacts/child-1.jsonl" in rendered
    assert "保留 worktree: /retained/wa_1" in rendered


class _MessageKernel:
    def __init__(self) -> None:
        self.origin = None

    def submit(self, **kwargs):
        self.origin = kwargs.get("origin")
        return SimpleNamespace(run_id="run-1")

    def stream(self, _session_id):
        async def _events():
            yield {"event": "assistant_message", "run_id": "run-1", "content": "ok"}
            yield {"event": "run_status", "run_id": "run-1", "status": "completed"}

        return _events()


@pytest.mark.asyncio
async def test_interactive_message_uses_human_origin(tmp_path: Path) -> None:
    from agent.sdk import RunOrigin

    kernel = _MessageKernel()
    await _send_message_async(
        out=io.StringIO(),
        kernel=kernel,
        session_id="sess-1",
        text="ultracode review",
        workspace_root=tmp_path,
        background_processor=BackgroundRunEventProcessor(),
        bg_event_queue=__import__("asyncio").Queue(),
    )

    assert kernel.origin is RunOrigin.HUMAN


@pytest.mark.asyncio
async def test_workflow_child_permission_resolves_from_parent_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decisions: list[dict[str, str]] = []
    kernel = SimpleNamespace(
        submit_permission_decision=lambda **kwargs: decisions.append(kwargs) or True
    )
    monkeypatch.setattr(
        "coding_cli.commands.repl_input.read_permission_choice",
        lambda **_kwargs: "allow_once",
    )

    resolved = await _resolve_workflow_permission_event(
        kernel=kernel,
        event={
            "event": "permission_request",
            "workflow_run_id": "wf_1",
            "agent_call_id": "wa_1",
            "request_id": "perm_1",
            "tool_name": "bash",
            "question": "Allow command?",
            "options": [
                {"id": "allow_once", "label": "Allow once"},
                {"id": "deny", "label": "Deny"},
            ],
        },
        out=io.StringIO(),
    )

    assert resolved is True
    assert decisions == [{"request_id": "perm_1", "decision": "allow_once"}]


class _TTYWorkflowKernel:
    def __init__(self) -> None:
        self.status = "running"
        self.controls: list[dict[str, object]] = []
        self.saved: list[dict[str, object]] = []

    def _run(self):
        return SimpleNamespace(
            run_id="wf_1",
            name="review",
            status=self.status,
            current_phase="Review",
            phases=(SimpleNamespace(title="Review", status="running"),),
            agents=(
                SimpleNamespace(
                    agent_call_id="wa_1",
                    label="review-api",
                    phase="Review",
                    status="running",
                ),
            ),
            result=None,
            error=None,
            usage={"total_tokens": 1200},
            duration_ms=2500,
            transcript_dir="/tmp/wf_1",
            script_path="/tmp/wf_1.py",
            warnings=(),
        )

    def list_workflow_runs(self, **_kwargs):
        return (self._run(),)

    def control_workflow(self, **kwargs):
        self.controls.append(dict(kwargs))
        action = kwargs["action"]
        if action.value == "pause":
            self.status = "paused"
        elif action.value == "resume":
            self.status = "running"
        return self._run()

    def save_workflow(self, **kwargs):
        self.saved.append(dict(kwargs))
        return SimpleNamespace(
            name="review", path="/project/.nanocode/workflows/review.py"
        )


def test_tty_workflow_view_controls_selected_run_and_agent() -> None:
    kernel = _TTYWorkflowKernel()
    keys = iter(["p", "p", "s", "\x1b[B", "r", "x", "q"])
    output = io.StringIO()

    _run_workflow_tty_controls(
        out=output,
        kernel=kernel,
        session_id="sess-1",
        key_reader=lambda: next(keys),
    )

    assert [call["action"].value for call in kernel.controls] == [
        "pause",
        "resume",
        "restart_agent",
        "stop",
    ]
    assert [call.get("agent_call_id") for call in kernel.controls] == [
        None,
        None,
        "wa_1",
        "wa_1",
    ]
    assert kernel.saved == [
        {
            "session_id": "sess-1",
            "run_id": "wf_1",
            "scope": WorkflowSaveScope.PROJECT,
            "name": None,
        }
    ]
    rendered = output.getvalue()
    assert "Workflow controls" in rendered
    assert "review-api (wa_1)" in rendered
    assert "p pause/resume" in rendered
