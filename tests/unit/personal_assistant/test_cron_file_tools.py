"""Tests for tool_allowlist as a TRUE whitelist + cron-as-gated-capability.

feat-394 fix (supersedes M7 R5-2): ``tool_allowlist`` is the user's explicit tool
whitelist — NOT an additive extras list. A user may select a subset of the product
defaults, i.e. default file/web tools CAN be disabled. ``cron`` is a gated capability
controlled by ``cron_enabled`` and appended on top; it is never part of the stored
whitelist.

These tests exercise the real ``resolve_effective_tool_allowlist`` function (single
source of truth used by the inbound pipeline), not an inline copy of the logic.
"""

from __future__ import annotations

from personal_assistant.gateway.inbound_pipeline import (
    resolve_effective_tool_allowlist,
)

# A representative product default set (order-independent for assertions).
_DEFAULTS = ["read", "write", "edit", "bash", "agent", "task_stop", "web_fetch"]


def test_explicit_whitelist_excludes_default_tools() -> None:
    """A non-empty whitelist resolves to EXACTLY those tools — defaults are disablable.

    This is the core regression: selecting ['read', 'bash'] must NOT silently re-add
    the other default file/web tools (the R5-2 force-merge bug).
    """
    resolved = resolve_effective_tool_allowlist(
        ["read", "bash"], cron_enabled=False, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == {"read", "bash"}, (
        "non-empty whitelist must be exact; default tools must be excludable"
    )


def test_empty_whitelist_resolves_to_product_defaults() -> None:
    """Empty whitelist (unconfigured agent) → product default tool set, no cron."""
    resolved = resolve_effective_tool_allowlist(
        [], cron_enabled=False, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == set(_DEFAULTS)
    assert "cron" not in resolved


def test_empty_whitelist_with_cron_enabled_appends_cron() -> None:
    """Empty whitelist + cron on → defaults + cron (cron appended as a capability)."""
    resolved = resolve_effective_tool_allowlist(
        [], cron_enabled=True, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == set(_DEFAULTS) | {"cron"}


def test_cron_appends_on_top_without_pulling_back_defaults() -> None:
    """Whitelist ['read'] + cron on → {read, cron} only.

    cron is appended on top of the explicit whitelist; it must NOT trigger re-adding
    the other defaults (that conflation was the R5-2 root cause).
    """
    resolved = resolve_effective_tool_allowlist(
        ["read"], cron_enabled=True, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == {"read", "cron"}


def test_cron_not_duplicated_when_already_listed() -> None:
    """If 'cron' is somehow already in the whitelist, cron_enabled must not duplicate it."""
    resolved = resolve_effective_tool_allowlist(
        ["read", "cron"], cron_enabled=True, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert resolved.count("cron") == 1


def test_cron_capability_never_persisted_into_whitelist_semantics() -> None:
    """cron off → cron absent even if defaults are used (capability strictly gated)."""
    resolved = resolve_effective_tool_allowlist(
        ["read", "write"], cron_enabled=False, default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert "cron" not in resolved
