from nano_multiagent.core.agent.skill_commands import rewrite_skill_command


def test_skill_command_rewrite_contract_without_user_args() -> None:
    assert rewrite_skill_command("/skill:doc") == 'Use the "doc" skill for this request.'


def test_skill_command_rewrite_contract_with_user_args() -> None:
    assert rewrite_skill_command("/skill:doc fix heading spacing") == (
        'Use the "doc" skill for this request.\nUser input:\nfix heading spacing'
    )
