"""HostnameRuleEngine: user-configured hostname allow/deny/ask rules for WebFetch.

Implements the D4.2 decision: a simple engine that evaluates a hostname against
three ordered lists (deny, ask, allow) from AutoModeConfig.web_fetch.
Returns the first matching decision, or "passthrough" if no rule matches.

This abstraction is extracted (rather than inlined into WebFetchTool) to provide
a clean, independently testable interface and a reuse point for future URL-based tools.

Priority: deny → ask → allow (deny has highest precedence, matching CC semantics).
Matching: exact match only (no wildcard/subdomain glob in this iteration).
Docstring notes this limitation explicitly so users know www.example.com != example.com.
"""

from __future__ import annotations

from typing import Literal


class HostnameRuleEngine:
    """Evaluate a hostname against user-configured deny/ask/allow rule lists.

    Rules come from ``AutoModeConfig.web_fetch.deny_hosts / ask_hosts / allow_hosts``.
    Priority order: deny → ask → allow (first match wins). No match → passthrough.

    Hostname matching is exact (case-sensitive) in this iteration. Subdomain glob
    and wildcard expansion are not supported; users who want to allow ``sub.example.com``
    must list it explicitly alongside ``example.com`` if both are desired.

    Args:
        deny: Hostnames that should always be denied.
        ask: Hostnames that require user confirmation.
        allow: Hostnames that should be unconditionally allowed.
    """

    def __init__(
        self,
        deny: tuple[str, ...],
        ask: tuple[str, ...],
        allow: tuple[str, ...],
    ) -> None:
        # Store as frozensets for O(1) lookup; order only matters for priority,
        # not for iteration within a tier.
        self._deny: frozenset[str] = frozenset(deny)
        self._ask: frozenset[str] = frozenset(ask)
        self._allow: frozenset[str] = frozenset(allow)

    def evaluate(self, hostname: str) -> Literal["allow", "deny", "ask", "passthrough"]:
        """Evaluate hostname against configured rules.

        Priority: deny wins over ask wins over allow wins over passthrough.

        Args:
            hostname: Lowercased hostname to evaluate (no port, no path).

        Returns:
            "deny" | "ask" | "allow" | "passthrough".
        """
        if hostname in self._deny:
            return "deny"
        if hostname in self._ask:
            return "ask"
        if hostname in self._allow:
            return "allow"
        return "passthrough"
