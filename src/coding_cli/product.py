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
    MemoryTool,
    PromptSlots,
    PromptText,
    SkillManageTool,
    SkillRegistry,
    build_kernel,
    default_skill_search_roots,
)

# Per-workspace config dir governing session JSONL / memory / skill layout.
# Matches the legacy LOCAL_CODING_PROFILE.workspace_config_dirname (.nanocode).
WORKSPACE_CONFIG_DIRNAME = ".nanocode"

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


def _build_self_evolution_tools(*, repo_root: Path) -> list[Any]:
    """Instantiate the path-resolved self-evolution tools (memory / skill_manage).

    These two built-ins need constructor-time path arguments, so the kernel does
    not auto-register them; the consumer factory resolves the workspace skill root
    and supplies the native objects via build_kernel(tools=…) (决策 2). Mirrors the
    legacy bootstrap self-evolution wiring (platform/bootstrap.py).

    Args:
        repo_root: Workspace/repository root for skill discovery.

    Returns:
        [SkillManageTool, MemoryTool] native tool objects.
    """
    skill_registry = SkillRegistry(
        search_roots=default_skill_search_roots(workspace_root=repo_root)
    )
    # Skill writes land in the workspace's per-config skills dir; mirrors the
    # legacy bootstrap which prefers the workspace skill root.
    skill_root = repo_root / WORKSPACE_CONFIG_DIRNAME / "skills"
    return [
        SkillManageTool(skill_root=skill_root, registry=skill_registry),
        # MemoryTool derives memory_root per-session from workspace_root +
        # workspace_config_dirname (threaded via create_session metadata).
        MemoryTool(),
    ]


def build_cli_kernel(
    *,
    llm: LLMConfig,
    can_use_tool: Any,
    repo_root: Path | None = None,
) -> Any:
    """Assemble coding_cli's Kernel via the 2-layer SDK surface (决策 1/2/5).

    Args:
        llm: SDK-owned LLM config (catalog + active connection). Built by the
            caller from env / CLI args via ``LLMConfig.from_payload`` /
            ``LLMConfig.from_env``.
        can_use_tool: Terminal y/n permission callback (process-level mechanism).
        repo_root: Workspace root for tool/skill discovery (defaults to cwd inside
            build_kernel).

    Returns:
        A ready-to-use Kernel.
    """
    resolved_root = (repo_root or Path.cwd()).expanduser().resolve()
    return build_kernel(
        llm=llm,
        tools=_build_self_evolution_tools(repo_root=resolved_root),
        hooks=[],
        can_use_tool=can_use_tool,
        workspace_config_dirname=WORKSPACE_CONFIG_DIRNAME,
        repo_root=resolved_root,
    )


async def open_cli_session(kernel: Any, *, workspace_root: Path) -> Any:
    """Open a CLI session with the default tool subset, features and prompt slots.

    Threads ``workspace_config_dirname`` into session metadata so the runtime and
    MemoryTool derive the per-workspace memory root correctly (parity with the
    legacy bootstrap default_session_metadata).

    Args:
        kernel: Kernel from ``build_cli_kernel``.
        workspace_root: Session workspace root (CLI cwd).

    Returns:
        SessionInfo for the new session.
    """
    return await kernel.create_session(
        workspace_root=workspace_root,
        enabled_tools=list(DEFAULT_ENABLED_TOOLS),
        features=dict(DEFAULT_FEATURES),
        prompt=cli_prompt_slots(),
        metadata={"workspace_config_dirname": WORKSPACE_CONFIG_DIRNAME},
    )
