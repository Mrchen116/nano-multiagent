"""agent.sdk — the sole public surface for products embedding the agent kernel.

Products (coding_cli, personal_assistant) must import only from this package.
All other agent.* sub-packages are internal implementation detail.

Public API:
    build_kernel          — assemble a Kernel from configuration
    Kernel                — in-process agent kernel with async-native interface
    CanUseToolFn          — permission callback type alias
    PermissionDecision    — decision returned from can_use_tool callback
    LLMFactoryConfig      — LLM connection configuration for build_kernel
    LLMConfigPayload      — LLM config payload (from gateway config)
    LLMModelPayload       — model entry in LLMConfigPayload
    LLMProviderPayload    — provider entry in LLMConfigPayload
    LOCAL_CODING_PROFILE  — default product profile for coding_cli
    PERSONAL_ASSISTANT_PROFILE — default product profile for personal_assistant
    RunOrigin             — run origin enum (USER / GATEWAY / AGENT)

Extended surface for personal_assistant (reporter / upstream_reporter):
    init_model_registry         — initialize LLM model registry from config
    get_default_model           — default model name for a provider
    get_default_provider        — default provider name
    list_provider_models        — enumerate models for a provider
    list_supported_providers    — enumerate all supported providers
    SkillRegistry               — skill metadata registry
    default_skill_search_roots  — default skill search root directories
    ConfigResolver              — workspace/global config directory resolver
"""

from .kernel import CanUseToolFn, Kernel, build_kernel
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from agent.core.llm.model_registry import (
    init_model_registry,
    get_default_model,
    get_default_provider,
    list_provider_models,
    list_supported_providers,
)
from agent.core.runs.origin import RunOrigin
from agent.core.skills.discovery import default_skill_search_roots
from agent.core.skills.registry import SkillRegistry
from agent.core.agent.prompt_sections.feature_registry import FEATURE_REGISTRY
from agent.platform.config.resolver import ConfigResolver
from agent.platform.permissions.broker import PermissionDecision
from agent.products.local_coding import LOCAL_CODING_PROFILE
from agent.products.personal_assistant import PERSONAL_ASSISTANT_PROFILE

__all__ = [
    # Core kernel assembly
    "CanUseToolFn",
    "Kernel",
    "LLMFactoryConfig",
    "build_kernel",
    # Permission
    "PermissionDecision",
    # LLM config
    "LLMConfigPayload",
    "LLMModelPayload",
    "LLMProviderPayload",
    # LLM model registry
    "init_model_registry",
    "get_default_model",
    "get_default_provider",
    "list_provider_models",
    "list_supported_providers",
    # Run origin
    "RunOrigin",
    # Skills
    "default_skill_search_roots",
    "SkillRegistry",
    # Config
    "ConfigResolver",
    # Prompt sections feature registry
    "FEATURE_REGISTRY",
    # Product profiles
    "LOCAL_CODING_PROFILE",
    "PERSONAL_ASSISTANT_PROFILE",
]
