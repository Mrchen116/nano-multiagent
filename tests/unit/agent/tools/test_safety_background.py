"""Tests for ToolSafety.start_command_background()."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig


def _make_safety(tmpdir: str) -> ToolSafety:
    config = ToolSafetyConfig()
    return ToolSafety(repo_root=Path(tmpdir), config=config)


def test_start_command_background_populates_output_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        safety = _make_safety(tmpdir)
        output_file = Path(tmpdir) / "out.log"
        handle = safety.start_command_background(
            command="echo hello",
            cwd=Path(tmpdir),
            tool_name="bash",
            output_file=output_file,
            timeout=10.0,
        )
        result = handle.wait()
        assert result.exit_code == 0
        assert "hello" in output_file.read_text(encoding="utf-8")


def test_start_command_background_stderr_prefix() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        safety = _make_safety(tmpdir)
        output_file = Path(tmpdir) / "out.log"
        handle = safety.start_command_background(
            command="echo error >&2",
            cwd=Path(tmpdir),
            tool_name="bash",
            output_file=output_file,
            timeout=10.0,
        )
        handle.wait()
        content = output_file.read_text(encoding="utf-8")
        assert "[stderr]" in content


def test_start_command_background_nonzero_exit() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        safety = _make_safety(tmpdir)
        output_file = Path(tmpdir) / "out.log"
        handle = safety.start_command_background(
            command="false",
            cwd=Path(tmpdir),
            tool_name="bash",
            output_file=output_file,
            timeout=10.0,
        )
        result = handle.wait()
        assert result.exit_code == 1


def test_start_command_background_terminate_tree() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        safety = _make_safety(tmpdir)
        output_file = Path(tmpdir) / "out.log"
        handle = safety.start_command_background(
            command="sleep 30",
            cwd=Path(tmpdir),
            tool_name="bash",
            output_file=output_file,
            timeout=10.0,
        )
        time.sleep(0.2)
        handle.terminate_tree()
        result = handle.wait()
        # Process was killed, exit code is non-zero
        assert result.exit_code != 0


def test_start_command_background_timeout() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        safety = _make_safety(tmpdir)
        output_file = Path(tmpdir) / "out.log"
        handle = safety.start_command_background(
            command="sleep 30",
            cwd=Path(tmpdir),
            tool_name="bash",
            output_file=output_file,
            timeout=0.2,
        )
        result = handle.wait()
        assert result.timed_out is True
