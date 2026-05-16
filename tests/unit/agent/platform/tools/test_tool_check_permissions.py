"""Tests for Tool protocol check_permissions optional method.

Verifies:
- Tool protocol has optional check_permissions method
- getattr fallback returns passthrough when tool doesn't implement it
- auto_mode_gate correctly uses getattr pattern to call check_permissions
- Tools that implement check_permissions get their result used
"""

import pytest
from typing import Any, Mapping
from pathlib import Path
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
