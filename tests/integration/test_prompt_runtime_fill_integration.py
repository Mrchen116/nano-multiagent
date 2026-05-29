from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMMessage
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
from collections.abc import AsyncIterator

# Fixture replaces deleted CODING_SYSTEM_PROMPT (coding content now lives in prompt_sections.py).
# Contains RUNTIME_FILL placeholders so runtime fills them before LLM call.
_FIXTURE_WITH_PLACEHOLDERS = (
    "You are an expert coding assistant.\n\n"
    "Available tools:\n<RUNTIME_FILL:AVAILABLE_TOOLS>\n\n"
    "Guidelines:\n- Be helpful\n\n"
    "Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>\n"
    "Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>"
)


class CapturePromptLLM:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


async def test_runtime_fills_system_prompt_placeholders_before_llm_call(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
    llm = CapturePromptLLM()
    # A fixture with RUNTIME_FILL placeholders is passed explicitly; AgentRuntime
    # default is "" which signals segment assembly (no monolithic template).
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
        system_prompt=_FIXTURE_WITH_PLACEHOLDERS,
    )

    await runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)

    system_prompt = llm.requests[-1].messages[0].content
    assert "Current date and time:" in system_prompt
    assert f"Current working directory: {tmp_path}" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
    assert "Available tools:" in system_prompt
    assert "input_schema" not in system_prompt
