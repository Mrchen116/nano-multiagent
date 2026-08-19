"""Failover lists stay in the product layer; PA keeps the sdk-only import boundary."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from agent.sdk import SessionRuntimeConfig
from tests.contract.import_rules import absolute_imports, matches_prefix

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def test_session_runtime_does_not_carry_fallback_lists() -> None:
    assert "model_fallbacks" not in {item.name for item in fields(SessionRuntimeConfig)}


def test_personal_assistant_does_not_import_agent_core() -> None:
    violations = [
        f"{reference.path.relative_to(SRC_ROOT)}:{reference.line}"
        for reference in absolute_imports(SRC_ROOT / "personal_assistant")
        if matches_prefix(reference.module, "agent.core")
    ]
    assert not violations, "personal_assistant imported agent.core:\n  " + "\n  ".join(
        violations
    )
