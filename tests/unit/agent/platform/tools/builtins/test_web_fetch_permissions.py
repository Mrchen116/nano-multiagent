"""Tests for WebFetchTool.check_permissions (bugfix-355 M3 R3).

Design ref: bugfix-355 design.md 接口与数据流段 + 锚点 H (G7):

WebFetchTool.check_permissions 5 decision branches:
  1. URL parse failure → ask (reason="Invalid URL")
  2. hostname+pathname in PREAPPROVED_HOSTS → allow (preapproved)
  3. HostnameRuleEngine.evaluate → deny/ask/allow from user rules
  4. fallback → ask ("permission not granted yet")

Also verifies SAFE_TOOL_ALLOWLIST no longer contains web_fetch.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


def _make_tool(
    deny_hosts=(),
    ask_hosts=(),
    allow_hosts=(),
    extra_preapproved=(),
):
    """Create a WebFetchTool instance with a config-backed check_permissions."""
    from agent.platform.tools.builtins.web_fetch import WebFetchTool  # noqa: PLC0415
    from agent.platform.config.auto_mode import AutoModeConfig, WebFetchConfig  # noqa: PLC0415

    tool = WebFetchTool()
    tool._auto_mode_config = AutoModeConfig(
        web_fetch=WebFetchConfig(
            preapproved_hosts_extra=extra_preapproved,
            deny_hosts=deny_hosts,
            ask_hosts=ask_hosts,
            allow_hosts=allow_hosts,
        )
    )
    return tool


def _check(tool, url: str):
    """Call tool.check_permissions with the given URL."""
    return tool.check_permissions({"url": url}, ctx=None)


class TestCheckPermissionsBranch1_InvalidURL:
    """Branch 1: URL parse / validation failure → ask."""

    def test_empty_url_ask(self):
        tool = _make_tool()
        result = _check(tool, "")
        assert result.behavior == "ask"
        assert "Invalid URL" in result.reason or "url" in result.reason.lower()

    def test_no_schema_ask(self):
        tool = _make_tool()
        result = _check(tool, "example.com/page")
        assert result.behavior == "ask"

    def test_ftp_schema_ask(self):
        tool = _make_tool()
        result = _check(tool, "ftp://example.com/file")
        assert result.behavior == "ask"

    def test_localhost_ask(self):
        """Single-label hostname rejected by _validate_url."""
        tool = _make_tool()
        result = _check(tool, "http://localhost/api")
        assert result.behavior == "ask"


class TestCheckPermissionsBranch2_Preapproved:
    """Branch 2: preapproved host → allow."""

    def test_docs_python_org_allow(self):
        tool = _make_tool()
        result = _check(tool, "https://docs.python.org/3/tutorial/")
        assert result.behavior == "allow"
        assert result.decision_reason is not None
        assert result.decision_reason.get("type") == "preapproved"

    def test_react_dev_allow(self):
        tool = _make_tool()
        result = _check(tool, "https://react.dev/learn")
        assert result.behavior == "allow"

    def test_github_anthropics_allow(self):
        """Path-prefix entry: github.com/anthropics."""
        tool = _make_tool()
        result = _check(tool, "https://github.com/anthropics/claude-code")
        assert result.behavior == "allow"

    def test_github_anthropics_evil_not_allow(self):
        """Path boundary: /anthropics-evil must NOT match /anthropics prefix."""
        tool = _make_tool()
        result = _check(tool, "https://github.com/anthropics-evil/malware")
        # Not preapproved — falls through to hostname rule or fallback ask
        assert result.behavior != "allow" or result.decision_reason.get("type") != "preapproved"

    def test_preapproved_hosts_extra_allow(self):
        """preapproved_hosts_extra from config also grants allow."""
        tool = _make_tool(extra_preapproved=("internal.company.com",))
        result = _check(tool, "https://internal.company.com/docs")
        assert result.behavior == "allow"

    def test_vercel_docs_allow(self):
        tool = _make_tool()
        result = _check(tool, "https://vercel.com/docs/cli")
        assert result.behavior == "allow"

    def test_vercel_pricing_not_preapproved(self):
        """vercel.com/pricing is NOT in preapproved list."""
        tool = _make_tool()
        result = _check(tool, "https://vercel.com/pricing")
        # Should not be allow-via-preapproved; might be ask from fallback
        if result.behavior == "allow":
            assert result.decision_reason is None or result.decision_reason.get("type") != "preapproved"


class TestCheckPermissionsBranch3_HostnameRules:
    """Branch 3: HostnameRuleEngine rule hit → deny/ask/allow."""

    def test_allow_hosts_rule(self):
        tool = _make_tool(allow_hosts=("example.org",))
        result = _check(tool, "https://example.org/x")
        assert result.behavior == "allow"

    def test_deny_hosts_rule(self):
        tool = _make_tool(deny_hosts=("evil.com",))
        result = _check(tool, "https://evil.com/phishing")
        assert result.behavior == "deny"

    def test_ask_hosts_rule(self):
        tool = _make_tool(ask_hosts=("review.io",))
        result = _check(tool, "https://review.io/page")
        assert result.behavior == "ask"

    def test_deny_beats_allow(self):
        tool = _make_tool(deny_hosts=("x.com",), allow_hosts=("x.com",))
        result = _check(tool, "https://x.com/")
        assert result.behavior == "deny"

    def test_preapproved_beats_deny_rule(self):
        """Preapproved check (branch 2) runs before user deny rules (branch 3)."""
        tool = _make_tool(deny_hosts=("docs.python.org",))
        result = _check(tool, "https://docs.python.org/3/")
        # Preapproved → allow, even if user put it in deny_hosts
        assert result.behavior == "allow"


class TestCheckPermissionsBranch4_Fallback:
    """Branch 4: unknown host, no rule → ask (fallback)."""

    def test_unknown_host_ask(self):
        tool = _make_tool()
        result = _check(tool, "https://evil.example.com/data")
        assert result.behavior == "ask"

    def test_unknown_host_ask_reason(self):
        tool = _make_tool()
        result = _check(tool, "https://unknown-host.xyz/")
        assert result.behavior == "ask"
        assert result.reason  # should have a non-empty reason


class TestSafeToolAllowlistNoWebFetch:
    """SAFE_TOOL_ALLOWLIST must not contain web_fetch (bugfix-355 S1)."""

    def test_web_fetch_not_in_safe_allowlist(self):
        from agent.platform.hooks.builtins.auto_mode_gate import SAFE_TOOL_ALLOWLIST  # noqa: PLC0415
        assert "web_fetch" not in SAFE_TOOL_ALLOWLIST

    def test_web_search_not_in_safe_allowlist(self):
        """web_search also removed (S2)."""
        from agent.platform.hooks.builtins.auto_mode_gate import SAFE_TOOL_ALLOWLIST  # noqa: PLC0415
        assert "web_search" not in SAFE_TOOL_ALLOWLIST

    def test_read_still_in_safe_allowlist(self):
        from agent.platform.hooks.builtins.auto_mode_gate import SAFE_TOOL_ALLOWLIST  # noqa: PLC0415
        assert "read" in SAFE_TOOL_ALLOWLIST
