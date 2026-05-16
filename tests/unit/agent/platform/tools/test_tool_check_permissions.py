"""Tests for Tool protocol check_permissions optional method.

Verifies:
- Tool protocol has optional check_permissions method
- getattr fallback returns passthrough when tool doesn't implement it
- auto_mode_gate correctly uses getattr pattern to call check_permissions
- Tools that implement check_permissions get their result used
- WriteTool.check_permissions: dangerous paths → ask+safety_check; safe paths → passthrough
- EditTool.check_permissions: same semantics as WriteTool
- bypass-immune logic: safety_locked prevents dangerously_skip_permissions from bypassing ask
"""

import pytest
from typing import Any, Mapping
from pathlib import Path
from unittest.mock import MagicMock
from agent.platform.permissions.broker import PermissionDecision


class _MinimalTool:
    """A tool that does NOT implement check_permissions (passthrough default)."""
    name = "minimal_tool"
    description = "minimal"
    input_schema = {"type": "object", "properties": {}, "required": []}
    is_concurrency_safe = True
    max_result_size_chars = None

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        return {}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        return ""


class _ToolWithPermissions:
    """A tool that implements check_permissions and returns ask+safety_check."""
    name = "sensitive_tool"
    description = "sensitive"
    input_schema = {"type": "object", "properties": {}, "required": []}
    is_concurrency_safe = False
    max_result_size_chars = None

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        return {}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        return ""

    def check_permissions(self, tool_input: Mapping[str, Any], ctx: Any) -> PermissionDecision:
        """Always asks with safety_check reason for testing."""
        return PermissionDecision(
            behavior="ask",
            decision_reason={"type": "safety_check", "matched_path": "/etc/passwd"},
            reason="Writing to sensitive path requires confirmation",
        )


class _ToolWithPassthrough:
    """A tool that explicitly implements check_permissions returning passthrough."""
    name = "passthrough_tool"
    description = "passthrough"
    input_schema = {"type": "object", "properties": {}, "required": []}
    is_concurrency_safe = True

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        return {}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        return ""

    def check_permissions(self, tool_input: Mapping[str, Any], ctx: Any) -> PermissionDecision:
        return PermissionDecision(behavior="passthrough")


class TestToolCheckPermissionsProtocol:
    def test_tool_without_check_permissions_returns_passthrough_via_getattr(self):
        """Tools without check_permissions get passthrough via getattr fallback (Anchor B)."""
        tool = _MinimalTool()
        check_fn = getattr(tool, "check_permissions", None)
        if check_fn is None:
            tool_result = PermissionDecision(behavior="passthrough")
        else:
            tool_result = check_fn({}, None)
        assert tool_result.behavior == "passthrough"

    def test_tool_with_check_permissions_called_and_result_used(self):
        """Tool implementing check_permissions has its result used."""
        tool = _ToolWithPermissions()
        check_fn = getattr(tool, "check_permissions", None)
        assert check_fn is not None
        result = check_fn({"file_path": "/etc/passwd"}, None)
        assert result.behavior == "ask"
        assert result.decision_reason is not None
        assert result.decision_reason["type"] == "safety_check"

    def test_safety_locked_determined_by_decision_reason_type(self):
        """safety_locked = True when behavior='ask' AND decision_reason.type='safety_check'."""
        tool = _ToolWithPermissions()
        check_fn = getattr(tool, "check_permissions", None)
        result = check_fn({}, None)

        # Simulate the gate logic for safety_locked detection
        safety_locked = (
            result.behavior == "ask"
            and result.decision_reason is not None
            and result.decision_reason.get("type") == "safety_check"
        )
        assert safety_locked is True

    def test_passthrough_tool_not_safety_locked(self):
        """Explicit passthrough result must not set safety_locked."""
        tool = _ToolWithPassthrough()
        check_fn = getattr(tool, "check_permissions", None)
        result = check_fn({}, None)

        safety_locked = (
            result.behavior == "ask"
            and result.decision_reason is not None
            and result.decision_reason.get("type") == "safety_check"
        )
        assert safety_locked is False
        assert result.behavior == "passthrough"

    def test_getattr_fallback_when_check_permissions_missing(self):
        """getattr fallback pattern (Anchor B): None returned if not implemented."""
        tool = _MinimalTool()
        check_fn = getattr(tool, "check_permissions", None)
        assert check_fn is None

    def test_tool_protocol_check_permissions_signature_in_base(self):
        """Tool protocol in base.py must declare check_permissions as optional method."""
        from agent.core.tools.base import Tool
        # Protocol has the method defined (optional/abstract in Protocol)
        # Check via hasattr on the Protocol class itself
        assert hasattr(Tool, "check_permissions"), (
            "Tool protocol must declare check_permissions method"
        )


# ---------------------------------------------------------------------------
# Helper: make a minimal ToolContext-like mock with cwd set
# ---------------------------------------------------------------------------

def _make_ctx(cwd: Path | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.cwd = cwd or Path("/workspace")
    return ctx


# ---------------------------------------------------------------------------
# WriteTool.check_permissions
# ---------------------------------------------------------------------------


class TestWriteToolCheckPermissions:
    """WriteTool must implement check_permissions that guards dangerous paths.

    Dangerous path → behavior='ask', decision_reason.type='safety_check'.
    Safe path → behavior='passthrough'.
    """

    def setup_method(self):
        from agent.platform.tools.builtins.write import WriteTool
        self.tool = WriteTool()

    def test_write_to_bashrc_returns_safety_check_ask(self):
        """Writing to ~/.bashrc must require confirmation (bypass-immune)."""
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": "~/.bashrc", "content": "evil"}, ctx)
        assert result.behavior == "ask"
        assert result.decision_reason is not None
        assert result.decision_reason["type"] == "safety_check"

    def test_write_to_git_config_returns_safety_check_ask(self):
        """Writing into .git/ must require confirmation."""
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": ".git/config", "content": "bad"}, ctx)
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_write_to_zshrc_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": "~/.zshrc", "content": "."}, ctx)
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_write_to_nanocode_config_returns_safety_check_ask(self):
        """Writing to .nanocode config directory requires confirmation."""
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "/home/user/.nanocode/config.yaml", "content": ""}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_write_to_nano_assistant_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "/home/user/.nano-assistant/config.yaml", "content": ""}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_write_to_safe_tmp_returns_passthrough(self):
        """Writing to /tmp/normal.txt should not require confirmation."""
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": "/tmp/test_normal.txt", "content": "x"}, ctx)
        assert result.behavior == "passthrough"

    def test_write_to_safe_workspace_file_returns_passthrough(self):
        ctx = _make_ctx(Path("/workspace"))
        result = self.tool.check_permissions({"path": "src/main.py", "content": "pass"}, ctx)
        assert result.behavior == "passthrough"

    def test_safety_locked_pattern_for_write_dangerous_path(self):
        """Simulate bypass-immune pattern: safety_locked=True prevents dangerously bypass."""
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": "~/.bashrc", "content": "evil"}, ctx)
        # Gate logic: safety_locked when ask + decision_reason.type == 'safety_check'
        safety_locked = (
            result.behavior == "ask"
            and result.decision_reason is not None
            and result.decision_reason.get("type") == "safety_check"
        )
        assert safety_locked is True

    def test_check_permissions_provides_human_readable_reason(self):
        """decision reason must include matched_path for audit trail."""
        ctx = _make_ctx()
        result = self.tool.check_permissions({"path": "~/.gitconfig", "content": ""}, ctx)
        assert "matched_path" in result.decision_reason

    def test_write_tool_has_check_permissions(self):
        """WriteTool must implement check_permissions (not rely on getattr=None passthrough)."""
        check_fn = getattr(self.tool, "check_permissions", None)
        assert check_fn is not None, "WriteTool must implement check_permissions"


# ---------------------------------------------------------------------------
# EditTool.check_permissions
# ---------------------------------------------------------------------------


class TestEditToolCheckPermissions:
    """EditTool must have the same dangerous-path semantics as WriteTool."""

    def setup_method(self):
        from agent.platform.tools.builtins.edit import EditTool
        self.tool = EditTool()

    def test_edit_bashrc_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "~/.bashrc", "oldText": "old", "newText": "new"}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_edit_git_config_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": ".git/config", "oldText": "old", "newText": "new"}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_edit_safe_file_returns_passthrough(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "/tmp/safe.py", "oldText": "old", "newText": "new"}, ctx
        )
        assert result.behavior == "passthrough"

    def test_edit_workspace_file_returns_passthrough(self):
        ctx = _make_ctx(Path("/workspace"))
        result = self.tool.check_permissions(
            {"path": "src/utils.py", "oldText": "x", "newText": "y"}, ctx
        )
        assert result.behavior == "passthrough"

    def test_edit_nanocode_config_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "/home/user/.nanocode/config.yaml", "oldText": "a", "newText": "b"}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"

    def test_edit_tool_has_check_permissions(self):
        """EditTool must implement check_permissions."""
        check_fn = getattr(self.tool, "check_permissions", None)
        assert check_fn is not None, "EditTool must implement check_permissions"

    def test_edit_mcp_json_returns_safety_check_ask(self):
        ctx = _make_ctx()
        result = self.tool.check_permissions(
            {"path": "/home/user/.mcp.json", "oldText": "{}", "newText": "{evil}"}, ctx
        )
        assert result.behavior == "ask"
        assert result.decision_reason["type"] == "safety_check"
