"""Behavior tests for the managed Feishu capability catalog."""

from __future__ import annotations

import pytest

from personal_assistant.channels.feishu.diagnostics import (
    FEISHU_CAPABILITY_CATALOG,
    FeishuDiagnosticCheck,
    evaluate_scope_capabilities,
    summarize_diagnostics,
)


EXPECTED_ACCEPTED_SCOPE_SETS = {
    "feishu.receive_p2p": [
        {"im:message.p2p_msg:readonly"},
        {"im:message.p2p_msg"},
    ],
    "feishu.receive_group_at": [
        {"im:message.group_at_msg:readonly"},
        {"im:message.group_at_msg"},
    ],
    "feishu.send_message": [
        {"im:message:send_as_bot"},
        {"im:message"},
        {"im:message:send"},
    ],
    "feishu.receive_group_message": [
        {"im:message.group_msg"},
        {"im:message.group_msg:readonly"},
    ],
    "feishu.message_history": [
        {"im:message:readonly"},
        {"im:message"},
        {"im:message.history:readonly"},
    ],
    "feishu.group_history": [
        {"im:message:readonly", "im:message.group_msg"},
        {"im:message:readonly", "im:message.group_msg:readonly"},
        {"im:message", "im:message.group_msg"},
        {"im:message", "im:message.group_msg:readonly"},
        {"im:message.history:readonly", "im:message.group_msg"},
        {"im:message.history:readonly", "im:message.group_msg:readonly"},
    ],
    "feishu.write_reaction": [
        {"im:message.reactions:write_only"},
        {"im:message"},
    ],
    "feishu.read_chat": [
        {"im:chat:readonly"},
        {"im:chat:read"},
        {"im:chat"},
        {"im:chat.group_info:readonly"},
    ],
}


def test_catalog_matches_current_and_supported_legacy_scope_contract() -> None:
    actual = {
        item.check_id: [set(scope_set) for scope_set in item.accepted_scope_sets]
        for item in FEISHU_CAPABILITY_CATALOG
    }

    assert actual == EXPECTED_ACCEPTED_SCOPE_SETS
    by_id = {item.check_id: item for item in FEISHU_CAPABILITY_CATALOG}
    assert by_id["feishu.receive_group_message"].recommended_scopes == (
        "im:message.group_msg",
    )
    assert by_id["feishu.read_chat"].recommended_scopes == ("im:chat:readonly",)
    assert (
        "legacy"
        not in " ".join(
            scope
            for item in FEISHU_CAPABILITY_CATALOG
            for scope in item.recommended_scopes
        ).lower()
    )


@pytest.mark.parametrize(
    ("check_id", "granted"),
    [
        (check_id, frozenset(scope_set))
        for check_id, accepted_sets in EXPECTED_ACCEPTED_SCOPE_SETS.items()
        for scope_set in accepted_sets
    ],
)
def test_every_current_or_legacy_accepted_set_satisfies_its_capability(
    check_id: str,
    granted: frozenset[str],
) -> None:
    checks = evaluate_scope_capabilities(granted)

    target = next(item for item in checks if item.check_id == check_id)
    assert target.state == "satisfied"


def test_complete_probe_only_marks_missing_when_no_full_set_is_granted() -> None:
    checks = evaluate_scope_capabilities(frozenset({"im:message:readonly"}))

    group_history = next(
        item for item in checks if item.check_id == "feishu.group_history"
    )
    assert group_history.state == "missing"


def test_unknown_probe_never_invents_a_missing_scope() -> None:
    checks = evaluate_scope_capabilities(None)

    assert {item.state for item in checks} == {"unknown"}
    assert summarize_diagnostics(checks).state == "unknown"


def test_confirmed_missing_precedes_other_unknown_checks_in_aggregate() -> None:
    summary = summarize_diagnostics(
        (
            FeishuDiagnosticCheck(
                check_id="feishu.receive_group_message",
                state="missing",
                accepted_scope_sets=(("im:message.group_msg",),),
                recommended_scopes=("im:message.group_msg",),
                effect="Group background context is incomplete.",
                remediation="Grant the recommended scope and publish the app.",
            ),
            FeishuDiagnosticCheck(
                check_id="feishu.event_subscription",
                state="unknown",
                accepted_scope_sets=(),
                recommended_scopes=(),
                effect="Event delivery could not be confirmed.",
                remediation="Retry the check later.",
            ),
        )
    )

    assert summary.state == "limited"
    assert [item.state for item in summary.checks] == ["missing", "unknown"]
