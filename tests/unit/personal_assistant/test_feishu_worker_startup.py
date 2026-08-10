"""Startup-boundary tests for the isolated Feishu listener worker."""

from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import threading

from personal_assistant.channels.feishu.worker import (
    FeishuWorkerProcessContext,
    FeishuWorkerRuntime,
    publish_event,
)


def _startup_probe_worker(context: FeishuWorkerProcessContext) -> None:
    publish_event(context, {"state": "running"})
    context.stop_event.wait(10)


def test_importing_worker_does_not_load_feishu_sdk() -> None:
    """Importing the spawn target stays independent of the heavy SDK package."""
    repo_root = Path(__file__).resolve().parents[3]
    probe_env = os.environ.copy()
    existing_pythonpath = probe_env.get("PYTHONPATH")
    probe_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(repo_root / "src"), existing_pythonpath) if path
    )
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import sys",
                    "import personal_assistant.channels.feishu.worker",
                    "blocked = [name for name in "
                    "('personal_assistant.channels.feishu.client', 'lark_oapi') "
                    "if name in sys.modules]",
                    "if blocked: raise SystemExit(', '.join(blocked))",
                )
            ),
        ],
        cwd=repo_root,
        env=probe_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr


def test_spawn_worker_initializes_with_production_ready_budget() -> None:
    """A real spawn worker becomes usable with the unwrapped runtime budget."""
    observed = threading.Event()
    runtime = FeishuWorkerRuntime(
        app_id="cli_startup",
        app_secret="secret",
        incarnation="inc-startup",
        on_event=lambda _event: observed.set(),
        on_status=lambda _status: None,
        worker_target=_startup_probe_worker,
        multiprocessing_context=multiprocessing.get_context("spawn"),
    )

    runtime.start()
    try:
        assert observed.wait(3)
        assert runtime.is_alive
    finally:
        report = runtime.stop(drain=False)

    assert report.joined
