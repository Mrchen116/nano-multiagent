"""Cron job execution runner for the personal assistant gateway.

Handles per-job isolated session submission and awareness injection
(System(untrusted) append to canonical direct-chat kernel session via kernel API).

feat-394 decision 4: cron jobs run in isolated sessions (origin=cron, no context).
feat-394 decision C-awareness: result text appended to canonical session as
System(untrusted) so the user can ask follow-up questions about cron output.
feat-394-M9 fix: awareness injection uses kernel.append_message() (cache-aware)
instead of raw JSONL file append (which bypasses kernel session cache and makes
awareness invisible to subsequent LLM turns).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

_logger = logging.getLogger(__name__)


class _KernelClientLike(Protocol):
    """Kernel client interface needed by CronRunner.

    Mirrors _KernelClientShim.create_session exactly — no session_id parameter.
    The kernel assigns session IDs; callers read the id from the returned payload.
    feat-394-M6 R2 fix: removed session_id kwarg that caused TypeError in round-4.
    feat-394-M9 fix: append_message added for cache-aware awareness injection.
    """

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        workspace_root: str | None = None,
        origin: str | None = None,
    ) -> dict[str, object]: ...

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        workspace_root: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Append a message to a session without triggering a model run.

        Provided by _KernelClientShim (main.py:1690).  Updating the session via
        this method keeps the kernel's in-process session cache consistent; raw
        JSONL writes bypass the cache and make new entries invisible to the next
        LLM turn (feat-394-M9 root cause).
        """
        ...


class CronRunner:
    """Submit cron jobs as isolated kernel runs and inject awareness into canonical session.

    Args:
        agent_id: Agent whose jobs this runner executes.
        workspace_root: Agent workspace root (used for job store and session JSONL).
        kernel_client: Gateway kernel client shim.
        session_binding_store: Optional gateway session binding store for looking up
            the canonical direct-chat session.  When None, awareness injection is skipped.
        canonical_session_id: Optional pre-resolved canonical session ID.  Takes priority
            over session_binding_store lookup.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        workspace_root: Path,
        kernel_client: _KernelClientLike,
        session_binding_store: object | None,
        canonical_session_id: str | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._workspace_root = workspace_root
        self._kernel_client = kernel_client
        self._session_binding_store = session_binding_store
        self._canonical_session_id = canonical_session_id

    async def _submit_cron_job(self, *, job: CronJob) -> tuple[str, str] | None:
        """Submit one cron job as an isolated run and return (run_id, kernel_session_id).

        The session key is ``cron:<jobId>`` — an ephemeral isolated session that
        carries no conversation context (feat-394 decision 4).

        feat-394-M7 R6 fix: now returns (run_id, kernel_session_id) so the caller
        (_cron_tick_for_agent) can seed run_context_store and consume kernel.stream
        to deliver the result to the owner's direct conversation (decision C-awareness).

        Side effects:
            - Creates an isolated kernel session.
            - Submits job.instruction as the run prompt.
            - Removes the job from CronJobStore if delete_after_run is True.

        Returns:
            (run_id, kernel_session_id) on success, or None on failure.
        """
        # feat-394-M6 R2 fix: do not pass session_id to create_session — _KernelClientShim
        # has no such parameter.  Kernel generates the session id; we read it from the payload.
        # The title "cron:<jobId>" is purely cosmetic (visible in session list).
        try:
            session_payload = await self._kernel_client.create_session(
                workspace_root=str(self._workspace_root),
                product_id="personal_assistant",
                title=f"cron:{job.id}",
                metadata={"agent_id": self._agent_id},
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "cron: session creation failed: agent=%s job=%s", self._agent_id, job.id
            )
            return None

        session_id = str(session_payload.get("session_id", "")).strip()
        if not session_id:
            _logger.error(
                "cron: create_session returned no session_id: agent=%s job=%s payload=%r",
                self._agent_id,
                job.id,
                session_payload,
            )
            return None

        try:
            run_payload = self._kernel_client.submit_message(
                session_id=session_id,
                texts=[job.instruction],
                workspace_root=str(self._workspace_root),
                origin="cron",
                # bugfix-429: shim resolves this agent's model (default_model or
                # product default) so unattended cron runs honour per-agent model.
                agent_id=self._agent_id,
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "cron: submit failed: agent=%s job=%s", self._agent_id, job.id
            )
            return None

        run_id = str(run_payload.get("run_id", "")).strip()
        if not run_id:
            return None

        # delete_after_run: remove the job from store now (before awaiting delivery).
        # feat-394 decision 4: one-shot 'at' jobs are cleaned up after submission.
        if job.delete_after_run:
            job_store = CronJobStore(workspace_root=self._workspace_root)
            job_store.remove(job.id)

        return run_id, session_id

    async def _append_awareness(
        self,
        *,
        session_id: str,
        result_text: str,
        workspace_root: Path,
    ) -> None:
        """Append a System(untrusted) entry to the canonical direct-chat session.

        Provenance: openclaw delivery-dispatch.ts:335 queueCronAwarenessSystemEvent —
        takes final result text → enqueueSystemEvent(text, {sessionKey:main, trusted:false}).

        feat-394-M9 fix: delegates to kernel.append_message() instead of writing
        directly to the session JSONL file.  The kernel holds an in-process session
        cache (cache-first load); bypassing it via raw file append leaves the cache
        stale — the next LLM turn reads from cache and never sees the awareness entry,
        so the agent replies "hasn't run yet" to follow-up questions.
        append_message() updates both the persistent JSONL and the live cache atomically.

        The entry role is ``user`` with content ``System (untrusted): [ts] <result>``
        so the LLM sees it as background context without treating it as a trusted instruction.

        Args:
            session_id: Canonical direct-chat kernel session ID to append to.
            result_text: Final assistant response text from the cron isolated run.
            workspace_root: Agent workspace root passed through to kernel for session lookup.
        """
        if not session_id:
            _logger.debug(
                "cron: awareness skip — empty session_id: agent=%s", self._agent_id
            )
            return

        ts = datetime.now(tz=UTC).isoformat()
        awareness_content = f"System (untrusted): [{ts}] {result_text}"

        self._kernel_client.append_message(
            session_id=session_id,
            role="user",
            content=awareness_content,
            workspace_root=str(workspace_root),
            metadata={"is_cron_awareness": True},
        )

        _logger.debug(
            "cron: awareness appended via kernel: agent=%s session=%s",
            self._agent_id,
            session_id,
        )

    def _resolve_canonical_session_id(self) -> str | None:
        """Return the canonical direct-chat kernel session for this agent, or None.

        Checks the injected canonical_session_id first; falls back to
        session_binding_store.find_direct_by_agent when available.
        """
        if self._canonical_session_id:
            return self._canonical_session_id
        if self._session_binding_store is None:
            return None
        find_fn = getattr(self._session_binding_store, "find_direct_by_agent", None)
        if not callable(find_fn):
            return None
        binding = find_fn(channel_name="web_relay", agent_id=self._agent_id)
        if binding is None:
            return None
        return getattr(binding, "kernel_session_id", None)
