"""Tests for command policy — now living in bash_policy after M6 migration.

After bugfix-355-M6, command policy logic (check_command_policy,
enforce_command_policy, allow-prefix lists, block lists) has moved from
ToolSafety to agent.platform.tools.builtins.bash_policy. Tests updated to
call the new module directly. Broader coverage lives in test_bash_policy.py.
"""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.builtins.bash_policy import (
    BashPolicyOverrides,
    check_command_policy,
    enforce_command_policy,
    load_bash_policy_overrides,
)


def test_default_policy_allows_command_v_probe() -> None:
    decision = check_command_policy("command -v npx >/dev/null 2>&1")
    assert decision.status == "allowed"


def test_and_segments_require_each_command_prefix_allowed() -> None:
    with pytest.raises(ToolError, match="not allowed"):
        enforce_command_policy("echo ok && uname -a")


def test_allow_unlisted_override_accepts_review_status() -> None:
    # Review-status commands pass when check_command_policy returns "review" (not denied).
    decision = check_command_policy("echo ok && uname -a")
    assert decision.status == "review"  # goes to classifier, not hard-denied


def test_load_bash_policy_overrides_reads_policy_file(tmp_path: Path) -> None:
    policy_file = tmp_path / ".nano" / "policy.toml"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text(
        """
[bash]
allow_prefixes = ["echo", "uname"]
deny_fragments = ["shutdown", "rm -rf /"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    overrides = load_bash_policy_overrides(tmp_path)

    assert overrides.allow_prefixes == ("echo", "uname")
    assert overrides.blocked_fragments == ("shutdown", "rm -rf /")


def test_rm_rf_user_path_routes_to_review_for_classifier() -> None:
    """User-workspace rm -rf belongs in classifier review, not hard-deny.

    This locks in CC Auto Mode parity: ``rm -rf /tmp/x`` must reach the
    auto_mode_gate classifier so the LLM can decide allow/ask/deny per the
    "Irreversible Local Destruction" category, surfacing a confirmation card
    when user intent is present.
    """
    decision = check_command_policy("rm -rf /tmp/test-fff")
    assert decision.status == "review"


def test_root_rm_rf_also_routes_to_review_not_hard_deny() -> None:
    """Even ``rm -rf /`` is classifier-decided — mirrors CC's design."""
    decision = check_command_policy("rm -rf /")
    assert decision.status == "review"


def test_reboot_base_command_is_hard_denied() -> None:
    """``reboot`` is a token-level hard-deny (deviation from CC, by design)."""
    assert check_command_policy("reboot").status == "denied"
    assert check_command_policy("shutdown -h now").status == "denied"
    # Script name that just starts with "reboot" must not false-positive.
    assert check_command_policy("reboot-now.sh").status == "review"


def test_zsh_module_dangerous_commands_are_hard_denied() -> None:
    """Mirror CC ZSH_DANGEROUS_COMMANDS Set as defense-in-depth."""
    for cmd in ("zmodload zsh/system", "emulate -c 'eval $code'", "zf_rm /tmp/x"):
        assert check_command_policy(cmd).status == "denied", (
            f"expected deny for {cmd!r}"
        )


def test_env_var_prefix_is_stripped_before_base_command_match() -> None:
    """``NAME=val reboot`` must hit the reboot denylist; ``NAME=val rm ...`` must not."""
    assert check_command_policy("DUMMY=1 reboot").status == "denied"
    # rm is NOT in the base-command denylist; env prefix stripping still works
    # but the result is "review" (classifier path), not "denied".
    assert check_command_policy("DUMMY=1 rm -rf /tmp/x").status == "review"


def test_fork_bomb_fragment_still_caught() -> None:
    """Fork bomb ``:(){:|:&};:`` has no base command — must hit fragment denylist."""
    decision = check_command_policy(":(){:|:&};:")
    assert decision.status == "denied"
    assert decision.details.get("blocked_fragment") == ":(){"


def test_policy_toml_deny_commands_overrides_defaults(tmp_path: Path) -> None:
    """``.nano/policy.toml`` ``deny_commands`` overrides the built-in token list."""
    policy_file = tmp_path / ".nano" / "policy.toml"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text(
        """
[bash]
deny_commands = ["uname"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    overrides = load_bash_policy_overrides(tmp_path)
    assert overrides.blocked_commands == ("uname",)
    # Built-in reboot is no longer denied because the toml replaces the list.
    assert check_command_policy("uname -a", overrides=overrides).status == "denied"
    assert check_command_policy("reboot", overrides=overrides).status == "review"
