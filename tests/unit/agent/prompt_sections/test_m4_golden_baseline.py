"""M4 重构前 runtime 段式输出 golden 基线测试。

这批测试捕获重构前的 runtime 汇编输出，作为 behavior-preserving 基线。
M4 重构（决策 15–21）完成后，这些测试必须仍然全绿，证明 runtime 输出字节不变。

重构前行为摘要:
- banner 由 MemoryStore._render_block 产生（含 ══ 分隔线 + 标题 + 百分比），
  作为字符串注入 PromptContext.memory_block / user_profile_block 字段。
- core 段 render 直接透传该预渲染串（不负责 banner 格式）。

重构后（M4 目标）:
- MemoryStore 只返回数据（content + pct），不产 banner。
- banner 由 core 段 render 自包含生成，格式逐字等价（golden 守）。
- 这批测试验证最终 assemble 输出不变（对外行为 = 字节一致）。
"""
from __future__ import annotations

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.core_sections import CORE_SECTIONS
from agent.core.memory.store import MemoryStore, MemoryEntry, MemorySource
from agent.core.types import ToolSpec
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name}.", input_schema={})


BASIC_PA_TOOLS = tuple(
    _tool(n) for n in ["read", "write", "edit", "bash", "web_search", "web_fetch", "send_message", "memory"]
)


def _build_store_with_entries(
    *,
    memory_entries: list[str] | None = None,
    user_entries: list[str] | None = None,
) -> tuple[MemoryStore, Path]:
    """Build a MemoryStore with given entries; returns (store, tmp_dir).

    Caller should clean up tmp_dir. Uses tempfile so tests are hermetic.
    """
    tmp = Path(tempfile.mkdtemp())
    store = MemoryStore(memory_root=tmp)
    src = MemorySource(session_id="test-session", timestamp=0.0)
    for text in (memory_entries or []):
        store.add("memory", MemoryEntry(text=text, source=src))
    for text in (user_entries or []):
        store.add("user", MemoryEntry(text=text, source=src))
    return store, tmp


# ---------------------------------------------------------------------------
# R1: Banner 格式基线 — MemoryStore 产出 banner 的格式契约
# ---------------------------------------------------------------------------

class TestMemoryStoreBannerFormat:
    """验证 MemoryStore._render_block 产出的 banner 格式，作为 M4 迁移基线。

    M4 后 banner 生成移进 core 段；格式必须与这里相同（逐字节一致）。
    """

    def test_memory_banner_separator_chars(self):
        """banner 使用 46 个 ═ 字符作为分隔线。"""
        store, tmp = _build_store_with_entries(memory_entries=["some fact"])
        block = store.format_for_prompt("memory")
        assert block is not None
        sep = "═" * 46
        assert block.startswith(sep), f"Expected banner to start with 46 ═ chars, got: {block[:60]!r}"

    def test_memory_banner_title_line(self):
        """memory banner 标题行: 'MEMORY (your personal notes) [pct]'。"""
        store, tmp = _build_store_with_entries(memory_entries=["fact1", "fact2"])
        block = store.format_for_prompt("memory")
        assert block is not None
        assert "MEMORY (your personal notes)" in block

    def test_memory_banner_structure(self):
        """banner 结构: sep\\ntitle [pct]\\nsep\\ncontent。"""
        store, tmp = _build_store_with_entries(memory_entries=["test entry"])
        block = store.format_for_prompt("memory")
        assert block is not None
        sep = "═" * 46
        lines = block.split("\n")
        assert lines[0] == sep
        assert lines[1].startswith("MEMORY (your personal notes)")
        assert lines[2] == sep
        # Content follows
        assert "test entry" in block

    def test_user_profile_banner_title_line(self):
        """user banner 标题行: 'USER PROFILE (who the user is) [pct]'。"""
        store, tmp = _build_store_with_entries(user_entries=["Alice is a developer"])
        block = store.format_for_prompt("user")
        assert block is not None
        assert "USER PROFILE (who the user is)" in block

    def test_empty_store_returns_none(self):
        """空 store 返回 None（feat-385 I1 fix）。"""
        store, tmp = _build_store_with_entries()
        assert store.format_for_prompt("memory") is None
        assert store.format_for_prompt("user") is None

    def test_banner_pct_format(self):
        """banner 标题含 '[N%' 格式的百分比。"""
        store, tmp = _build_store_with_entries(memory_entries=["some fact"])
        block = store.format_for_prompt("memory")
        assert block is not None
        # Should contain pct like [3% — 40/2,200 chars] or similar
        assert "%" in block
        assert "chars]" in block


# ---------------------------------------------------------------------------
# R1: Runtime assembly golden — banner 注入后的汇编输出快照
# ---------------------------------------------------------------------------

class TestRuntimeAssemblyBannerGolden:
    """验证 banner 注入进 PromptContext 后，runtime 汇编输出包含完整 banner。

    重构后（M4）：banner 由 core 段自生成，最终汇编输出字节一致。
    这批测试保证 banner 在最终 prompt 中的位置和内容不变。
    """

    def _assemble_with_memory(
        self,
        memory_block: str | None = None,
        user_profile_block: str | None = None,
    ) -> str:
        # Use only CORE_SECTIONS — cache_safe invariant is preserved within core.
        # PA segments are not needed for these banner-position golden tests.
        # (M4 R4 will introduce build_pa_system_prompt() which provides the
        # correct full ordering; tests involving PA content will be updated then.)
        ctx = PromptContext(
            available_tools=BASIC_PA_TOOLS,
            available_skills=(),
            current_datetime="2026-01-01T00:00:00",
            cwd="/workspace",
            memory_block=memory_block,
            user_profile_block=user_profile_block,
            flags={"memory_curation": True},
            scenario={},
            vars={},
        )
        return assemble_system_prompt(list(CORE_SECTIONS), ctx)

    def test_memory_banner_appears_in_assembled_prompt(self):
        """memory banner（含 ═ 分隔线 + 标题行）出现在汇编输出中。"""
        sep = "═" * 46
        banner = f"{sep}\nMEMORY (your personal notes) [37% — 814/2,200 chars]\n{sep}\nsome fact"
        result = self._assemble_with_memory(memory_block=banner)
        assert sep in result
        assert "MEMORY (your personal notes)" in result
        assert "some fact" in result

    def test_user_profile_banner_appears_in_assembled_prompt(self):
        """user profile banner（含 ═ 分隔线 + 标题行）出现在汇编输出中。"""
        sep = "═" * 46
        banner = f"{sep}\nUSER PROFILE (who the user is) [20% — 200/1,375 chars]\n{sep}\nAlice is dev"
        result = self._assemble_with_memory(user_profile_block=banner)
        assert "USER PROFILE (who the user is)" in result
        assert "Alice is dev" in result

    def test_memory_after_other_stable_sections(self):
        """memory_block 段出现在 runtime_footer 之后（volatile 尾部）。"""
        sep = "═" * 46
        banner = f"{sep}\nMEMORY (your personal notes) [5% — 100/2,200 chars]\n{sep}\ntest note"
        result = self._assemble_with_memory(memory_block=banner)
        # runtime footer comes before memory block (volatile tail)
        footer_idx = result.find("Current date and time:")
        memory_idx = result.find("MEMORY (your personal notes)")
        assert memory_idx > footer_idx, (
            f"memory_block must appear after runtime_footer: memory@{memory_idx} footer@{footer_idx}"
        )

    def test_user_profile_after_memory_block(self):
        """user_profile_block 段出现在 memory_block 之后（order 960 > 950）。"""
        sep = "═" * 46
        mem_banner = f"{sep}\nMEMORY (your personal notes) [5% — 100/2,200 chars]\n{sep}\nmem fact"
        user_banner = f"{sep}\nUSER PROFILE (who the user is) [3% — 50/1,375 chars]\n{sep}\nuser fact"
        result = self._assemble_with_memory(memory_block=mem_banner, user_profile_block=user_banner)
        memory_idx = result.find("MEMORY (your personal notes)")
        user_idx = result.find("USER PROFILE (who the user is)")
        assert user_idx > memory_idx, (
            f"user_profile_block must appear after memory_block: user@{user_idx} mem@{memory_idx}"
        )

    def test_no_banner_when_memory_block_none(self):
        """memory_block=None 时 banner 不出现（段失活）。"""
        result = self._assemble_with_memory(memory_block=None)
        assert "MEMORY (your personal notes)" not in result

    def test_no_user_profile_when_none(self):
        """user_profile_block=None 时 banner 不出现。"""
        result = self._assemble_with_memory(user_profile_block=None)
        assert "USER PROFILE (who the user is)" not in result

    def test_banner_separator_exact_46_chars(self):
        """banner 分隔线精确 46 个 ═ 字符（M4 迁移后需保持一致）。"""
        sep = "═" * 46
        banner = f"{sep}\nMEMORY (your personal notes) [5%]\n{sep}\nfact"
        result = self._assemble_with_memory(memory_block=banner)
        # Separator appears in the result
        assert sep in result, "46-char ═ separator must be present in assembled prompt"

    def test_end_to_end_with_real_memory_store(self):
        """End-to-end：MemoryStore 产出 banner → 注入 ctx → 汇编包含 banner。"""
        store, tmp = _build_store_with_entries(memory_entries=["User prefers Python 3.12"])
        memory_block = store.format_for_prompt("memory")
        assert memory_block is not None  # pre-condition

        result = self._assemble_with_memory(memory_block=memory_block)
        assert "MEMORY (your personal notes)" in result
        assert "User prefers Python 3.12" in result
        sep = "═" * 46
        assert sep in result
