"""Tests for dangerous_paths.py — DANGEROUS_FILES / DANGEROUS_DIRECTORIES constants and
check_dangerous_path function.

Coverage:
- DANGEROUS_FILES: 8 items matching D5.2 spec exactly
- DANGEROUS_DIRECTORIES: 6 items matching D5.2 spec exactly
- check_dangerous_path: basename match, segment match, case-insensitive, .claude/skills/ exemption,
  absolute/relative/tilde paths, cwd resolution
"""

from pathlib import Path

import pytest

from agent.platform.tools.dangerous_paths import (
    DANGEROUS_DIRECTORIES,
    DANGEROUS_FILES,
    check_dangerous_path,
)

# ---------------------------------------------------------------------------
# Constants spec compliance
# ---------------------------------------------------------------------------

EXPECTED_DANGEROUS_FILES = frozenset(
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

EXPECTED_DANGEROUS_DIRECTORIES = frozenset(
    {
        ".git",
        ".vscode",
        ".idea",
        ".claude",
        ".nanocode",
        ".nano-assistant",
    }
)


class TestDangerousFilesConstant:
    def test_dangerous_files_has_exactly_8_items(self):
        assert len(DANGEROUS_FILES) == 8, f"Expected 8 items, got {len(DANGEROUS_FILES)}: {DANGEROUS_FILES}"

    def test_dangerous_files_matches_d52_spec_exactly(self):
        assert DANGEROUS_FILES == EXPECTED_DANGEROUS_FILES

    def test_dangerous_files_contains_gitconfig(self):
        assert ".gitconfig" in DANGEROUS_FILES

    def test_dangerous_files_contains_shell_startup_files(self):
        shell_files = {".bashrc", ".bash_profile", ".zshrc", ".zprofile", ".profile"}
        assert shell_files.issubset(DANGEROUS_FILES)

    def test_dangerous_files_contains_mcp_json(self):
        assert ".mcp.json" in DANGEROUS_FILES

    def test_dangerous_files_does_not_contain_ripgreprc(self):
        """CC has .ripgreprc but this repo doesn't use ripgrep — omitted per D5.2."""
        assert ".ripgreprc" not in DANGEROUS_FILES

    def test_dangerous_files_does_not_contain_claude_json(self):
        """CC has .claude.json (CC config) but this repo has no such file — omitted per D5.2."""
        assert ".claude.json" not in DANGEROUS_FILES


class TestDangerousDirectoriesConstant:
    def test_dangerous_directories_has_exactly_6_items(self):
        assert len(DANGEROUS_DIRECTORIES) == 6, f"Expected 6 items, got {len(DANGEROUS_DIRECTORIES)}: {DANGEROUS_DIRECTORIES}"

    def test_dangerous_directories_matches_d52_spec_exactly(self):
        assert DANGEROUS_DIRECTORIES == EXPECTED_DANGEROUS_DIRECTORIES

    def test_dangerous_directories_contains_cc_baseline_4_items(self):
        """CC's 4 baseline items must all be present."""
        assert {".git", ".vscode", ".idea", ".claude"}.issubset(DANGEROUS_DIRECTORIES)

    def test_dangerous_directories_contains_this_repo_extras(self):
        """Two repo-specific directories added per D5.2."""
        assert ".nanocode" in DANGEROUS_DIRECTORIES
        assert ".nano-assistant" in DANGEROUS_DIRECTORIES


# ---------------------------------------------------------------------------
# check_dangerous_path — basename match (DANGEROUS_FILES)
# ---------------------------------------------------------------------------


class TestCheckDangerousPathBasenameMatch:
    def test_absolute_path_dangerous_file(self):
        """Absolute path with dangerous filename triggers match."""
        assert check_dangerous_path("/home/user/.bashrc") is True

    def test_absolute_path_gitconfig(self):
        assert check_dangerous_path("/home/user/.gitconfig") is True

    def test_absolute_path_zshrc(self):
        assert check_dangerous_path("/root/.zshrc") is True

    def test_absolute_path_mcp_json(self):
        assert check_dangerous_path("/some/dir/.mcp.json") is True

    def test_tilde_home_bashrc(self):
        """~/.bashrc should match after expanduser."""
        assert check_dangerous_path("~/.bashrc") is True

    def test_tilde_home_gitconfig(self):
        assert check_dangerous_path("~/.gitconfig") is True

    def test_safe_absolute_path_not_matched(self):
        assert check_dangerous_path("/tmp/test_normal.txt") is False

    def test_safe_filename_with_dangerous_substring(self):
        """'my.bashrc.bak' should NOT match — basename must be exact."""
        assert check_dangerous_path("/home/user/my.bashrc.bak") is False

    def test_safe_filename_bashrc_prefix(self):
        """'bashrc' (no dot) should not match '.bashrc'."""
        assert check_dangerous_path("/home/user/bashrc") is False


# ---------------------------------------------------------------------------
# check_dangerous_path — segment match (DANGEROUS_DIRECTORIES)
# ---------------------------------------------------------------------------


class TestCheckDangerousPathSegmentMatch:
    def test_git_directory_absolute(self):
        """Writing to a file inside .git directory is dangerous."""
        assert check_dangerous_path("/repo/.git/config") is True

    def test_git_directory_at_root(self):
        assert check_dangerous_path("/.git/COMMIT_EDITMSG") is True

    def test_vscode_directory(self):
        assert check_dangerous_path("/project/.vscode/settings.json") is True

    def test_idea_directory(self):
        assert check_dangerous_path("/project/.idea/workspace.xml") is True

    def test_claude_directory(self):
        assert check_dangerous_path("/project/.claude/config.json") is True

    def test_nanocode_directory(self):
        assert check_dangerous_path("/home/user/.nanocode/settings.yaml") is True

    def test_nano_assistant_directory(self):
        assert check_dangerous_path("/home/user/.nano-assistant/config.yaml") is True

    def test_safe_directory_not_matched(self):
        assert check_dangerous_path("/project/src/main.py") is False

    def test_safe_tmp_path(self):
        assert check_dangerous_path("/tmp/test_normal.txt") is False


# ---------------------------------------------------------------------------
# check_dangerous_path — case-insensitive
# ---------------------------------------------------------------------------


class TestCheckDangerousPathCaseInsensitive:
    def test_uppercase_bashrc(self):
        assert check_dangerous_path("/home/user/.BASHRC") is True

    def test_mixed_case_gitconfig(self):
        assert check_dangerous_path("/home/user/.GitConfig") is True

    def test_uppercase_git_directory(self):
        assert check_dangerous_path("/project/.GIT/config") is True

    def test_mixed_case_vscode(self):
        assert check_dangerous_path("/project/.VSCode/settings.json") is True


# ---------------------------------------------------------------------------
# check_dangerous_path — .claude/skills/ exemption (Anchor G)
# ---------------------------------------------------------------------------


class TestCheckDangerousPathClaudeWorktreesExemption:
    def test_claude_directory_plain_triggers(self):
        """.claude directory itself without worktrees child is dangerous."""
        assert check_dangerous_path("/project/.claude/config.json") is True

    def test_claude_skills_not_exempt(self):
        """.claude/skills/ is NOT in the exemption list — only worktrees."""
        # .claude/skills/ is NOT exempt — only .claude/worktrees/ is exempt per Anchor G
        assert check_dangerous_path("/project/.claude/skills/my_skill.py") is True

    def test_claude_worktrees_is_exempt(self):
        """.claude/worktrees/ is exempt per Anchor G (CC AgentTool.tsx worktrees comment)."""
        assert check_dangerous_path("/project/.claude/worktrees/my-worktree/file.py") is False

    def test_claude_worktrees_exempt_nested(self):
        """Nested paths under .claude/worktrees/ are also exempt."""
        assert check_dangerous_path("/project/.claude/worktrees/feat-100/src/main.py") is False

    def test_claude_config_still_dangerous(self):
        assert check_dangerous_path("/project/.claude/config.json") is True


# ---------------------------------------------------------------------------
# check_dangerous_path — relative paths + cwd resolution
# ---------------------------------------------------------------------------


class TestCheckDangerousPathRelativePaths:
    def test_relative_dangerous_file_with_cwd(self, tmp_path):
        """Relative path to dangerous file resolved with cwd."""
        assert check_dangerous_path(".bashrc", cwd=tmp_path) is True

    def test_relative_safe_file_with_cwd(self, tmp_path):
        assert check_dangerous_path("main.py", cwd=tmp_path) is False

    def test_relative_git_dir_with_cwd(self, tmp_path):
        assert check_dangerous_path(".git/config", cwd=tmp_path) is True

    def test_relative_path_no_cwd_absolute_tilde(self):
        """Relative path without cwd and no tilde: cannot resolve, should return False
        (we don't know the absolute path)."""
        # Without cwd, a bare relative path like 'somefile.txt' stays relative
        # and should NOT trigger (we can't determine absolute path)
        assert check_dangerous_path("some_random_file.txt") is False

    def test_relative_dangerous_file_no_cwd(self):
        """Bare relative dangerous filename without cwd: still check basename."""
        # Even without cwd, if basename matches, it's dangerous
        assert check_dangerous_path(".bashrc") is True

    def test_relative_git_dir_no_cwd(self):
        """Relative path with dangerous directory segment, no cwd."""
        assert check_dangerous_path(".git/config") is True


# ---------------------------------------------------------------------------
# check_dangerous_path — dotfile backup/variant prefix matching (bugfix-355 M4)
#
# Reviewer Issue #2 (major): exact-basename matching misses .bashrc.test.bak,
# .zshrc.bak.20260101 etc. Rule: basename startswith <dangerous-file> + "."
# (dot-separator required to avoid false positives like ".bashrcevil").
# ---------------------------------------------------------------------------


class TestCheckDangerousPathDotfilePrefix:
    """Dotfile backup/variant files must match via prefix rule (bugfix-355 M4)."""

    def test_bashrc_dot_test_dot_bak(self):
        """.bashrc.test.bak starts with .bashrc. → dangerous."""
        assert check_dangerous_path("/home/user/.bashrc.test.bak") is True

    def test_bashrc_dot_bak(self):
        """.bashrc.bak starts with .bashrc. → dangerous."""
        assert check_dangerous_path("~/.bashrc.bak") is True

    def test_bashrc_backup_suffix(self):
        """.bashrc_backup uses _ separator — only . separator triggers prefix match."""
        # _ is not a valid separator for prefix match rule; should NOT match
        # (design.md: "basename 以 <dangerous-file> 或 <dangerous-file>. 开头")
        # Without separator we'd catch .bashrcevil; require dot separator
        assert check_dangerous_path("/home/user/.bashrc_backup") is False

    def test_zshrc_bak_with_date(self):
        """.zshrc.bak.20260101 starts with .zshrc. → dangerous."""
        assert check_dangerous_path("~/.zshrc.bak.20260101") is True

    def test_bash_profile_dot_bak(self):
        """.bash_profile.bak starts with .bash_profile. → dangerous."""
        assert check_dangerous_path("/home/user/.bash_profile.bak") is True

    def test_gitconfig_dot_backup(self):
        """.gitconfig.backup starts with .gitconfig. → dangerous."""
        assert check_dangerous_path("/home/user/.gitconfig.backup") is True

    def test_zprofile_dot_orig(self):
        """.zprofile.orig starts with .zprofile. → dangerous."""
        assert check_dangerous_path("~/.zprofile.orig") is True

    def test_profile_dot_save(self):
        """.profile.save starts with .profile. → dangerous."""
        assert check_dangerous_path("/home/user/.profile.save") is True

    def test_mcp_json_dot_bak(self):
        """.mcp.json.bak — tricky because .mcp.json already contains a dot.
        basename is .mcp.json.bak; .mcp.json is in DANGEROUS_FILES;
        .mcp.json.bak startswith .mcp.json. → dangerous."""
        assert check_dangerous_path("/home/user/.mcp.json.bak") is True

    def test_no_false_positive_bashrc_evil(self):
        """.bashrcevil must NOT match — no dot separator."""
        assert check_dangerous_path("/home/user/.bashrcevil") is False

    def test_no_false_positive_dot_zshrc_evil(self):
        """.zshrcdanger must NOT match — no separator."""
        assert check_dangerous_path("~/.zshrcdanger") is False

    def test_case_insensitive_prefix(self):
        """.BASHRC.BAK should match (case-insensitive prefix rule)."""
        assert check_dangerous_path("/home/user/.BASHRC.BAK") is True

    def test_non_dangerous_dotfile_with_bak(self):
        """.vimrc.bak should NOT match — .vimrc is not in DANGEROUS_FILES."""
        assert check_dangerous_path("/home/user/.vimrc.bak") is False
