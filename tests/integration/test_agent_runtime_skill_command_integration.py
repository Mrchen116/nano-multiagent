from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
from collections.abc import AsyncIterator


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        yield LLMMessage(role="assistant", content=f"ack:{request.messages[-1].content}")
        yield LLMMessage(role="assistant", content="", finish_reason="stop")
async def test_runtime_skill_command_rewrite_runs_through_normal_pipeline(tmp_path: Path) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
    )

    result = await runtime.run(
        session.session_id,
        [{"type": "text", "text": "/skill:doc polish this paragraph"}],
        stream=False,
    )

    rewritten = 'Use the "doc" skill for this request.\nUser input:\npolish this paragraph'
    assert llm.requests[-1].messages[-1].content == rewritten
    assert result.messages[0].content == f"ack:{rewritten}"

    turn_events = [event for event in manager.list_entries(session.session_id) if event.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 2
    assert turn_events[0].data["role"] == "user"
    assert turn_events[0].data["content"] == rewritten
    assert turn_events[1].data["role"] == "assistant"
