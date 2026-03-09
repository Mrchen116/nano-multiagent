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

_PERSONAL_ASSISTANT_SYSTEM_PROMPT = (
    "You are a helpful personal assistant. "
    "You help with scheduling, communication, information lookup, and general tasks. "
    "You are collaborative, concise, and friendly. "
    "You do not execute shell commands or modify files unless explicitly asked."
)

PERSONAL_ASSISTANT_PROFILE = ProductProfile(
    product_id="personal_assistant",
    display_name="Nano Personal Assistant",
    config_namespace="nanoassistant",
    # IM/collaboration-oriented prompt; distinct from the coding assistant persona.
    default_system_prompt=_PERSONAL_ASSISTANT_SYSTEM_PROMPT,
    # Conservative tool set: read for information, task for delegation.
    # No write/edit/bash — personal assistant does not modify files or run commands.
    default_tool_ids=["read", "task"],
    # No bash_risk_gate: personal_assistant has no bash tool to gate.
    default_hook_modules=["default_status", "usage_metrics"],
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    safety_defaults={},
    capabilities={"im": True, "heartbeat": True, "memory": True},
    # M75 path resolution fields.
    global_config_home=Path("~/.nanoassistant"),
    workspace_config_dirname=".nanoassistant",
    session_db_filename="sessions.sqlite3",
    # No compat skill roots: personal_assistant does not share ~/.codex/skills.
    compat_skill_roots=[],
)
