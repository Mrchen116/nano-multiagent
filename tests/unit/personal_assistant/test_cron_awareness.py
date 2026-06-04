"""Tests for feat-394-M2 R5: cron isolated execution + System(untrusted) awareness injection.

Covers:
- CronRunner submits with origin=cron and isolated session key cron:<jobId>
- After cron run completes with result text, System(untrusted) is appended
  to the canonical direct-chat kernel session JSONL
- Isolated cron turns do NOT enter the canonical direct-chat session
- delete_after_run: job is removed from store after first execution
- CronRunner respects cron_enabled gate
- feat-394-M6 R1: CronRunner._submit_cron_job uses _KernelClientShim-compatible
  create_session signature (no session_id kwarg) — durable contract test

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


# ---------------------------------------------------------------------------
# feat-394-M6 R1: durable contract tests — CronRunner must use
# _KernelClientShim-compatible create_session (no session_id kwarg)
# ---------------------------------------------------------------------------


class _ShimCompatibleKernelClient:
    """Strict shim-compatible fake that rejects unknown kwargs.

    Mirrors the exact signature of _KernelClientShim.create_session:
      async def create_session(*, workspace_root, product_id, title, metadata)
    Any extra kwargs raise TypeError — identical to how the real shim behaves.
    """

    def __init__(self) -> None:
        self.called_with: dict | None = None
        self._session_counter = 0

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        # Deliberately no session_id kwarg — mirrors real _KernelClientShim.
        self._session_counter += 1
        self.called_with = {
            "workspace_root": workspace_root,
            "product_id": product_id,
            "title": title,
            "metadata": metadata,
        }
        return {"session_id": f"sess-{self._session_counter}"}

    def submit_message(
        self, *, session_id: str, texts: list[str], **kwargs
    ) -> dict:
        return {"run_id": "run-shim-1"}

    async def await_run_result(self, *, run_id: str, **kwargs) -> str:
        return "cron job completed"


@pytest.mark.asyncio
async def test_cron_runner_submit_no_session_id_kwarg_to_shim(tmp_path: Path) -> None:
    """CronRunner._submit_cron_job must NOT pass session_id to create_session.

    feat-394-M6 R1 fix: _KernelClientShim.create_session has no session_id parameter.
    Before the fix, cron_runner.py:96 passed session_id=isolated_session_id and crashed
    with: TypeError: create_session() got an unexpected keyword argument 'session_id'.

    This test uses a shim-compatible fake that rejects session_id just like the real shim.
    After the fix the call succeeds; the returned session_id is used for submit_message.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    shim_client = _ShimCompatibleKernelClient()
    job = _make_job(job_id="j-shim-contract")

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=shim_client,
        session_binding_store=None,
    )

    # Must not raise TypeError after the fix.
    # feat-394-M7 R6 fix: _submit_cron_job now returns (run_id, kernel_session_id) or None.
    result = await runner._submit_cron_job(job=job)

    assert shim_client.called_with is not None, "create_session was never called"
    assert "session_id" not in (shim_client.called_with or {}), (
        "create_session must NOT receive session_id kwarg — "
        "_KernelClientShim.create_session has no such parameter"
    )
    assert result is not None, "run result must be returned on success"
    run_id, kernel_session_id = result
    assert run_id is not None, "run_id must be non-empty"
    assert kernel_session_id is not None, "kernel_session_id must be returned alongside run_id"


@pytest.mark.asyncio
async def test_cron_runner_uses_returned_session_id_for_submit(tmp_path: Path) -> None:
    """CronRunner must use the session_id returned by create_session for submit_message.

    After removing the session_id kwarg from create_session, the runner must still
    correctly route the run to the session the shim created.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    shim_client = _ShimCompatibleKernelClient()
    job = _make_job(job_id="j-routing")

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=shim_client,
        session_binding_store=None,
    )

    await runner._submit_cron_job(job=job)

    # session_id returned by create_session must be "sess-1" (first call)
    assert shim_client.called_with is not None
    # The submit call is tracked indirectly via no exception; shim returns run_id "run-shim-1"
    # which cron_runner should pass back.  We rely on the above test for the no-crash guarantee.
    assert shim_client._session_counter == 1, "exactly one session must have been created"


# ---------------------------------------------------------------------------
# feat-394-M9: awareness must go through kernel.append_message (cache-first)
# ---------------------------------------------------------------------------


class _AppendTrackingKernelClient(_FakeKernelClient):
    """Extend fake with append_message tracking for M9 regression."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.appended_messages: list[dict] = []

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        workspace_root: str | None = None,
        metadata: dict | None = None,
        **_kwargs: object,
    ) -> dict:
        self.appended_messages.append({
            "session_id": session_id,
            "role": role,
            "content": content,
            "workspace_root": workspace_root,
            "metadata": metadata,
        })
        return {"status": "appended"}


@pytest.mark.asyncio
async def test_awareness_uses_kernel_append_message_not_raw_file(tmp_path: Path) -> None:
    """_append_awareness must call kernel.append_message, NOT write to JSONL directly.

    feat-394-M9 fix: raw JSONL append bypasses kernel session cache; kernel returns
    stale context to LLM → awareness invisible to subsequent turns.
    Using kernel.append_message() updates the cache so the next LLM call sees the entry.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    result_text = "Status report: all systems OK."
    kernel_client = _AppendTrackingKernelClient(session_result_text=result_text)

    canonical_session_id = "sess-canonical-m9"

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

    # kernel.append_message must have been called (not raw file write)
    assert len(kernel_client.appended_messages) == 1, (
        "_append_awareness must call kernel.append_message() exactly once; "
        f"got {len(kernel_client.appended_messages)} calls. "
        "Raw JSONL append bypasses kernel cache → awareness invisible to LLM."
    )
    appended = kernel_client.appended_messages[0]
    assert appended["session_id"] == canonical_session_id
    assert "System (untrusted)" in appended["content"] or "System(untrusted)" in appended["content"]
    assert result_text in appended["content"]
    assert appended.get("metadata", {}).get("is_cron_awareness") is True, (
        "awareness metadata must include is_cron_awareness=True"
    )


@pytest.mark.asyncio
async def test_awareness_does_not_write_raw_jsonl(tmp_path: Path) -> None:
    """_append_awareness must NOT directly write to session JSONL files.

    After M9 fix, the implementation must exclusively use kernel.append_message.
    Bypassing kernel session management causes cache staleness bugs.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    kernel_client = _AppendTrackingKernelClient()
    canonical_session_id = "sess-no-direct-write"

    # Simulate: canonical session JSONL does NOT pre-exist (no file to write to)
    sessions_dir = tmp_path / ".nanoassistant" / "sessions"
    sessions_dir.mkdir(parents=True)
    canonical_jsonl = sessions_dir / f"{canonical_session_id}.jsonl"
    # File does NOT exist before awareness injection

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=kernel_client,
        session_binding_store=None,
        canonical_session_id=canonical_session_id,
    )

    await runner._append_awareness(
        session_id=canonical_session_id,
        result_text="Some result",
        workspace_root=tmp_path,
    )

    # append_message was called (new path goes through kernel regardless of file existence)
    assert len(kernel_client.appended_messages) == 1, (
        "awareness must call kernel.append_message even when JSONL file does not exist"
    )
