"""feat-428-M1 R3: 机制 B — read 触发就近加载 AGENTS.md 的注入逻辑.

覆盖：
- 工作区内 read：目录链上 AGENTS.md 内容注入 read tool_result（<project-instructions path=...>）。
- 工作区外 read：所属 git 仓内逐级 AGENTS.md 给英文路径提示（<project-instructions-hint>），不含正文。
- 工作区外不属任何 git 仓：不提示。
- 去重：同一份一会话只注入一次；含机制 A 已预置的根。
- 压缩后清空 loaded_agents_md → 可重注。
- 关闭 nested_memory flag → 内/外都不注入；空态 read 照常返回。

直接构造 ToolContext + SessionFileState 调 ReadTool.run（不起 LLM）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.tools.base import (
    ToolContext,
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.core.tools.session_file_state import SessionFileState
from agent.platform.tools.builtins.read import ReadTool
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def test_nested_memory_in_feature_registry_default_on() -> None:
    from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY

    assert "nested_memory" in FEATURE_REGISTRY
    entry = FEATURE_REGISTRY["nested_memory"]
    assert entry["default_on"] is True
    assert entry["layer"] == "core"
    assert entry["requires_tool"] == "read"
    assert entry["sections"] == ()


def _ctx(
    workspace_root: Path,
    state: SessionFileState,
    *,
    nested_on: bool | None = None,
) -> ToolContext:
    metadata: dict = {}
    if nested_on is not None:
        metadata["agent_features"] = {"nested_memory": nested_on}
    base = ToolContext.create(repo_root=workspace_root)
    return base.with_session(
        "sess",
        session_metadata=metadata,
        session_file_state=state,
    )


def _read_text(tool: ReadTool, output) -> str:
    """Render the tool output the way the loop serializes it (text only)."""
    serialized = tool.serialize_result(output)
    if isinstance(serialized, list):
        return "\n".join(b.get("text", "") for b in serialized if isinstance(b, dict))
    return str(serialized)


# ---------------------------------------------------------------------------
# 工作区内 — 注入正文
# ---------------------------------------------------------------------------


def test_inside_workspace_injects_subdir_agents_md(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    sub = ws / "backend" / "api"
    sub.mkdir(parents=True)
    (sub.parent / "AGENTS.md").write_text("BACKEND CONVENTIONS", encoding="utf-8")
    target = sub / "user.py"
    target.write_text("print('x')", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    out = tool.run({"path": str(target)}, _ctx(ws, state))
    text = _read_text(tool, out)
    assert "BACKEND CONVENTIONS" in text
    assert "<project-instructions path=" in text
    # 路径记进去重集。
    assert str((sub.parent / "AGENTS.md").resolve()) in state.loaded_agents_md


def test_inside_workspace_no_agents_md_returns_plain(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    target = ws / "a.py"
    target.write_text("code", encoding="utf-8")
    tool = ReadTool()
    out = tool.run({"path": str(target)}, _ctx(ws, SessionFileState()))
    text = _read_text(tool, out)
    assert "<project-instructions" not in text
    assert "code" in text


def test_inside_workspace_dedup_skips_root_preseeded_by_mechanism_a(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    root_md = ws / "AGENTS.md"
    root_md.write_text("ROOT CONVENTIONS", encoding="utf-8")
    target = ws / "a.py"
    target.write_text("code", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    # 机制 A 预置根路径。
    state.loaded_agents_md.add(str(root_md.resolve()))
    out = tool.run({"path": str(target)}, _ctx(ws, state))
    text = _read_text(tool, out)
    # 根已被机制 A 注入 → 不重复注入。
    assert "ROOT CONVENTIONS" not in text


def test_inside_workspace_dedup_once_per_session(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    t1 = sub / "a.py"
    t1.write_text("a", encoding="utf-8")
    t2 = sub / "b.py"
    t2.write_text("b", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    out1 = tool.run({"path": str(t1)}, _ctx(ws, state))
    assert "PKG RULES" in _read_text(tool, out1)
    # 第二次 read 同目录另一文件 → 该 AGENTS.md 已注入，不再带。
    out2 = tool.run({"path": str(t2)}, _ctx(ws, state))
    assert "PKG RULES" not in _read_text(tool, out2)


def test_compaction_clear_allows_reinjection(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    target = sub / "a.py"
    target.write_text("a", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    tool.run({"path": str(target)}, _ctx(ws, state))
    # 模拟压缩边界清空。
    state.loaded_agents_md.clear()
    out = tool.run({"path": str(target)}, _ctx(ws, state))
    assert "PKG RULES" in _read_text(tool, out)


# ---------------------------------------------------------------------------
# 工作区外 — 路径提示
# ---------------------------------------------------------------------------


def test_outside_workspace_git_repo_gives_hint(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "other-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("OTHER PROJECT RULES", encoding="utf-8")
    target = repo / "src" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("code", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    out = tool.run({"path": str(target)}, _ctx(ws, state))
    text = _read_text(tool, out)
    assert "<project-instructions-hint>" in text
    assert str((repo / "AGENTS.md").resolve()) in text
    # 提示不含正文。
    assert "OTHER PROJECT RULES" not in text


def test_outside_workspace_nested_repos_lists_all_in_range(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)
    (outer / "AGENTS.md").write_text("OUTER", encoding="utf-8")
    inner = outer / "x" / "inner"
    (inner / ".git").mkdir(parents=True)
    (inner / "AGENTS.md").write_text("INNER", encoding="utf-8")
    target = inner / "y" / "f.py"
    target.parent.mkdir(parents=True)
    target.write_text("code", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    out = tool.run({"path": str(target)}, _ctx(ws, state))
    text = _read_text(tool, out)
    # 外层与内层 AGENTS.md 路径都列出。
    assert str((outer / "AGENTS.md").resolve()) in text
    assert str((inner / "AGENTS.md").resolve()) in text


def test_outside_workspace_not_git_no_hint(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "AGENTS.md").write_text("STRAY", encoding="utf-8")
    target = outside / "f.py"
    target.write_text("code", encoding="utf-8")

    tool = ReadTool()
    out = tool.run({"path": str(target)}, _ctx(ws, SessionFileState()))
    text = _read_text(tool, out)
    assert "<project-instructions-hint>" not in text
    assert "STRAY" not in text


def test_outside_workspace_hint_dedup_once(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("RULES", encoding="utf-8")
    t1 = repo / "a.py"
    t1.write_text("a", encoding="utf-8")
    t2 = repo / "b.py"
    t2.write_text("b", encoding="utf-8")

    tool = ReadTool()
    state = SessionFileState()
    out1 = tool.run({"path": str(t1)}, _ctx(ws, state))
    assert "<project-instructions-hint>" in _read_text(tool, out1)
    out2 = tool.run({"path": str(t2)}, _ctx(ws, state))
    assert "<project-instructions-hint>" not in _read_text(tool, out2)


# ---------------------------------------------------------------------------
# 关闭 flag
# ---------------------------------------------------------------------------


def test_disabled_flag_no_injection_inside(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    target = sub / "a.py"
    target.write_text("a", encoding="utf-8")

    tool = ReadTool()
    out = tool.run({"path": str(target)}, _ctx(ws, SessionFileState(), nested_on=False))
    assert "PKG RULES" not in _read_text(tool, out)


def test_disabled_flag_no_hint_outside(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("RULES", encoding="utf-8")
    target = repo / "a.py"
    target.write_text("a", encoding="utf-8")

    tool = ReadTool()
    out = tool.run({"path": str(target)}, _ctx(ws, SessionFileState(), nested_on=False))
    assert "<project-instructions-hint>" not in _read_text(tool, out)


def test_default_on_when_no_override(tmp_path: Path) -> None:
    # 不传 agent_features → 取 registry default_on=True。
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    target = sub / "a.py"
    target.write_text("a", encoding="utf-8")

    tool = ReadTool()
    out = tool.run({"path": str(target)}, _ctx(ws, SessionFileState()))
    assert "PKG RULES" in _read_text(tool, out)


# ---------------------------------------------------------------------------
# fix r1: 行号污染 / 去重提交时机 / symlink
# ---------------------------------------------------------------------------


def test_injection_block_not_line_numbered(tmp_path: Path) -> None:
    # CRITICAL (verifier W1 + code-review C1/B1): serialize_result 不能把注入块
    # 一起过 _add_line_numbers——只有文件正文加行号，<project-instructions> 块原样。
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    target = sub / "a.py"
    target.write_text("line one\nline two", encoding="utf-8")

    tool = ReadTool()
    serialized = tool.serialize_result(
        tool.run({"path": str(target)}, _ctx(ws, SessionFileState()))
    )
    assert isinstance(serialized, str)
    # 文件正文有行号（cat -n 风格 "N→"）。
    assert "→line one" in serialized
    # 注入块标签行不得带行号前缀（"N→<project-instructions").
    assert "<project-instructions path=" in serialized
    for line in serialized.splitlines():
        if "<project-instructions" in line or "PKG RULES" in line:
            # 行号格式是 右对齐数字 + →；注入块行不应匹配。
            assert "→" not in line.split("<project-instructions")[0], (
                f"injection line got line-numbered: {line!r}"
            )


def test_hint_block_not_line_numbered(tmp_path: Path) -> None:
    # 外部路径提示块同样不得被加行号。
    ws = tmp_path / "ws"
    ws.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("RULES", encoding="utf-8")
    target = repo / "a.py"
    target.write_text("x\ny", encoding="utf-8")

    tool = ReadTool()
    serialized = tool.serialize_result(
        tool.run({"path": str(target)}, _ctx(ws, SessionFileState()))
    )
    assert isinstance(serialized, str)
    assert "<project-instructions-hint>" in serialized
    for line in serialized.splitlines():
        if "<project-instructions-hint>" in line:
            assert not line.startswith(" ") or "→" not in line[:8], (
                f"hint line got line-numbered: {line!r}"
            )


def test_non_utf8_main_file_does_not_pollute_dedup(tmp_path: Path) -> None:
    # fix 2: _nested_memory_blocks compute 时不得 mutate loaded_agents_md；
    # 主文件读失败(ToolError)时注入未交付，事后 read 同目录正常文件仍能注入。
    ws = tmp_path / "ws"
    sub = ws / "pkg"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("PKG RULES", encoding="utf-8")
    bad = sub / "bad.bin"
    bad.write_bytes(b"\xff\xfe\x00\x01not utf8\xff")

    tool = ReadTool()
    state = SessionFileState()
    with pytest.raises(Exception):
        tool.run({"path": str(bad)}, _ctx(ws, state))
    # 失败的 read 不应把该 AGENTS.md 记进去重集。
    assert str((sub / "AGENTS.md").resolve()) not in state.loaded_agents_md
    # 事后 read 同目录正常文件仍能注入。
    good = sub / "ok.py"
    good.write_text("code", encoding="utf-8")
    out = tool.run({"path": str(good)}, _ctx(ws, state))
    assert "PKG RULES" in _read_text(tool, out)


def test_symlink_dir_resolves_for_chain_and_dedup(tmp_path: Path) -> None:
    # fix 4: file_dir 须先 resolve(file_path) 再取 parent，否则 symlink 目录下
    # 链走错 + 去重 key 与 is_path_in_workspace(resolve) 不匹配。
    ws = tmp_path / "ws"
    real = ws / "real"
    real.mkdir(parents=True)
    (real / "AGENTS.md").write_text("REAL RULES", encoding="utf-8")
    (real / "f.py").write_text("code", encoding="utf-8")
    link = ws / "link"
    link.symlink_to(real, target_is_directory=True)

    tool = ReadTool()
    state = SessionFileState()
    out = tool.run({"path": str(link / "f.py")}, _ctx(ws, state))
    text = _read_text(tool, out)
    assert "REAL RULES" in text
    # 去重 key 用 resolve 后的真实路径。
    assert str((real / "AGENTS.md").resolve()) in state.loaded_agents_md
