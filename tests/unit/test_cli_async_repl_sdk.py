"""CLI entry tests for the in-process ``agent.sdk`` integration."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from coding_cli import commands
from coding_cli.main import run_cli
from tests.unit._cli_kernel_stubs import _BaseKernelStub, _make_kernel_factory


class _CtrlCThenCancelledStream:
    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._step = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        self._step += 1
        if self._step == 1:
            raise KeyboardInterrupt
        if self._step == 2:
            return {
                "event": "run_status",
                "run_id": "run-1",
                "session_id": self._session_id,
                "status": "cancelled",
                "stop_reason": "cancelled",
            }
        raise StopAsyncIteration


class _CtrlCKernel(_BaseKernelStub):
    def stream(self, session_id: str, *, after_sequence: int = 0):
        return _CtrlCThenCancelledStream(session_id)


def test_run_cli_without_args_enters_repl_and_closes_kernel(tmp_path) -> None:
    stub = _BaseKernelStub()
    output = io.StringIO()

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: "/exit",
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert ("aclose", None) in stub.calls


def test_run_cli_ctrl_c_interrupts_active_run_and_keeps_repl_alive(tmp_path) -> None:
    stub = _CtrlCKernel()
    output = io.StringIO()
    inputs = iter(["/new", "run something long", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    assert any(call[0] == "interrupt" for call in stub.calls)
    assert "send failed" not in output.getvalue()


def test_llm_config_get_uses_production_sdk_path(monkeypatch) -> None:
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_MODEL", "kimiCoding:K2.6")
    monkeypatch.setenv("NANO_MULTIAGENT_LLM_BASE_URL", "http://127.0.0.1:4000")
    output = io.StringIO()

    exit_code = run_cli(["llm-config", "get"], stdout=output)

    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert set(payload) == {"provider", "model", "base_url", "timeout_seconds"}
    assert payload["provider"] == "anthropic"
    assert payload["model"] == "kimiCoding:K2.6"
    assert payload["base_url"] == "http://127.0.0.1:4000"
    assert isinstance(payload["timeout_seconds"], (int, float))
    assert payload["timeout_seconds"] > 0


def test_llm_config_set_is_not_a_public_command(tmp_path) -> None:
    with pytest.raises(SystemExit):
        run_cli(
            ["llm-config", "set", "--model", "x"],
            stdout=io.StringIO(),
            kernel_factory=_make_kernel_factory(_BaseKernelStub()),
            workspace_root=tmp_path,
        )


def test_repl_warns_when_workspace_bypasses_permissions(monkeypatch, tmp_path) -> None:
    global_home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    global_home.mkdir()
    (workspace / ".nanocode").mkdir(parents=True)
    (workspace / ".nanocode" / "config.yaml").write_text(
        "auto_mode:\n  enabled: true\n  dangerously_skip_permissions: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: global_home)
    monkeypatch.setattr("pathlib.Path.cwd", lambda: workspace)
    output = io.StringIO()

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(_BaseKernelStub()),
        input_fn=lambda _: "/exit",
        workspace_root=workspace,
    )

    assert exit_code == 0
    assert "WARNING: dangerously_skip_permissions is enabled" in output.getvalue()


class _WorkflowPermissionKernel(_BaseKernelStub):
    def __init__(self) -> None:
        super().__init__()
        self.can_use_tool = None
        self.permission_decision = None

    def stream(self, session_id: str, *, after_sequence: int = 0):
        async def _events():
            run_id = f"run-{self._run_id_counter}"
            if self._run_id_counter == 0:
                return
            assert self.can_use_tool is not None
            decision = await self.can_use_tool(
                "Workflow",
                {"script": "async def main(): return 'ok'"},
                SimpleNamespace(
                    question="Run Python Workflow 'review'? Phases: Review. Scale: medium.",
                    options=(
                        SimpleNamespace(
                            id="allow_once",
                            label="Allow once",
                            description="Allow this launch",
                        ),
                        SimpleNamespace(
                            id="allow_always",
                            label="Always allow",
                            description="Remember this Workflow",
                        ),
                        SimpleNamespace(
                            id="deny", label="Deny", description="Block this launch"
                        ),
                    ),
                ),
            )
            self.permission_decision = decision.decision
            yield {
                "event": "assistant_message",
                "run_id": run_id,
                "session_id": session_id,
                "content": "workflow launched",
            }
            yield {
                "event": "run_status",
                "run_id": run_id,
                "session_id": session_id,
                "status": "completed",
                "stop_reason": "stop",
            }

        return _events()


def test_interactive_repl_owns_workflow_permission_input_without_competing_reader(
    monkeypatch, tmp_path
) -> None:
    stub = _WorkflowPermissionKernel()
    output = io.StringIO()
    picker_calls = []
    lines = iter(["/new", "run one Workflow"])

    def _build_reader(**kwargs):
        on_idle = kwargs["on_idle"]

        def _read(_prompt, _history):
            try:
                return next(lines)
            except StopIteration:
                while stub.permission_decision is None:
                    on_idle()
                return "/exit"

        return _read

    def _build_cli_kernel(**kwargs):
        stub.can_use_tool = kwargs["can_use_tool"]
        return stub

    monkeypatch.setattr(commands.repl_input, "build_repl_input_reader", _build_reader)
    monkeypatch.setattr(
        commands.repl_input,
        "read_permission_choice",
        lambda **kwargs: picker_calls.append(kwargs) or "allow_always",
    )
    monkeypatch.setattr("coding_cli.product.build_cli_kernel", _build_cli_kernel)

    exit_code = run_cli([], stdout=output, workspace_root=tmp_path)

    assert exit_code == 0, output.getvalue()
    assert stub.permission_decision == "allow_always"
    assert len(picker_calls) == 1
    assert "Phases: Review" in picker_calls[0]["header"]
    assert [option.id for option in picker_calls[0]["options"]] == [
        "allow_once",
        "allow_always",
        "deny",
    ]
    assert "can_use_tool raised" not in output.getvalue()
