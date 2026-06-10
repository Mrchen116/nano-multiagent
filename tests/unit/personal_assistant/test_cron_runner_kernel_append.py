"""Tests for feat-394-M9: awareness injection via kernel.append_message.

CronRunner._append_awareness must use kernel.append_message (cache-first),
not write raw JSONL directly. Raw writes bypass kernel session cache →
awareness invisible to subsequent LLM turns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant.scheduler.cron_scheduler import CronJob


class _FakeKernelClient:
    """Minimal kernel client fake — base for append tracking."""

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
        self.awaited_runs.append(run_id)
        return self._result_text


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


@pytest.mark.asyncio
async def test_awareness_uses_kernel_append_message_not_raw_file(
    tmp_path: Path,
) -> None:
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
    assert (
        "System (untrusted)" in appended["content"]
        or "System(untrusted)" in appended["content"]
    )
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
