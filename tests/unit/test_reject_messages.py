"""Semantic tool-rejection feedback tests."""

from agent.core.agent.reject_messages import (
    DENIAL_WORKAROUND_GUIDANCE,
    REJECT_MESSAGE,
    REJECT_MESSAGE_WITH_REASON_PREFIX,
    SUBAGENT_REJECT_MESSAGE,
    auto_reject_message,
    build_reject_message,
)


def test_auto_reject_includes_reason_and_safety_guidance() -> None:
    message = auto_reject_message("blocked by classifier")

    assert "blocked by classifier" in message
    assert DENIAL_WORKAROUND_GUIDANCE in message


def test_auto_reject_empty_reason_omits_broken_reason_clause() -> None:
    message = auto_reject_message("")

    assert "Reason:" not in message
    assert DENIAL_WORKAROUND_GUIDANCE in message


def test_subagent_rejection_takes_precedence() -> None:
    assert (
        build_reject_message(approval=None, reason=None, is_subagent=True)
        == SUBAGENT_REJECT_MESSAGE
    )
    assert (
        build_reject_message(approval="user_deny", reason="x", is_subagent=True)
        == SUBAGENT_REJECT_MESSAGE
    )


def test_user_rejection_preserves_optional_reason() -> None:
    assert (
        build_reject_message(
            approval="user_deny", reason="先别动这个文件", is_subagent=False
        )
        == REJECT_MESSAGE_WITH_REASON_PREFIX + "先别动这个文件"
    )
    assert (
        build_reject_message(approval="user_deny", reason="", is_subagent=False)
        == REJECT_MESSAGE
    )
    assert (
        build_reject_message(approval="user_deny", reason=None, is_subagent=False)
        == REJECT_MESSAGE
    )


def test_missing_approval_uses_auto_rejection_semantics() -> None:
    assert build_reject_message(
        approval=None, reason="deny-limit exceeded", is_subagent=False
    ) == auto_reject_message("deny-limit exceeded")
    assert build_reject_message(
        approval=None, reason="", is_subagent=False
    ) == auto_reject_message("")
