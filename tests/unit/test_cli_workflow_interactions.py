from __future__ import annotations

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.sdk import RunOrigin, WorkflowSaveScope
from coding_cli.commands import (
    _run_workflow_tty_controls,
    _send_message_async,
)
from coding_cli.events.background_runs import BackgroundRunEventProcessor


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
    kernel = _MessageKernel()
    await _send_message_async(
        out=io.StringIO(),
        kernel=kernel,
        session_id="sess-1",
        text="ultracode review",
        workspace_root=tmp_path,
        background_processor=BackgroundRunEventProcessor(),
        bg_event_queue=asyncio.Queue(),
    )

    assert kernel.origin is RunOrigin.HUMAN


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
