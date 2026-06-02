"""Tests for feat-394-M2 R5: cron isolated execution + System(untrusted) awareness injection.

Covers:
- CronRunner submits with origin=cron and isolated session key cron:<jobId>
- After cron run completes with result text, System(untrusted) is appended
  to the canonical direct-chat kernel session JSONL
- Isolated cron turns do NOT enter the canonical direct-chat session
- delete_after_run: job is removed from store after first execution
- CronRunner respects cron_enabled gate

feat-394 decision C-awareness + decision 4.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from personal_assistant.scheduler.cron_scheduler import (
    CronJob,
    CronJobStore,
    CronSchedulerStateStore,
)


# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------


def _make_job(
    job_id: str = "job-1",
    instruction: str = "Do something",
    delete_after_run: bool = False,
) -> CronJob:
    return CronJob(
        id=job_id,
        name="test",
        schedule={"kind": "every", "everyMs": 60_000},
        instruction=instruction,
        enabled=True,
        delete_after_run=delete_after_run,
    )


class _FakeKernelClient:
    """Minimal kernel client fake for cron runner tests."""

    def __init__(
        self,
        *,
        session_result_text: str = "Cron job completed: all done.",
        submit_run_id: str = "run-1",
    ) -> None:
        self.created_sessions: list[dict] = []
        self.submitted_messages: list[dict] = []
        self.awaited_runs: list[str] = []
        self._session_counter = 0
        self._result_text = session_result_text
        self._submit_run_id = submit_run_id

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        self._session_counter += 1
        sid = session_id or f"sess-{self._session_counter}"
        payload = {
            "session_id": sid,
            "workspace_root": workspace_root,
            "product_id": product_id,
        }
        self.created_sessions.append(payload)
        return payload

    def submit_message(
        self, *, session_id: str, texts: list[str], **kwargs
    ) -> dict:
        payload = {
            "run_id": self._submit_run_id,
            "session_id": session_id,
            "texts": texts,
            "kwargs": kwargs,
        }
        self.submitted_messages.append(payload)
        return payload

    def current_event_sequence(self) -> int:
        return 0

    async def await_run_result(self, *, run_id: str, **kwargs) -> str:
        """Fake: return stored result text."""
        self.awaited_runs.append(run_id)
        return self._result_text


# ---------------------------------------------------------------------------
# CronRunner existence and interface
# ---------------------------------------------------------------------------


def test_cron_runner_class_exists() -> None:
    """CronRunner must be importable from personal_assistant.scheduler.cron_runner."""
    from personal_assistant.scheduler.cron_runner import CronRunner
    assert CronRunner is not None


@pytest.mark.asyncio
async def test_cron_runner_submit_uses_isolated_session(tmp_path: Path) -> None:
    """CronRunner must submit with origin=cron in session metadata.

    feat-394 decision 4: cron jobs run in isolated sessions (no conversation context).
    The session_id must be 'cron:<jobId>' so it's distinct from any conversation session.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    kernel_client = _FakeKernelClient()
    store = CronJobStore(workspace_root=tmp_path)
    job = _make_job(job_id="jx")
    store.add(job)

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=kernel_client,
        session_binding_store=None,
    )

    await runner._submit_cron_job(job=job)

    assert len(kernel_client.created_sessions) >= 1
    # The submit must pass origin=cron
    msg = kernel_client.submitted_messages[0]
    origin = msg.get("kwargs", {}).get("origin") or msg.get("origin")
    assert origin == "cron", f"cron runs must use origin=cron, got: {origin!r}"


@pytest.mark.asyncio
async def test_cron_runner_awareness_appended_to_canonical_session(tmp_path: Path) -> None:
    """After cron result, System(untrusted) is appended to canonical direct-chat JSONL.

    feat-394 decision C-awareness: result text appended to canonical direct chat
    kernel session JSONL as System(untrusted) so user can ask follow-up questions.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    result_text = "Here is your GitHub summary: 3 new PRs."
    kernel_client = _FakeKernelClient(session_result_text=result_text)

    # Set up canonical direct-chat session JSONL
    workspace_config_dir = tmp_path / ".nanoassistant"
    sessions_dir = workspace_config_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    canonical_session_id = "sess-canonical"
    canonical_jsonl = sessions_dir / f"{canonical_session_id}.jsonl"
    # Write a header entry so file exists
    canonical_jsonl.write_text(
        json.dumps({"type": "config", "session_id": canonical_session_id}) + "\n",
        encoding="utf-8",
    )

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=kernel_client,
        session_binding_store=None,
        canonical_session_id=canonical_session_id,
    )

    await runner._append_awareness(
        session_id=canonical_session_id,
        result_text=result_text,
        workspace_root=tmp_path,
    )

    # Canonical JSONL must contain the System(untrusted) entry
    lines = canonical_jsonl.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2, f"Expected 2 lines (config + awareness), got {len(lines)}"
    awareness_entry = json.loads(lines[1])
    assert awareness_entry.get("role") in ("user", "system"), (
        f"awareness entry must have role=user or system, got: {awareness_entry.get('role')!r}"
    )
    content = awareness_entry.get("content", "")
    assert "System (untrusted)" in content or "System(untrusted)" in content, (
        f"awareness content must contain 'System (untrusted)', got: {content!r}"
    )
    assert result_text in content, (
        f"awareness content must contain the result text, got: {content!r}"
    )


@pytest.mark.asyncio
async def test_cron_runner_isolated_turns_not_in_canonical(tmp_path: Path) -> None:
    """Isolated cron session turns must NOT be appended to canonical direct-chat session.

    feat-394 decision C-awareness: only the final result text (as System(untrusted))
    enters the canonical session; the isolated cron run's intermediate turns are discarded.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    # Canonical JSONL starts empty (just a header)
    workspace_config_dir = tmp_path / ".nanoassistant"
    sessions_dir = workspace_config_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    canonical_session_id = "sess-canonical"
    canonical_jsonl = sessions_dir / f"{canonical_session_id}.jsonl"
    canonical_jsonl.write_text(
        json.dumps({"type": "config", "session_id": canonical_session_id}) + "\n",
        encoding="utf-8",
    )

    # Isolated cron session gets its own JSONL (simulating cron run turns)
    cron_session_id = "cron:j1"
    cron_jsonl = sessions_dir / f"{cron_session_id}.jsonl"
    cron_jsonl.write_text(
        json.dumps({"type": "config", "session_id": cron_session_id}) + "\n"
        + json.dumps({"type": "turn", "role": "user", "content": "cron instruction"}) + "\n"
        + json.dumps({"type": "turn", "role": "assistant", "content": "cron thinking..."}) + "\n",
        encoding="utf-8",
    )

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=_FakeKernelClient(),
        session_binding_store=None,
        canonical_session_id=canonical_session_id,
    )

    await runner._append_awareness(
        session_id=canonical_session_id,
        result_text="Final answer",
        workspace_root=tmp_path,
    )

    # Canonical JSONL must only have header + awareness (NOT the cron session turns)
    canonical_lines = canonical_jsonl.read_text("utf-8").strip().split("\n")
    assert len(canonical_lines) == 2, (
        f"Canonical JSONL must have exactly 2 lines (header + awareness), "
        f"got {len(canonical_lines)}: {canonical_lines}"
    )
    for line in canonical_lines:
        entry = json.loads(line)
        # No cron intermediate turns (the cron instruction or thinking) must appear
        if entry.get("type") == "turn":
            content = entry.get("content", "")
            assert "cron thinking..." not in content, (
                "Isolated cron intermediate turns must NOT appear in canonical session"
            )


@pytest.mark.asyncio
async def test_cron_runner_delete_after_run(tmp_path: Path) -> None:
    """Jobs with delete_after_run=True must be removed after first execution.

    feat-394 decision 4: one-shot 'at' jobs with deleteAfterRun are cleaned up.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    store = CronJobStore(workspace_root=tmp_path)
    job = _make_job(job_id="j-onetime", delete_after_run=True)
    store.add(job)

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=_FakeKernelClient(),
        session_binding_store=None,
    )

    await runner._submit_cron_job(job=job)

    # Job must be gone from the store after execution
    remaining = store.list_jobs(include_disabled=True)
    assert not any(j.id == "j-onetime" for j in remaining), (
        "delete_after_run job must be removed from store after execution"
    )
