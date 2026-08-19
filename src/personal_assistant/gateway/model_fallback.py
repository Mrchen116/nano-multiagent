"""Gateway-owned model fallback sticky state and kind-based failover rules.

内核不知道备用链。Gateway 只根据 run_status.error.kind 决定是否换模型。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.sdk import ReplayLastUserRejected, RunOrigin

from personal_assistant.config.local_store import (
    resolve_model_candidates,
    resolve_run_model,
)
from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome

FAILOVER_KINDS = frozenset({"quota", "overload", "timeout", "rate_limit", "auth"})
SWITCH_NOTICE_TEMPLATE = "已改用 {model}，因为主模型不可用。"


@dataclass(frozen=True, slots=True)
class StickyModelOverride:
    """Remember the model that should admit the next turn on one Kernel session."""

    model: str
    noticed: bool = False


class ModelStickyStore:
    """Process-memory sticky map keyed by kernel_session_id.

    /new 换会话后自然消失。Agent 的 default_model 或 model_fallbacks 成功 apply
    时清掉该 Agent 下所有 session 覆盖。不写磁盘。
    """

    def __init__(self) -> None:
        self._by_session: dict[str, StickyModelOverride] = {}
        self._sessions_by_agent: dict[str, set[str]] = {}
        self._agent_by_session: dict[str, str] = {}

    def get(self, session_id: str | None) -> StickyModelOverride | None:
        """Return the sticky override for one Kernel session, if any."""

        if not session_id:
            return None
        return self._by_session.get(session_id)

    def set(self, session_id: str, agent_id: str, sticky: StickyModelOverride) -> None:
        """Remember sticky model for one session belonging to ``agent_id``."""

        previous_agent = self._agent_by_session.get(session_id)
        if previous_agent is not None and previous_agent != agent_id:
            sessions = self._sessions_by_agent.get(previous_agent)
            if sessions is not None:
                sessions.discard(session_id)
        self._by_session[session_id] = sticky
        self._agent_by_session[session_id] = agent_id
        self._sessions_by_agent.setdefault(agent_id, set()).add(session_id)

    def mark_noticed(self, session_id: str) -> None:
        """Record that the switch notice for this session has been delivered."""

        current = self._by_session.get(session_id)
        if current is None or current.noticed:
            return
        self._by_session[session_id] = StickyModelOverride(
            model=current.model, noticed=True
        )

    def clear_agent(self, agent_id: str) -> None:
        """Drop every session override after the Agent model chain is rewritten."""

        sessions = self._sessions_by_agent.pop(agent_id, set())
        for session_id in sessions:
            self._by_session.pop(session_id, None)
            self._agent_by_session.pop(session_id, None)

    def drop_session(self, session_id: str) -> None:
        """Drop sticky for a session that no longer exists."""

        agent_id = self._agent_by_session.pop(session_id, None)
        self._by_session.pop(session_id, None)
        if agent_id is None:
            return
        sessions = self._sessions_by_agent.get(agent_id)
        if sessions is None:
            return
        sessions.discard(session_id)
        if not sessions:
            self._sessions_by_agent.pop(agent_id, None)


def error_kind_from_run_state(run_state: Mapping[str, Any] | None) -> str | None:
    """Read the kernel-projected ``error.kind`` without guessing from reply text."""

    if not isinstance(run_state, Mapping):
        return None
    error = run_state.get("error")
    if isinstance(error, Mapping):
        kind = error.get("kind")
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
    return None


def should_failover(kind: str | None) -> bool:
    """Return whether Gateway should try the next candidate for this kind."""

    return kind in FAILOVER_KINDS


def next_candidate(candidates: list[str], current: str | None) -> str | None:
    """Return the candidate after ``current``, or None when the chain is exhausted."""

    if not candidates:
        return None
    if current is None:
        return candidates[0]
    try:
        index = candidates.index(current)
    except ValueError:
        return candidates[0]
    if index + 1 >= len(candidates):
        return None
    return candidates[index + 1]


def switch_notice(model: str) -> str:
    """Return the one-shot user-visible switch explanation."""

    return SWITCH_NOTICE_TEMPLATE.format(model=model)


def model_chain_changed(previous: object | None, updated: object) -> bool:
    """Return whether saved default_model or model_fallbacks changed."""

    if previous is None:
        return False
    return getattr(previous, "default_model", None) != getattr(
        updated, "default_model", None
    ) or tuple(getattr(previous, "model_fallbacks", ()) or ()) != tuple(
        getattr(updated, "model_fallbacks", ()) or ()
    )


async def failover_unattended_run(
    *,
    kernel: Any,
    session_id: str,
    workspace_root: Path | str,
    agent_snapshot: Any,
    sticky_store: ModelStickyStore,
    product_default: str | None,
    reasoning_catalog: Any,
    time_context: Any,
    current_model: str,
    outcome: StreamRunOutcome,
    origin: RunOrigin,
    consume_replay: Callable[..., Awaitable[StreamRunOutcome]],
    deliver_notice: Callable[[str], Awaitable[None]] | None = None,
) -> StreamRunOutcome:
    """Replay the last user turn onto later candidates after an unattended failure.

    Chat owns its own loop because it has a SessionBinding and control-reply path.
    Heartbeat and cron share this helper so they cannot invent a third kind check.
    """

    while outcome.status == "failed":
        if not should_failover(outcome.error_kind):
            return outcome
        nxt = next_candidate(
            resolve_model_candidates(
                agent_snapshot.config,
                product_default=product_default,
                sticky=current_model,
            ),
            current_model,
        )
        if nxt is None:
            return outcome
        try:
            from personal_assistant.gateway.session_composition import (
                project_agent_runtime,
            )

            runtime = project_agent_runtime(
                agent_snapshot,
                scenario={"agent_id": agent_snapshot.agent_id},
                resolved_model=nxt,
                reasoning_catalog=reasoning_catalog,
                time_context=time_context,
                apply_saved_reasoning=False,
            ).runtime
            await kernel.reconfigure_session(
                session_id=session_id,
                workspace_root=workspace_root,
                runtime=runtime,
            )
            replay = kernel.replay_last_user(
                session_id=session_id,
                workspace_root=workspace_root,
                origin=origin,
            )
        except ReplayLastUserRejected:
            sticky_store.set(
                session_id,
                agent_snapshot.agent_id,
                StickyModelOverride(model=nxt, noticed=False),
            )
            return outcome
        current_model = nxt
        sticky_store.set(
            session_id,
            agent_snapshot.agent_id,
            StickyModelOverride(model=nxt, noticed=False),
        )

        async def _before_flush(model: str = nxt) -> None:
            chain_head = resolve_run_model(
                agent_snapshot.config, product_default=product_default
            )
            sticky = sticky_store.get(session_id)
            if (
                deliver_notice is not None
                and chain_head
                and model != chain_head
                and (sticky is None or not sticky.noticed)
            ):
                await deliver_notice(model)
                sticky_store.mark_noticed(session_id)

        outcome = await consume_replay(
            run_id=replay.run_id,
            stream_anchor=int(getattr(replay, "start_sequence", 0) or 0),
            before_flush=_before_flush,
        )
    return outcome
