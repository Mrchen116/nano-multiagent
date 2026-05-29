"""Canonical profile for the personal_assistant product."""

from agent.products.base import ProductProfile

from .defaults import (
    CAPABILITIES,
    COMPAT_SKILL_ROOTS,
    CONFIG_NAMESPACE,
    GLOBAL_CONFIG_HOME,
    HEARTBEAT_LAYOUT,
    MEMORY_LAYOUT,
    SESSION_DB_FILENAME,
    WORKSPACE_CONFIG_DIRNAME,
)
from .hooks import DEFAULT_HOOK_MODULES
from .prompt_sections import PA_SECTIONS, build_pa_system_prompt
from .toolsets import DEFAULT_TOOL_IDS, OPTIONAL_TOOL_IDS

PERSONAL_ASSISTANT_PROFILE = ProductProfile(
    product_id="personal_assistant",
    display_name="Nano Personal Assistant",
    config_namespace=CONFIG_NAMESPACE,
    default_system_prompt="",  # empty string signals segment assembly; no monolithic f-string template
    prompt_sections=PA_SECTIONS,
    # M4 Decision 15/20: explicit assembly function replaces CORE+PA merge in bootstrap.
    prompt_sections_builder=build_pa_system_prompt,
    default_tool_ids=list(DEFAULT_TOOL_IDS),
    optional_tool_ids=list(OPTIONAL_TOOL_IDS),
    default_hook_modules=list(DEFAULT_HOOK_MODULES),
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    memory_layout=dict(MEMORY_LAYOUT),
    heartbeat_layout=dict(HEARTBEAT_LAYOUT),
    safety_defaults={},
    capabilities=dict(CAPABILITIES),
    global_config_home=GLOBAL_CONFIG_HOME,
    workspace_config_dirname=WORKSPACE_CONFIG_DIRNAME,
    session_db_filename=SESSION_DB_FILENAME,
    compat_skill_roots=list(COMPAT_SKILL_ROOTS),
)

__all__ = ["PERSONAL_ASSISTANT_PROFILE"]
