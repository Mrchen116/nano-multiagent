"""Contract: every builtin tool must have an explicit auto_mode_gate position.

Regression for #31 / bugfix-368: ``memory`` tool was added (feat-349) without
registering in ``SAFE_TOOL_ALLOWLIST`` or implementing ``check_permissions``.
The classifier then judged every call as deny, breaking PA self-improvement
with a 14-call retry loop.

Each builtin tool must land in exactly one of three buckets, declared
explicitly in ``EXPECTED_GATE_POSITION`` below:

- ``allowlist``   — listed in ``SAFE_TOOL_ALLOWLIST`` (fast-path, no classifier)
- ``check``       — class implements ``check_permissions``
- ``classifier``  — explicitly opted into classifier gating
                    (no allowlist entry, no check_permissions method)

Adding a new builtin tool? Add it to ``EXPECTED_GATE_POSITION`` AND make
the source match. Forgetting either side trips this test.
"""

from __future__ import annotations

import inspect

import agent.platform.tools.builtins as builtins_pkg
from agent.platform.hooks.builtins.auto_mode_gate import SAFE_TOOL_ALLOWLIST

# Maintained by hand. Each entry is a deliberate choice — the test exists
# so the choice cannot be skipped silently.
EXPECTED_GATE_POSITION: dict[str, str] = {
    "read": "allowlist",
    "agent": "allowlist",
    "task_stop": "allowlist",
    "memory": "allowlist",        # bugfix-368
    "bash": "check",
    "edit": "check",
    "write": "check",
    "web_fetch": "check",
    "skill_manage": "classifier",  # writes user skill files → classifier judges per call
}


def _builtin_tool_classes() -> dict[str, type]:
    """Return {tool_name: class} for every class in ``builtins`` with a ``name`` str."""

    found: dict[str, type] = {}
    for _, cls in inspect.getmembers(builtins_pkg, inspect.isclass):
        if cls.__module__ and not cls.__module__.startswith("agent.platform.tools.builtins"):
            continue
        tool_name = getattr(cls, "name", None)
        if isinstance(tool_name, str) and tool_name:
            found[tool_name] = cls
    return found


def test_every_builtin_tool_has_an_expected_gate_position() -> None:
    discovered = _builtin_tool_classes()
    undeclared = sorted(set(discovered) - set(EXPECTED_GATE_POSITION))
    stale = sorted(set(EXPECTED_GATE_POSITION) - set(discovered))
    assert not undeclared, (
        f"New builtin tool(s) discovered without a gate position declaration: {undeclared}. "
        "Add each to EXPECTED_GATE_POSITION in this test (and to SAFE_TOOL_ALLOWLIST "
        "or implement check_permissions accordingly)."
    )
    assert not stale, (
        f"EXPECTED_GATE_POSITION has stale entries (tool no longer in builtins): {stale}"
    )


def test_each_builtin_tool_matches_its_declared_gate_position() -> None:
    discovered = _builtin_tool_classes()
    mismatches: list[str] = []
    for tool_name, expected in EXPECTED_GATE_POSITION.items():
        cls = discovered.get(tool_name)
        if cls is None:
            continue  # caught by the previous test
        in_allowlist = tool_name in SAFE_TOOL_ALLOWLIST
        has_check = callable(getattr(cls, "check_permissions", None))
        actual = (
            "allowlist" if in_allowlist
            else "check" if has_check
            else "classifier"
        )
        if actual != expected:
            mismatches.append(
                f"{tool_name}: declared={expected} actual={actual} "
                f"(allowlist={in_allowlist}, check_permissions={has_check})"
            )
    assert not mismatches, "Tool gate position mismatch:\n  " + "\n  ".join(mismatches)
