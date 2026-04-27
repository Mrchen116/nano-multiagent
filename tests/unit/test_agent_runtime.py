from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import set_tool_safety_config_factory, set_tool_safety_factory
from agent.platform.tools.safety import ToolSafety, ToolSafetyConfig
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
    LLMToolCall,
)
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager
from agent.platform.tools.base import ToolContext
from agent.platform.tools.registry import ToolRegistry

set_tool_safety_factory(ToolSafety)
set_tool_safety_config_factory(ToolSafetyConfig)


def _make_workspace_session(manager: SessionManager, tmp_path: Path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(exist_ok=True)
    return manager.create_session(workspace_root=workspace_root.resolve())


class FakeLLMClient:
    def __init__(self, responses: tuple[LLMGenerateResponse, ...] | None = None) -> None:
        self.requests: list[LLMGenerateRequest] = []
        self._responses = list(responses) if responses is not None else None

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        if self._responses is None:
            response = LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            )
        else:
            if not self._responses:
                raise AssertionError("unexpected llm call")
            response = self._responses.pop(0)
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


class EchoTool:
    name = "echo"
    description = "echo text"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):  # noqa: ANN001, ANN201
        del ctx
        return {"echoed": args["text"]}


async def test_runtime_run_appends_user_and_assistant_events(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(session_manager=manager, llm_client=FakeLLMClient(), model="mock-model")

    result = await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)
    manager.writer.flush()

    assert result.session_id == session.session_id
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content == "runtime-pong"
    entries = manager.list_entries(session.session_id)
    created_event, user_event, assistant_event = entries
    assert created_event.kind is SessionEntryKind.SESSION_CREATED
    assert user_event.kind is SessionEntryKind.TURN_APPENDED
    assert user_event.data["role"] == "user"
    assert user_event.data["content"] == "ping"
    assert assistant_event.kind is SessionEntryKind.TURN_APPENDED
    assert assistant_event.data["role"] == "assistant"
    assert assistant_event.data["content"] == "runtime-pong"


async def test_runtime_run_with_default_workspace_root() -> None:
    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    runtime = AgentRuntime(session_manager=manager, llm_client=FakeLLMClient(), model="mock-model")

    result = await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.session_id == session.session_id
    assert result.messages[0].role == "assistant"


async def test_runtime_builds_followup_context_from_session_events(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model")

    await runtime.run(session.session_id, [{"type": "text", "text": "first"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "second"}], stream=False)

    second_call_messages = llm_client.requests[-1].messages
    assert [message.role for message in second_call_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second_call_messages[1].content == "first"
    assert second_call_messages[2].content == "runtime-pong"
    assert second_call_messages[3].content == "second"


async def test_runtime_filters_prompt_skills_from_session_metadata(tmp_path: Path) -> None:
    skills_root = tmp_path / ".codex" / "skills"
    selected_dir = skills_root / "selected-skill"
    ignored_dir = skills_root / "ignored-skill"
    selected_dir.mkdir(parents=True)
    ignored_dir.mkdir(parents=True)
    (selected_dir / "SKILL.md").write_text("---\nname: selected-skill\ndescription: selected skill\n---\n", encoding="utf-8")
    (ignored_dir / "SKILL.md").write_text("---\nname: ignored-skill\ndescription: ignored skill\n---\n", encoding="utf-8")

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace_root = tmp_path
    session = manager.create_session(
        workspace_root=workspace_root.resolve(),
        skills=("selected-skill",),
    )
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model", repo_root=workspace_root)

    await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    system_prompt = llm_client.requests[-1].messages[0].content
    assert "<name>selected-skill</name>" in system_prompt
    assert "<name>ignored-skill</name>" not in system_prompt


async def test_runtime_persists_tool_events_with_metadata_and_replays_context(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_runtime_1",
                            name="echo",
                            arguments={"text": "first"},
                        ),
                    ),
                ),
                finish_reason="tool_calls",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-after-tool"),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-second"),
                finish_reason="stop",
            ),
        )
    )
    runtime = AgentRuntime(session_manager=manager, llm_client=llm_client, model="mock-model")
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(EchoTool())
    runtime.bind_tool_registry(registry)

    await runtime.run(session.session_id, [{"type": "text", "text": "first"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "second"}], stream=False)
    manager.writer.flush()

    entries = manager.list_entries(session.session_id)
    turn_events = [
        entry
        for entry in entries
        if entry.kind is SessionEntryKind.TURN_APPENDED
    ]
    call_events = [
        entry
        for entry in turn_events
        if entry.data["metadata"].get("tool_calls")
    ]
    result_events = [
        entry
        for entry in turn_events
        if entry.data["metadata"].get("tool_name")
    ]
    assert len(call_events) == 1
    assert len(result_events) == 1
    assert call_events[0].data["role"] == "assistant"
    assert result_events[0].data["role"] == "tool"
    assert call_events[0].data["metadata"]["tool_calls"] == [
        {
            "call_id": "call_runtime_1",
            "name": "echo",
            "arguments": {"text": "first"},
        }
    ]
    assert result_events[0].data["metadata"]["tool_name"] == "echo"

    second_turn_request = llm_client.requests[-1]
    assert [message.role for message in second_turn_request.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert second_turn_request.messages[2].tool_calls[0].call_id == "call_runtime_1"
    assert second_turn_request.messages[3].tool_call_id == "call_runtime_1"


async def test_hook_context_model_call_uses_same_session_id(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content='{"risk":"safe","reason":"read only"}'),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            ),
        )
    )
    hooks = HookRegistry()

    async def on_input(payload, ctx):  # noqa: ANN001
        _ = await ctx.call_model(
            system_prompt="risk-system",
            user_prompt="risk-user",
        )
        return {"action": "continue", "text": payload["text"]}

    hooks.on("input", on_input, priority=10)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
    )

    await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm_client.requests[0].session_id == session.session_id
    assert llm_client.requests[1].session_id == session.session_id


async def test_hook_context_model_call_supports_model_override(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="risk-model-x",
                message=LLMMessage(role="assistant", content='{"risk":"safe","reason":"ok"}'),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="mock-model",
                message=LLMMessage(role="assistant", content="runtime-pong"),
                finish_reason="stop",
            ),
        )
    )
    hooks = HookRegistry()

    async def on_input(payload, ctx):  # noqa: ANN001
        _ = await ctx.call_model(
            system_prompt="risk-system",
            user_prompt="risk-user",
            model="risk-model-x",
        )
        return {"action": "continue", "text": payload["text"]}

    hooks.on("input", on_input, priority=10)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
        hook_runner=HookRunner(registry=hooks),
    )

    await runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm_client.requests[0].model == "risk-model-x"
    assert llm_client.requests[0].session_id == session.session_id


async def test_runtime_skill_command_rewrite_runs_through_normal_pipeline(tmp_path: Path) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
    )

    result = await runtime.run(
        session.session_id,
        [{"type": "text", "text": "/skill:doc polish this paragraph"}],
        stream=False,
    )
    manager.writer.flush()

    rewritten = 'Use the "doc" skill for this request.\nUser input:\npolish this paragraph'
    assert llm_client.requests[-1].messages[-1].content == rewritten
    assert result.messages[0].content == "runtime-pong"

    entries = manager.list_entries(session.session_id)
    created_event, user_event, assistant_event = entries
    assert created_event.kind is SessionEntryKind.SESSION_CREATED
    assert user_event.kind is SessionEntryKind.TURN_APPENDED
    assert user_event.data["role"] == "user"
    assert user_event.data["content"] == rewritten
    assert assistant_event.kind is SessionEntryKind.TURN_APPENDED
    assert assistant_event.data["role"] == "assistant"


async def test_task_tool_is_registered_and_validated_by_registry(tmp_path: Path) -> None:
    from agent.core.errors import ToolError
    from agent.platform.tools.loader import build_tool_registry

    registry = build_tool_registry(repo_root=tmp_path)

    with pytest.raises(ToolError, match="missing required argument: load_skills"):
        await registry.execute("task", {})


async def test_single_part_creates_single_user_message_in_llm_history(tmp_path: Path) -> None:
    """单条 part（向后兼容路径）→ LLM history 末尾只有一条 user message。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
    )

    await runtime.run(session.session_id, [{"type": "text", "text": "hello"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "turn two"}], stream=False)

    # First call: 1 user message
    call1_user = [m for m in llm_client.requests[0].messages if m.role == "user"]
    assert len(call1_user) == 1
    assert call1_user[0].content == "hello"

    # Second call: history has prior turn + current user
    call2_user = [m for m in llm_client.requests[1].messages if m.role == "user"]
    assert call2_user[-1].content == "turn two"


async def test_multiple_parts_become_independent_user_messages_in_llm_history(tmp_path: Path) -> None:
    """多条 parts → LLM history 中每条 part 对应一条独立 user message（而非 \\n join）。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
    )

    await runtime.run(
        session.session_id,
        [
            {"type": "text", "text": "[alice] hello"},
            {"type": "text", "text": "[bob] world"},
            {"type": "text", "text": "[charlie] @agent go"},
        ],
        stream=False,
    )

    assert len(llm_client.requests) == 1
    user_messages = [m for m in llm_client.requests[0].messages if m.role == "user"]
    assert len(user_messages) == 3
    assert user_messages[0].content == "[alice] hello"
    assert user_messages[1].content == "[bob] world"
    assert user_messages[2].content == "[charlie] @agent go"
    # Must NOT be joined
    assert not any(m.content == "[alice] hello\n[bob] world\n[charlie] @agent go" for m in user_messages)
