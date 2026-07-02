"""coding_cli's default kernel factory (refactor-406 决策 1/2/8).

This is the consumer-owned composition layer: coding_cli assembles its own
Kernel through ``agent.sdk.build_kernel`` (the product-neutral 2-layer surface),
supplying its tool catalog, hooks, permission callback, and per-session prompt
slots. The SDK has no notion of "local_coding" — it only sees ``build_kernel``
inputs. coding_cli imports **only** ``agent.sdk`` (module boundary hard rule).

The system-prompt text below is migrated verbatim from the legacy
``agent.products.local_coding.prompt_sections`` (lc.* segments) so the full
assembled prompt stays byte-identical to the refactor-406 golden baselines
(``test_full_system_prompt_byte_identical`` lc_full case). The kernel skeleton
owns the fixed section order; coding_cli supplies only the product-specific slot
text (identity / tools footer / guidelines).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.sdk import (
    LLMConfig,
    PromptSlots,
    PromptText,
    build_kernel,
)

# Per-workspace config dir governing session JSONL / memory / skill layout.
# Matches the legacy LOCAL_CODING_PROFILE.workspace_config_dirname (.nanocode).
WORKSPACE_CONFIG_DIRNAME = ".nanocode"

# Deployment-level skill search roots shared across CLI sessions (refactor-406-M3fix #6).
# The per-workspace root (<cwd>/.nanocode/skills) is added by the kernel from
# workspace_config_dirname; these are the global + compat roots, ported verbatim from
# the dissolved LOCAL_CODING_PROFILE (global_config_home ~/.nanocode + compat_skill_roots
# ~/.codex/skills). M2 补了 PA 的 skill_search_roots 但漏了 CLI 这同类——CLI 用户的
# ~/.codex/skills compat skill 因此丢失发现。
CLI_SKILL_SEARCH_ROOTS: tuple[Path, ...] = (
    Path("~/.nanocode/skills"),
    Path("~/.codex/skills"),
)

# Deployment-level user tool / hook plugin dirs (refactor-406-M3fix #2). Ported from
# the dissolved LOCAL_CODING_PROFILE user_tool_roots/user_hook_roots global layer
# (~/.nanocode/{tools,hooks}). Passed to build_kernel as tool_search_roots /
# hook_search_roots (consumer-supplied roots, no ConfigResolver); the kernel also scans
# the workspace <repo>/.nano/{tools,hooks} on top.
CLI_TOOL_SEARCH_ROOTS: tuple[Path, ...] = (Path("~/.nanocode/tools"),)
CLI_HOOK_SEARCH_ROOTS: tuple[Path, ...] = (Path("~/.nanocode/hooks"),)

# Default tool subset selected per session (mirrors legacy
# LOCAL_CODING_PROFILE default_tool_ids). bash/read/edit/write/agent/task_stop are
# registered as kernel built-ins by build_kernel; memory/skill_manage are
# supplied as path-resolved native objects via tools= (see build_cli_kernel).
DEFAULT_ENABLED_TOOLS = [
    "read",
    "write",
    "edit",
    "bash",
    "agent",
    "task_stop",
    "skill_manage",
    "skill_view",
    "memory",
]

# Self-evolution features always on for the CLI (parity with prior behaviour:
# memory + skill tools present → guidance segments render).
DEFAULT_FEATURES = {"memory_curation": True, "skill_creation": True}


# ---------------------------------------------------------------------------
# Verbatim lc.* prompt text (migrated from products/local_coding/prompt_sections)
# ---------------------------------------------------------------------------

_LC_IDENTITY_TEXT = (
    "You are an expert coding assistant operating inside a coding agent harness. "
    "You help users by reading files, executing commands, editing code, and writing new files."
)

_LC_TOOLS_FOOTER_TEXT = (
    "In addition to the tools above, you may have access to other custom tools "
    "depending on the project."
)

_LC_GUIDELINES_TEXT = (
    "Guidelines:\n"
    "- Use bash for file operations like ls, rg, find\n"
    "- Use read to examine files before editing. You must use this tool instead of cat or sed.\n"
    "- Use edit for precise changes (old text must match exactly)\n"
    "- Use write only for new files or complete rewrites\n"
    "- When summarizing your actions, output plain text directly - "
    "do NOT use cat or bash to display what you did\n"
    "- Be concise in your responses\n"
    "- Show file paths clearly when working with files"
)


def cli_prompt_slots() -> PromptSlots:
    """Build the CLI's per-session PromptSlots (决策 8).

    LC has no group chat / heartbeat / cron / custom prompt, so only the stable
    head (identity) and body (tools footer + guidelines) slots are populated. The
    kernel skeleton interleaves these with the core behaviour segments to
    reproduce the legacy assembly byte-for-byte.

    Returns:
        PromptSlots with head=[identity], body=[tools_footer, guidelines].
    """
    return PromptSlots(
        head=(PromptText(name="lc.identity", text=_LC_IDENTITY_TEXT),),
        body=(
            PromptText(name="lc.tools_footer", text=_LC_TOOLS_FOOTER_TEXT),
            PromptText(name="lc.guidelines", text=_LC_GUIDELINES_TEXT),
        ),
    )


def build_cli_kernel(
    *,
    llm: LLMConfig,
    can_use_tool: Any,
    repo_root: Path | None = None,
) -> Any:
    """Assemble coding_cli's Kernel via the 2-layer SDK surface (决策 1/2/5).

    coding_cli supplies no product-specific tools — its catalog is exactly the
    kernel built-ins (read/write/edit/bash/agent/task_stop/web_fetch + the
    self-evolution memory/skill_manage built-ins, 决策 3). The features
    {memory_curation, skill_creation} gate the self-evolution tools per session.

    Args:
        llm: SDK-owned LLM config (catalog + active connection).
        can_use_tool: Terminal y/n permission callback (process-level mechanism).
        repo_root: Workspace root for tool/skill discovery (defaults to cwd inside
            build_kernel).

    Returns:
        A ready-to-use Kernel.
    """
    resolved_root = (repo_root or Path.cwd()).expanduser().resolve()
    return build_kernel(
        llm=llm,
        tools=[],
        hooks=[],
        can_use_tool=can_use_tool,
        workspace_config_dirname=WORKSPACE_CONFIG_DIRNAME,
        repo_root=resolved_root,
        skill_search_roots=CLI_SKILL_SEARCH_ROOTS,  # #6: ~/.nanocode + ~/.codex compat
        tool_search_roots=CLI_TOOL_SEARCH_ROOTS,  # #2: ~/.nanocode/tools
        hook_search_roots=CLI_HOOK_SEARCH_ROOTS,  # #2: ~/.nanocode/hooks
    )


async def open_cli_session(kernel: Any, *, workspace_root: Path) -> Any:
    """Open a CLI session with the default tool subset, features and prompt slots.

    ``workspace_config_dirname`` is threaded into the session-metadata baseline by
    ``build_kernel`` (build-time deployment constant), so the runtime + MemoryTool
    derive the per-workspace memory root without this caller re-passing it.

    Args:
        kernel: Kernel from ``build_cli_kernel``.
        workspace_root: Session workspace root (CLI cwd).

    Returns:
        SessionInfo for the new session.
    """
    if hasattr(kernel, "run_skill_maintenance"):
        kernel.run_skill_maintenance(workspace_root=workspace_root)
    return await kernel.create_session(
        workspace_root=workspace_root,
        enabled_tools=list(DEFAULT_ENABLED_TOOLS),
        features=dict(DEFAULT_FEATURES),
        prompt=cli_prompt_slots(),
    )
