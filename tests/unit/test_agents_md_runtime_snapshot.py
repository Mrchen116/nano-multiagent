"""feat-428-M1 R2: 机制 A — runtime 并入 MemorySnapshot 的 AGENTS.md 生命周期.

验证（不起 LLM，直接调内部 helper）：
- _ensure_memory_snapshot 读 workspace_root/AGENTS.md（含 @import 展开）进快照。
- 读到根 AGENTS.md 后把其绝对路径预置进 SessionFileState.loaded_agents_md（供机制 B 去重）。
- 工作区无 AGENTS.md → 快照 agents_md_content 为 None，不预置。
- _invalidate_memory_snapshot（挂 on_compaction）失效快照 + 清空 loaded_agents_md。

这些测试在 R2 实施之前是红的。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.session.manager import SessionManager
from agent.core.session.jsonl_store import JsonlSessionStore


class _StubLLMClient:
    async def complete(self, *args, **kwargs):  # pragma: no cover - never called
        raise AssertionError("LLM should not be called in these tests")


@pytest.fixture
def runtime(tmp_path: Path) -> AgentRuntime:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    return AgentRuntime(
        session_manager=SessionManager(store=store),
        llm_client=_StubLLMClient(),
    )


def test_snapshot_reads_workspace_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "AGENTS.md").write_text("WS CONVENTIONS", encoding="utf-8")
    snap = runtime._ensure_memory_snapshot("s1", {"workspace_root": str(ws)})
    assert snap["agents_md_content"] is not None
    assert "WS CONVENTIONS" in snap["agents_md_content"]


def test_snapshot_expands_import_in_workspace_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "sub.md").write_text("IMPORTED RULE", encoding="utf-8")
    (ws / "AGENTS.md").write_text("ROOT\n@./sub.md", encoding="utf-8")
    snap = runtime._ensure_memory_snapshot("s2", {"workspace_root": str(ws)})
    assert "ROOT" in snap["agents_md_content"]
    assert "IMPORTED RULE" in snap["agents_md_content"]


def test_snapshot_preseeds_root_into_loaded_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    root_md = ws / "AGENTS.md"
    root_md.write_text("WS", encoding="utf-8")
    runtime._ensure_memory_snapshot("s3", {"workspace_root": str(ws)})
    state = runtime._session_file_states["s3"]
    assert str(root_md.resolve()) in state.loaded_agents_md


def test_snapshot_empty_when_no_workspace_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    snap = runtime._ensure_memory_snapshot("s4", {"workspace_root": str(ws)})
    assert snap["agents_md_content"] is None
    # 无根 AGENTS.md → 不预置任何路径。
    state = runtime._session_file_states.get("s4")
    if state is not None:
        assert state.loaded_agents_md == set()


def test_invalidate_clears_snapshot_and_loaded_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "AGENTS.md").write_text("WS", encoding="utf-8")
    runtime._ensure_memory_snapshot("s5", {"workspace_root": str(ws)})
    state = runtime._session_file_states["s5"]
    assert state.loaded_agents_md  # 预置非空

    runtime._invalidate_memory_snapshot("s5")
    assert "s5" not in runtime._memory_snapshots
    # 去重集随压缩边界清空，压缩后可重注（含根）。
    assert runtime._session_file_states["s5"].loaded_agents_md == set()


def test_preseed_idempotent_after_compaction_reseed(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    # fix 3: 压缩后 _invalidate 清空 loaded_agents_md，下一轮 _ensure 重新预埋根——
    # 根路径恰好一份（set 幂等），不因 reseed 重复，机制 B 仍正确跳过根。
    ws = tmp_path / "ws"
    ws.mkdir()
    root_md = ws / "AGENTS.md"
    root_md.write_text("WS", encoding="utf-8")
    key = str(root_md.resolve())

    runtime._ensure_memory_snapshot("s6", {"workspace_root": str(ws)})
    assert runtime._session_file_states["s6"].loaded_agents_md == {key}

    # 压缩边界清空 + 下一轮重新预埋。
    runtime._invalidate_memory_snapshot("s6")
    runtime._ensure_memory_snapshot("s6", {"workspace_root": str(ws)})
    assert runtime._session_file_states["s6"].loaded_agents_md == {key}


def test_no_preseed_when_workspace_has_no_agents_md(
    runtime: AgentRuntime, tmp_path: Path
) -> None:
    # fix 3 配套：机制 A 未注入根（无 AGENTS.md）→ 不预埋，机制 B 后续若命中可正常注入。
    # 同理 frozen/hook-override 路径不调 _ensure_memory_snapshot 时根本不预埋——
    # 机制 A 没注入，机制 B 命中根时应注入（非重复）。
    ws = tmp_path / "ws"
    ws.mkdir()
    runtime._ensure_memory_snapshot("s7", {"workspace_root": str(ws)})
    state = runtime._session_file_states.get("s7")
    if state is not None:
        assert state.loaded_agents_md == set()
