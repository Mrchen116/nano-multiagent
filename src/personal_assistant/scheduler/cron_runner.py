"""Cron job execution runner for the personal assistant gateway.

Handles per-job isolated session submission and awareness injection
(System(untrusted) append to canonical direct-chat kernel session JSONL).

feat-394 decision 4: cron jobs run in isolated sessions (origin=cron, no context).
feat-394 decision C-awareness: result text appended to canonical session as
System(untrusted) so the user can ask follow-up questions about cron output.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from personal_assistant.config.local_store import WORKSPACE_CONFIG_DIRNAME as _WORKSPACE_CONFIG_DIRNAME
from personal_assistant.scheduler.cron_scheduler import CronJob, CronJobStore

_logger = logging.getLogger(__name__)


class _KernelClientLike(Protocol):
    """Kernel client interface needed by CronRunner."""

    async def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, object]: ...

    def submit_message(
        self,
        *,
        session_id: str,
        texts: list[str],
        workspace_root: str | None = None,
        origin: str | None = None,
    ) -> dict[str, object]: ...


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

    async def _submit_cron_job(self, *, job: CronJob) -> str | None:
        """Submit one cron job as an isolated run and return the run_id.

        The session key is ``cron:<jobId>`` — an ephemeral isolated session that
        carries no conversation context (feat-394 decision 4).

        Side effects:
            - Creates an isolated kernel session.
            - Submits job.instruction as the run prompt.
            - Removes the job from CronJobStore if delete_after_run is True.

        Returns:
            run_id returned by kernel.submit_message, or None on failure.
        """
        isolated_session_id = f"cron:{job.id}"
        try:
            session_payload = await self._kernel_client.create_session(
                workspace_root=str(self._workspace_root),
                product_id="personal_assistant",
                title=f"cron:{job.id}",
                session_id=isolated_session_id,
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "cron: session creation failed: agent=%s job=%s", self._agent_id, job.id
            )
            return None

        session_id = str(session_payload.get("session_id", isolated_session_id)).strip()

        try:
            run_payload = self._kernel_client.submit_message(
                session_id=session_id,
                texts=[job.instruction],
                workspace_root=str(self._workspace_root),
                origin="cron",
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "cron: submit failed: agent=%s job=%s", self._agent_id, job.id
            )
            return None

        run_id = str(run_payload.get("run_id", "")).strip()

        # delete_after_run: remove the job from store now (before awaiting delivery).
        # feat-394 decision 4: one-shot 'at' jobs are cleaned up after submission.
        if job.delete_after_run:
            job_store = CronJobStore(workspace_root=self._workspace_root)
            job_store.remove(job.id)

        return run_id or None

    async def _append_awareness(
        self,
        *,
        session_id: str,
        result_text: str,
        workspace_root: Path,
    ) -> None:
        """Append a System(untrusted) entry to the canonical direct-chat session JSONL.

        Provenance: openclaw delivery-dispatch.ts:335 queueCronAwarenessSystemEvent —
        takes final result text → enqueueSystemEvent(text, {sessionKey:main, trusted:false}).
        In nano, the event is persisted directly to the session JSONL (more stable than
        an in-memory queue), with the same untrusted semantics.

        The entry is formatted as a ``user``-role turn with content:
        ``System (untrusted): [<ISO-timestamp>] <result_text>``
        so the next LLM turn sees it as context without treating it as a trusted instruction.

        Args:
            session_id: Canonical direct-chat kernel session ID to append to.
            result_text: Final assistant response text from the cron isolated run.
            workspace_root: Agent workspace root (locates session JSONL directory).
        """
        sessions_dir = workspace_root / _WORKSPACE_CONFIG_DIRNAME / "sessions"
        jsonl_path = sessions_dir / f"{session_id}.jsonl"

        if not jsonl_path.exists():
            _logger.debug(
                "cron: awareness skip — canonical session JSONL not found: %s", jsonl_path
            )
            return

        ts = datetime.now(tz=UTC).isoformat()
        awareness_content = f"System (untrusted): [{ts}] {result_text}"
        entry = {
            "type": "turn",
            "uuid": uuid.uuid4().hex,
            "parent_uuid": None,
            "session_id": session_id,
            "role": "user",
            "content": awareness_content,
            "timestamp": ts,
            "is_cron_awareness": True,  # marker for transcript trim / compaction skip
        }
        # Append to the JSONL (after the existing entries, never modifying them).
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        _logger.debug(
            "cron: awareness appended: agent=%s session=%s", self._agent_id, session_id
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
