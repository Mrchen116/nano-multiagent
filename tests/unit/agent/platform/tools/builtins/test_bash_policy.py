"""Command-policy behavior, pinned-reference parity, and explicit overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.core.errors import ToolError
from agent.platform.tools.builtins import bash_readonly
from agent.platform.tools.builtins.bash_policy import (
    BashPolicyOverrides,
    check_command_policy,
    enforce_command_policy,
    load_bash_policy_overrides,
)

_REFERENCE = json.loads(
    Path(__file__)
    .with_name("fixtures")
    .joinpath("bash_readonly_cc_2_1_267.json")
    .read_text()
)


@pytest.mark.parametrize(
    "group", ["commands_and_flags", "syntax_and_security", "windows_security"]
)
def test_readonly_decisions_match_fixed_reference(group, tmp_path, monkeypatch):
    """Every frozen expected result comes from the pinned JavaScript functions."""
    monkeypatch.setattr(os, "environ", {"PATH": "/usr/bin", "HOME": str(tmp_path)})
    monkeypatch.setattr(bash_readonly, "_IS_WINDOWS", group == "windows_security")
    for command, expected in _REFERENCE[group]:
        decision = check_command_policy(command, cwd=tmp_path)
        assert decision.status == expected, (command, expected, decision)


@pytest.mark.parametrize("command", ["reboot", "python3 script.py"])
def test_enforce_requires_readonly_or_explicit_permission(command):
    with pytest.raises(ToolError):
        enforce_command_policy(command)
    enforce_command_policy("ls -la")


@pytest.mark.parametrize(
    "command", ["reboot", "ls | reboot", 'echo "prefix $(reboot)"']
)
def test_explicit_deny_override_precedes_explicit_allow(command):
    overrides = BashPolicyOverrides(
        allow_prefixes=("reboot", "ls", "echo"), blocked_commands=("reboot",)
    )
    assert check_command_policy(command, overrides=overrides).status == "denied"


def test_explicit_allow_override_replaces_defaults_and_keeps_its_scope():
    overrides = BashPolicyOverrides(allow_prefixes=("custom-tool", "git"))
    assert (
        check_command_policy("custom-tool --write", overrides=overrides).status
        == "allowed"
    )
    assert check_command_policy("git push", overrides=overrides).status == "allowed"
    assert check_command_policy("cat README.md", overrides=overrides).status == "review"


def test_explicit_fragment_override_still_denies():
    rules = BashPolicyOverrides(blocked_fragments=("forbidden-text",))
    assert (
        check_command_policy("echo forbidden-text", overrides=rules).status == "denied"
    )


@pytest.mark.parametrize("marker", ["HEAD", "objects", "refs"])
def test_git_checks_effective_cwd_and_ancestors_for_bare_indicators(tmp_path, marker):
    (tmp_path / marker).write_text("untrusted")
    nested = tmp_path / "nested"
    nested.mkdir()
    assert check_command_policy("git status", cwd=nested).status == "review"
    assert check_command_policy("ls", cwd=nested).status == "allowed"


def test_git_allows_a_normal_repository(tmp_path):
    dotgit = tmp_path / ".git"
    dotgit.mkdir()
    (dotgit / "HEAD").write_text("ref: refs/heads/main\n")
    (dotgit / "objects").mkdir()
    (dotgit / "refs").mkdir()
    assert check_command_policy("git status", cwd=tmp_path).status == "allowed"


@pytest.mark.parametrize("symlink", [False, True])
def test_git_rejects_plantable_gitdir_indirection(tmp_path, symlink):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "HEAD").write_text("ref: refs/heads/main\n")
    if symlink:
        (checkout / ".git").symlink_to(payload)
    else:
        (checkout / ".git").write_text(f"gitdir: {payload}\n")
    assert check_command_policy("git log", cwd=checkout).status == "review"


def test_git_allows_worktree_gitdir_inside_original_git_directory(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    gitdir = tmp_path / "original" / ".git" / "worktrees" / "checkout"
    gitdir.mkdir(parents=True)
    (gitdir / "HEAD").write_text("ref: refs/heads/work\n")
    (checkout / ".git").write_text(f"gitdir: {gitdir}\n")
    assert check_command_policy("git status", cwd=checkout).status == "allowed"


def test_malformed_command_does_not_produce_an_allow_decision():
    with pytest.raises(ToolError, match="command parsing failed"):
        check_command_policy("echo 'unterminated")
    assert check_command_policy("echo hi &&").status == "review"


@pytest.mark.parametrize("count, expected", [(4997, "allowed"), (4998, "review")])
def test_command_length_uses_reference_utf16_units(count, expected):
    assert check_command_policy("echo " + "😀" * count).status == expected


class TestBashPolicyOverrides:
    """BashPolicyOverrides 和 load_bash_policy_overrides 兼容性测试。"""

    def test_load_overrides_no_toml_returns_defaults(self, tmp_path):
        """无 policy.toml 时返回含 None 字段（表示使用模块级默认值）。"""
        overrides = load_bash_policy_overrides(tmp_path)
        assert isinstance(overrides, BashPolicyOverrides)
        # Without override file, fields should be None (use module defaults)
        assert overrides.allow_prefixes is None
        assert overrides.blocked_commands is None
        assert overrides.blocked_fragments is None

    def test_load_overrides_from_tool_safety_bash_policy_section(self, tmp_path):
        """[tool_safety.bash_policy] 段仍被正确读取（向后兼容，锚点 R）。"""
        policy_dir = tmp_path / ".nano"
        policy_dir.mkdir()
        policy_file = policy_dir / "policy.toml"
        # Write TOML manually (no external deps needed)
        policy_file.write_text(
            "[tool_safety.bash_policy]\n"
            'allow_prefixes = ["cat", "ls", "custom-tool"]\n'
            'deny_commands = ["badcmd"]\n'
            'deny_fragments = [":(){"]\n',
            encoding="utf-8",
        )

        overrides = load_bash_policy_overrides(tmp_path)
        assert overrides.allow_prefixes == ("cat", "ls", "custom-tool")
        assert overrides.blocked_commands == ("badcmd",)

    def test_load_overrides_flat_bash_section(self, tmp_path):
        """[bash] 顶层段同样被识别（旧格式兼容）。"""
        policy_dir = tmp_path / ".nano"
        policy_dir.mkdir()
        policy_file = policy_dir / "policy.toml"
        policy_file.write_text(
            '[bash]\nallow_prefixes = ["echo", "custom-readonly"]\n',
            encoding="utf-8",
        )

        overrides = load_bash_policy_overrides(tmp_path)
        assert overrides.allow_prefixes == ("echo", "custom-readonly")

    def test_check_command_policy_respects_overrides(self, tmp_path):
        """check_command_policy 接受 overrides 参数，用户自定义 allow_prefixes 生效。"""
        overrides = BashPolicyOverrides(allow_prefixes=("custom-tool",))
        # custom-tool is not in default list, but with overrides it should be allowed
        decision = check_command_policy("custom-tool --flag", overrides=overrides)
        assert decision.status == "allowed"
