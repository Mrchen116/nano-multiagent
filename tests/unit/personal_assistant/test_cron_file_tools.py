"""Tests for ``resolve_enabled_tools`` TRUE whitelist semantics.

feat-394 fix + cleanup: ``tool_allowlist`` is the user's explicit tool whitelist.
Empty means no tools (not "unconfigured"), and ``cron`` is appended separately
via ``agent.cron_enabled``.
"""

from __future__ import annotations

from personal_assistant.product import DEFAULT_TOOL_IDS, resolve_enabled_tools


def _agent(tool_allowlist: tuple[str, ...] | list[str], cron_enabled: bool = False):
    """Minimal duck-typed agent for resolve_enabled_tools."""

    class _Agent:
        pass

    a = _Agent()
    a.tool_allowlist = tuple(tool_allowlist)
    a.cron_enabled = cron_enabled
    return a


def test_non_empty_whitelist_is_exact() -> None:
    """A non-empty whitelist resolves to EXACTLY those tools — defaults are disablable."""
    resolved = resolve_enabled_tools(_agent(["read", "bash"]))
    assert resolved == ["read", "bash"]


def test_empty_whitelist_means_no_tools() -> None:
    """Empty whitelist is a TRUE empty set, not a fallback to defaults."""
    resolved = resolve_enabled_tools(_agent([]))
    assert resolved == []


def test_cron_appended_when_enabled() -> None:
    """cron_enabled=True appends 'cron' to the resolved list."""
    resolved = resolve_enabled_tools(_agent([], cron_enabled=True))
    assert resolved == ["cron"]


def test_cron_appended_on_top_of_defaults() -> None:
    """cron_enabled=True appends 'cron' to an explicit default allowlist."""
    resolved = resolve_enabled_tools(_agent(list(DEFAULT_TOOL_IDS), cron_enabled=True))
    assert set(resolved) == set(DEFAULT_TOOL_IDS) | {"cron"}
    assert resolved.count("cron") == 1


def test_cron_not_duplicated_when_already_in_allowlist() -> None:
    """If 'cron' is already in the allowlist it is not duplicated."""
    resolved = resolve_enabled_tools(_agent(["read", "cron"], cron_enabled=True))
    assert resolved == ["read", "cron"]


def test_cron_absent_when_disabled() -> None:
    """cron absent when cron_enabled=False, even if other tools are present."""
    resolved = resolve_enabled_tools(_agent(["read", "write"]))
    assert resolved == ["read", "write"]
    assert "cron" not in resolved
