from collections.abc import AsyncIterator
from pathlib import Path

from agent.core.agent.prompting import (
    DEFAULT_SYSTEM_PROMPT,
    MEMORY_GUIDANCE,
    SKILLS_GUIDANCE,
    build_prompt_messages,
    build_system_prompt,
)
from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.core.types import Message
from agent.core.types import ToolSpec
from agent.core.skills.registry import SkillMetadata

# Minimal coding prompt fixture — replaces the deleted CODING_SYSTEM_PROMPT constant.
# Coding-specific content now lives in prompt_sections.py (segment assembly).
# Contains RUNTIME_FILL placeholders so runtime-fill tests remain meaningful.
_CODING_FIXTURE = (
    "You are an expert coding assistant.\n\n"
    "Available tools:\n<RUNTIME_FILL:AVAILABLE_TOOLS>\n\n"
    "Guidelines:\n- Be helpful\n\n"
    "Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>\n"
    "Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"
)


def test_default_system_prompt_is_generic_fallback() -> None:
    """DEFAULT_SYSTEM_PROMPT must be a generic (non-coding-specific) fallback after feat-385."""
    # Generic fallback: empty string signals segment-assembled prompt path.
    assert "coding assistant" not in DEFAULT_SYSTEM_PROMPT
    assert "expert coding" not in DEFAULT_SYSTEM_PROMPT


def test_build_prompt_messages_includes_system_history_and_user() -> None:
    history = (Message(message_id="msg_1", role="assistant", content="past answer"),)

    # Verify role ordering: system → history → user.
    prompts = build_prompt_messages(
        history_messages=history,
        user_text="new question",
        system_prompt=_CODING_FIXTURE,
    )

    assert [item.role for item in prompts] == ["system", "assistant", "user"]
    assert "You are an expert coding assistant" in prompts[0].content
    assert "Current date and time:" in prompts[0].content
    assert "Current working directory:" in prompts[0].content
    assert "input_schema" not in prompts[0].content
    assert "<RUNTIME_FILL:" not in prompts[0].content
    assert prompts[-1].content == "new question"


def test_build_prompt_messages_injects_available_skills_section_with_absolute_location() -> (
    None
):
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
    assert "Use the skill_view tool to load a skill's SKILL.md" in system_prompt
    assert "call read on its <location>" not in system_prompt
    assert "resolve it against the skill directory" in system_prompt
    assert (
        f"<location>{relative_location.expanduser().resolve()}</location>"
        in system_prompt
    )


def test_build_prompt_messages_skips_available_skills_section_when_empty() -> None:
    # Use _CODING_FIXTURE explicitly: default is now generic empty string.
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="run this",
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
    )
    assert "<available_skills>" not in prompts[0].content
    assert "Available tools:" in prompts[0].content
    assert "input_schema" not in prompts[0].content


def test_build_prompt_messages_only_displays_tool_name_and_description() -> None:
    # Use _CODING_FIXTURE explicitly: default is now generic empty string.
    prompts = build_prompt_messages(
        history_messages=(),
        user_text="run this",
        system_prompt=_CODING_FIXTURE,
        available_tools=(
            ToolSpec(
                name="read",
                description="Read file contents",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            ),
        ),
    )

    system_prompt = prompts[0].content
    assert "Available tools:" in system_prompt
    assert "- read: Read file contents" in system_prompt
    assert "input_schema" not in system_prompt


async def test_runtime_fills_system_prompt_placeholders_before_llm_call(
    tmp_path: Path,
) -> None:
    """AgentRuntime fills system prompt placeholders with runtime context before LLM call."""

    class CapturePromptLLM:
        def __init__(self) -> None:
            self.requests: list[LLMGenerateRequest] = []

        async def generate(
            self, request: LLMGenerateRequest
        ) -> AsyncIterator[LLMMessage]:
            self.requests.append(request)
            response = LLMGenerateResponse(
                model=request.model,
                message=LLMMessage(role="assistant", content="ok"),
                finish_reason="stop",
            )
            yield response.message
            yield LLMMessage(
                role="assistant",
                content="",
                finish_reason=response.finish_reason,
                usage=response.usage,
            )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)
    llm = CapturePromptLLM()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
        system_prompt=_CODING_FIXTURE,
    )

    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello"}], stream=False
    )

    system_prompt = llm.requests[-1].messages[0].content
    assert "Current date and time:" in system_prompt
    assert f"Current working directory: {tmp_path}" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
    assert "Available tools:" in system_prompt
    assert "input_schema" not in system_prompt


# ---------------------------------------------------------------------------
# R2 tests: SKILLS_GUIDANCE / MEMORY_GUIDANCE constants + injection logic
# ---------------------------------------------------------------------------


def test_skills_guidance_constant_exists_and_mentions_skill_view_and_manage():
    """SKILLS_GUIDANCE must guide read-side skill usage and write-side maintenance."""
    assert SKILLS_GUIDANCE, "SKILLS_GUIDANCE must be non-empty"
    assert "skill_view" in SKILLS_GUIDANCE
    assert "skill_manage" in SKILLS_GUIDANCE


def test_memory_guidance_constant_exists_and_mentions_memory():
    """MEMORY_GUIDANCE must exist and guide when to use memory tool."""
    assert MEMORY_GUIDANCE, "MEMORY_GUIDANCE must be non-empty"
    assert "memory" in MEMORY_GUIDANCE.lower()


def test_build_system_prompt_injects_skills_guidance_when_skill_manage_in_tools():
    """SKILLS_GUIDANCE is injected when skill_manage tool is in available_tools."""
    tools = (
        ToolSpec(name="skill_manage", description="Manage skills.", input_schema={}),
        ToolSpec(name="read", description="Read a file.", input_schema={}),
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert "skill_manage" in result


def test_build_system_prompt_injects_read_side_guidance_when_skill_view_in_tools():
    """skill_view alone should enable skill guidance without advertising skill writes."""
    tools = (
        ToolSpec(name="skill_view", description="View skills.", input_schema={}),
        ToolSpec(name="read", description="Read a file.", input_schema={}),
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert "skill_view" in result
    assert "skill_manage" not in result


def test_build_system_prompt_no_skills_guidance_without_skill_manage():
    """Skill guidance is NOT injected when neither skill tool is present."""
    tools = (
        ToolSpec(name="read", description="Read a file.", input_schema={}),
        ToolSpec(name="bash", description="Run bash.", input_schema={}),
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert "skill_view" not in result
    assert "skill_manage" not in result


def test_build_system_prompt_injects_memory_guidance_when_memory_in_tools():
    """MEMORY_GUIDANCE is injected when memory tool is in available_tools."""
    tools = (
        ToolSpec(name="memory", description="Manage memory.", input_schema={}),
        ToolSpec(name="read", description="Read a file.", input_schema={}),
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert MEMORY_GUIDANCE in result


def test_build_system_prompt_no_memory_guidance_without_memory_tool():
    """MEMORY_GUIDANCE is NOT injected when memory tool is absent."""
    tools = (ToolSpec(name="read", description="Read a file.", input_schema={}),)
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert MEMORY_GUIDANCE not in result


def test_build_system_prompt_injects_both_guidance_when_both_tools_present():
    """Both SKILLS_GUIDANCE and MEMORY_GUIDANCE injected when both tools present."""
    tools = (
        ToolSpec(name="skill_manage", description="Manage skills.", input_schema={}),
        ToolSpec(name="memory", description="Manage memory.", input_schema={}),
        ToolSpec(name="read", description="Read a file.", input_schema={}),
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        available_tools=tools,
    )
    assert SKILLS_GUIDANCE in result
    assert MEMORY_GUIDANCE in result


def test_build_system_prompt_injects_memory_block_when_provided():
    """Memory block is injected verbatim when memory_block kwarg is supplied."""
    fake_memory_block = (
        "══════\nMEMORY (your personal notes) [0% — 0/2,200 chars]\n══════\n"
    )
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        memory_block=fake_memory_block,
    )
    assert fake_memory_block in result


def test_build_system_prompt_no_memory_block_when_not_provided():
    """No memory section injected when memory_block not supplied or None."""
    result = build_system_prompt(
        system_prompt=_CODING_FIXTURE,
        available_skills=(),
        memory_block=None,
    )
    assert "MEMORY (your personal notes)" not in result
