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
"""

from nano_multiagent.agent.prompting import DEFAULT_SYSTEM_PROMPT

from nano_multiagent.platform.product import ProductProfile

LOCAL_CODING_PROFILE = ProductProfile(
    product_id="local_coding",
    display_name="Nano Coding CLI",
    # Global config: ~/.nanocode  Workspace config: <workspace>/.nanocode
    config_namespace="nanocode",
    # Reproduce current DEFAULT_SYSTEM_PROMPT exactly so no behavioral change.
    default_system_prompt=DEFAULT_SYSTEM_PROMPT,
    # None = use all registered built-ins + workspace tools (current behavior).
    default_tool_ids=None,
    # None = load all built-in hooks + workspace hooks (current behavior).
    default_hook_modules=None,
    skill_search_policy="workspace",
    session_store_policy="sqlite",
    safety_defaults={},
    capabilities={},
)
