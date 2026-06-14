"""R2 proof: kernel template skeleton + PromptSlots reproduces golden byte-for-byte.

refactor-406 决策 8: the kernel owns a product-neutral fixed-order template
skeleton; product text enters via four PromptSlots (head/body/custom/tail). This
test proves the new assembly path produces **exactly** the refactor-406 golden
baselines (locked in R1) for the full PA/LC scenario matrix.

It builds PromptSlots from the existing PA/LC segments (pre-gated by the same
enabled_when conditions the legacy assembly used) and assembles them through
``build_kernel_prompt_skeleton`` — proving the skeleton's slot placement matches
the legacy interleaved order to the byte. The real consumer factories
(coding_cli / personal_assistant) build the same slots in R5/R6; here we drive
the slots directly to isolate the skeleton-placement correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.core.agent.prompt_sections.base import PromptContext, assemble_system_prompt
from agent.core.agent.prompt_sections.skeleton import build_kernel_prompt_skeleton
from agent.core.types import ToolSpec
from agent.sdk.prompt import PromptSlots, PromptText

_GOLDEN_DIR = Path(__file__).parent / "golden_prompts"
_DT = "2026-01-01T00:00:00"
_CWD = "/workspace"


def _tool(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=f"{name} tool.", input_schema={})


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


def _ctx(tools, flags, *, scenario=None, custom="") -> PromptContext:
    return PromptContext(
        available_tools=tools,
        available_skills=(),
        current_datetime=_DT,
        cwd=_CWD,
        memory_block=None,
        flags=flags,
        scenario=scenario or {},
        vars={"custom_prompt": custom} if custom else {},
    )


def _piece(seg, ctx: PromptContext) -> PromptText | None:
    """Render a legacy PromptSection into a PromptText iff it is enabled."""
    if not seg.enabled_when(ctx):
        return None
    text = seg.render(ctx)
    if not text:
        return None
    return PromptText(name=seg.name, text=text)


def _collect(ctx: PromptContext, *segs) -> tuple[PromptText, ...]:
    return tuple(p for p in (_piece(s, ctx) for s in segs) if p is not None)


class _FakeAgent:
    """Duck-typed agent config for the PA prompt factory (mirrors prompt_for's reads)."""

    def __init__(self, *, cron_enabled: bool, heartbeat_enabled: bool, custom: str):
        self.cron_enabled = cron_enabled
        self.heartbeat_enabled = heartbeat_enabled
        self.custom_prompt = custom or None


def _pa_slots(ctx: PromptContext) -> PromptSlots:
    # refactor-406-M2: golden守的是 PA *生产* 路径（personal_assistant.product.prompt_for），
    # 不再是退役的 agent.products prompt_sections。flags/scenario/custom 映射成假想 agent
    # 喂给生产工厂——「预览=真实=golden」三者同源。
    from personal_assistant.product import prompt_for  # noqa: PLC0415

    flags = ctx.flags or {}
    agent = _FakeAgent(
        cron_enabled=bool(flags.get("cron_scheduling")),
        heartbeat_enabled=bool(flags.get("heartbeat")),
        custom=(ctx.vars or {}).get("custom_prompt", ""),
    )
    return prompt_for(agent, scenario=ctx.scenario or None)


def _lc_slots(ctx: PromptContext) -> PromptSlots:
    # refactor-406-M2: golden守 LC 生产路径（coding_cli.product.cli_prompt_slots）。
    from coding_cli.product import cli_prompt_slots  # noqa: PLC0415

    return cli_prompt_slots()


# case_name -> (ctx, slots-builder). Mirrors the golden matrix from R1.
def _cases() -> dict[str, tuple[PromptContext, PromptSlots]]:
    pa = lambda flags, **kw: _ctx(_PA_TOOLS, flags, **kw)  # noqa: E731
    cases: dict[str, tuple[PromptContext, PromptSlots]] = {}
    for name, ctx in {
        "pa_direct_basic": pa({}),
        "pa_cron_on": pa({"cron_scheduling": True}),
        "pa_heartbeat_on": pa({"heartbeat": True}),
        "pa_both_on": pa({"cron_scheduling": True, "heartbeat": True}),
        "pa_group": pa(
            {"memory_curation": True, "skill_creation": True},
            scenario=_GROUP_SCENARIO,
        ),
        "pa_custom": pa({}, custom="Be my legal advisor."),
    }.items():
        cases[name] = (ctx, _pa_slots(ctx))
    lc_ctx = _ctx(_LC_TOOLS, {})
    cases["lc_full"] = (lc_ctx, _lc_slots(lc_ctx))
    return cases


@pytest.mark.parametrize("case_name", sorted(_cases()))
def test_skeleton_plus_slots_reproduces_golden(case_name: str) -> None:
    """skeleton + PromptSlots assembly must equal the R1 golden byte-for-byte."""
    ctx, slots = _cases()[case_name]
    # Re-bind the slots onto the assembly context (prompt_slots carries product text).
    skel_ctx = PromptContext(
        available_tools=ctx.available_tools,
        available_skills=ctx.available_skills,
        current_datetime=ctx.current_datetime,
        cwd=ctx.cwd,
        memory_block=ctx.memory_block,
        flags=ctx.flags,
        scenario=ctx.scenario,
        vars=ctx.vars,
        prompt_slots=slots,
    )
    actual = assemble_system_prompt(build_kernel_prompt_skeleton(), skel_ctx)
    expected = (_GOLDEN_DIR / f"{case_name}.txt").read_text(encoding="utf-8")
    assert actual == expected, (
        f"kernel skeleton + PromptSlots for {case_name!r} drifted from golden "
        f"(决策 8 byte-identity broken)"
    )
