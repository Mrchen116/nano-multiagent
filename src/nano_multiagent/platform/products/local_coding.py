"""local_coding product profile: reproduces the current default coding CLI behavior.

This profile is the drop-in replacement for the ad-hoc assembly that was
previously done directly in server/app.py. It carries no new behavior — it
exists solely to make the current defaults explicit and portable so that
future products can diverge without touching the kernel.

Architecture note (M74 scope):
- session_store_policy / skill_search_policy are declared but not yet wired
  at bootstrap time (M75 will implement the store path logic).
- default_tool_ids=None means "activate all registered built-ins + workspace",
  which is the current platform default behavior.

Path resolution (M75):
- global_config_home: ~/.nanocode
- workspace_config_dirname: .nanocode
- compat_skill_roots includes ~/.codex/skills for users who keep skills there.
"""

from pathlib import Path

from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT

from nano_multiagent.platform.product import ProductProfile

LOCAL_CODING_PROFILE = ProductProfile(
    product_id="local_coding",
    display_name="Nano Coding CLI",
    # Global config: ~/.nanocode  Workspace config: <workspace>/.nanocode
    config_namespace="nanocode",
    # Coding-persona prompt; owned by this product, not the shared prompting layer.
    default_system_prompt=CODING_SYSTEM_PROMPT,
    # Explicit declaration; equivalent to the current "all builtins" but now
    # auditable.  Order mirrors registration order in tools/builtins/__init__.py.
    default_tool_ids=["read", "write", "edit", "bash", "task"],
    # Explicit declaration; module stems match hooks/builtins/*.py filenames.
    default_hook_modules=["bash_risk_gate", "default_status", "realtime_stream", "usage_metrics"],
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    safety_defaults={},
    capabilities={},
    # M75 path resolution fields.
    global_config_home=Path("~/.nanocode"),
    workspace_config_dirname=".nanocode",
    session_db_filename="sessions.sqlite3",
    # Backward-compat: users who stored skills at ~/.codex/skills still find them.
    compat_skill_roots=[Path("~/.codex/skills")],
)
