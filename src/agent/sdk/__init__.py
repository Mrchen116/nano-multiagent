"""agent.sdk — the sole public surface for products embedding the agent kernel.

Products (coding_cli, personal_assistant) must import only from this package.
All other agent.* sub-packages are internal implementation detail.

Public API:
    build_kernel        — assemble a Kernel from configuration
    Kernel              — in-process agent kernel with async-native interface
    CanUseToolFn        — permission callback type alias
    PermissionDecision  — decision returned from can_use_tool callback
    LLMFactoryConfig    — LLM connection configuration for build_kernel
    LOCAL_CODING_PROFILE  — default product profile for coding_cli
"""

from .kernel import CanUseToolFn, Kernel, build_kernel
from agent.core.llm.factory import LLMFactoryConfig
from agent.platform.permissions.broker import PermissionDecision
from agent.products.local_coding import LOCAL_CODING_PROFILE

__all__ = [
    "CanUseToolFn",
    "Kernel",
    "LLMFactoryConfig",
    "LOCAL_CODING_PROFILE",
    "PermissionDecision",
    "build_kernel",
]
