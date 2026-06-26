"""feat-440-M1: semantic tool-rejection feedback text builder.

Covers the four-class mapping of ``build_reject_message`` plus the CC-verbatim /
localization invariants on the constants. The model-facing rejection text is the
only observable contract here, so we assert the exact strings rather than internals.
"""

from agent.core.agent.reject_messages import (
    DENIAL_WORKAROUND_GUIDANCE,
    REJECT_MESSAGE,
    REJECT_MESSAGE_WITH_REASON_PREFIX,
    SUBAGENT_REJECT_MESSAGE,
    auto_reject_message,
    build_reject_message,
)

# CC src/utils/messages.ts bodies (Provenance: claude-code messages.ts), with the
# single localization new_string → newText (本项目 Edit 参数名, edit.py:116).
_CC_REJECT = (
    "The user doesn't want to proceed with this tool use. The tool use was "
    "rejected (eg. if it was a file edit, the newText was NOT written to the "
    "file). STOP what you are doing and wait for the user to tell you how to proceed."
)
_CC_REJECT_WITH_REASON_PREFIX = (
    "The user doesn't want to proceed with this tool use. The tool use was "
    "rejected (eg. if it was a file edit, the newText was NOT written to the "
    "file). To tell you how to proceed, the user said:\n"
)
_CC_SUBAGENT_REJECT = (
    "Permission for this tool use was denied. The tool use was rejected (eg. if "
    "it was a file edit, the newText was NOT written to the file). Try a "
    "different approach or report the limitation to complete your task."
)


class TestConstantsVerbatim:
    def test_reject_message_matches_cc_body_localized(self):
        assert REJECT_MESSAGE == _CC_REJECT

    def test_reject_with_reason_prefix_matches_cc_body_localized(self):
        assert REJECT_MESSAGE_WITH_REASON_PREFIX == _CC_REJECT_WITH_REASON_PREFIX

    def test_subagent_reject_matches_cc_body_localized(self):
        assert SUBAGENT_REJECT_MESSAGE == _CC_SUBAGENT_REJECT

    def test_new_string_is_localized_to_newText(self):
        # CC's private Edit param name must not leak; localized to this project's.
        for const in (
            REJECT_MESSAGE,
            REJECT_MESSAGE_WITH_REASON_PREFIX,
            SUBAGENT_REJECT_MESSAGE,
        ):
            assert "new_string" not in const
            assert "newText" in const

    def test_denial_workaround_guidance_verbatim(self):
        assert DENIAL_WORKAROUND_GUIDANCE == (
            "IMPORTANT: You *may* attempt to accomplish this action using other "
            "tools that might naturally be used to accomplish this goal, e.g. using "
            "head instead of cat. But you *should not* attempt to work around this "
            "denial in malicious ways, e.g. do not use your ability to run tests to "
            "execute non-test actions. You should only try to work around this "
            "restriction in reasonable ways that do not attempt to bypass the intent "
            "behind this denial. If you believe this capability is essential to "
            "complete the user's request, STOP and explain to the user what you were "
            "trying to do and why you need this permission. Let the user decide how "
            "to proceed."
        )


class TestAutoRejectMessage:
    def test_auto_reject_prefix_and_reason_and_guidance(self):
        msg = auto_reject_message("blocked by classifier")
        assert msg == (
            "Permission for this action has been denied. Reason: blocked by "
            "classifier. " + DENIAL_WORKAROUND_GUIDANCE
        )

    def test_auto_reject_has_no_settings_rule_hint(self):
        # 本项目无 settings/Bash(...) 权限规则 UX — the CC rule-hint sentence is dropped.
        msg = auto_reject_message("no permission channel (fail-closed)")
        assert "settings" not in msg
        assert "permission rule" not in msg


class TestBuildRejectMessageMapping:
    def test_subagent_takes_precedence(self):
        # is_subagent=True wins regardless of approval/reason (non-allowlisted
        # synthetic error path carries neither, but still → SUBAGENT).
        assert (
            build_reject_message(approval=None, reason=None, is_subagent=True)
            == SUBAGENT_REJECT_MESSAGE
        )
        assert (
            build_reject_message(approval="user_deny", reason="x", is_subagent=True)
            == SUBAGENT_REJECT_MESSAGE
        )

    def test_user_deny_with_reason(self):
        msg = build_reject_message(
            approval="user_deny", reason="先别动这个文件", is_subagent=False
        )
        assert msg == REJECT_MESSAGE_WITH_REASON_PREFIX + "先别动这个文件"

    def test_user_deny_without_reason(self):
        assert (
            build_reject_message(approval="user_deny", reason="", is_subagent=False)
            == REJECT_MESSAGE
        )
        assert (
            build_reject_message(approval="user_deny", reason=None, is_subagent=False)
            == REJECT_MESSAGE
        )

    def test_auto_reject_when_no_approval(self):
        msg = build_reject_message(
            approval=None, reason="deny-limit exceeded", is_subagent=False
        )
        assert msg == auto_reject_message("deny-limit exceeded")
