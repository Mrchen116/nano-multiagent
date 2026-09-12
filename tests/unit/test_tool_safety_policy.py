"""Legacy policy-file override compatibility at the tool-safety boundary."""

from pathlib import Path

from agent.platform.tools.builtins.bash_policy import (
    check_command_policy,
    load_bash_policy_overrides,
)


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
