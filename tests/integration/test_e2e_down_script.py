"""Integration coverage for the worktree e2e shutdown script."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_gateway_grace_period_uses_point_two_second_ticks(tmp_path: Path) -> None:
    """A five-second grace period must poll 25 times before force-killing."""
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "e2e-down.sh"
    calls_file = tmp_path / "calls.log"
    (tmp_path / ".gateway.pid").write_text("424242\n", encoding="utf-8")

    command = f"""
kill() {{
  printf 'kill %s\\n' "$*" >> "$CALLS_FILE"
  return 0
}}
sleep() {{
  printf 'sleep %s\\n' "$*" >> "$CALLS_FILE"
  return 0
}}
export -f kill sleep
exec bash "{script}" --wt "{tmp_path}"
"""
    env = dict(os.environ, CALLS_FILE=str(calls_file))

    subprocess.run(
        ["bash", "-c", command],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    calls = calls_file.read_text(encoding="utf-8").splitlines()
    assert calls.count("sleep 0.2") == 25
    assert "kill -9 424242" in calls
