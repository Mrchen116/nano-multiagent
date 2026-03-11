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
