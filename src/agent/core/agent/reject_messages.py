"""Semantic tool-rejection feedback text (feat-440-M1).

When a tool call is blocked, the LLM-visible tool result must tell it *why* —
otherwise it can't tell a user's deliberate "Deny" from an automatic policy block
and ends up retrying the same operation with a tweaked argument (the symptom this
unit fixes). This module centralizes the four rejection texts (mirroring CC's
``src/utils/messages.ts`` constant-集中 pattern) and a single selector so the
mapping can be exhaustively unit-tested.

Provenance: claude-code ``src/utils/messages.ts``. The message bodies are copied
verbatim with three localizations (design 决策 2):
  - the example param name ``new_string`` → ``newText`` (this project's Edit param,
    edit.py:116; CC's ``old_string/new_string`` is its own private naming);
  - CC's auto-reject "add a Bash(...) rule to settings" hint is dropped — this
    project's permission rules live in YAML ``config.allow/soft_deny``, not a
    settings UX, so the sentence has no本项目 meaning;
  - ``DONT_ASK_REJECT_MESSAGE`` is not implemented — this project has no
    don't-ask mode.

Intentional omission: CC's ``SUBAGENT_REJECT_MESSAGE_WITH_REASON_PREFIX`` (the
with-reason subagent variant) is deliberately NOT ported. This project's subagents
are unattended (fork side-chain, no permission channel) and therefore never produce
a ``user_deny`` — a with-reason subagent rejection is a dead path. Do not "complete"
the set by adding it unless subagents gain an authorization channel.
"""

# Main-session user reject (Provenance: messages.ts REJECT_MESSAGE), newText-localized.
REJECT_MESSAGE = (
    "The user doesn't want to proceed with this tool use. The tool use was "
    "rejected (eg. if it was a file edit, the newText was NOT written to the "
    "file). STOP what you are doing and wait for the user to tell you how to proceed."
)

# User reject with reason — the user's verbatim reason is appended after this prefix.
REJECT_MESSAGE_WITH_REASON_PREFIX = (
    "The user doesn't want to proceed with this tool use. The tool use was "
    "rejected (eg. if it was a file edit, the newText was NOT written to the "
    "file). To tell you how to proceed, the user said:\n"
)

# Subagent reject (Provenance: messages.ts SUBAGENT_REJECT_MESSAGE): "换做法/上报"
# rather than the main session's "停下等人" — a subagent has no user to wait on.
SUBAGENT_REJECT_MESSAGE = (
    "Permission for this tool use was denied. The tool use was rejected (eg. if "
    "it was a file edit, the newText was NOT written to the file). Try a "
    "different approach or report the limitation to complete your task."
)

# Shared workaround guidance for permission denials (Provenance: messages.ts
# DENIAL_WORKAROUND_GUIDANCE, verbatim — contains no CC-private names).
DENIAL_WORKAROUND_GUIDANCE = (
    "IMPORTANT: You *may* attempt to accomplish this action using other tools "
    "that might naturally be used to accomplish this goal, e.g. using head "
    "instead of cat. But you *should not* attempt to work around this denial in "
    "malicious ways, e.g. do not use your ability to run tests to execute "
    "non-test actions. You should only try to work around this restriction in "
    "reasonable ways that do not attempt to bypass the intent behind this "
    "denial. If you believe this capability is essential to complete the user's "
    "request, STOP and explain to the user what you were trying to do and why "
    "you need this permission. Let the user decide how to proceed."
)

# Prefix for automatic (policy/classifier) denials. Provenance: messages.ts
# AUTO_MODE_REJECTION_PREFIX.
_AUTO_REJECT_PREFIX = "Permission for this action has been denied. Reason: "


def auto_reject_message(reason: str) -> str:
    """Build the auto-reject text for a policy/classifier block.

    design 决策 2 (review R1): CC splits auto reject into ``AUTO_REJECT_MESSAGE``
    (no reason) and ``buildYoloRejectionMessage`` (with reason). Every auto block
    in this project carries a ``reason`` string (classifier ``<reason>`` /
    "no permission channel (fail-closed)" / "gate error: ..." / "deny-limit
    exceeded..."), so the two collapse into this single with-reason template. The
    CC settings rule-hint tail sentence is dropped (no settings UX here).
    """
    return f"{_AUTO_REJECT_PREFIX}{reason}. {DENIAL_WORKAROUND_GUIDANCE}"


def build_reject_message(
    *, approval: str | None, reason: str | None, is_subagent: bool
) -> str:
    """Select the LLM-visible rejection text from the block's signals.

    Top-down first-match (design 选择逻辑表):
      1. subagent context → SUBAGENT_REJECT_MESSAGE (wins regardless of the other
         signals; the non-allowlisted synthetic-error path carries neither approval
         nor reason but is still a subagent block).
      2. user_deny + reason → REJECT_MESSAGE_WITH_REASON_PREFIX + reason
      3. user_deny + no reason → REJECT_MESSAGE
      4. no approval (automatic block) → auto_reject_message(reason)

    Args:
        approval: gate verdict — ``"user_deny"`` for a user Deny, ``None`` for an
            automatic block.
        reason: free-text reason (user's verbatim text for a Deny, classifier/系统
            string for an auto block). May be empty/None for a bare user Deny.
        is_subagent: True when running inside a fork side-chain (the executor's
            tool_execution_allowlist is active).
    """
    if is_subagent:
        return SUBAGENT_REJECT_MESSAGE
    if approval == "user_deny":
        if reason:
            return REJECT_MESSAGE_WITH_REASON_PREFIX + reason
        return REJECT_MESSAGE
    return auto_reject_message(reason or "")
