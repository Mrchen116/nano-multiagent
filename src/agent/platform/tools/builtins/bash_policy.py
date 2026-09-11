"""Single authoritative Bash permission entry point.

The pinned read-only policy proves command arguments and shell structure before
allowing a call. Other commands go to the Auto classifier. Only explicit user
policy denies are hard denials; executors trust this result without rechecking.
"""

from __future__ import annotations

import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from agent.core.errors import ToolError


from agent.platform.tools.builtins.bash_readonly import readonly_reason
from agent.platform.tools.builtins.bash_syntax import parse_bash

# Overrides replace these defaults, retaining the existing configuration seam.
BASH_ALLOWED_PREFIXES: tuple[str, ...] = ()
BASH_BLOCKED_COMMANDS: tuple[str, ...] = ()
BASH_BLOCKED_FRAGMENTS: tuple[str, ...] = ()


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
    return load_bash_policy_overrides_at(repo_root / ".nano" / "policy.toml")


def load_bash_policy_overrides_at(policy_path: Path) -> BashPolicyOverrides:
    """Load bash policy overrides from one already-selected policy file."""

    policy_path = policy_path.expanduser().resolve()
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
    cwd: Path | None = None,
) -> CommandPolicyDecision:
    """Classify a shell command using explicit rules then the pinned policy.

    Args:
        command: Original shell input; quotes and case remain significant.
        overrides: Optional replacement rules from the existing policy file.
        cwd: Effective tool working directory for Git path checks.

    Returns:
        An allowed, denied, or review decision, with details for the caller.
    """
    rules = overrides or BashPolicyOverrides()
    for fragment in rules.blocked_fragments or ():
        if fragment in command.strip().lower():
            return CommandPolicyDecision("denied", {"blocked_fragment": fragment})
    _ensure_command_parseable(command)
    syntax = parse_bash(command)
    blocked = {item.lower() for item in rules.blocked_commands or ()}
    for name, segment in syntax.command_names:
        if name.lower() in blocked:
            return CommandPolicyDecision(
                "denied", {"blocked_command": name, "segment": segment}
            )
    # Explicit allow_prefixes remains a replacement allowlist. Its permission
    # scope is user-provided, so it does not acquire the default flag restrictions.
    if rules.allow_prefixes is not None:
        unmatched = tuple(
            segment
            for segment in _split_and_segments(command)
            if not _matches_any_allowed_prefix(
                segment=segment, allow_prefixes=rules.allow_prefixes
            )
        )
        if not unmatched:
            return CommandPolicyDecision("allowed", {})
        return CommandPolicyDecision(
            "review",
            {"allow_prefixes": rules.allow_prefixes, "unmatched_segments": unmatched},
        )
    reason = readonly_reason(command, syntax, cwd=cwd)
    if reason:
        return CommandPolicyDecision(
            "review", {"reason": reason, "unmatched_segments": (command,)}
        )
    return CommandPolicyDecision("allowed", {})


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


def _matches_any_allowed_prefix(
    *, segment: str, allow_prefixes: tuple[str, ...]
) -> bool:
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
