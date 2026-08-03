"""Per-agent cron enablement at the product tool-selection seam."""

from __future__ import annotations

import pytest

from personal_assistant.product import DEFAULT_TOOL_IDS, resolve_enabled_tools


def _agent(tool_allowlist: list[str], *, cron_enabled: bool) -> object:
    class _Agent:
        pass

    agent = _Agent()
    agent.tool_allowlist = tuple(tool_allowlist)
    agent.cron_enabled = cron_enabled
    return agent


@pytest.mark.parametrize(
    ("allowlist", "cron_enabled", "expected"),
    [
        (["read", "bash"], False, ["read", "bash"]),
        ([], False, []),
        ([], True, ["cron"]),
        (["read", "cron"], True, ["read", "cron"]),
        (list(DEFAULT_TOOL_IDS), True, [*DEFAULT_TOOL_IDS, "cron"]),
    ],
)
def test_resolve_enabled_tools_preserves_whitelist_and_cron_gate(
    allowlist: list[str], cron_enabled: bool, expected: list[str]
) -> None:
    """Keep the explicit whitelist exact and append cron at most once when enabled."""

    assert resolve_enabled_tools(
        _agent(allowlist, cron_enabled=cron_enabled)
    ) == expected
