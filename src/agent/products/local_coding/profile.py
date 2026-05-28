"""Canonical profile for the local_coding product."""

from agent.products.base import ProductProfile

from .defaults import (
    COMPAT_SKILL_ROOTS,
    CONFIG_NAMESPACE,
    GLOBAL_CONFIG_HOME,
    HEARTBEAT_LAYOUT,
    MEMORY_LAYOUT,
    SESSION_DB_FILENAME,
    WORKSPACE_CONFIG_DIRNAME,
)
from .hooks import DEFAULT_HOOK_MODULES
from .prompt_sections import LC_SECTIONS
from .toolsets import DEFAULT_TOOL_IDS, OPTIONAL_TOOL_IDS

LOCAL_CODING_PROFILE = ProductProfile(
    product_id="local_coding",
    display_name="Nano Coding CLI",
    config_namespace=CONFIG_NAMESPACE,
    default_system_prompt="",  # decision 11: segment assembly replaces f-string template
    prompt_sections=LC_SECTIONS,
    default_tool_ids=list(DEFAULT_TOOL_IDS),
    optional_tool_ids=list(OPTIONAL_TOOL_IDS),
    default_hook_modules=list(DEFAULT_HOOK_MODULES),
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    memory_layout=dict(MEMORY_LAYOUT),
    heartbeat_layout=dict(HEARTBEAT_LAYOUT),
    safety_defaults={},
    capabilities={},
    global_config_home=GLOBAL_CONFIG_HOME,
    workspace_config_dirname=WORKSPACE_CONFIG_DIRNAME,
    session_db_filename=SESSION_DB_FILENAME,
    compat_skill_roots=list(COMPAT_SKILL_ROOTS),
)

__all__ = ["LOCAL_CODING_PROFILE"]
