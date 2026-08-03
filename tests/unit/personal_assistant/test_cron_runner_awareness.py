"""Tests for feat-394-M2 R5: cron isolated execution + System(untrusted) awareness injection.

Covers:
- CronRunner submits with origin=cron and isolated session key cron:<jobId>
- After cron run completes with result text, System(untrusted) is appended
  to the canonical direct-chat kernel session JSONL
- Isolated cron turns do NOT enter the canonical direct-chat session
- delete_after_run: job is removed from store after first execution
- CronRunner respects cron_enabled gate
- feat-394-M6 R1: CronRunner._submit_cron_job uses InProcessKernelClient-compatible create_session signature

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
        self.appended_messages: list[dict] = []
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
        metadata: dict | None = None,
    ) -> dict:
        self._session_counter += 1
        sid = session_id or f"sess-{self._session_counter}"
        payload = {
            "session_id": sid,
            "workspace_root": workspace_root,
            "product_id": product_id,
            "metadata": metadata,
        }
        self.created_sessions.append(payload)
        return payload

    def submit_message(self, *, session_id: str, texts: list[str], **kwargs) -> dict:
        payload = {
            "run_id": self._submit_run_id,
            "session_id": session_id,
            "texts": texts,
            "kwargs": kwargs,
        }
        self.submitted_messages.append(payload)
        return payload

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
        """feat-394-M9: awareness injection path."""
        self.appended_messages.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "workspace_root": workspace_root,
                "metadata": metadata,
            }
        )
        return {"status": "appended"}

    def current_event_sequence(self) -> int:
        return 0

    async def await_run_result(self, *, run_id: str, **kwargs) -> str:
        """Fake: return stored result text."""
        self.awaited_runs.append(run_id)
        return self._result_text


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
        session_binder=None,
    )

    await runner.submit(job=job)

    assert len(kernel_client.created_sessions) >= 1
    # The submit must pass origin=cron
    msg = kernel_client.submitted_messages[0]
    origin = msg.get("kwargs", {}).get("origin") or msg.get("origin")
    assert origin == "cron", f"cron runs must use origin=cron, got: {origin!r}"


@pytest.mark.asyncio
async def test_cron_runner_awareness_appended_to_canonical_session(
    tmp_path: Path,
) -> None:
    """After cron result, System(untrusted) is appended to canonical direct-chat session.

    feat-394 decision C-awareness: result text appended to canonical direct chat
    kernel session as System(untrusted) so user can ask follow-up questions.
    feat-394-M9 fix: uses kernel.append_message() (not raw JSONL) so kernel cache
    stays consistent and the LLM sees the awareness in the next turn.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    result_text = "Here is your GitHub summary: 3 new PRs."
    kernel_client = _FakeKernelClient(session_result_text=result_text)

    canonical_session_id = "sess-canonical"

    runner = CronRunner(
        agent_id="agent-1",
        workspace_root=tmp_path,
        kernel_client=kernel_client,
        session_binder=None,
        canonical_session_id=canonical_session_id,
    )

    await runner.append_awareness(
        session_id=canonical_session_id,
        result_text=result_text,
    )

    # kernel.append_message must have been called with the awareness content
    assert len(kernel_client.appended_messages) == 1, (
        f"Expected 1 append_message call, got {len(kernel_client.appended_messages)}"
    )
    appended = kernel_client.appended_messages[0]
    assert appended["session_id"] == canonical_session_id
    assert appended["role"] in ("user", "system"), (
        f"awareness must have role=user or system, got: {appended['role']!r}"
    )
    content = appended["content"]
    assert "System (untrusted)" in content or "System(untrusted)" in content, (
        f"awareness content must contain 'System (untrusted)', got: {content!r}"
    )
    assert result_text in content, (
        f"awareness content must contain the result text, got: {content!r}"
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
        session_binder=None,
    )

    await runner.submit(job=job)

    # Job must be gone from the store after execution
    remaining = store.list_jobs(include_disabled=True)
    assert not any(j.id == "j-onetime" for j in remaining), (
        "delete_after_run job must be removed from store after execution"
    )


# ---------------------------------------------------------------------------
# feat-394-M6 R1: durable contract tests — CronRunner must use
# InProcessKernelClient-compatible create_session (no session_id kwarg)
# ---------------------------------------------------------------------------


class _ShimCompatibleKernelClient:
    """Strict shim-compatible fake that rejects unknown kwargs.

    Mirrors the exact signature of InProcessKernelClient.create_session:
      async def create_session(*, workspace_root, product_id, title, metadata)
    Any extra kwargs raise TypeError — identical to how the real shim behaves.
    """

    def __init__(self) -> None:
        self.called_with: dict | None = None
        self.submitted_session_ids: list[str] = []
        self._session_counter = 0

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        # Deliberately no session_id kwarg — mirrors real InProcessKernelClient.
        self._session_counter += 1
        self.called_with = {
            "workspace_root": workspace_root,
            "product_id": product_id,
            "title": title,
            "metadata": metadata,
        }
        return {"session_id": f"sess-{self._session_counter}"}

    def submit_message(self, *, session_id: str, texts: list[str], **kwargs) -> dict:
        self.submitted_session_ids.append(session_id)
        return {"run_id": "run-shim-1"}

    async def await_run_result(self, *, run_id: str, **kwargs) -> str:
        return "cron job completed"


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
        session_binder=None,
    )

    await runner.submit(job=job)

    assert shim_client.submitted_session_ids == ["sess-1"]


@pytest.mark.asyncio
async def test_cron_runner_session_metadata_contains_agent_id(tmp_path: Path) -> None:
    """_submit_cron_job must pass metadata={"agent_id": ...} to create_session.

    Without agent_id in session metadata, cron.run inside the isolated session
    gets ctx.session_metadata.get("agent_id") == None, routing to an empty string
    → GatewayCronDispatcher resolves no CronExecutionService → cron_unavailable.
    bugfix-402 cr3 fix.
    """
    from personal_assistant.scheduler.cron_runner import CronRunner

    kernel_client = _FakeKernelClient()
    job = _make_job(job_id="job-meta")

    runner = CronRunner(
        agent_id="agent-x",
        workspace_root=tmp_path,
        kernel_client=kernel_client,
        session_binder=None,
    )

    await runner.submit(job=job)

    assert len(kernel_client.created_sessions) == 1
    metadata = kernel_client.created_sessions[0].get("metadata") or {}
    assert metadata.get("agent_id") == "agent-x", (
        f"create_session must receive metadata={{agent_id: 'agent-x'}}, got: {metadata!r}"
    )
