"""Normalize Feishu tenant grants into actionable capability diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence


DiagnosticState = Literal["satisfied", "missing", "unknown"]


@dataclass(frozen=True, slots=True)
class FeishuScopeProbe:
    """Represent one complete or unusable tenant-authorization response."""

    complete: bool
    granted_scopes: frozenset[str] | None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class FeishuCapability:
    """Define every supported scope set for one user-visible capability."""

    check_id: str
    accepted_scope_sets: tuple[tuple[str, ...], ...]
    recommended_scopes: tuple[str, ...]
    effect: str
    remediation: str


@dataclass(frozen=True, slots=True)
class FeishuDiagnosticCheck:
    """Describe one evaluated capability and its remediation contract."""

    check_id: str
    state: DiagnosticState
    accepted_scope_sets: tuple[tuple[str, ...], ...]
    recommended_scopes: tuple[str, ...]
    effect: str
    remediation: str

    def as_payload(self) -> dict[str, object]:
        """Serialize the provider check for the channel status protocol."""
        return {
            "check_id": self.check_id,
            "state": self.state,
            "required": {
                "accepted_scope_sets": [
                    list(scope_set) for scope_set in self.accepted_scope_sets
                ],
                "recommended_scopes": list(self.recommended_scopes),
            },
            "effect": self.effect,
            "remediation": self.remediation,
        }


@dataclass(frozen=True, slots=True)
class FeishuDiagnostics:
    """Aggregate checks without hiding confirmed gaps behind unknown probes."""

    state: Literal["complete", "limited", "unknown"]
    checks: tuple[FeishuDiagnosticCheck, ...]

    def check_payloads(self) -> tuple[dict[str, object], ...]:
        """Return immutable-order protocol payloads for one status snapshot."""
        return tuple(check.as_payload() for check in self.checks)


_GROUP_HISTORY_SCOPE_SETS = tuple(
    (history_scope, group_scope)
    for history_scope in (
        "im:message:readonly",
        "im:message",
        "im:message.history:readonly",
    )
    for group_scope in (
        "im:message.group_msg",
        "im:message.group_msg:readonly",
    )
)


FEISHU_CAPABILITY_CATALOG: tuple[FeishuCapability, ...] = (
    FeishuCapability(
        check_id="feishu.receive_p2p",
        accepted_scope_sets=(
            ("im:message.p2p_msg:readonly",),
            ("im:message.p2p_msg",),
        ),
        recommended_scopes=("im:message.p2p_msg:readonly",),
        effect="The bot cannot receive direct messages.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.receive_group_at",
        accepted_scope_sets=(
            ("im:message.group_at_msg:readonly",),
            ("im:message.group_at_msg",),
        ),
        recommended_scopes=("im:message.group_at_msg:readonly",),
        effect="Messages that mention the bot in a group cannot trigger the Agent.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.send_message",
        accepted_scope_sets=(
            ("im:message:send_as_bot",),
            ("im:message",),
            ("im:message:send",),
        ),
        recommended_scopes=("im:message:send_as_bot",),
        effect="The Agent cannot reply through this bot.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.receive_group_message",
        accepted_scope_sets=(
            ("im:message.group_msg",),
            ("im:message.group_msg:readonly",),
        ),
        recommended_scopes=("im:message.group_msg",),
        effect="Messages without an @Bot mention do not enter group background context.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.message_history",
        accepted_scope_sets=(
            ("im:message:readonly",),
            ("im:message",),
            ("im:message.history:readonly",),
        ),
        recommended_scopes=("im:message:readonly",),
        effect="Message history cannot be recovered after an interruption.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.group_history",
        accepted_scope_sets=_GROUP_HISTORY_SCOPE_SETS,
        recommended_scopes=(
            "im:message:readonly",
            "im:message.group_msg",
        ),
        effect="Group history cannot provide complete background context.",
        remediation="Grant both recommended scopes and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.write_reaction",
        accepted_scope_sets=(
            ("im:message.reactions:write_only",),
            ("im:message",),
        ),
        recommended_scopes=("im:message.reactions:write_only",),
        effect="The bot cannot show the THINKING reaction while processing.",
        remediation="Grant the recommended scope and publish the app.",
    ),
    FeishuCapability(
        check_id="feishu.read_chat",
        accepted_scope_sets=(
            ("im:chat:readonly",),
            ("im:chat:read",),
            ("im:chat",),
            ("im:chat.group_info:readonly",),
        ),
        recommended_scopes=("im:chat:readonly",),
        effect="Group shadow-conversation titles may fall back to a chat ID.",
        remediation="Grant the recommended scope and publish the app.",
    ),
)


def normalize_tenant_scope_grants(data: object) -> FeishuScopeProbe:
    """Accept only fully parsed tenant grants from Feishu application v6."""
    raw_scopes = _read_value(data, "scopes")
    if raw_scopes is None:
        raw_scopes = _read_value(data, "items")
    if not isinstance(raw_scopes, Sequence) or isinstance(
        raw_scopes, (str, bytes, bytearray)
    ):
        return FeishuScopeProbe(False, None, "scope_payload_invalid")

    granted: set[str] = set()
    for item in raw_scopes:
        scope_name = _first_text(item, ("scope_name", "scopeName", "name"))
        grant_status = _read_value(item, "grant_status")
        scope_type = _read_value(item, "scope_type")
        if (
            scope_name is None
            or isinstance(grant_status, bool)
            or not isinstance(grant_status, int)
            or grant_status not in {1, 2}
            or scope_type not in {"tenant", "user"}
        ):
            return FeishuScopeProbe(False, None, "scope_payload_invalid")
        if grant_status == 1 and scope_type == "tenant":
            granted.add(scope_name)
    return FeishuScopeProbe(True, frozenset(granted))


def evaluate_scope_capabilities(
    granted_scopes: frozenset[str] | None,
) -> tuple[FeishuDiagnosticCheck, ...]:
    """Evaluate complete accepted sets or preserve an unknown probe wholesale."""
    checks: list[FeishuDiagnosticCheck] = []
    for capability in FEISHU_CAPABILITY_CATALOG:
        if granted_scopes is None:
            state: DiagnosticState = "unknown"
        else:
            state = (
                "satisfied"
                if any(
                    frozenset(scope_set).issubset(granted_scopes)
                    for scope_set in capability.accepted_scope_sets
                )
                else "missing"
            )
        checks.append(
            FeishuDiagnosticCheck(
                check_id=capability.check_id,
                state=state,
                accepted_scope_sets=capability.accepted_scope_sets,
                recommended_scopes=capability.recommended_scopes,
                effect=capability.effect,
                remediation=capability.remediation,
            )
        )
    return tuple(checks)


def summarize_diagnostics(
    checks: Sequence[FeishuDiagnosticCheck],
) -> FeishuDiagnostics:
    """Aggregate missing before unknown, otherwise report complete."""
    frozen = tuple(checks)
    if any(check.state == "missing" for check in frozen):
        state: Literal["complete", "limited", "unknown"] = "limited"
    elif any(check.state == "unknown" for check in frozen):
        state = "unknown"
    else:
        state = "complete"
    return FeishuDiagnostics(state=state, checks=frozen)


def _read_value(value: object, key: str) -> object:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _first_text(value: object, keys: Sequence[str]) -> str | None:
    for key in keys:
        candidate = _read_value(value, key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None
