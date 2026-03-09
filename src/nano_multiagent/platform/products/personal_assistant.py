"""personal_assistant product profile: conversational assistant variant.

Provides a distinct product identity from local_coding, with its own config
directories so the two products cannot interfere with each other's sessions,
tools, hooks, or skills.

Architecture note:
- global_config_home: ~/.nanoassistant (distinct from ~/.nanocode)
- workspace_config_dirname: .nanoassistant (optional; workspace config is not
  required for a conversational assistant)
- No compat_skill_roots by default (personal_assistant does not inherit the
  Codex CLI skill convention; add explicitly if needed).
"""

from pathlib import Path

from nano_multiagent.platform.product import ProductProfile

PERSONAL_ASSISTANT_PROFILE = ProductProfile(
    product_id="personal_assistant",
    display_name="Nano Personal Assistant",
    config_namespace="nanoassistant",
    default_system_prompt=None,  # uses platform DEFAULT_SYSTEM_PROMPT
    default_tool_ids=None,
    default_hook_modules=None,
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    safety_defaults={},
    capabilities={},
    # M75 path resolution fields.
    global_config_home=Path("~/.nanoassistant"),
    workspace_config_dirname=".nanoassistant",
    session_db_filename="sessions.sqlite3",
    # No compat skill roots: personal_assistant does not share ~/.codex/skills.
    compat_skill_roots=[],
)
