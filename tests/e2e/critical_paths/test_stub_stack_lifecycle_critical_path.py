"""Critical-path harness lifecycle regressions for partial stack startup."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import yaml

from .test_agent_config_context_continuity_critical_path import (
    _E2E_CONFIG,
    _E2E_DOWN,
    _E2E_UP,
    _cleanup_stub_stack,
    _read_pid,
    _wait_process_gone,
)


def test_partial_stack_start_failure_reaps_im_and_stub(tmp_path: Path) -> None:
    """A setup error after IM startup leaves no fixture-owned process behind."""
    config = yaml.safe_load(_E2E_CONFIG.read_text(encoding="utf-8"))
    config.pop("llm", None)
    invalid_config = tmp_path / "missing-llm.yaml"
    invalid_config.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    runtime = tmp_path / "stack"
    runtime.mkdir()
    stub_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        up = subprocess.run(
            [
                "bash",
                str(_E2E_UP),
                "--wt",
                str(runtime),
                "--main-config",
                str(invalid_config),
            ],
            cwd=str(_E2E_UP.parents[1]),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
            },
        )
        assert up.returncode != 0
        im_pid = _read_pid(runtime / ".im.pid")
        assert im_pid is not None
        os.kill(im_pid, 0)

        down = _cleanup_stub_stack(runtime, stub_proc, preserve_logs=True)

        assert down.returncode == 0, down.stderr
        _wait_process_gone(im_pid)
        assert stub_proc.poll() is not None
        assert not (runtime / ".im.pid").exists()
    finally:
        subprocess.run(
            ["bash", str(_E2E_DOWN), "--wt", str(runtime)],
            capture_output=True,
            text=True,
        )
        if stub_proc.poll() is None:
            stub_proc.kill()
        stub_proc.wait(timeout=5)
