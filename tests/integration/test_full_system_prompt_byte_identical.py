"""Full system-prompt byte-identical golden tests (refactor-406 risk 1 防线).

设计风险 1：cron/heartbeat/群聊三段从内核 segment 迁到 PA 的 PromptSlots，模板装配
改造；目标是**逐字节复现现状**，任何措辞/顺序/位置漂移都破坏 K2.6 HEARTBEAT_OK 反射
规避、bugfix-358 mention 格式与 provider 前缀缓存。

这批 golden 在 refactor-406 重构**之前**录制（基线 = 重构前完整 system prompt 快照），
存为 golden_prompts/*.txt。重构（PromptSlots 四槽 + 内核模板骨架）完成后，同一场景矩阵
经新装配路径产出的完整 prompt 必须与这些 golden 文件**逐字节一致**。

测试矩阵覆盖 design 退出标准要求的「PA 群聊/heartbeat/cron 各配置 + CLI 完整 system prompt」：
- PA cron 开 / heartbeat 开 / 两者都开（cron_routing 段）/ 群聊 / custom_prompt / 基础直聊
- LC 完整（memory + skill 工具）/ LC 基础

`_assemble_full_prompt(case)` 是装配 seam：R1 走重构前路径（build_<product>_system_prompt
+ assemble_system_prompt）；后续 roadpoint 把它内部改走内核模板骨架 + PromptSlots，但
golden 字节冻结不动——这正是「逐字节等价」的可执行守卫。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.types import ToolSpec

_GOLDEN_DIR = Path(__file__).parent / "golden_prompts"


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} tool.", input_schema={})


# Representative full toolsets (stable across the refactor; tool list itself is
# not under test here — the assembled prompt bytes are).
_PA_TOOLS = tuple(
    _tool(n)
    for n in [
        "read",
        "write",
        "edit",
        "bash",
        "web_search",
        "web_fetch",
        "send_message",
        "memory",
        "skill_manage",
        "agent",
        "cron",
    ]
)
_LC_TOOLS = tuple(
    _tool(n)
    for n in ["read", "write", "edit", "bash", "agent", "memory", "skill_manage"]
)

_GROUP_SCENARIO = {
    "conversation_type": "group",
    "agent_id": "agent-123",
    "participants": [
        {"type": "user", "user_id": "user-abc", "display_name": "Alice"},
        {"type": "agent", "agent_id": "agent-123", "display_name": "BotB"},
    ],
    "participant_agent_ids": ["agent-123"],
}

# Stable runtime values so the volatile footer (datetime/cwd) is deterministic.
_DT = "2026-01-01T00:00:00"
_CWD = "/workspace"


def _pa_ctx(
    flags: dict, *, scenario: dict | None = None, custom: str = ""
) -> PromptContext:
    return PromptContext(
        available_tools=_PA_TOOLS,
        available_skills=(),
        current_datetime=_DT,
        cwd=_CWD,
        memory_block=None,
        flags=flags,
        scenario=scenario or {},
        vars={"custom_prompt": custom} if custom else {},
    )


def _lc_ctx() -> PromptContext:
    return PromptContext(
        available_tools=_LC_TOOLS,
        available_skills=(),
        current_datetime=_DT,
        cwd=_CWD,
        memory_block=None,
        flags={},
        scenario={},
        vars={},
    )


# Scenario matrix: case_name -> (product, PromptContext).
# Product/context fully determine the assembled prompt for the seam below.
_CASES: dict[str, tuple[str, PromptContext]] = {
    "pa_direct_basic": ("pa", _pa_ctx({})),
    "pa_cron_on": ("pa", _pa_ctx({"cron_scheduling": True})),
    "pa_heartbeat_on": ("pa", _pa_ctx({"heartbeat": True})),
    "pa_both_on": ("pa", _pa_ctx({"cron_scheduling": True, "heartbeat": True})),
    "pa_group": (
        "pa",
        _pa_ctx(
            {"memory_curation": True, "skill_creation": True},
            scenario=_GROUP_SCENARIO,
        ),
    ),
    "pa_custom": ("pa", _pa_ctx({}, custom="Be my legal advisor.")),
    "lc_full": ("lc", _lc_ctx()),
}


def _assemble_full_prompt(product: str, ctx: PromptContext) -> str:
    """Assemble the full system prompt for one case.

    This is the refactor seam: it currently drives the pre-refactor assembly
    (product build_<product>_system_prompt + assemble_system_prompt). Later
    roadpoints re-wire the internals to go through the kernel template skeleton
    + PromptSlots; the produced bytes must stay identical to the golden files.
    """
    if product == "pa":
        from agent.products.personal_assistant.prompt_sections import (  # noqa: PLC0415
            build_pa_system_prompt,
        )

        sections = build_pa_system_prompt()
    elif product == "lc":
        from agent.products.local_coding.prompt_sections import (  # noqa: PLC0415
            build_lc_system_prompt,
        )

        sections = build_lc_system_prompt()
    else:  # pragma: no cover - guard
        raise ValueError(f"unknown product {product!r}")
    return assemble_system_prompt(sections, ctx)


@pytest.mark.parametrize("case_name", sorted(_CASES))
def test_full_system_prompt_byte_identical(case_name: str) -> None:
    """Assembled full prompt must equal the committed golden byte-for-byte."""
    product, ctx = _CASES[case_name]
    actual = _assemble_full_prompt(product, ctx)
    golden_path = _GOLDEN_DIR / f"{case_name}.txt"
    assert golden_path.is_file(), (
        f"missing golden {golden_path}; regenerate with the R1 capture harness"
    )
    expected = golden_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"full system prompt for {case_name!r} drifted from golden baseline "
        f"(refactor-406 risk 1: byte-identical preservation broken)"
    )
