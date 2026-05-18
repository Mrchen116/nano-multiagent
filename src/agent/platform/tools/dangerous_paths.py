"""Dangerous file/directory constants and path safety check for tool-level permissions.

This module is the single source of truth for "sensitive path" detection used by
WriteTool and EditTool in their check_permissions implementations (bugfix-355 D5).

MAINTENANCE NOTE: DANGEROUS_DIRECTORIES includes .nanocode and .nano-assistant —
these are this repo's own config directories (declared in AGENTS.md). When new
persistent config directories are added to this project, update this set accordingly.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


# ---------------------------------------------------------------------------
# Sensitive file basenames — case-insensitive exact match on Path.name
#
# Derived from CC's DANGEROUS_FILES list (permissions.ts) with two omissions:
#   - .ripgreprc  → this repo doesn't use ripgrep
#   - .claude.json → CC main program config; no equivalent in this repo
# ---------------------------------------------------------------------------

DANGEROUS_FILES: frozenset[str] = frozenset(
    {
        ".gitconfig",
        ".gitmodules",
        ".bashrc",
        ".bash_profile",
        ".zshrc",
        ".zprofile",
        ".profile",
        ".mcp.json",
    }
)

# ---------------------------------------------------------------------------
# Sensitive directory path segments — case-insensitive exact match on any part
#
# CC baseline (4 items): .git, .vscode, .idea, .claude
# Repo-specific additions (2 items): .nanocode, .nano-assistant
#   → both are persistent config roots listed in AGENTS.md; writing to them
#     without confirmation is a prompt-injection persistence attack vector.
# ---------------------------------------------------------------------------

DANGEROUS_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git",
        ".vscode",
        ".idea",
        ".claude",
        ".nanocode",
        ".nano-assistant",
    }
)


def check_dangerous_path(file_path: str, *, cwd: Path | None = None) -> bool:
    """Return True if file_path resolves to a dangerous file or directory.

    Used by WriteTool and EditTool check_permissions to decide whether to
    require user confirmation even in dangerously_skip_permissions mode (W1).

    Resolution rules:
      1. Path(file_path).expanduser()  — expands ~
      2. If still relative and cwd given → cwd / path (absolute anchoring)
      3. No resolve() — avoids symlink traversal; CC also defers resolve to
         later permission stages. Matching runs on the unexpanded absolute path.
      4. basename(path).lower() matched against DANGEROUS_FILES (case-insensitive)
      5. Each path part .lower() matched against DANGEROUS_DIRECTORIES
      6. Special exemption: .claude segment is skipped when the *next* part is
         'worktrees' — matches CC AgentTool.tsx worktrees comment exemption.
         (.claude/skills/ is NOT exempt; only .claude/worktrees/ is.)

    Args:
        file_path: Raw path from tool input (~/foo, ./bar, /abs/path, or bare name).
        cwd: Used to convert relative paths to absolute; None leaves relative as-is.

    Returns:
        True if the path should require user confirmation.
    """
    path = Path(file_path).expanduser()

    # Anchor relative paths to cwd when provided
    if not path.is_absolute() and cwd is not None:
        path = cwd / path

    # --- Basename match (DANGEROUS_FILES) ---
    # Two rules (bugfix-355 M4 Issue #2 — reviewer major):
    #   1. Exact match: basename == dangerous_file (case-insensitive)
    #   2. Prefix match: basename startswith dangerous_file + "." (dot separator required)
    #      Covers backup/variant names like .bashrc.test.bak, .zshrc.bak.20260101.
    #      The dot separator prevents false positives like ".bashrcevil".
    basename_lower = path.name.lower()
    for dangerous_file in DANGEROUS_FILES:
        df_lower = dangerous_file.lower()
        if basename_lower == df_lower:
            return True
        # Prefix rule: must start with the dangerous filename followed by a dot
        # e.g. ".bashrc.bak" starts with ".bashrc." → dangerous
        if basename_lower.startswith(df_lower + "."):
            return True

    # --- Segment match (DANGEROUS_DIRECTORIES) ---
    # Iterate over path.parts to check each directory component
    parts = path.parts
    i = 0
    while i < len(parts):
        part_lower = parts[i].lower()
        if part_lower in {d.lower() for d in DANGEROUS_DIRECTORIES}:
            # Exemption: .claude/worktrees/ paths are safe (CC AgentTool worktrees exception)
            if part_lower == ".claude" and i + 1 < len(parts) and parts[i + 1].lower() == "worktrees":
                # Skip this .claude segment — it's a worktrees path, not config
                i += 2  # skip .claude and worktrees
                continue
            return True
        i += 1

    return False
