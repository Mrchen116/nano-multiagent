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


def _probe_import(module_name: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[3]
    probe_env = os.environ.copy()
    existing_pythonpath = probe_env.get("PYTHONPATH")
    probe_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(repo_root / "src"), existing_pythonpath) if path
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import sys",
                    f"import {module_name}",
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


def test_importing_worker_does_not_load_feishu_sdk() -> None:
    """Importing the spawn target stays independent of the heavy SDK package."""
    probe = _probe_import("personal_assistant.channels.feishu.worker")

    assert probe.returncode == 0, probe.stderr


def test_importing_gateway_entry_does_not_load_feishu_sdk() -> None:
    """Spawn re-execution of the Gateway entry stays outside provider imports."""
    probe = _probe_import("personal_assistant.main")

    assert probe.returncode == 0, probe.stderr


def test_spawn_worker_initializes_with_production_ready_budget() -> None:
    """A real spawn worker becomes usable with the unwrapped runtime budget."""
    observed = threading.Event()
    consumer_release = threading.Event()

    def observe_event(_event: object) -> None:
        consumer_release.wait()
        observed.set()

    runtime = FeishuWorkerRuntime(
        app_id="cli_startup",
        app_secret="secret",
        incarnation="inc-startup",
        on_event=observe_event,
        on_status=lambda _status: None,
        worker_target=_startup_probe_worker,
        multiprocessing_context=multiprocessing.get_context("spawn"),
    )

    runtime.start()
    try:
        assert runtime.is_alive
    finally:
        consumer_release.set()
        report = runtime.stop(drain=True)

    assert observed.is_set()
    assert report.joined
