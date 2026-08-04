"""Additional command-policy security cases beyond the lower policy suite."""

from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.builtins.bash_policy import (
    check_command_policy,
    enforce_command_policy,
    load_bash_policy_overrides,
)


def test_mixed_command_chain_requires_review() -> None:
    decision = check_command_policy("echo ok && uname -a")
    assert decision.status == "review"
    with pytest.raises(ToolError, match="not allowed"):
        enforce_command_policy("echo ok && uname -a")


def test_emulate_command_is_hard_denied() -> None:
    assert check_command_policy("emulate -c 'eval $code'").status == "denied"


def test_env_var_prefix_is_stripped_before_base_command_match() -> None:
    assert check_command_policy("DUMMY=1 reboot").status == "denied"
    assert check_command_policy("DUMMY=1 rm -rf /tmp/x").status == "review"


def test_policy_toml_deny_commands_overrides_defaults(tmp_path: Path) -> None:
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
    assert check_command_policy("uname -a", overrides=overrides).status == "denied"
    assert check_command_policy("reboot", overrides=overrides).status == "review"
