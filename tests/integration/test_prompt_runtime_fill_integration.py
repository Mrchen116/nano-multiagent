from pathlib import Path

from agent.core.agent.prompting import CODING_SYSTEM_PROMPT
from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.manager import SessionManager
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore
from collections.abc import AsyncIterator


class CapturePromptLLM:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        yield LLMMessage(role="assistant", content="ok")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")
def test_runtime_fills_system_prompt_placeholders_before_llm_call(tmp_path: Path) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "prompt-runtime-fill.sqlite3")
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = CapturePromptLLM()
    # CODING_SYSTEM_PROMPT must be injected explicitly; AgentRuntime default is now "".
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        repo_root=tmp_path,
        system_prompt=CODING_SYSTEM_PROMPT,
    )

    runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)

    system_prompt = llm.requests[-1].messages[0].content
    assert "Current date and time:" in system_prompt
    assert f"Current working directory: {tmp_path}" in system_prompt
    assert "<RUNTIME_FILL:" not in system_prompt
    assert "Available tools:" in system_prompt
    assert "input_schema" not in system_prompt
