#!/usr/bin/env python3
"""Run truthful self-evolution receipts through the real Coding CLI PTY."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import pty
import re
import secrets
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

import httpx
import yaml


_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "scripts/fixtures/openai_self_evolution_recording.py"
_UPDATE_PREFIX = "· background self-evolution review:"
_RAW_MARKERS = (
    "Nothing to save.",
    "Save failed:",
    "Saved:",
    "Traceback (most recent call last)",
)
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


@dataclass(frozen=True, slots=True)
class _Case:
    name: str
    scenario: str
    foreground_marker: str
    review_event: str
    seed_marker: str | None
    skill_creation: bool
    memory_curation: bool
    expected_update: str | None


_CASES = (
    _Case(
        "memory",
        "cli_memory",
        "CLI-FOREGROUND-MEMORY",
        "cli_memory_review_completed",
        "CLI-FOREGROUND-SEED",
        False,
        True,
        "· background self-evolution review: memory updated",
    ),
    _Case(
        "skills",
        "cli_skill",
        "CLI-FOREGROUND-SKILL",
        "cli_skill_review_completed",
        None,
        True,
        False,
        "· background self-evolution review: skills updated",
    ),
    _Case(
        "both",
        "cli_both",
        "CLI-FOREGROUND-BOTH",
        "cli_both_review_completed",
        "CLI-FOREGROUND-SEED",
        True,
        True,
        "· background self-evolution review: skills + memory updated",
    ),
    _Case(
        "no-save",
        "cli_no_save",
        "CLI-FOREGROUND-NO-SAVE",
        "cli_no_save_review_completed",
        "CLI-FOREGROUND-SEED",
        False,
        True,
        None,
    ),
    _Case(
        "read-only",
        "cli_read",
        "CLI-FOREGROUND-READ",
        "cli_read_review_completed",
        None,
        True,
        False,
        None,
    ),
    _Case(
        "failure",
        "cli_failure",
        "CLI-FOREGROUND-FAILURE",
        "cli_failure_review_completed",
        "CLI-FOREGROUND-SEED",
        False,
        True,
        None,
    ),
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_fixture(runtime: Path) -> tuple[subprocess.Popen[str], str]:
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, str(_FIXTURE), str(port)],
        env={
            **os.environ,
            "NANO_FIXTURE_RECORD_PATH": str(runtime / "llm-record.jsonl"),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"controlled LLM exited early: {stderr}")
        try:
            httpx.get(f"{url}/state", timeout=0.3, trust_env=False).raise_for_status()
            return process, url
        except httpx.HTTPError:
            time.sleep(0.05)
    _stop_process(process)
    raise RuntimeError("controlled LLM did not become ready")


def _stop_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _control(url: str, case: _Case, skill_name: str) -> None:
    response = httpx.post(
        f"{url}/control",
        json={
            "scenario": case.scenario,
            "reset": True,
            "response_tag": f"cli-{case.name}",
            "skill_name": skill_name,
        },
        timeout=5,
        trust_env=False,
    )
    response.raise_for_status()


def _wait_fixture_event(url: str, event: str) -> None:
    deadline = time.monotonic() + 30
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state = httpx.get(f"{url}/state", timeout=5, trust_env=False).json()
        if any(item.get("event") == event for item in state["events"]):
            return
        time.sleep(0.05)
    raise RuntimeError(
        f"timed out waiting for controlled event {event}: "
        f"{json.dumps(state, ensure_ascii=False, sort_keys=True)}"
    )


def _write_workspace_config(workspace: Path, case: _Case) -> None:
    config_path = workspace / ".nanocode/config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "auto_mode": {
                    "enabled": True,
                    "dangerously_skip_permissions": True,
                },
                "self_evolution": {
                    "enabled": True,
                    "skill_creation": case.skill_creation,
                    "memory_curation": case.memory_curation,
                    "skill_nudge_interval": 1,
                    "memory_nudge_interval": 1,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _cli_command(fixture_url: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "coding_cli.main",
        "--provider",
        "openai_compat",
        "--model",
        "controlled-e2e",
        "--llm-base-url",
        fixture_url,
        "--api-key",
        "controlled-e2e-key",
    ]


class _PTY:
    def __init__(self, workspace: Path, fixture_url: str, home: Path) -> None:
        master_fd, slave_fd = pty.openpty()
        self._master_fd = master_fd
        self._buffer = bytearray()
        self.process = subprocess.Popen(
            _cli_command(fixture_url),
            cwd=workspace,
            env={
                **os.environ,
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "PYTHONPATH": str(_ROOT / "src"),
                "PYTHONUNBUFFERED": "1",
            },
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

    def send_line(self, text: str) -> None:
        os.write(self._master_fd, f"{text}\n".encode())

    def wait_for(self, marker: str, *, timeout: float = 30) -> None:
        self.wait_for_count(marker, 1, timeout=timeout)

    def wait_for_count(self, marker: str, count: int, *, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._read_once(min(0.2, max(0.0, deadline - time.monotonic())))
            if self.text().count(marker) >= count:
                return
            if self.process.poll() is not None:
                break
        raise RuntimeError(f"Coding CLI PTY did not show {marker!r}\n{self.text()}")

    def settle(self, seconds: float = 0.5) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._read_once(min(0.1, deadline - time.monotonic()))

    def finish(self) -> str:
        self.send_line("/exit")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and self.process.poll() is None:
            self._read_once(0.1)
        if self.process.poll() is None:
            _stop_process(self.process)
            raise RuntimeError("Coding CLI did not exit after /exit")
        self.settle(0.2)
        if self.process.returncode != 0:
            raise RuntimeError(
                f"Coding CLI exited with status {self.process.returncode}\n{self.text()}"
            )
        os.close(self._master_fd)
        return self.text()

    def stop(self) -> None:
        if self.process.poll() is None:
            _stop_process(self.process)
        try:
            os.close(self._master_fd)
        except OSError:
            pass

    def text(self) -> str:
        return _clean_terminal(self._buffer.decode("utf-8", errors="replace"))

    def _read_once(self, timeout: float) -> None:
        ready, _, _ = select.select([self._master_fd], [], [], max(0.0, timeout))
        if not ready:
            return
        try:
            chunk = os.read(self._master_fd, 65536)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return
            raise
        if chunk:
            self._buffer.extend(chunk)


def _clean_terminal(value: str) -> str:
    value = _ANSI.sub("", value).replace("\r", "\n")
    lines = [line.rstrip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line.strip())


def _evidence_excerpt(transcript: str) -> str:
    prefixes = (
        "⚠ WARNING:",
        "Started new session ",
        "Active session:",
        "▸ Tool:",
        "✓ Tool:",
        "> CLI-",
        "State:",
        "Tool:",
        "Usage:",
        _UPDATE_PREFIX,
    )
    lines = [
        line
        for line in transcript.splitlines()
        if line.startswith(prefixes) or any(marker in line for marker in _RAW_MARKERS)
    ]
    return "\n".join(lines)


def _run_case(
    runtime: Path,
    fixture_url: str,
    case: _Case,
    nonce: str,
) -> tuple[str, dict[str, object]]:
    workspace = runtime / case.name
    workspace.mkdir()
    _write_workspace_config(workspace, case)
    skill_name = f"cli-review-{case.name}-{nonce}"
    _control(fixture_url, case, skill_name)
    terminal = _PTY(workspace, fixture_url, runtime / "home")
    try:
        terminal.wait_for("nano>")
        if case.seed_marker is not None:
            terminal.send_line(
                f"Seed controlled {case.name} self-evolution acceptance."
            )
            terminal.wait_for(case.seed_marker)
            terminal.wait_for_count("State: completed", 1)
        if case.name == "both":
            _wait_fixture_event(fixture_url, "cli_seed_review_completed")
        terminal.send_line(f"Run controlled {case.name} self-evolution acceptance.")
        terminal.wait_for(case.foreground_marker)
        terminal.wait_for_count(
            "State: completed", 2 if case.seed_marker is not None else 1
        )
        _wait_fixture_event(fixture_url, case.review_event)
        # The REPL consumer renders session-level background events at its next idle
        # input boundary. `/session` is a public, side-effect-free wake for that seam.
        terminal.send_line("/session")
        terminal.wait_for("Active session:")
        terminal.settle()
        if case.expected_update is not None:
            if case.expected_update not in terminal.text():
                terminal.send_line("")
                terminal.wait_for(case.expected_update)
        else:
            terminal.send_line("")
            terminal.settle()
        transcript = terminal.finish()
    finally:
        terminal.stop()

    assert case.foreground_marker in transcript
    assert not any(marker in transcript for marker in _RAW_MARKERS)
    update_lines = [line for line in transcript.splitlines() if _UPDATE_PREFIX in line]
    if case.expected_update is None:
        assert update_lines == []
    else:
        assert update_lines.count(case.expected_update) == 1
        assert len(update_lines) == 1

    memory_path = workspace / ".nanocode/memory/USER.md"
    skill_path = workspace / f".nanocode/skills/{skill_name}/SKILL.md"
    if case.name in {"memory", "both"}:
        assert memory_path.is_file()
    if case.name in {"skills", "both"}:
        assert skill_path.is_file()
    if case.expected_update is None:
        assert not memory_path.exists()
        assert not skill_path.exists()
    return transcript, {
        "case": case.name,
        "expected_update": case.expected_update,
        "foreground_visible": True,
        "memory_persisted": memory_path.is_file(),
        "raw_private_output_visible": False,
        "skill_name": skill_name if case.name in {"skills", "both"} else None,
        "skill_persisted": skill_path.is_file(),
        "update_count": len(update_lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wt", type=Path, default=_ROOT)
    parser.add_argument("--transcript", type=Path)
    parser.add_argument(
        "--case",
        action="append",
        choices=tuple(case.name for case in _CASES),
        help="Run only the named case; repeat to select more than one.",
    )
    args = parser.parse_args()
    worktree = args.wt.resolve()
    if not (worktree / "src/coding_cli/main.py").is_file():
        parser.error("--wt must point at a nano-multiagent worktree")

    runtime = Path(tempfile.mkdtemp(prefix=".e2e-cli-self-evolution.", dir=worktree))
    (runtime / "home").mkdir()
    fixture: subprocess.Popen[str] | None = None
    evidence: dict[str, object] = {"cases": []}
    rendered: list[str] = []
    nonce = secrets.token_hex(5)
    selected_cases = tuple(
        case for case in _CASES if not args.case or case.name in args.case
    )
    try:
        fixture, fixture_url = _start_fixture(runtime)
        for case in selected_cases:
            transcript, case_evidence = _run_case(runtime, fixture_url, case, nonce)
            rendered.extend(
                (
                    f"=== {case.name} ===",
                    _evidence_excerpt(transcript),
                    "assertions: "
                    + json.dumps(case_evidence, ensure_ascii=False, sort_keys=True),
                    "",
                )
            )
            evidence["cases"].append(case_evidence)
        evidence["nonce"] = nonce
    finally:
        if fixture is not None:
            _stop_process(fixture)
        shutil.rmtree(runtime, ignore_errors=True)
    if runtime.exists():
        raise RuntimeError(f"Coding CLI acceptance runtime was not cleaned: {runtime}")
    evidence["runtime_cleaned"] = True
    transcript_text = "\n".join(rendered).rstrip() + "\n"
    if args.transcript is not None:
        transcript_path = args.transcript.resolve()
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(transcript_text, encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
