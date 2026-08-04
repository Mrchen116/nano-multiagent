"""Behavioral tests for BashTool command policy decisions and overrides."""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile

# These imports will fail (Red) until bash_policy.py is created.
from agent.platform.tools.builtins.bash_policy import (
    check_command_policy,
    enforce_command_policy,
    load_bash_policy_overrides,
    BashPolicyOverrides,
)
from agent.core.errors import ToolError


class TestCheckCommandPolicyAllowed:
    """check_command_policy 对允许命令返回 status='allowed'。"""

    @pytest.mark.parametrize(
        "cmd",
        [
            "ls -la",
            "ls",
            "cat /etc/hosts",
            "cat README.md",
            "echo hello",
            "head -n 10 file.txt",
            "tail -f log.txt",
            "pwd",
            "wc -l src/main.py",
            "rg 'TODO' src/",
            "true",
            "false",
            "command -v python3",
        ],
    )
    def test_single_readonly_commands_allowed(self, cmd):
        decision = check_command_policy(cmd)
        assert decision.status == "allowed", (
            f"{cmd!r} should be allowed, got {decision}"
        )

    @pytest.mark.parametrize(
        "cmd",
        [
            "git status",
            "git log --oneline",
            "git diff HEAD~1",
            "git show HEAD",
            "git branch -a",
            "git config --list",
            "git rev-parse HEAD",
            "git ls-files",
            "git blame src/main.py",
            "git tag",
            "git describe --tags",
            "git remote -v",
            "git stash list",
        ],
    )
    def test_git_readonly_subcommands_allowed(self, cmd):
        decision = check_command_policy(cmd)
        assert decision.status == "allowed", (
            f"{cmd!r} should be allowed, got {decision}"
        )

    @pytest.mark.parametrize(
        "cmd",
        [
            "python --version",
            "python -V",
            "python3 --version",
            "python3 -V",
        ],
    )
    def test_python_version_flags_allowed(self, cmd):
        decision = check_command_policy(cmd)
        assert decision.status == "allowed", (
            f"{cmd!r} should be allowed, got {decision}"
        )

    def test_and_chain_of_readonly(self):
        """ls && cat file.txt → allowed（两段都匹配 prefix）。"""
        decision = check_command_policy("ls -la && cat README.md")
        assert decision.status == "allowed"


class TestCheckCommandPolicyReview:
    """check_command_policy 对未列入 prefix 的命令返回 status='review'。"""

    @pytest.mark.parametrize(
        "cmd",
        [
            "python3 file.py",
            "python3 src/main.py",
            "python app.py",
            "bash script.sh",
            "bash -c 'echo hi'",
            "pytest tests/",
            "pytest -xvs tests/unit/",
            "sed -i 's/x/y/' file.txt",
            "sed 's/a/b/' file.txt",  # sed 本身整体 review，无论是否 -i
            "sleep 5",
            "git push origin main",
            "git commit -m 'msg'",
            "git reset --hard HEAD~1",
            "git checkout -b new-branch",
            "git merge main",
            "rm -rf /tmp/test",
            "npm install",
            "make build",
        ],
    )
    def test_non_allowlisted_commands_review(self, cmd):
        decision = check_command_policy(cmd)
        assert decision.status == "review", f"{cmd!r} should be review, got {decision}"

    def test_review_contains_unmatched_segments(self):
        """review 状态 details 包含 unmatched_segments。"""
        decision = check_command_policy("python3 script.py")
        assert decision.status == "review"
        assert "unmatched_segments" in decision.details


class TestCheckCommandPolicyDenied:
    """check_command_policy 对硬 deny 命令返回 status='denied'。"""

    @pytest.mark.parametrize(
        "cmd",
        [
            "mkfs /dev/sda",
            "reboot",
            "shutdown -h now",
            "halt",
            "poweroff",
            "zmodload zsh/net/tcp",
            "mapfile -t lines < file.txt",
            "zf_rm /etc/passwd",
        ],
    )
    def test_blocked_commands_denied(self, cmd):
        decision = check_command_policy(cmd)
        assert decision.status == "denied", f"{cmd!r} should be denied, got {decision}"

    def test_fork_bomb_fragment_denied(self):
        """Fork-bomb 语法 fragment 直接 deny。"""
        decision = check_command_policy(":(){:|:&};:")
        assert decision.status == "denied"
        assert "blocked_fragment" in decision.details

    def test_blocked_command_not_substring(self):
        """'reboot-helper.sh' 不命中 blocked_commands（token 级匹配）。"""
        decision = check_command_policy("./reboot-helper.sh")
        # Should be review, not denied
        assert decision.status != "denied", (
            "reboot-helper.sh should NOT be denied (substring guard)"
        )

    def test_blocked_command_details(self):
        decision = check_command_policy("reboot")
        assert decision.status == "denied"
        assert (
            "blocked_command" in decision.details
            or "blocked_fragment" in decision.details
        )


class TestEnforceCommandPolicy:
    """enforce_command_policy 行为验证。"""

    def test_allowed_does_not_raise(self):
        enforce_command_policy("ls -la")  # should not raise

    def test_denied_raises_tool_error(self):
        with pytest.raises(ToolError):
            enforce_command_policy("reboot")

    def test_review_raises_tool_error(self):
        """review 状态下 enforce_command_policy 也 raise（单点 policy，D10）。"""
        with pytest.raises(ToolError):
            enforce_command_policy("python3 script.py")


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
