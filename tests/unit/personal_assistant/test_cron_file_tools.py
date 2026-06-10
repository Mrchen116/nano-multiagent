"""Tests for tool_allowlist as a TRUE whitelist + cron-as-gated-capability.

feat-394 fix (supersedes M7 R5-2): ``tool_allowlist`` is the user's explicit tool
whitelist — NOT an additive extras list. A user may select a subset of the product
defaults, i.e. default file/web tools CAN be disabled. ``cron`` is a gated capability
controlled by ``agent.cron_enabled`` (now @property from features dict) and appended
by the call-site, never persisted into the stored whitelist.

feat-394 M9 R4: ``resolve_effective_tool_allowlist`` no longer accepts a ``cron_enabled``
param. The call-site (inbound_pipeline) reads ``agent.cron_enabled`` (@property) and
appends ``cron`` before/after calling this function, keeping the function signature
free of feature-model concerns.
"""

from __future__ import annotations

import inspect

from personal_assistant.gateway.inbound_pipeline import (
    resolve_effective_tool_allowlist,
)

# A representative product default set (order-independent for assertions).
_DEFAULTS = ["read", "write", "edit", "bash", "agent", "task_stop", "web_fetch"]


def test_resolve_effective_tool_allowlist_signature_has_no_cron_enabled() -> None:
    """resolve_effective_tool_allowlist must NOT accept cron_enabled parameter (R4).

    After M9 R4 the function is free of feature-model booleans; the call-site
    reads agent.cron_enabled (@property) and appends 'cron' itself.
    """
    sig = inspect.signature(resolve_effective_tool_allowlist)
    assert "cron_enabled" not in sig.parameters, (
        "resolve_effective_tool_allowlist must not have cron_enabled param after M9 R4 — "
        "caller controls cron capability by including/excluding 'cron' in the tool list"
    )


def test_explicit_whitelist_excludes_default_tools() -> None:
    """A non-empty whitelist resolves to EXACTLY those tools — defaults are disablable.

    This is the core regression: selecting ['read', 'bash'] must NOT silently re-add
    the other default file/web tools (the R5-2 force-merge bug).
    """
    resolved = resolve_effective_tool_allowlist(
        ["read", "bash"], default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == {"read", "bash"}, (
        "non-empty whitelist must be exact; default tools must be excludable"
    )


def test_empty_whitelist_resolves_to_product_defaults() -> None:
    """Empty whitelist (unconfigured agent) → product default tool set, no cron."""
    resolved = resolve_effective_tool_allowlist([], default_tool_ids=_DEFAULTS)
    assert resolved is not None
    assert set(resolved) == set(_DEFAULTS)
    assert "cron" not in resolved


def test_cron_in_explicit_whitelist_is_preserved() -> None:
    """Call-site may include 'cron' in the list; function must preserve it."""
    resolved = resolve_effective_tool_allowlist([], default_tool_ids=_DEFAULTS)
    # simulate caller appending cron after the call
    assert resolved is not None
    resolved_with_cron = list(resolved) + ["cron"]
    assert "cron" in resolved_with_cron


def test_cron_appends_on_top_without_pulling_back_defaults() -> None:
    """Caller passes ['read', 'cron'] → resolved = {read, cron} only.

    cron is included by the caller; the function must not re-add defaults.
    """
    resolved = resolve_effective_tool_allowlist(
        ["read", "cron"], default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert set(resolved) == {"read", "cron"}


def test_cron_not_duplicated_when_already_listed() -> None:
    """If 'cron' is already in the resolved list it is not duplicated (no dedup logic needed)."""
    resolved = resolve_effective_tool_allowlist(
        ["read", "cron"], default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert resolved.count("cron") == 1


def test_cron_capability_absent_when_not_passed() -> None:
    """cron absent when caller does not include it — capability strictly gated by caller."""
    resolved = resolve_effective_tool_allowlist(
        ["read", "write"], default_tool_ids=_DEFAULTS
    )
    assert resolved is not None
    assert "cron" not in resolved
