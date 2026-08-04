"""Foreground interrupt behavior through a real in-process kernel."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from tests.integration.test_bash_engine import (
    _SUPPRESS_STREAM_STOP,
    _BashThenStopLLM,
    _build,
    _collect_stream,
)


@pytest.mark.asyncio
async def test_interrupt_reaps_foreground_subprocess_and_self_heals(
    tmp_path: Path,
) -> None:
    """Interrupt reaps the command tree and leaves the session reusable.

    Drive a real foreground bash command that spawns a uniquely-tagged sleep
    child, then call ``kernel.interrupt`` while it is in flight. The process
    disappears, its run is cancelled, and a subsequent turn completes.
    """
    # Unique marker encoded into the sleep's OWN argv (a fractional duration), so
    # ``pgrep -f`` finds exactly this test's child and not unrelated host processes.
    # A trailing ``# comment`` would NOT work: bash strips it, leaving argv ``sleep
    # 30`` with no marker.  ``sleep 30.<unique>`` keeps the marker in the process
    # arguments while still sleeping ~30s.
    unique = uuid.uuid4().int % 1_000_000
    marker = f"30.{unique:06d}"
    command = f"sleep {marker}"

    kernel = _build(tmp_path, _BashThenStopLLM(command=command, timeout=None))
    session_id: str | None = None
    events: list[dict] = []
    stop = asyncio.Event()
    collector: asyncio.Task | None = None
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        session_id = session.session_id
        collector = asyncio.create_task(
            _collect_stream(kernel, session_id, stop, events)
        )

        run = kernel.submit(
            session_id=session_id,
            parts=[{"type": "text", "text": "run a long command"}],
            workspace_root=tmp_path,
        )

        # Wait until the foreground sleep child is actually spawned.
        def _find_marker_pids() -> list[int]:
            out = subprocess.run(
                ["pgrep", "-f", marker],
                capture_output=True,
                text=True,
            )
            return [int(p) for p in out.stdout.split() if p.strip().isdigit()]

        deadline = time.monotonic() + 10.0
        child_pids: list[int] = []
        while time.monotonic() < deadline:
            child_pids = _find_marker_pids()
            if child_pids:
                break
            await asyncio.sleep(0.1)
        assert child_pids, "foreground sleep child never spawned"

        # Interrupt the active run — must reap the subprocess tree.
        interrupted = kernel.interrupt(session_id)
        assert interrupted == run.run_id

        # The marked sleep process(es) must die promptly.
        reap_deadline = time.monotonic() + 10.0
        while time.monotonic() < reap_deadline:
            if not _find_marker_pids():
                break
            await asyncio.sleep(0.1)
        survivors = _find_marker_pids()
        assert not survivors, (
            f"orphan subprocess(es) survived interrupt: {survivors} (marker {marker})"
        )

        record1 = kernel.get_run(run.run_id)
        assert record1 is not None and record1.status == "cancelled", (
            f"interrupted run did not reach cancelled: {record1!r}"
        )

        # A new turn in the same session must complete normally.
        run2 = kernel.submit(
            session_id=session_id,
            parts=[{"type": "text", "text": "are you back"}],
            workspace_root=tmp_path,
        )
        heal_deadline = time.monotonic() + 15.0
        while time.monotonic() < heal_deadline:
            record = kernel.get_run(run2.run_id)
            if record and record.status in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.05)
        record2 = kernel.get_run(run2.run_id)
        assert record2 is not None and record2.status == "completed", (
            f"session did not self-heal after interrupt: {record2!r}"
        )

        await asyncio.sleep(0.3)
        stop.set()
    finally:
        # Belt-and-suspenders: kill any surviving marked process so a failing test
        # never leaks a 30s sleep onto the host.
        with contextlib.suppress(Exception):
            leftover = subprocess.run(
                ["pgrep", "-f", marker], capture_output=True, text=True
            )
            for p in leftover.stdout.split():
                if p.strip().isdigit():
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(int(p), signal.SIGKILL)
        if collector is not None:
            stop.set()
            if session_id is not None:
                kernel.submit(
                    session_id=session_id,
                    parts=[{"type": "text", "text": "noop"}],
                    workspace_root=tmp_path,
                )
            with contextlib.suppress(*_SUPPRESS_STREAM_STOP):
                await asyncio.wait_for(collector, timeout=3.0)
            if not collector.done():
                collector.cancel()
                with contextlib.suppress(*_SUPPRESS_STREAM_STOP):
                    await collector
        kernel.close()
