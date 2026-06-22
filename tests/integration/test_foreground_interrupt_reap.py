"""bugfix-417-M5 (#114) DONE hard gate: interrupt reaps the in-flight foreground
subprocess tree, recovers the orphaned tool_call as a user-attributed interrupt,
and the session self-heals — all end-to-end through a real ``build_kernel``.

Split out of ``test_bash_engine.py`` (which owns the M4 unified-engine
guards) to keep each file under the 400-line cap; the shared build_kernel + fake-LLM
harness is imported from that module.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
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
    """bugfix-417-M5 (#114) DONE hard gate, end-to-end through build_kernel.

    Drive a real foreground bash command that spawns a uniquely-tagged sleep
    child, then call ``kernel.interrupt`` while it is in-flight. Assert the
    observable M5 contracts:
      1. the subprocess tree is killed — no orphan sleep survives;
      2. the interrupted run reaches the cancelled terminal state;
      3. the same session self-heals — a subsequent turn reaches completed;
      4. the in-flight bash tool_call is recovered as a user-attributed interrupt.
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

        # 1. No orphan: the marked sleep process(es) die promptly.
        reap_deadline = time.monotonic() + 10.0
        while time.monotonic() < reap_deadline:
            if not _find_marker_pids():
                break
            await asyncio.sleep(0.1)
        survivors = _find_marker_pids()
        assert not survivors, (
            f"orphan subprocess(es) survived interrupt: {survivors} (marker {marker})"
        )

        # 3. Self-heal: a new turn in the same session reaches a terminal state.
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

        # 2. The interrupted run reaches the cancelled terminal state.
        record1 = kernel.get_run(run.run_id)
        assert record1 is not None and record1.status == "cancelled", (
            f"interrupted run did not reach cancelled: {record1!r}"
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

    # 4. The in-flight bash tool_call is recovered as 'interrupted' in the session
    # transcript (kernel-level evidence; the Gateway projects this into the IM
    # "已中断" badge via run_terminal_reconcile). Scan the session JSONL for the
    # tool_call_recovery entry the runtime's finally path wrote.
    jsonl_files = list(tmp_path.rglob("*.jsonl"))
    recoveries: list[dict] = []
    for jf in jsonl_files:
        for line in jf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(json.JSONDecodeError):
                entry = json.loads(line)
                if entry.get("type") == "tool_call_recovery":
                    recoveries.append(entry)
    assert recoveries, (
        "no tool_call_recovery entry written for the interrupted in-flight bash "
        f"tool_call; jsonl files scanned: {[str(f) for f in jsonl_files]}"
    )
    interrupted = [r for r in recoveries if r.get("reason") == "interrupted"]
    assert interrupted, (
        f"in-flight bash tool_call not recovered as 'interrupted': {recoveries!r}"
    )
    # kernel.interrupt is the user-initiated path, so the recovery content must be
    # the CC-identical user-attribution string (decoupled from the badge reason).
    assert any(
        r.get("content") == "[Request interrupted by user for tool use]"
        for r in interrupted
    ), f"user-initiated interrupt did not backfill CC content: {interrupted!r}"
