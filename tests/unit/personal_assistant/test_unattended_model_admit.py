"""Heartbeat/cron admit the first candidate and failover by error.kind."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent.sdk import ReplayLastUserRejected, RunOrigin
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog, LiveAgentSnapshot
from personal_assistant.gateway.kernel_client import InProcessKernelClient
from personal_assistant.gateway.model_fallback import (
    ModelStickyStore,
    StickyModelOverride,
    failover_unattended_run,
)
from personal_assistant.gateway.runtime_delivery.stream import StreamRunOutcome
from personal_assistant.scheduler.heartbeat_scheduler import (
    HeartbeatScheduler,
    HeartbeatSchedulerStateStore,
)


def test_submit_message_uses_explicit_candidate_not_saved_primary(
    tmp_path: Path,
) -> None:
    captured: list[str | None] = []

    def _submit(**kwargs: object) -> object:
        captured.append(kwargs.get("model"))  # type: ignore[arg-type]
        return MagicMock(run_id="run-1")

    kernel = MagicMock()
    kernel.submit.side_effect = _submit
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=tmp_path / "a",
                default_model="primary",
                model_fallbacks=("backup",),
            ),
        )
    )
    sticky = ModelStickyStore()
    sticky.set("sess-1", "agent-a", StickyModelOverride("backup", noticed=True))
    client = InProcessKernelClient(
        kernel,
        agent_catalog=catalog,
        product_default_model="prod",
        sticky_store=sticky,
    )

    admitted = client.admit_model(agent_id="agent-a", session_id="sess-1")
    client.submit_message(
        session_id="sess-1",
        texts=["tick"],
        workspace_root=str(tmp_path / "a"),
        origin="heartbeat",
        agent_id="agent-a",
        model=admitted,
    )

    assert admitted == "backup"
    assert captured == ["backup"]


def _write_heartbeat(workspace_root: Path, content: str) -> None:
    path = workspace_root / ".nanoassistant" / "HEARTBEAT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_heartbeat_reuses_canonical_session_sticky_model(tmp_path: Path) -> None:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir(parents=True, exist_ok=True)
    agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace_root,
        title="Canonical Agent",
        features={"heartbeat": True},
        default_model="primary",
        model_fallbacks=("backup",),
    )
    _write_heartbeat(workspace_root, "- Check inbox status\n")
    catalog = LiveAgentCatalog((agent,))
    sticky = ModelStickyStore()
    sticky.set("canonical-sess", "agent-a", StickyModelOverride("backup", noticed=True))
    captured: list[str | None] = []

    def _submit(**kwargs: object) -> object:
        captured.append(kwargs.get("model"))  # type: ignore[arg-type]
        return MagicMock(run_id="run-hb")

    kernel = MagicMock()
    kernel.submit.side_effect = _submit
    kernel.current_event_sequence.return_value = 0
    client = InProcessKernelClient(
        kernel,
        agent_catalog=catalog,
        product_default_model="prod",
        sticky_store=sticky,
    )
    scheduler = HeartbeatScheduler(
        agents=(agent,),
        kernel_client=client,
        state_store=HeartbeatSchedulerStateStore(tmp_path / "state.json"),
        canonical_session_store={"agent-a": "canonical-sess"},
    )

    summary = asyncio.run(scheduler.tick(now=datetime(2026, 3, 11, 9, 0, tzinfo=UTC)))

    assert captured == ["backup"]
    assert summary.triggered_runs[0].session_id == "canonical-sess"


def _snapshot(tmp_path: Path, *fallbacks: str) -> LiveAgentSnapshot:
    workspace_root = tmp_path / "agent-a"
    workspace_root.mkdir(parents=True, exist_ok=True)
    return LiveAgentSnapshot(
        config=AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=workspace_root,
            default_model="primary",
            model_fallbacks=fallbacks,
        ),
        revision=1,
    )


def _failed(kind: str) -> StreamRunOutcome:
    return StreamRunOutcome(
        status="failed",
        final_text="",
        delivery=None,
        error=kind,
        error_kind=kind,
    )


def _ok(text: str = "backup reply") -> StreamRunOutcome:
    return StreamRunOutcome(
        status="completed",
        final_text=text,
        delivery=None,
        error=None,
        error_kind=None,
    )


class _ReplayKernel:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.reconfigure_calls: list[dict[str, object]] = []
        self.replay_calls: list[dict[str, object]] = []
        self._n = 0

    async def reconfigure_session(self, **kwargs: object) -> None:
        self.reconfigure_calls.append(kwargs)

    def replay_last_user(self, **kwargs: object) -> SimpleNamespace:
        if self.reject:
            raise ReplayLastUserRejected("run already produced assistant output")
        self._n += 1
        self.replay_calls.append(kwargs)
        return SimpleNamespace(run_id=f"replay-{self._n}", start_sequence=0)


async def _run_failover(
    tmp_path: Path,
    *,
    outcome: StreamRunOutcome,
    consume_results: list[StreamRunOutcome] | None = None,
    reject: bool = False,
    fallbacks: tuple[str, ...] = ("backup",),
    current_model: str = "primary",
) -> tuple[StreamRunOutcome, _ReplayKernel, ModelStickyStore, list[str]]:
    snapshot = _snapshot(tmp_path, *fallbacks)
    kernel = _ReplayKernel(reject=reject)
    sticky = ModelStickyStore()
    notices: list[str] = []
    remaining = list(consume_results or [])

    async def consume_replay(
        *,
        run_id: str,
        stream_anchor: int,
        before_flush: object,
    ) -> StreamRunOutcome:
        del run_id, stream_anchor
        next_outcome = remaining.pop(0) if remaining else _ok()
        if next_outcome.status == "completed" and callable(before_flush):
            await before_flush()
        return next_outcome

    async def deliver_notice(model: str) -> None:
        notices.append(model)

    result = await failover_unattended_run(
        kernel=kernel,
        session_id="sess-1",
        workspace_root=snapshot.config.workspace_root,
        agent_snapshot=snapshot,
        sticky_store=sticky,
        product_default="prod",
        reasoning_catalog=None,
        time_context=None,
        current_model=current_model,
        outcome=outcome,
        origin=RunOrigin.HEARTBEAT,
        consume_replay=consume_replay,
        deliver_notice=deliver_notice,
    )
    return result, kernel, sticky, notices


@pytest.mark.asyncio
async def test_unattended_quota_replays_backup_and_notices_once(tmp_path: Path) -> None:
    result, kernel, sticky, notices = await _run_failover(
        tmp_path, outcome=_failed("quota")
    )

    assert result.status == "completed"
    assert result.final_text == "backup reply"
    assert len(kernel.replay_calls) == 1
    assert "parts" not in kernel.replay_calls[0]
    assert kernel.reconfigure_calls[0]["runtime"].model == "backup"
    assert sticky.get("sess-1") == StickyModelOverride("backup", noticed=True)
    assert notices == ["backup"]


@pytest.mark.asyncio
async def test_unattended_context_length_does_not_replay(tmp_path: Path) -> None:
    result, kernel, sticky, notices = await _run_failover(
        tmp_path, outcome=_failed("context_length")
    )

    assert result.status == "failed"
    assert result.error_kind == "context_length"
    assert kernel.replay_calls == []
    assert sticky.get("sess-1") is None
    assert notices == []


@pytest.mark.asyncio
async def test_unattended_rejected_replay_sticks_next_candidate(tmp_path: Path) -> None:
    result, kernel, sticky, notices = await _run_failover(
        tmp_path, outcome=_failed("quota"), reject=True
    )

    assert result.status == "failed"
    assert result.error_kind == "quota"
    assert kernel.replay_calls == []
    assert sticky.get("sess-1") == StickyModelOverride("backup", noticed=False)
    assert notices == []


@pytest.mark.asyncio
async def test_unattended_exhausted_chain_stays_failed_without_notice(
    tmp_path: Path,
) -> None:
    result, kernel, sticky, notices = await _run_failover(
        tmp_path,
        outcome=_failed("quota"),
        fallbacks=("backup-a", "backup-b"),
        consume_results=[_failed("quota"), _failed("quota")],
    )

    assert result.status == "failed"
    assert result.error_kind == "quota"
    assert [call["runtime"].model for call in kernel.reconfigure_calls] == [
        "backup-a",
        "backup-b",
    ]
    assert len(kernel.replay_calls) == 2
    assert notices == []
    assert sticky.get("sess-1") == StickyModelOverride("backup-b", noticed=False)
