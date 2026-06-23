"""Unit tests for the shared AGENTS.md loader + git-root helpers (feat-428).

Covers the three pure-core helpers consumed by both injection mechanisms:
- load_agents_md: @import expansion (recursion / cycle guard / depth cap /
  missing-file silent ignore / code-block skip), aligned with CC claudemd.ts.
- find_outermost_git_root: single walk-up to the *outermost* git root (covers
  nested repos), recognising both .git directory and .git file (worktree).
- iter_agents_md_chain: yield existing AGENTS.md on the [file_dir … top] range.
"""

from __future__ import annotations

from pathlib import Path

from agent.core.agent.agents_md import (
    find_outermost_git_root,
    iter_agents_md_chain,
    load_agents_md,
)


# ---------------------------------------------------------------------------
# load_agents_md
# ---------------------------------------------------------------------------


def test_load_plain_file_returns_content(tmp_path: Path) -> None:
    f = tmp_path / "AGENTS.md"
    f.write_text("hello conventions", encoding="utf-8")
    assert load_agents_md(f) == "hello conventions"


def test_load_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_agents_md(tmp_path / "AGENTS.md") is None


def test_import_relative_dot_path_expanded(tmp_path: Path) -> None:
    (tmp_path / "sub.md").write_text("SUB BODY", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text("root line\n@./sub.md\nafter", encoding="utf-8")
    out = load_agents_md(root)
    assert "root line" in out
    assert "SUB BODY" in out
    assert "after" in out


def test_import_bare_path_treated_as_relative(tmp_path: Path) -> None:
    (tmp_path / "sub.md").write_text("BARE BODY", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text("@sub.md", encoding="utf-8")
    assert "BARE BODY" in load_agents_md(root)


def test_import_absolute_path_expanded(tmp_path: Path) -> None:
    target = tmp_path / "abs.md"
    target.write_text("ABS BODY", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text(f"@{target}", encoding="utf-8")
    assert "ABS BODY" in load_agents_md(root)


def test_import_missing_target_silently_ignored(tmp_path: Path) -> None:
    root = tmp_path / "AGENTS.md"
    root.write_text("body\n@./nope.md\ntail", encoding="utf-8")
    out = load_agents_md(root)
    assert "body" in out
    assert "tail" in out


def test_import_inside_code_block_not_expanded(tmp_path: Path) -> None:
    (tmp_path / "secret.md").write_text("SHOULD NOT APPEAR", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text(
        "real\n```\n@./secret.md\n```\nend",
        encoding="utf-8",
    )
    out = load_agents_md(root)
    assert "SHOULD NOT APPEAR" not in out
    assert "real" in out and "end" in out


def test_import_inside_tilde_code_fence_not_expanded(tmp_path: Path) -> None:
    (tmp_path / "secret.md").write_text("SHOULD NOT APPEAR", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text("~~~\n@./secret.md\n~~~", encoding="utf-8")
    assert "SHOULD NOT APPEAR" not in load_agents_md(root)


def test_import_inside_inline_code_span_not_expanded(tmp_path: Path) -> None:
    # An @path written inline as a code span (`@foo`) is not an import — CC's
    # leaf-text rule excludes codespan tokens, so the loader strips inline spans
    # before extracting @import directives.
    (tmp_path / "spanned.md").write_text("SHOULD NOT APPEAR", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text(
        "use the `@./spanned.md` syntax to import another file",
        encoding="utf-8",
    )
    out = load_agents_md(root)
    assert "SHOULD NOT APPEAR" not in out
    assert "syntax to import" in out


def test_fence_close_requires_length_ge_open(tmp_path: Path) -> None:
    # fix 5 (CommonMark): 关闭 fence 须同字符且长度 ≥ 开启长度。
    # 开启用 ```（3），中间出现 ```` (4) 不应关闭它——@import 仍在 fence 内、不展开。
    (tmp_path / "secret.md").write_text("SHOULD NOT APPEAR", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text(
        "```\ncode\n````\n@./secret.md\n```\nend",
        encoding="utf-8",
    )
    out = load_agents_md(root)
    assert "SHOULD NOT APPEAR" not in out
    assert "end" in out


def test_import_inline_replace_drops_directive_text(tmp_path: Path) -> None:
    # fix 6: @import 应 inline replace（对齐 CC + docstring "replaced inline"），
    # 即原 @import 路径文本不再出现在输出里（被展开内容取代）。
    (tmp_path / "sub.md").write_text("SUB BODY", encoding="utf-8")
    root = tmp_path / "AGENTS.md"
    root.write_text("before\n@./sub.md\nafter", encoding="utf-8")
    out = load_agents_md(root)
    assert "SUB BODY" in out
    assert "before" in out and "after" in out
    assert "@./sub.md" not in out


def test_non_utf8_agents_md_not_silently_dropped(tmp_path: Path) -> None:
    # fix 7: load_agents_md 用 errors='replace'，非 UTF-8 的 AGENTS.md 不被吞成 None。
    root = tmp_path / "AGENTS.md"
    root.write_bytes("RULE cafe\n".encode("utf-8") + b"\xff\xfe garbage")
    out = load_agents_md(root)
    assert out is not None
    assert "RULE" in out


def test_import_cycle_guard_no_infinite_loop(tmp_path: Path) -> None:
    a = tmp_path / "AGENTS.md"
    b = tmp_path / "b.md"
    a.write_text("A_BODY\n@./b.md", encoding="utf-8")
    b.write_text("B_BODY\n@./AGENTS.md", encoding="utf-8")
    out = load_agents_md(a)
    assert "A_BODY" in out
    assert "B_BODY" in out
    # Each file's body appears exactly once despite the cycle.
    assert out.count("A_BODY") == 1
    assert out.count("B_BODY") == 1


def test_import_depth_cap_5(tmp_path: Path) -> None:
    # Chain root -> l1 -> l2 -> l3 -> l4 -> l5 -> l6.
    # MAX depth is 5: levels beyond the cap are not expanded.
    names = ["AGENTS.md", "l1.md", "l2.md", "l3.md", "l4.md", "l5.md", "l6.md"]
    bodies = ["BODY0", "BODY1", "BODY2", "BODY3", "BODY4", "BODY5", "BODY6"]
    for i, name in enumerate(names):
        text = bodies[i]
        if i + 1 < len(names):
            text += f"\n@./{names[i + 1]}"
        (tmp_path / name).write_text(text, encoding="utf-8")
    out = load_agents_md(tmp_path / "AGENTS.md")
    # Root + 5 levels of import are reachable.
    for b in bodies[:6]:
        assert b in out
    # The 6th level (depth 6) is beyond the cap.
    assert "BODY6" not in out


# ---------------------------------------------------------------------------
# find_outermost_git_root
# ---------------------------------------------------------------------------


def test_no_git_returns_none(tmp_path: Path) -> None:
    d = tmp_path / "a" / "b"
    d.mkdir(parents=True)
    assert find_outermost_git_root(d) is None


def test_single_git_dir_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    deep = repo / "x" / "y"
    deep.mkdir(parents=True)
    assert find_outermost_git_root(deep) == repo


def test_git_file_worktree_form_recognised(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: /elsewhere", encoding="utf-8")
    deep = repo / "sub"
    deep.mkdir()
    assert find_outermost_git_root(deep) == repo


def test_nested_repos_returns_outermost(tmp_path: Path) -> None:
    # outer = git repo; inner = git repo nested under outer.
    outer = tmp_path / "outer"
    (outer / ".git").mkdir(parents=True)
    inner = outer / "x" / "inner"
    (inner / ".git").mkdir(parents=True)
    deep = inner / "y" / "z"
    deep.mkdir(parents=True)
    # Must return the OUTERMOST repo, not the nearest (inner).
    assert find_outermost_git_root(deep) == outer


# ---------------------------------------------------------------------------
# iter_agents_md_chain
# ---------------------------------------------------------------------------


def test_chain_yields_existing_in_range(tmp_path: Path) -> None:
    top = tmp_path / "top"
    mid = top / "mid"
    leaf = mid / "leaf"
    leaf.mkdir(parents=True)
    (top / "AGENTS.md").write_text("TOP", encoding="utf-8")
    (leaf / "AGENTS.md").write_text("LEAF", encoding="utf-8")
    # mid has no AGENTS.md.
    found = list(iter_agents_md_chain(leaf, top=top))
    assert (leaf / "AGENTS.md") in found
    assert (top / "AGENTS.md") in found
    assert (mid / "AGENTS.md") not in found


def test_chain_empty_when_none_exist(tmp_path: Path) -> None:
    top = tmp_path / "top"
    leaf = top / "leaf"
    leaf.mkdir(parents=True)
    assert list(iter_agents_md_chain(leaf, top=top)) == []
