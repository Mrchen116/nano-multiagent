"""Tests for PermissionDecision extended data structure.

Verifies:
- behavior field accepts 'passthrough' in addition to existing values
- new decision_reason and updated_input fields exist with correct defaults
- backward compatibility: existing rule_source field retained
- frozen dataclass semantics preserved
"""

import pytest
from agent.platform.permissions.broker import PermissionDecision


class TestPermissionDecisionStructure:
    def test_passthrough_behavior_accepted(self):
        """behavior='passthrough' must be valid after M1 extension."""
        d = PermissionDecision(behavior="passthrough")
        assert d.behavior == "passthrough"

    def test_existing_behaviors_still_valid(self):
        """Existing allow/deny/ask values must remain valid."""
        for b in ("allow", "deny", "ask"):
            d = PermissionDecision(behavior=b)
            assert d.behavior == b

    def test_decision_reason_defaults_to_none(self):
        """New decision_reason field must default to None."""
        d = PermissionDecision(behavior="passthrough")
        assert d.decision_reason is None

    def test_decision_reason_accepts_dict(self):
        """decision_reason must accept a dict with type key."""
        d = PermissionDecision(
            behavior="ask",
            decision_reason={"type": "safety_check", "matched_path": "/home/user/.bashrc"},
        )
        assert d.decision_reason == {"type": "safety_check", "matched_path": "/home/user/.bashrc"}

    def test_updated_input_defaults_to_none(self):
        """New updated_input field must default to None."""
        d = PermissionDecision(behavior="passthrough")
        assert d.updated_input is None

    def test_updated_input_accepts_dict(self):
        """updated_input must accept a dict (for future tool input rewriting)."""
        d = PermissionDecision(
            behavior="allow",
            updated_input={"file_path": "/normalized/path"},
        )
        assert d.updated_input == {"file_path": "/normalized/path"}

    def test_rule_source_backward_compat(self):
        """Existing rule_source field must still be present for backward compat."""
        d = PermissionDecision(behavior="allow", rule_source="classifier")
        assert d.rule_source == "classifier"

    def test_reason_field_preserved(self):
        """reason field must be preserved."""
        d = PermissionDecision(behavior="deny", reason="not allowed")
        assert d.reason == "not allowed"

    def test_frozen_dataclass(self):
        """PermissionDecision must remain immutable (frozen dataclass)."""
        d = PermissionDecision(behavior="allow")
        with pytest.raises((AttributeError, TypeError)):
            d.behavior = "deny"  # type: ignore[misc]

    def test_safety_check_decision_reason(self):
        """safety_check type decision_reason used for bypass-immune ask."""
        d = PermissionDecision(
            behavior="ask",
            decision_reason={"type": "safety_check", "matched_path": "~/.bashrc"},
            reason="Writing to ~/.bashrc requires explicit confirmation (sensitive system file)",
        )
        assert d.decision_reason is not None
        assert d.decision_reason["type"] == "safety_check"
        assert d.behavior == "ask"

    def test_preapproved_decision_reason(self):
        """preapproved type decision_reason used by WebFetch for approved hosts."""
        d = PermissionDecision(
            behavior="allow",
            decision_reason={"type": "preapproved", "host": "docs.python.org"},
        )
        assert d.decision_reason["type"] == "preapproved"
