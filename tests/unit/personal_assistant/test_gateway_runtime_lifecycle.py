"""GatewayRuntime startup, heartbeat gate, and shutdown cleanup resilience."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from personal_assistant.channels.web_relay_adapter import WebRelayAdapter
from personal_assistant.main import GatewayRuntime
from personal_assistant.ws.im_connection import IMConnectionConfig, IMConnectionManager

from ._gateway_runtime_test_utils import make_config, run_in_thread
from ._im_connection_helpers import _minimal_reporter


class _GateFakeIM:
    """Resolve the first-connect signal only after a delay.

    Heartbeat startup must wait for that resolution before its first tick.
    """

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._closed = asyncio.Event()
        self._resolved = asyncio.Event()
        self.connected = False

    async def connect_once(self) -> None:
        self._events.append("im.connect.eager")

    async def run_forever(self) -> None:
        await asyncio.sleep(0.05)
        self.connected = True
        self._events.append("im.connect.resolved")
        self._resolved.set()
        await self._closed.wait()

    async def wait_first_connect_attempt(self, *, timeout: float = 10.0) -> None:
        try:
            await asyncio.wait_for(self._resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return

    async def close(self) -> None:
        self._events.append("im.close")
        self._closed.set()


class _RecordingHeartbeatRunner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def start(self) -> None:
        self._events.append("heartbeat.start")

    async def close(self) -> None:
        self._events.append("heartbeat.close")


class _SkillReviewKernel:
    def __init__(self) -> None:
        self.maintenance_roots: list[Path] = []
        self.drained = False
        self.created_sessions: list[dict[str, object]] = []
        self.submitted_parts: list[dict[str, object]] = []
        self.scheduler = None
        self.drain_roots: list[Path | None] = []

    def run_skill_maintenance(self, *, workspace_root: Path) -> None:
        self.maintenance_roots.append(workspace_root)

    def set_skill_batch_review_drain_scheduler(self, scheduler):
        self.scheduler = scheduler

    async def run_queued_skill_batch_reviews(
        self, *, run_background_analysis, skill_root=None
    ):
        self.drained = True
        self.drain_roots.append(skill_root)
        await run_background_analysis(
            "review prompt",
            tool_allowlist=("skill_view", "skill_manage"),
            metadata={"background_task": "skill_batch_review"},
        )
        return (SimpleNamespace(completed=True),)

    async def create_session(self, **kwargs):
        self.created_sessions.append(dict(kwargs))
        return SimpleNamespace(session_id="skill-review-session")

    def submit(self, **kwargs):
        self.submitted_parts.append(dict(kwargs))
        return SimpleNamespace(run_id="run-1", status="queued")

    def get_run(self, run_id: str):
        return SimpleNamespace(run_id=run_id, status="completed")


def test_gateway_survives_unreachable_im_at_startup(tmp_path: Path) -> None:
    """Gateway reaches ready even when IM is unreachable at startup."""

    config = make_config(tmp_path)
    relay_adapter = WebRelayAdapter()
    relay_adapter.start(lambda _message: None)

    async def _connect(url: str, headers: dict[str, str]):  # noqa: ARG001
        raise RuntimeError("offline")

    manager = IMConnectionManager(
        config=IMConnectionConfig(
            url="http://im.local:9000",
            reconnect_initial_seconds=0.01,
            reconnect_max_seconds=0.02,
        ),
        reporter=_minimal_reporter(tmp_path),
        relay_adapter=relay_adapter,
        connect=_connect,
    )
    runtime = GatewayRuntime(config, im_connection_manager=manager)

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
        time.sleep(0.2)
        assert thread.is_alive() is True
        assert "error" not in outcome
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0, (
        f"gateway must survive unreachable IM at startup; outcome={outcome}"
    )


def test_heartbeat_start_waits_for_first_connect_attempt(tmp_path: Path) -> None:
    """Heartbeat startup waits until the first connect attempt has resolved."""

    events: list[str] = []
    manager = _GateFakeIM(events)
    heartbeat = _RecordingHeartbeatRunner(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        im_connection_manager=manager,
        heartbeat_runner=heartbeat,
    )

    thread, outcome = run_in_thread(runtime)
    try:
        deadline = time.time() + 3.0
        while "heartbeat.start" not in events and time.time() < deadline:
            time.sleep(0.01)
        assert "heartbeat.start" in events, f"heartbeat never started; events={events}"
        assert "im.connect.resolved" in events
        assert events.index("im.connect.resolved") < events.index("heartbeat.start"), (
            f"heartbeat must start only after first connect resolution; events={events}"
        )
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0


def test_shutdown_cleanup_continues_when_im_task_await_raises_base_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CancelledError from IM task cleanup must not skip later shutdown steps."""

    from personal_assistant import main as gateway_main

    events: list[str] = []

    async def _raise_cancelled(_task: asyncio.Task[None]) -> None:
        events.append("await.im_task")
        raise asyncio.CancelledError()

    monkeypatch.setattr(gateway_main, "_await_background_task", _raise_cancelled)

    manager = _GateFakeIM(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        im_connection_manager=manager,
        resource_closers=(lambda: events.append("resource.close"),),
    )

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0
    assert "error" not in outcome
    assert "resource.close" in events


def test_shutdown_cleanup_continues_when_im_close_raises(tmp_path: Path) -> None:
    """An IM close failure must not skip resource closers or successful exit."""

    events: list[str] = []

    class _CloseRaisesIM(_GateFakeIM):
        async def close(self) -> None:
            events.append("im.close")
            self._closed.set()
            raise RuntimeError("close failed")

    manager = _CloseRaisesIM(events)
    runtime = GatewayRuntime(
        make_config(tmp_path),
        im_connection_manager=manager,
        resource_closers=(lambda: events.append("resource.close"),),
    )

    thread, outcome = run_in_thread(runtime)
    try:
        assert runtime.wait_until_ready(timeout=2.0) is True
    finally:
        runtime.request_shutdown()
        thread.join(timeout=5.0)

    assert outcome.get("exit_code") == 0
    assert "error" not in outcome
    assert "im.close" in events
    assert "resource.close" in events


def test_gateway_skill_maintenance_drains_queued_skill_batch_reviews(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    kernel = _SkillReviewKernel()
    runtime = GatewayRuntime(config, kernel=kernel)

    asyncio.run(runtime._run_skill_maintenance())  # noqa: SLF001

    workspace_root = config.agents[0].workspace_root
    assert kernel.maintenance_roots == [workspace_root]
    assert kernel.drained is True
    assert kernel.drain_roots == [workspace_root / ".nanoassistant" / "skills"]
    assert kernel.created_sessions == [
        {
            "workspace_root": workspace_root,
            "enabled_tools": ["skill_view", "skill_manage"],
            "metadata": {"background_task": "skill_batch_review"},
        }
    ]
    assert kernel.submitted_parts == [
        {
            "session_id": "skill-review-session",
            "parts": [{"type": "text", "text": "review prompt"}],
            "workspace_root": workspace_root,
        }
    ]


def test_gateway_live_skill_batch_enqueue_schedules_drain(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    workspace_root = config.agents[0].workspace_root
    session_path = workspace_root / ".nanoassistant" / "sessions" / "sess-1.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text("{}", encoding="utf-8")
    kernel = _SkillReviewKernel()
    runtime = GatewayRuntime(config, kernel=kernel)

    async def _exercise() -> None:
        runtime._install_skill_batch_review_scheduler()  # noqa: SLF001
        assert callable(kernel.scheduler)
        kernel.scheduler(
            SimpleNamespace(
                skill_name="auto-skill",
                skill_root=Path("~/.nanoassistant/skills"),
                session_refs=({"session_id": "sess-1"},),
            )
        )
        for _ in range(5):
            await asyncio.sleep(0)
            if kernel.drained:
                break

    asyncio.run(_exercise())

    assert kernel.drained is True
    assert kernel.drain_roots == [workspace_root / ".nanoassistant" / "skills"]
    assert kernel.created_sessions == [
        {
            "workspace_root": workspace_root,
            "enabled_tools": ["skill_view", "skill_manage"],
            "metadata": {"background_task": "skill_batch_review"},
        }
    ]
