from nano_multiagent.agent.prompting import build_prompt_messages
from nano_multiagent.core.types import Message


def test_build_prompt_messages_includes_system_history_and_user() -> None:
    history = (
        Message(message_id="msg_1", role="assistant", content="past answer"),
    )

    prompts = build_prompt_messages(history_messages=history, user_text="new question")

    assert [item.role for item in prompts] == ["system", "assistant", "user"]
    assert prompts[0].content.startswith("You are nano-multiagent")
    assert prompts[-1].content == "new question"
