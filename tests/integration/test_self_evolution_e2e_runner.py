"""Invocation regression for the deterministic self-evolution E2E runner."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _REPO_ROOT / "scripts" / "e2e-self-evolution.sh"


def test_runner_resolves_main_checkout_from_an_external_cwd(tmp_path: Path) -> None:
    """An absolute runner path is independent of the caller's working directory."""
    main_checkout = tmp_path / "main-checkout"
    scripts_dir = main_checkout / "scripts"
    scripts_dir.mkdir(parents=True)
    copied_runner = scripts_dir / _RUNNER.name
    shutil.copy2(_RUNNER, copied_runner)
    subprocess.run(
        ["git", "init", "-q", str(main_checkout)],
        check=True,
        capture_output=True,
        text=True,
    )
    external_cwd = tmp_path / "external-caller"
    external_cwd.mkdir()
    true_binary = shutil.which("true")
    assert true_binary is not None

    completed = subprocess.run(
        [str(copied_runner)],
        cwd=external_cwd,
        env={**os.environ, "PYTHON": true_binary},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "self-evolution E2E runtime cleaned:" in completed.stdout
    assert not list(main_checkout.glob(".e2e-self-evolution.*"))
