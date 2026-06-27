"""RuntimeRunner.start must thread the parent run model into runtime.run.

bugfix-443 decision 3: the background subagent dispatch goes through
RuntimeRunner.start; without forwarding ``model`` the subagent's run would
register no per-run model and fall back to the build-time global default.
"""

from __future__ import annotations

import threading

from agent.platform.background_tasks.runtime_runner import RuntimeRunner


class _FakeTurnResult:
    usage = None
    tool_calls = ()
    messages = ()


class _RecordingRuntime:
    """Captures the kwargs runtime.run is called with."""

    def __init__(self, done: threading.Event) -> None:
        self.captured: dict = {}
        self._done = done

    async def run(self, session_id, parts, **kwargs):  # noqa: ANN001
        self.captured["session_id"] = session_id
        self.captured["model"] = kwargs.get("model")
        self._done.set()
        return _FakeTurnResult()


def _noop(**kwargs):  # noqa: ANN003
    return None


def test_start_forwards_model_to_runtime_run() -> None:
    done = threading.Event()
    runtime = _RecordingRuntime(done)
    runner = RuntimeRunner(runtime=runtime)  # no event_loop → daemon-thread fallback

    runner.start(
        agent_session_id="sub-1",
        parent_session_id="parent-1",
        prompt="go",
        on_complete=_noop,
        on_fail=_noop,
        on_kill=_noop,
        model="mimo-model",
    )

    assert done.wait(timeout=5.0), "runtime.run was never invoked"
    assert runtime.captured["session_id"] == "sub-1"
    assert runtime.captured["model"] == "mimo-model"
