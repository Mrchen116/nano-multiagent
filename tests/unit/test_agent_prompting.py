from pathlib import Path

from nano_multiagent.core.agent.prompting import CODING_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT, build_prompt_messages
from nano_multiagent.core.types import Message
from nano_multiagent.core.types import ToolSpec
from nano_multiagent.core.skills.registry import SkillMetadata


def test_default_system_prompt_is_generic_fallback() -> None:
    """DEFAULT_SYSTEM_PROMPT must be a generic (non-coding-specific) fallback after M76."""
    # Generic fallback: empty string or a non-coding-specific placeholder.
    assert "coding assistant" not in DEFAULT_SYSTEM_PROMPT
    assert "expert coding" not in DEFAULT_SYSTEM_PROMPT


def test_coding_system_prompt_contains_coding_content() -> None:
    """CODING_SYSTEM_PROMPT must contain the coding-specific assistant persona."""
    assert "coding assistant" in CODING_SYSTEM_PROMPT or "expert coding" in CODING_SYSTEM_PROMPT
    assert "Available tools:" in CODING_SYSTEM_PROMPT
    assert "Guidelines:" in CODING_SYSTEM_PROMPT


def test_build_prompt_messages_includes_system_history_and_user() -> None:
    history = (
        Message(message_id="msg_1", role="assistant", content="past answer"),
    )

    # Explicit CODING_SYSTEM_PROMPT: verify coding content renders correctly.
    prompts = build_prompt_messages(
        history_messages=history,
        user_text="new question",
        system_prompt=CODING_SYSTEM_PROMPT,
    )

    assert [item.role for item in prompts] == ["system", "assistant", "user"]
    assert prompts[0].content.startswith("You are an expert coding assistant")
    assert "Available tools:" in prompts[0].content
    assert "Guidelines:" in prompts[0].content
    assert "Current date and time:" in prompts[0].content
    assert "Current working directory:" in prompts[0].content
    assert "input_schema" not in prompts[0].content
    assert "<RUNTIME_FILL:" not in prompts[0].content
    assert "input_schema" not in prompts[0].content
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
    # Use CODING_SYSTEM_PROMPT explicitly: default is now generic empty string.
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="run this",
        system_prompt=CODING_SYSTEM_PROMPT,
        available_skills=(),
    )
    assert "<available_skills>" not in prompts[0].content
    assert "Available tools:" in prompts[0].content
    assert "input_schema" not in prompts[0].content


def test_build_prompt_messages_only_displays_tool_name_and_description() -> None:
    # Use CODING_SYSTEM_PROMPT explicitly: default is now generic empty string.
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="run this",
        system_prompt=CODING_SYSTEM_PROMPT,
        available_tools=(
            ToolSpec(
                name="read",
                description="Read file contents",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
        ),
    )

    system_prompt = prompts[0].content
    assert "Available tools:" in system_prompt
    assert "- read: Read file contents" in system_prompt
    assert "input_schema" not in system_prompt
