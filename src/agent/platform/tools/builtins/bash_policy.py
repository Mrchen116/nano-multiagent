"""Bash command policy layer — strategy for BashTool permission decisions.

This module owns the single authoritative command policy for bash execution.
Policy is checked exactly once per tool call, at BashTool.check_permissions
(called by auto_mode_gate hook). Neither BashTool.run nor shell_runner
performs a second check — trusting the hook's decision (D10 single-point
principle).

Known gap: prefix-level precision only (not CC's full flag-level validator
from readOnlyValidation.ts). Flag-level precision (e.g. blocking
``git log --output=/file``) is tracked as a future unit. This module's
docstring is the canonical notice for that work.

Policy entry point for bypasses: any caller that directly runs bash commands
WITHOUT going through ToolRegistry.execute (and therefore skips the hook)
MUST call check_command_policy manually and respect the result.
"""

from __future__ import annotations

import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from agent.core.errors import ToolError


# ---------------------------------------------------------------------------
# Policy constants (D9 — prefix-level precision, per CC isReadOnly alignment)
# ---------------------------------------------------------------------------

# True read-only command prefixes. Each entry is a complete prefix that, when
# matched against the lowercased segment, indicates no filesystem side-effects.
# Multi-token prefixes (e.g. "git status") are checked with boundary awareness:
# the segment must be equal to the prefix or the next char must be whitespace
# or a shell separator.
#
# Removed vs. previous ToolSafetyConfig.bash_allowed_prefixes (D9 rationale):
#   - "bash"   → executes arbitrary scripts → review
#   - "pytest" → arbitrary fixture side-effects → review
#   - "sed"    → sed -i modifies files → review (whole command, not just -i)
#   - "sleep"  → not a retrieval operation → review
#   - "python" / "python3" (bare) → executes arbitrary scripts → review
#   - "git"    (bare) → write subcommands (push/commit/reset) → review
#
# Added (sub-command precision, per CC GIT_READ_ONLY_COMMANDS):
#   - git status / log / diff / show / branch / config / rev-parse / ls-files /
#     blame / tag / describe / remote / stash list
#
# Added (interpreter version flags only, anchored — per CC readOnlyValidation.ts):
#   - python --version / python -V / python3 --version / python3 -V
BASH_ALLOWED_PREFIXES: tuple[str, ...] = (
    "cat",
    "command -v",
    "echo",
    "false",
    "head",
    "ls",
    "pwd",
    "rg",
    "tail",
    "true",
    "wc",
    # git read-only subcommands (mirrors CC GIT_READ_ONLY_COMMANDS)
    "git status",
    "git log",
    "git diff",
    "git show",
    "git branch",
    "git config",
    "git rev-parse",
    "git ls-files",
    "git blame",
    "git tag",
    "git describe",
    "git remote",
    "git stash list",
    # interpreter version queries only — anchored prefix prevents
    # "python3 file.py" from matching (next char after "-V" must be space/sep)
    "python --version",
    "python -V",
    "python3 --version",
    "python3 -V",
)

# Hard-deny: base-command token match (not substring).
# Mirrors CC bashSecurity.ts ZSH_DANGEROUS_COMMANDS set semantics.
# Deviations from CC (narrow): mkfs/reboot/shutdown/halt/poweroff are
# hard-denied here because a dev agent has zero legitimate use; CC routes
# them through classifier, but the classifier round-trip cost is unjustified
# for commands that are universally destructive in a dev context.
BASH_BLOCKED_COMMANDS: tuple[str, ...] = (
    "mkfs",
    "reboot",
    "shutdown",
    "halt",
    "poweroff",
    "zmodload",
    "emulate",
    "ztcp",
    "zsocket",
    "zpty",
    "sysopen",
    "sysread",
    "syswrite",
    "sysseek",
    "zf_rm",
    "zf_mv",
    "zf_ln",
    "zf_chmod",
    "zf_chown",
    "zf_mkdir",
    "zf_rmdir",
    "zf_chgrp",
    "mapfile",
)

# Structural-syntax fragment (substring match). Reserved for shell constructs
# without a base command. Fork-bomb function literal ":(){" is the canonical
# example — it is a function definition, not an executable, so base-command
# matching cannot catch it.
BASH_BLOCKED_FRAGMENTS: tuple[str, ...] = (
    ":(){",
)


# ---------------------------------------------------------------------------
# Configuration override (from .nano/policy.toml — backward compat, Anchor R)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BashPolicyOverrides:
    """User overrides loaded from .nano/policy.toml [tool_safety.bash_policy].

    Fields are None when the corresponding TOML key is absent, meaning the
    module-level default constant is used instead.
    """

    allow_prefixes: tuple[str, ...] | None = None
    blocked_commands: tuple[str, ...] | None = None
    blocked_fragments: tuple[str, ...] | None = None


def load_bash_policy_overrides(repo_root: Path) -> BashPolicyOverrides:
    """Load optional .nano/policy.toml overrides for bash policy.

    TOML path: .nano/policy.toml
    Recognized tables (in priority order):
      1. [tool_safety.bash_policy]   — canonical new-style key
      2. [bash]                       — legacy flat key (backward compat)

    Recognized keys within the table:
      allow_prefixes  → BashPolicyOverrides.allow_prefixes
      deny_commands   → BashPolicyOverrides.blocked_commands
      deny_fragments  → BashPolicyOverrides.blocked_fragments
    """
    policy_path = (repo_root / ".nano" / "policy.toml").expanduser().resolve()
    if not policy_path.is_file():
        return BashPolicyOverrides()

    loaded = tomllib.loads(policy_path.read_text(encoding="utf-8"))
    table = _read_bash_policy_table(loaded)
    if not table:
        return BashPolicyOverrides()

    return BashPolicyOverrides(
        allow_prefixes=_read_optional_string_tuple(table.get("allow_prefixes")),
        blocked_commands=_read_optional_string_tuple(table.get("deny_commands")),
        blocked_fragments=_read_optional_string_tuple(table.get("deny_fragments")),
    )


# ---------------------------------------------------------------------------
# Policy decision
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CommandPolicyDecision:
    """Policy classification result for a shell command."""

    status: Literal["allowed", "denied", "review"]
    details: Mapping[str, Any]


def check_command_policy(
    command: str,
    *,
    overrides: BashPolicyOverrides | None = None,
) -> CommandPolicyDecision:
    """Classify a shell command as allowed / denied / review.

    Decision order:
      1. Fragment denylist (substring): immediate deny (fork-bomb etc.)
      2. Parse check: unparseable command → ToolError (caller should surface)
      3. Base-command denylist (token): immediate deny per segment
      4. Prefix allowlist (multi-token boundary): all segments must match → allowed
      5. Otherwise: review (classifier will decide)

    Args:
        command: Raw command string as received from the model.
        overrides: Optional user overrides from .nano/policy.toml; if None,
                   module-level constants are used.
    """
    if overrides is not None:
        allowed_prefixes = overrides.allow_prefixes if overrides.allow_prefixes is not None else BASH_ALLOWED_PREFIXES
        blocked_commands = overrides.blocked_commands if overrides.blocked_commands is not None else BASH_BLOCKED_COMMANDS
        blocked_fragments = overrides.blocked_fragments if overrides.blocked_fragments is not None else BASH_BLOCKED_FRAGMENTS
    else:
        allowed_prefixes = BASH_ALLOWED_PREFIXES
        blocked_commands = BASH_BLOCKED_COMMANDS
        blocked_fragments = BASH_BLOCKED_FRAGMENTS

    normalized = command.strip().lower()

    # Step 1: Fragment denylist (structural shell constructs)
    for fragment in blocked_fragments:
        if fragment in normalized:
            return CommandPolicyDecision(
                status="denied",
                details={"blocked_fragment": fragment},
            )

    # Step 2: Parse check — shlex.split with posix=True; raises ToolError on
    # failure so the caller (BashTool.check_permissions) surfaces it to the
    # hook as an error rather than silently passing or denying.
    _ensure_command_parseable(command)

    # Step 3: Per-segment base-command denylist
    blocked_set = {cmd.lower() for cmd in blocked_commands}
    for segment in _split_and_segments(command):
        base_cmd = _extract_base_command(segment)
        if base_cmd and base_cmd in blocked_set:
            return CommandPolicyDecision(
                status="denied",
                details={"blocked_command": base_cmd, "segment": segment},
            )

    # Step 4: Prefix allowlist — every &&-segment must match
    unmatched: list[str] = []
    for segment in _split_and_segments(command):
        if not _matches_any_allowed_prefix(segment=segment, allow_prefixes=allowed_prefixes):
            unmatched.append(segment)

    if unmatched:
        return CommandPolicyDecision(
            status="review",
            details={
                "allow_prefixes": allowed_prefixes,
                "unmatched_segments": tuple(unmatched),
            },
        )

    return CommandPolicyDecision(status="allowed", details={})


def enforce_command_policy(
    command: str,
    *,
    overrides: BashPolicyOverrides | None = None,
) -> None:
    """Raise ToolError if command is denied or review (convenience wrapper).

    This function is kept for testing and exceptional direct-call scenarios
    (see module docstring). Production paths go through BashTool.check_permissions
    via the hook; this wrapper should not be called in normal tool execution.
    """
    decision = check_command_policy(command, overrides=overrides)
    if decision.status == "allowed":
        return
    raise ToolError(
        "command is not allowed by bash policy",
        tool_name="bash",
        details=dict(decision.details),
    )


# ---------------------------------------------------------------------------
# Private helpers (migrated from safety.py, behaviour-identical)
# ---------------------------------------------------------------------------

def _ensure_command_parseable(command: str) -> None:
    try:
        parsed = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ToolError("command parsing failed", tool_name="bash") from exc
    if not parsed:
        raise ToolError("command cannot be empty", tool_name="bash")


def _split_and_segments(command: str) -> tuple[str, ...]:
    segments = [segment.strip() for segment in command.split("&&")]
    return tuple(segment for segment in segments if segment)


def _extract_base_command(segment: str) -> str:
    """Return lowercased base command of segment, stripping VAR=val prefixes."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    for token in tokens:
        if "=" in token:
            head, _, _ = token.partition("=")
            if head and (head[0].isalpha() or head[0] == "_") and all(
                ch.isalnum() or ch == "_" for ch in head
            ):
                continue
        return token.lower()
    return ""


def _matches_any_allowed_prefix(*, segment: str, allow_prefixes: tuple[str, ...]) -> bool:
    lowered_segment = segment.strip().lower()
    for prefix in allow_prefixes:
        lowered_prefix = prefix.strip().lower()
        if not lowered_prefix:
            continue
        if not lowered_segment.startswith(lowered_prefix):
            continue
        if len(lowered_segment) == len(lowered_prefix):
            return True
        next_char = lowered_segment[len(lowered_prefix)]
        if next_char.isspace() or next_char in "<>|;&()":
            return True
    return False


def _read_bash_policy_table(raw: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Extract bash policy table from TOML, trying canonical then legacy key."""
    if not isinstance(raw, Mapping):
        return None
    # Priority 1: [tool_safety.bash_policy]
    tool_safety = raw.get("tool_safety")
    if isinstance(tool_safety, Mapping):
        nested = tool_safety.get("bash_policy")
        if isinstance(nested, Mapping):
            return nested
    # Priority 2: legacy [bash] top-level
    direct = raw.get("bash")
    if isinstance(direct, Mapping):
        return direct
    # Legacy [tools.bash] (compat with old safety.py format)
    tools_section = raw.get("tools")
    if isinstance(tools_section, Mapping):
        nested_bash = tools_section.get("bash")
        if isinstance(nested_bash, Mapping):
            return nested_bash
    return None


def _read_optional_string_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped:
            normalized.append(stripped)
    if not normalized:
        return None
    return tuple(normalized)
