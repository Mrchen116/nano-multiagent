"""kernel.cancel must also cancel the run's pending permission requests (#110).

A run parked on a permission decision holds a pending future in the broker.
Force-cancelling the carrier Task (M1/R1) releases the session lock, but the
broker's pending future would leak unless cancel also resolves it. M1/R2 wires
``kernel.cancel`` to call ``broker.cancel_all_pending(run_id=run_id)`` so the
parked permission request is denied and no pending entry survives.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from unittest.mock import MagicMock

from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message, TurnResult
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.permissions.broker import PermissionBroker
from agent.sdk.kernel import Kernel, _KernelComponents


class _ParkedOnPermissionRuntime:
    """Runtime that parks forever, standing in for a run awaiting permission."""

    async def run(
        self,
        session_id: str,
        parts,
        *,
        stream: bool = True,
        run_id: str | None = None,
        controller=None,
        workspace_root=None,
        origin=None,
    ):  # noqa: ANN001, ANN201
        del session_id, parts, stream, run_id, controller, workspace_root, origin
        await asyncio.Event().wait()
        return TurnResult(
            session_id="sess",
            turn_id="turn",
            messages=(Message(message_id="m", role="assistant", content="ok"),),
            completed=True,
            stop_reason="completed",
        )


def _make_kernel(registry: RunsRegistry, broker: PermissionBroker) -> Kernel:
    """Assemble a Kernel exercising only the cancel path.

    cancel touches solely runs_registry + permission_broker (both real here);
    the other components are never reached on this path, so they are placeholders.
    """
    components = _KernelComponents(
        runtime=MagicMock(),
        runs_registry=registry,
        event_hub=MagicMock(),
        permission_broker=broker,
        session_service=MagicMock(),
        hook_registry=MagicMock(),
        hook_runner=MagicMock(),
    )
    return Kernel(
        components=components,
        can_use_tool=None,
        repo_root=Path("."),
    )


def _run_on_loop(loop: asyncio.AbstractEventLoop, coro):  # noqa: ANN001, ANN202
    fut: concurrent.futures.Future = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=2.0)


def test_kernel_cancel_denies_pending_permission_for_run(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    registry = RunsRegistry(
        runtime=_ParkedOnPermissionRuntime(), session_manager=manager
    )
    broker = PermissionBroker(config=AutoModeConfig())
    kernel = _make_kernel(registry, broker)

    try:
        submitted = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "needs permission"}],
            workspace_root=tmp_path,
        )

        def _running() -> bool:
            rec = registry.get(submitted.run_id)
            return rec is not None and rec.status is RunStatus.RUNNING

        import time

        end = time.time() + 2.0
        while time.time() < end and not _running():
            time.sleep(0.01)
        assert _running()

        loop = registry.get_event_loop()
        assert loop is not None

        # Register a pending permission request for this run on the registry loop
        # (broker futures must be created/resolved on the same loop).
        async def _register():  # noqa: ANN202
            return broker.register_request("req_for_run", run_id=submitted.run_id)

        pending_future = _run_on_loop(loop, _register())
        assert broker.is_pending("req_for_run")

        # Cancel the run via the public kernel entry point.
        cancelled = kernel.cancel(submitted.run_id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"

        # The pending permission request is denied and no longer pending.
        async def _await_resolution():  # noqa: ANN202
            return await asyncio.wait_for(pending_future, timeout=1.0)

        response = _run_on_loop(loop, _await_resolution())
        assert response.decision == "deny"
        assert not broker.is_pending("req_for_run")
    finally:
        registry.shutdown()


def test_kernel_cancel_unknown_run_returns_none_and_no_broker_error(
    tmp_path: Path,
) -> None:
    """Cancelling an unknown run is safe: returns None, broker untouched."""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    registry = RunsRegistry(
        runtime=_ParkedOnPermissionRuntime(), session_manager=manager
    )
    broker = PermissionBroker(config=AutoModeConfig())
    kernel = _make_kernel(registry, broker)

    try:
        assert kernel.cancel("run_does_not_exist") is None
    finally:
        registry.shutdown()
