from pathlib import Path

from nano_multiagent.agent.prompting import build_prompt_messages
from nano_multiagent.core.types import Message
from nano_multiagent.skills.registry import SkillMetadata


def test_build_prompt_messages_includes_system_history_and_user() -> None:
    history = (
        Message(message_id="msg_1", role="assistant", content="past answer"),
    )

    prompts = build_prompt_messages(history_messages=history, user_text="new question")

    assert [item.role for item in prompts] == ["system", "assistant", "user"]
    assert prompts[0].content.startswith("You are nano-multiagent")
    assert prompts[-1].content == "new question"


def test_build_prompt_messages_injects_available_skills_section_with_absolute_location() -> None:
    relative_location = Path("./relative/demo/SKILL.md")
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="run this",
        available_skills=(
            SkillMetadata(
                name="demo",
                description="demo skill",
                location=relative_location,
                base_dir=relative_location.parent,
            ),
        ),
    )

    system_prompt = prompts[0].content
    assert "<available_skills>" in system_prompt
    assert "<name>demo</name>" in system_prompt
    assert "Use the read tool to load a skill's file" in system_prompt
    assert "resolve it against the skill directory" in system_prompt
    assert f"<location>{relative_location.expanduser().resolve()}</location>" in system_prompt


def test_build_prompt_messages_skips_available_skills_section_when_empty() -> None:
    prompts = build_prompt_messages(history_messages=(), user_text="run this", available_skills=())
    assert "<available_skills>" not in prompts[0].content
