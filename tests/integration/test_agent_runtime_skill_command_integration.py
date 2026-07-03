from pathlib import Path
import json

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService
from collections.abc import AsyncIterator
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
from agent.platform.tools.builtins.skill_view import SkillViewTool
from agent.platform.tools.registry import ToolRegistry
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
from agent.platform.tools.base import ToolContext

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        yield LLMMessage(
            role="assistant", content=f"ack:{request.messages[-1].content}"
        )
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


async def test_runtime_skill_command_rewrite_runs_through_normal_pipeline(
    tmp_path: Path,
) -> None:
    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    skill_root = tmp_path / ".nanoassistant" / "skills"
    skill_file = skill_root / "doc" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("---\nname: doc\ndescription: Doc\n---\n\nDoc body", encoding="utf-8")
    session = service.create_session(
        workspace_root=tmp_path,
        metadata={"workspace_config_dirname": ".nanoassistant"},
        tool_allowlist=("skill_view",),
    )
    llm = EchoLLMClient()
    context = ToolContext.create(repo_root=tmp_path)
    registry = ToolRegistry(context=context)
    registry.register(SkillViewTool(workspace_config_dirname=".nanoassistant"))
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        tool_registry=registry,
        workspace_config_dirname=".nanoassistant",
    )

    result = await runtime.run(
        session.session_id,
        [{"type": "text", "text": "/skill:doc polish this paragraph"}],
        stream=False,
    )

    rewritten = (
        'Use the "doc" skill for this request.\nUser input:\npolish this paragraph'
    )
    assert llm.requests[-1].messages[-1].content == rewritten
    assert result.messages[-1].content == f"ack:{rewritten}"
    assert [call.name for call in result.tool_calls] == ["skill_view"]
    assert [tool.name for tool in result.tool_results] == ["skill_view"]
    usage = json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))
    assert usage["doc"]["use_count"] == 1
    assert usage["doc"]["session_refs"][0]["session_id"] == session.session_id
    assert (
        usage["doc"]["session_refs"][0]["transcript_path"]
        == str(
            manager.store.resolve_path(
                session.session_id,
                workspace_root=tmp_path,
            )
        )
    )

    turn_events = [
        event
        for event in manager.list_entries(session.session_id)
        if event.kind is SessionEntryKind.TURN_APPENDED
    ]
    assert len(turn_events) == 4
    assert turn_events[0].data["role"] == "user"
    assert turn_events[0].data["content"] == rewritten
    assert turn_events[1].data["role"] == "assistant"
    assert turn_events[1].data["metadata"]["tool_calls"][0]["name"] == "skill_view"
    assert turn_events[2].data["role"] == "tool"
    assert turn_events[2].data["metadata"]["tool_name"] == "skill_view"
    assert turn_events[3].data["role"] == "assistant"
