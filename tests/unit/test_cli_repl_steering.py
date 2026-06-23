"""CLI REPL 运行中 steer 行为测试 (bugfix-426-M2)。

覆盖决策4：run 执行期间用户输入不阻塞、不排队到 run 结束，而是经
``kernel.submit(steer=True)`` 注入当前活跃 run 的下一轮；空闲输入仍开新 run；
abort 侧（SIGINT）维持既有 interrupt 语义。

时序由 ``_SteerableKernelStub`` 控制：run 的 stream 在产出终态前 await 一个
release event，测试得以在 run "仍在执行" 的窗口内喂入第二行输入，断言它走 steer
路径而非排队等待。
"""

from __future__ import annotations

import asyncio
import io
from typing import Any, AsyncIterator

from coding_cli.main import run_cli

from tests.unit._cli_kernel_stubs import _BaseKernelStub, _make_kernel_factory


class _SteerableKernelStub(_BaseKernelStub):
    """Kernel stub whose active run blocks until a steer (or release) arrives.

    The first submit starts run ``run-1`` whose stream emits one assistant line
    then parks on ``self._release`` — modelling a run still executing tool
    rounds.  When ``submit(steer=True)`` is called the stub records it and
    releases the parked run so it finishes; this lets a test assert that mid-run
    input was routed through steer instead of queued behind the active run.
    """

    def __init__(self, *, session_id: str = "sess_cli") -> None:
        super().__init__(session_id=session_id)
        self.submit_calls: list[dict[str, Any]] = []
        self._release: asyncio.Event | None = None

    def _ensure_release(self) -> asyncio.Event:
        if self._release is None:
            self._release = asyncio.Event()
        return self._release

    def submit(self, *, session_id, parts, **kwargs):  # type: ignore[override]
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        steer = bool(kwargs.get("steer", False))
        self.submit_calls.append({"text": text, "steer": steer})
        self._run_id_counter += 1
        if steer:
            # Steered message rides the already-active run; release it so the
            # parked stream can finish and the turn completes.
            release = self._ensure_release()
            release.set()
            return type("R", (), {"run_id": "run-1", "injected": True})()
        return type("R", (), {"run_id": f"run-{self._run_id_counter}", "injected": False})()

    def stream(self, session_id: str, *, after_sequence: int = 0) -> AsyncIterator[dict[str, Any]]:
        release = self._ensure_release()
        run_id = "run-1"

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            yield {
                "event": "assistant_message",
                "run_id": run_id,
                "session_id": session_id,
                "content": "working...",
            }
            # Park here until a mid-run steer releases us — models an in-flight run.
            # A bounded wait keeps a *blocking* (pre-fix) REPL from hanging the
            # test: when no steer ever arrives the run simply finishes and the
            # later assertion (mid-run input must steer) fails cleanly.
            try:
                await asyncio.wait_for(release.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            yield {
                "event": "run_status",
                "run_id": run_id,
                "session_id": session_id,
                "status": "completed",
                "stop_reason": "stop",
            }

        return _gen()


class _IdleNewRunKernelStub(_BaseKernelStub):
    """Stub that completes each run immediately, recording steer flag per submit."""

    def __init__(self, *, session_id: str = "sess_cli") -> None:
        super().__init__(session_id=session_id)
        self.submit_calls: list[dict[str, Any]] = []

    def submit(self, *, session_id, parts, **kwargs):  # type: ignore[override]
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
        self.submit_calls.append({"text": text, "steer": bool(kwargs.get("steer", False))})
        self._run_id_counter += 1
        run_id = f"run-{self._run_id_counter}"
        self._last_run_id = run_id
        return type("R", (), {"run_id": run_id, "injected": False})()

    def stream(self, session_id: str, *, after_sequence: int = 0) -> AsyncIterator[dict[str, Any]]:
        run_id = getattr(self, "_last_run_id", f"run-{self._run_id_counter}")

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            yield {
                "event": "assistant_message",
                "run_id": run_id,
                "session_id": session_id,
                "content": "done",
            }
            yield {
                "event": "run_status",
                "run_id": run_id,
                "session_id": session_id,
                "status": "completed",
                "stop_reason": "stop",
            }

        return _gen()


def test_mid_run_input_routes_through_steer_not_a_new_run(tmp_path) -> None:
    stub = _SteerableKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "start long task", "use web_search instead", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    # First message starts a new run (steer=False); the mid-run message is
    # steered into the active run (steer=True) rather than queued as a new run.
    assert stub.submit_calls[0] == {"text": "start long task", "steer": False}
    assert stub.submit_calls[1] == {"text": "use web_search instead", "steer": True}


def test_idle_input_opens_new_run_without_steer(tmp_path) -> None:
    stub = _IdleNewRunKernelStub()
    output = io.StringIO()
    inputs = iter(["/new", "first", "second", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    # Each run completes before the next input is read (idle), so both are
    # plain new runs — steer must NOT be set when there is no active run.
    assert stub.submit_calls == [
        {"text": "first", "steer": False},
        {"text": "second", "steer": False},
    ]


def test_mid_run_multiple_messages_each_steered_in_order(tmp_path) -> None:
    """Two messages sent while a run is active are each routed through steer, in order."""

    class _TwoSteerStub(_SteerableKernelStub):
        def __init__(self) -> None:
            super().__init__()
            self._steer_count = 0

        def submit(self, *, session_id, parts, **kwargs):  # type: ignore[override]
            text = ""
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
            steer = bool(kwargs.get("steer", False))
            self.submit_calls.append({"text": text, "steer": steer})
            self._run_id_counter += 1
            if steer:
                self._steer_count += 1
                # Release only after the second steered message so both ride the
                # same active run.
                if self._steer_count >= 2:
                    self._ensure_release().set()
                return type("R", (), {"run_id": "run-1", "injected": True})()
            return type("R", (), {"run_id": "run-1", "injected": False})()

    stub = _TwoSteerStub()
    output = io.StringIO()
    inputs = iter(["/new", "go", "first steer", "second steer", "/exit"])

    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(stub),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    assert exit_code == 0
    steered = [c["text"] for c in stub.submit_calls if c["steer"]]
    assert steered == ["first steer", "second steer"]
