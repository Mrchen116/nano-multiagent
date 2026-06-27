from agent.core.agent.skill_commands import rewrite_skill_command


def test_skill_command_rewrite_contract_without_user_args() -> None:
    assert (
        rewrite_skill_command("/skill:doc") == 'Use the "doc" skill for this request.'
    )


def test_skill_command_rewrite_contract_with_user_args() -> None:
    assert rewrite_skill_command("/skill:doc fix heading spacing") == (
        'Use the "doc" skill for this request.\nUser input:\nfix heading spacing'
    )


# feat-430: a command may be preceded by an optional `[..]` annotation segment
# (product-agnostic — the kernel does not interpret its content). IM 群聊 prefixes
# each message with `[sender] `; rewrite must still fire and preserve the prefix.


def test_skill_command_rewrite_preserves_leading_bracket_prefix() -> None:
    assert rewrite_skill_command("[Alice] /skill:doc fix spacing") == (
        '[Alice] Use the "doc" skill for this request.\nUser input:\nfix spacing'
    )


def test_skill_command_rewrite_preserves_bracket_prefix_without_args() -> None:
    assert rewrite_skill_command("[Alice] /skill:doc") == (
        '[Alice] Use the "doc" skill for this request.'
    )


def test_skill_command_rewrite_ignores_bracket_when_no_skill_command() -> None:
    # A plain bracketed message that is not a /skill command stays untouched.
    assert rewrite_skill_command("[Alice] hello there") == "[Alice] hello there"
