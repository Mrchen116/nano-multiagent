"""agent.sdk — the sole public surface for products embedding the agent kernel.

Products (coding_cli, personal_assistant) must import only from this package.
All other agent.* sub-packages are internal implementation detail.

Public API:
    build_kernel          — assemble a Kernel from configuration (2-layer surface)
    Kernel                — in-process agent kernel with async-native interface
    CanUseToolFn          — permission callback type alias
    Tool / ToolContext / HookAPI — SDK-owned extension-author Protocols (决策 2)
    PromptSlots / PromptText — per-session prompt slots (决策 8)
    LLMConfig / LLMProvider / LLMModel — SDK-owned LLM config (决策 5)
    SessionInfo / RunInfo — SDK-owned boundary DTOs (决策 6)
    ModelInfo / ToolInfo / FeatureInfo / SkillInfo — capability-query DTOs (决策 4)
    ToolPresenter / ToolPresentationEvent — tool presentation (决策 12)
    PermissionDecision    — decision returned from can_use_tool callback (C1 re-export)
    RunOrigin             — run origin enum (USER / GATEWAY / AGENT) (C1 re-export)
    TERMINAL_RUN_STATUSES — terminal run-status set (C1 re-export)
"""

from .kernel import CanUseToolFn, Kernel, build_kernel
from .contracts import HookAPI, Tool, ToolContext
from .dto import (
    FeatureInfo,
    LLMConfig,
    LLMModel,
    LLMProvider,
    ModelInfo,
    RunInfo,
    SessionInfo,
    SkillInfo,
    ToolInfo,
)
from .prompt import PromptSlots, PromptText
from agent.core.tools.presentation import ToolPresentationEvent, ToolPresenter
from agent.core.runs.origin import RunOrigin
from agent.core.runs.registry import TERMINAL_RUN_STATUSES
from agent.platform.permissions.broker import PermissionDecision

__all__ = [
    # Core kernel assembly
    "CanUseToolFn",
    "Kernel",
    "build_kernel",
    # 2-layer surface (refactor-406 决策 2/4/5/6/8)
    "Tool",
    "ToolContext",
    "HookAPI",
    "PromptSlots",
    "PromptText",
    "LLMConfig",
    "LLMProvider",
    "LLMModel",
    "SessionInfo",
    "RunInfo",
    "ModelInfo",
    "ToolInfo",
    "FeatureInfo",
    "SkillInfo",
    # Tool presentation (决策 12: core-owned pure-function types, sdk re-export, 闸2 豁免)
    "ToolPresenter",
    "ToolPresentationEvent",
    # Permission (C1: platform-owned, re-export, 闸2 豁免)
    "PermissionDecision",
    # Run origin and terminal statuses (C1: core-owned, re-export, 闸2 豁免)
    "RunOrigin",
    "TERMINAL_RUN_STATUSES",
]
