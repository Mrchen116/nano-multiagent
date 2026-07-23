"""内置子 agent 类型目录（feat-474 M1 决策 1/2/3/5）。

真类型 = 工具 deny-list（相对父有效工具求交）+ 角色 `PromptSlotSeed` 的静态映射；
`AgentTool` 只编排（解析类型、算 deny 交集、传参），不内联长文案。

分层约束（design 决策 1）：本模块只依赖 core `agent.core.session.types.PromptSlotSeed` /
`PromptSlotText`，**禁止** `import agent.sdk`——角色文案走内核持久化的四槽种子，
不经公共会话唯一暴露的 sdk `PromptSlots`（`platform → core`，不允许 `platform → sdk`）。

角色文案语义参考实机 Claude Code 系统提示词摘录
（`docs/changes/feat-474-agent-tool-ergonomics/cc-subagent-system-prompts/*.md`），
按 nano 工具名（bash/read/write/edit/agent/skill_manage）重写，非逐字照抄。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agent.core.errors import ToolError
from agent.core.session.types import PromptSlotSeed, PromptSlotText

_TOOL_NAME = "agent"

# CC `disallowedTools` 同构：Explore/Plan 去掉一切会直接改仓库的写类工具，
# 以及会再派生子 agent / 改 skill 配置的工具（design 决策 2 起步 DENY）。
_READ_ONLY_DENY: frozenset[str] = frozenset({"write", "edit", "agent", "skill_manage"})


@dataclass(frozen=True, slots=True)
class SubagentTypeDefinition:
    """描述一个内置子 agent 类型的能力边界与角色文案。

    Args:
        name: 字面量类型名，区分大小写（与 CC 对齐，如 `Explore`/`Plan`）。
        when_to_use: 供 `agent` 工具 description 拼装的一句话适用场景摘要。
        disallowed_tools: 相对父有效工具集要去掉的工具名；`general-purpose` 为空集。
        role_prompt_seed: 写入子 session 的专属四槽种子（不含父产品 PromptSlots 副本）。
    """

    name: str
    when_to_use: str
    disallowed_tools: frozenset[str]
    role_prompt_seed: PromptSlotSeed


def _seed(identity: str, guidance: str) -> PromptSlotSeed:
    return PromptSlotSeed(
        head=(PromptSlotText(name="agent_type.identity", text=identity),),
        body=(PromptSlotText(name="agent_type.guidance", text=guidance),),
    )


_GENERAL_PURPOSE = SubagentTypeDefinition(
    name="general-purpose",
    when_to_use=(
        "General-purpose agent for complex, multi-step tasks that may need to "
        "modify files, run commands, or research across many files. Default when "
        "no other type fits."
    ),
    disallowed_tools=frozenset(),
    role_prompt_seed=_seed(
        "You are a sub-agent dispatched to complete a task fully and "
        "independently, then report back concisely.",
        "Complete the task fully - don't gold-plate it, but don't leave it "
        "half-done either. Search broadly when you don't know where something "
        "lives; read files directly when you already know the path. When you "
        "finish, respond with a concise report covering what was done and any "
        "key findings - the caller relays this to the user, so it only needs "
        "the essentials.",
    ),
)

_EXPLORE = SubagentTypeDefinition(
    name="Explore",
    when_to_use=(
        "Fast read-only agent for exploring the codebase: find files by pattern, "
        "search code for keywords, or answer 'where is X / what does Y do' "
        "questions. Cannot modify the repository."
    ),
    disallowed_tools=_READ_ONLY_DENY,
    role_prompt_seed=_seed(
        "You are a read-only file search specialist dispatched to explore the "
        "codebase.",
        "READ-ONLY MODE: you have no write/edit/agent/skill-management tools and "
        "must not attempt to modify the repository. Search broadly and quickly, "
        "then report your findings directly as your final message - do not write "
        "report files. Share relevant file paths (always absolute) and only "
        "include code snippets when the exact text is load-bearing.",
    ),
)

_PLAN = SubagentTypeDefinition(
    name="Plan",
    when_to_use=(
        "Read-only planning agent: explore the codebase and design an "
        "implementation approach, returning steps and key files. Cannot modify "
        "the repository."
    ),
    disallowed_tools=_READ_ONLY_DENY,
    role_prompt_seed=_seed(
        "You are a read-only software architect and planning specialist "
        "dispatched to design an implementation plan.",
        "READ-ONLY MODE: you have no write/edit/agent/skill-management tools and "
        "must not attempt to modify the repository. Explore thoroughly, then "
        "report a step-by-step implementation strategy ending with a short list "
        "of the critical files for implementation - do not write plan files, "
        "respond directly as your final message.",
    ),
)

# 注册顺序即 description / 错误文案的展示顺序（design 决策 5：稳定顺序，对齐 CC）。
_REGISTRY: tuple[SubagentTypeDefinition, ...] = (_GENERAL_PURPOSE, _EXPLORE, _PLAN)
_BY_NAME: dict[str, SubagentTypeDefinition] = {
    definition.name: definition for definition in _REGISTRY
}

DEFAULT_AGENT_TYPE_NAME = _GENERAL_PURPOSE.name


def iter_agent_types() -> tuple[SubagentTypeDefinition, ...]:
    """按注册顺序返回全部内置类型定义（供工具 description 拼装 whenToUse 摘要）。"""

    return _REGISTRY


def format_available_agents() -> str:
    """渲染未知类型错误信息复用的 'Available agents: …' 文案，顺序稳定。"""

    return "Available agents: " + ", ".join(
        definition.name for definition in _REGISTRY
    )


def resolve_agent_type(name: str | None) -> SubagentTypeDefinition:
    """解析 `subagent_type` 为内置类型定义。

    Args:
        name: 消费者传入的类型名；`None` 落缺省 `general-purpose`。

    Returns:
        匹配的类型定义。

    Raises:
        ToolError: 类型名未知或大小写不匹配（对齐 CC：直接失败，不静默降级）。
    """

    effective_name = name if name is not None else DEFAULT_AGENT_TYPE_NAME
    definition = _BY_NAME.get(effective_name)
    if definition is None:
        raise ToolError(
            f"Agent type '{effective_name}' not found. {format_available_agents()}",
            tool_name=_TOOL_NAME,
            details={"code": "unknown_agent_type", "requested": effective_name},
        )
    return definition


def apply_tool_deny(
    parent_tools: Sequence[str], disallowed: frozenset[str]
) -> list[str]:
    """从父有效工具集中去掉某类型的禁用工具，保持父集合原有顺序。"""

    return [name for name in parent_tools if name not in disallowed]


__all__ = [
    "DEFAULT_AGENT_TYPE_NAME",
    "SubagentTypeDefinition",
    "apply_tool_deny",
    "format_available_agents",
    "iter_agent_types",
    "resolve_agent_type",
]
