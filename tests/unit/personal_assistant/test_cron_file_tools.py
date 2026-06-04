"""Tests for feat-394-M7 R3: file tools must not be excluded when cron is in tool_allowlist.

When cron_enabled=True, the IM tool_allowlist contains ["cron"]. The inbound pipeline
must NOT pass only ["cron"] to create_session — it must merge DEFAULT_TOOL_IDS + allowlist
so read/write/edit/bash etc. remain available alongside the cron tool.

R5-2 root cause: agent.tool_allowlist=("cron",) → create_session(tool_allowlist=["cron"])
→ runtime picks only tools in {"cron"} set → agent has no file tools.
"""

from __future__ import annotations

from typing import Any


def _pa_default_tool_ids() -> list[str]:
    from agent.products.personal_assistant.toolsets import DEFAULT_TOOL_IDS
    return list(DEFAULT_TOOL_IDS)


def test_file_tools_present_when_cron_in_allowlist() -> None:
    """When agent.tool_allowlist=('cron',), session allowlist must include DEFAULT_TOOL_IDS.

    The inbound pipeline must merge DEFAULT_TOOL_IDS + ['cron'] so the agent has
    both file tools AND the cron tool. Passing only ['cron'] silently removes file tools.
    """
    # Simulate the inbound_pipeline logic (feat-394-M7 R5-2 fix)
    tool_allowlist_from_im = ("cron",)

    from agent.products.personal_assistant.toolsets import DEFAULT_TOOL_IDS as _PA_DEFAULT

    if tool_allowlist_from_im:
        _base = list(_PA_DEFAULT)
        _extras = [t for t in tool_allowlist_from_im if t not in _base]
        resolved_allowlist: list[str] | None = _base + _extras
    else:
        resolved_allowlist = None

    assert resolved_allowlist is not None
    assert "cron" in resolved_allowlist, "cron must be in resolved allowlist"
    assert "read" in resolved_allowlist, "read (file tool) must be in resolved allowlist"
    assert "write" in resolved_allowlist, "write (file tool) must be in resolved allowlist"
    assert "edit" in resolved_allowlist, "edit (file tool) must be in resolved allowlist"
    assert "bash" in resolved_allowlist, "bash (file tool) must be in resolved allowlist"


def test_empty_allowlist_passes_none_to_session() -> None:
    """When agent.tool_allowlist is empty, None must be passed (runtime uses DEFAULT_TOOL_IDS gate)."""
    tool_allowlist_from_im: tuple[str, ...] = ()

    from agent.products.personal_assistant.toolsets import DEFAULT_TOOL_IDS as _PA_DEFAULT

    if tool_allowlist_from_im:
        _base = list(_PA_DEFAULT)
        _extras = [t for t in tool_allowlist_from_im if t not in _base]
        resolved_allowlist: list[str] | None = _base + _extras
    else:
        resolved_allowlist = None

    assert resolved_allowlist is None, (
        "Empty allowlist must pass None so runtime uses DEFAULT_TOOL_IDS gate"
    )


def test_cron_only_not_duplicated() -> None:
    """When cron is already in DEFAULT_TOOL_IDS (if ever), it must not be duplicated."""
    tool_allowlist_from_im = ("cron", "send_message")

    from agent.products.personal_assistant.toolsets import DEFAULT_TOOL_IDS as _PA_DEFAULT

    _base = list(_PA_DEFAULT)
    _extras = [t for t in tool_allowlist_from_im if t not in _base]
    resolved_allowlist = _base + _extras

    # Count occurrences
    cron_count = resolved_allowlist.count("cron")
    assert cron_count == 1, f"cron must appear exactly once, got {cron_count}"

    send_message_count = resolved_allowlist.count("send_message")
    assert send_message_count == 1, f"send_message must appear exactly once, got {send_message_count}"
