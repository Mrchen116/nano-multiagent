"""close_session must drop per-session PromptSlots (refactor-406-M3fix #7).

refactor-406 added ``_session_prompt_slots`` (per-session system-prompt slots
registered via ``register_session_prompt_slots``). ``close_session`` evicted the
other per-session caches but not this one, so a long-running gateway's session churn
grew ``_session_prompt_slots`` unboundedly. This guards the eviction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class _FakeLLMClient:
    async def generate(self, request):  # noqa: ANN001
        if False:  # pragma: no cover - never iterated in this test
            yield None


def _make_runtime(tmp_path: Path) -> AgentRuntime:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    return AgentRuntime(
        session_manager=manager, llm_client=_FakeLLMClient(), model="mock-model"
    )


@pytest.mark.asyncio
async def test_close_session_drops_prompt_slots(tmp_path: Path) -> None:
    """register_session_prompt_slots then close_session must leave the map empty."""
    runtime = _make_runtime(tmp_path)
    runtime.register_session_prompt_slots("sess-1", object())
    assert "sess-1" in runtime._session_prompt_slots  # noqa: SLF001

    await runtime.close_session("sess-1")

    assert "sess-1" not in runtime._session_prompt_slots, (  # noqa: SLF001
        "close_session must drop the per-session PromptSlots entry (M3fix #7 leak)"
    )


@pytest.mark.asyncio
async def test_prompt_slots_map_does_not_grow_across_session_churn(
    tmp_path: Path,
) -> None:
    """Many open/close cycles must not accumulate _session_prompt_slots entries."""
    runtime = _make_runtime(tmp_path)
    for i in range(20):
        sid = f"sess-{i}"
        runtime.register_session_prompt_slots(sid, object())
        await runtime.close_session(sid)
    assert runtime._session_prompt_slots == {}, (  # noqa: SLF001
        "_session_prompt_slots must not grow across session churn (M3fix #7)"
    )
