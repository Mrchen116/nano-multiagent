from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig, load_tool_safety_config


def test_default_policy_allows_command_v_probe(tmp_path: Path) -> None:
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())

    safety.enforce_command_policy(
        "command -v npx >/dev/null 2>&1",
        tool_name="bash",
    )


def test_and_segments_require_each_command_prefix_allowed(tmp_path: Path) -> None:
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())

    with pytest.raises(ToolError, match="not allowed"):
        safety.enforce_command_policy(
            "echo ok && uname -a",
            tool_name="bash",
        )


def test_allow_unlisted_override_accepts_review_status(tmp_path: Path) -> None:
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())

    safety.enforce_command_policy(
        "echo ok && uname -a",
        tool_name="bash",
        allow_unlisted=True,
    )


def test_load_tool_safety_config_reads_policy_file(tmp_path: Path) -> None:
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

    loaded = load_tool_safety_config(repo_root=tmp_path)

    assert loaded.bash_allowed_prefixes == ("echo", "uname")
    assert loaded.bash_blocked_fragments == ("shutdown", "rm -rf /")


def test_rm_rf_user_path_routes_to_review_for_classifier(tmp_path: Path) -> None:
    """User-workspace rm -rf belongs in classifier review, not hard-deny.

    This locks in CC Auto Mode parity: ``rm -rf /tmp/x`` must reach the
    auto_mode_gate classifier so the LLM can decide allow/ask/deny per the
    "Irreversible Local Destruction" category, surfacing a confirmation card
    when user intent is present. Hard-deny via substring (former
    ``bash_blocked_fragments = ("rm -rf /",)``) over-caught any
    ``rm -rf /<anything>`` and made the ask flow unreachable.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    decision = safety.check_command_policy("rm -rf /tmp/test-fff", tool_name="bash")
    assert decision.status == "review"


def test_root_rm_rf_also_routes_to_review_not_hard_deny(tmp_path: Path) -> None:
    """Even ``rm -rf /`` is classifier-decided — mirrors CC's design.

    CC has zero hard-deny entries for ``rm`` at the security layer; all rm
    classification lives in yoloClassifier system prompt. We follow suit so
    the user can always reach the ask card to override or confirm.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    decision = safety.check_command_policy("rm -rf /", tool_name="bash")
    assert decision.status == "review"


def test_reboot_base_command_is_hard_denied(tmp_path: Path) -> None:
    """``reboot`` is a token-level hard-deny (deviation from CC, by design).

    A dev agent has no legitimate reason to invoke ``reboot``; short-circuit
    saves a classifier LLM round-trip. Matched by base command, so
    ``reboot-now.sh`` (an unrelated script) is NOT caught.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    assert safety.check_command_policy("reboot", tool_name="bash").status == "denied"
    assert safety.check_command_policy("shutdown -h now", tool_name="bash").status == "denied"
    # Script name that just starts with "reboot" must not false-positive.
    assert safety.check_command_policy("reboot-now.sh", tool_name="bash").status == "review"


def test_zsh_module_dangerous_commands_are_hard_denied(tmp_path: Path) -> None:
    """Mirror CC ZSH_DANGEROUS_COMMANDS Set as defense-in-depth.

    ``zmodload`` is the gateway to ``zsh/system``/``zsh/files``/``zsh/zpty``
    modules whose builtins bypass binary-name checks. CC enumerates these in
    bashSecurity.ts; we copy verbatim so the binary-name escape hatch is
    closed on our side too.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    for cmd in ("zmodload zsh/system", "emulate -c 'eval $code'", "zf_rm /tmp/x"):
        assert (
            safety.check_command_policy(cmd, tool_name="bash").status == "denied"
        ), f"expected deny for {cmd!r}"


def test_env_var_prefix_is_stripped_before_base_command_match(tmp_path: Path) -> None:
    """``NAME=val reboot`` must hit the reboot denylist; ``NAME=val rm ...`` must not.

    Bash treats leading ``NAME=value`` as env var assignment, not the
    executable. The base-command extractor must strip them so a wrapper-style
    rule can't be bypassed by ``DUMMY=1 reboot``.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    assert safety.check_command_policy(
        "DUMMY=1 reboot", tool_name="bash"
    ).status == "denied"
    # rm is NOT in the base-command denylist; env prefix stripping still works
    # but the result is "review" (classifier path), not "denied".
    assert safety.check_command_policy(
        "DUMMY=1 rm -rf /tmp/x", tool_name="bash"
    ).status == "review"


def test_fork_bomb_fragment_still_caught(tmp_path: Path) -> None:
    """Fork bomb ``:(){:|:&};:`` has no base command — must hit fragment denylist.

    Demonstrates the ``bash_blocked_fragments`` substring path still
    fires for syntactic constructs (function-definition literals) that
    bypass the base-command extractor.
    """
    safety = ToolSafety(repo_root=tmp_path, config=ToolSafetyConfig())
    decision = safety.check_command_policy(":(){:|:&};:", tool_name="bash")
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

    loaded = load_tool_safety_config(repo_root=tmp_path)
    assert loaded.bash_blocked_commands == ("uname",)
    # Built-in reboot is no longer denied because the toml replaces the list.
    safety = ToolSafety(repo_root=tmp_path, config=loaded)
    assert safety.check_command_policy("uname -a", tool_name="bash").status == "denied"
    assert safety.check_command_policy("reboot", tool_name="bash").status == "review"
