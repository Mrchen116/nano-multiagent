"""Tests for webfetch_preapproved — PREAPPROVED_HOSTS + is_preapproved_host.

Design ref: bugfix-355 design.md 锚点 H (G7):
- 89 literal entries (matching CC preapproved.ts:14-131)
- HOSTNAME_ONLY / PATH_PREFIXES split at module load
- is_preapproved_host enforces path segment boundaries
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# R1: C1 red tests — module not yet created, these must fail on import
# ---------------------------------------------------------------------------


def _import_module():
    from agent.platform.tools.builtins import webfetch_preapproved  # noqa: PLC0415

    return webfetch_preapproved


class TestPreapprovedHosts:
    """Verify PREAPPROVED_HOSTS is a frozenset of exactly the CC entries."""

    def test_preapproved_hosts_is_frozenset(self):
        mod = _import_module()
        assert isinstance(mod.PREAPPROVED_HOSTS, frozenset)

    def test_preapproved_hosts_has_89_entries(self):
        """CC preapproved.ts:14-131 has 89 string literals (including duplicate learn.microsoft.com).
        As a frozenset deduplication gives 88 unique items."""
        mod = _import_module()
        # The frozenset deduplicates learn.microsoft.com → 88 unique
        assert len(mod.PREAPPROVED_HOSTS) == 88

    def test_known_hostname_only_entries(self):
        mod = _import_module()
        # Spot-check some hostname-only entries from CC
        for host in [
            "docs.python.org",
            "developer.mozilla.org",
            "react.dev",
            "go.dev",
            "pkg.go.dev",
            "doc.rust-lang.org",
            "docs.aws.amazon.com",
            "kubernetes.io",
            "git-scm.com",
        ]:
            assert host in mod.PREAPPROVED_HOSTS, (
                f"{host!r} should be in PREAPPROVED_HOSTS"
            )

    def test_known_path_prefix_entries(self):
        mod = _import_module()
        assert "github.com/anthropics" in mod.PREAPPROVED_HOSTS
        assert "vercel.com/docs" in mod.PREAPPROVED_HOSTS

    def test_hostname_only_split(self):
        """HOSTNAME_ONLY should contain only entries without '/'."""
        mod = _import_module()
        assert isinstance(mod.HOSTNAME_ONLY, frozenset)
        for entry in mod.HOSTNAME_ONLY:
            assert "/" not in entry

    def test_path_prefixes_split(self):
        """PATH_PREFIXES maps hostname → tuple of path prefixes (each starts with '/')."""
        mod = _import_module()
        assert isinstance(mod.PATH_PREFIXES, dict)
        for host, prefixes in mod.PATH_PREFIXES.items():
            assert "/" not in host
            assert isinstance(prefixes, tuple)
            for p in prefixes:
                assert p.startswith("/"), f"path prefix {p!r} must start with '/'"

    def test_all_entries_accounted_for(self):
        """Union of HOSTNAME_ONLY and PATH_PREFIXES hosts should cover all PREAPPROVED_HOSTS."""
        mod = _import_module()
        covered = set(mod.HOSTNAME_ONLY)
        for host in mod.PATH_PREFIXES:
            for p in mod.PATH_PREFIXES[host]:
                covered.add(f"{host}{p}")
        # Every entry in PREAPPROVED_HOSTS must be representable via HOSTNAME_ONLY or PATH_PREFIXES
        for entry in mod.PREAPPROVED_HOSTS:
            slash = entry.find("/")
            if slash == -1:
                assert entry in mod.HOSTNAME_ONLY
            else:
                host = entry[:slash]
                path = entry[slash:]
                assert host in mod.PATH_PREFIXES
                assert path in mod.PATH_PREFIXES[host]


class TestIsPreapprovedHost:
    """Verify is_preapproved_host matches CC isPreapprovedHost semantics."""

    def test_hostname_only_match(self):
        mod = _import_module()
        assert mod.is_preapproved_host("docs.python.org", "/3/tutorial/") is True

    def test_hostname_only_any_path(self):
        mod = _import_module()
        assert mod.is_preapproved_host("react.dev", "/learn") is True
        assert mod.is_preapproved_host("react.dev", "/") is True
        assert mod.is_preapproved_host("react.dev", "") is True

    def test_path_prefix_exact(self):
        mod = _import_module()
        # github.com/anthropics — pathname = /anthropics exactly
        assert mod.is_preapproved_host("github.com", "/anthropics") is True

    def test_path_prefix_with_subpath(self):
        mod = _import_module()
        # github.com/anthropics/... — must match
        assert mod.is_preapproved_host("github.com", "/anthropics/claude-code") is True

    def test_path_prefix_boundary_not_matched(self):
        """'/anthropics-evil' must NOT match the '/anthropics' prefix."""
        mod = _import_module()
        assert mod.is_preapproved_host("github.com", "/anthropics-evil") is False
        assert (
            mod.is_preapproved_host("github.com", "/anthropics-evil/malware") is False
        )

    def test_unknown_host_returns_false(self):
        mod = _import_module()
        assert mod.is_preapproved_host("evil.example.com", "/") is False

    def test_unknown_host_with_matching_path_returns_false(self):
        """Segment boundary only matters for known path-prefix hosts."""
        mod = _import_module()
        assert mod.is_preapproved_host("unknown.org", "/anthropics") is False

    def test_vercel_docs_prefix(self):
        mod = _import_module()
        assert mod.is_preapproved_host("vercel.com", "/docs") is True
        assert mod.is_preapproved_host("vercel.com", "/docs/cli") is True
        # vercel.com without /docs path should NOT be preapproved
        assert mod.is_preapproved_host("vercel.com", "/pricing") is False

    def test_case_sensitive(self):
        """Matching should be case-sensitive (per CC behavior)."""
        mod = _import_module()
        # CC doesn't lowercase hostnames in PREAPPROVED_HOSTS
        assert mod.is_preapproved_host("Docs.Python.Org", "/3/") is False
        assert mod.is_preapproved_host("docs.python.org", "/3/") is True


class TestHostnameRuleEngine:
    """Verify HostnameRuleEngine.evaluate deny→ask→allow priority + exact match."""

    def _engine(self, deny=(), ask=(), allow=()):
        from agent.platform.permissions.hostname_rules import HostnameRuleEngine  # noqa: PLC0415

        return HostnameRuleEngine(deny=deny, ask=ask, allow=allow)

    def test_empty_rules_returns_passthrough(self):
        engine = self._engine()
        assert engine.evaluate("example.com") == "passthrough"

    def test_allow_rule(self):
        engine = self._engine(allow=("example.org",))
        assert engine.evaluate("example.org") == "allow"

    def test_deny_rule(self):
        engine = self._engine(deny=("evil.com",))
        assert engine.evaluate("evil.com") == "deny"

    def test_ask_rule(self):
        engine = self._engine(ask=("confirm.me",))
        assert engine.evaluate("confirm.me") == "ask"

    def test_deny_beats_ask(self):
        """deny has higher priority than ask."""
        engine = self._engine(deny=("x.com",), ask=("x.com",))
        assert engine.evaluate("x.com") == "deny"

    def test_deny_beats_allow(self):
        engine = self._engine(deny=("x.com",), allow=("x.com",))
        assert engine.evaluate("x.com") == "deny"

    def test_ask_beats_allow(self):
        engine = self._engine(ask=("x.com",), allow=("x.com",))
        assert engine.evaluate("x.com") == "ask"

    def test_exact_match_only(self):
        """exact match — subdomain does NOT match parent."""
        engine = self._engine(allow=("example.com",))
        assert engine.evaluate("sub.example.com") == "passthrough"
        assert engine.evaluate("example.com.evil") == "passthrough"

    def test_unknown_host_passthrough(self):
        engine = self._engine(deny=("a.com",), ask=("b.com",), allow=("c.com",))
        assert engine.evaluate("d.com") == "passthrough"
