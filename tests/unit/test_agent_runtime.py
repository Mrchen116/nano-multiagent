from collections.abc import AsyncIterator
from pathlib import Path
import json

import pytest

from agent.core.agent.runtime import AgentRuntime
from agent.core.agent.run_control import RunController
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.tools.base import (
    set_tool_safety_config_factory,
    set_tool_safety_factory,
)
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
    def __init__(
        self, responses: tuple[LLMGenerateResponse, ...] | None = None
    ) -> None:
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
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )
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
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert result.session_id == session.session_id
    assert result.messages[0].role == "assistant"


async def test_runtime_builds_followup_context_from_session_events(
    tmp_path: Path,
) -> None:
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager, llm_client=llm_client, model="mock-model"
    )

    await runtime.run(
        session.session_id, [{"type": "text", "text": "first"}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "second"}], stream=False
    )

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


async def test_runtime_filters_prompt_skills_from_session_metadata(
    tmp_path: Path,
) -> None:
    # bugfix-431: skills are discovered via workspace_config_dirname resolver,
    # not the legacy Codex fallback roots. Place skills under the workspace
    # config dirname so make_skill_resolver finds them.
    workspace_config_dirname = ".testconfig"
    skills_root = tmp_path / workspace_config_dirname / "skills"
    selected_dir = skills_root / "selected-skill"
    ignored_dir = skills_root / "ignored-skill"
    selected_dir.mkdir(parents=True)
    ignored_dir.mkdir(parents=True)
    (selected_dir / "SKILL.md").write_text(
        "---\nname: selected-skill\ndescription: selected skill\n---\n",
        encoding="utf-8",
    )
    (ignored_dir / "SKILL.md").write_text(
        "---\nname: ignored-skill\ndescription: ignored skill\n---\n", encoding="utf-8"
    )

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    workspace_root = tmp_path
    session = manager.create_session(
        workspace_root=workspace_root.resolve(),
        skills=("selected-skill",),
    )
    llm_client = FakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="mock-model",
        repo_root=workspace_root,
        workspace_config_dirname=workspace_config_dirname,
        skill_search_roots=(),
    )

    await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    system_prompt = llm_client.requests[-1].messages[0].content
    assert "<name>selected-skill</name>" in system_prompt
    assert "<name>ignored-skill</name>" not in system_prompt


async def test_runtime_persists_tool_events_with_metadata_and_replays_context(
    tmp_path: Path,
) -> None:
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
    runtime = AgentRuntime(
        session_manager=manager, llm_client=llm_client, model="mock-model"
    )
    registry = ToolRegistry(context=ToolContext.create(repo_root=Path.cwd()))
    registry.register(EchoTool())
    runtime.bind_tool_registry(registry)

    await runtime.run(
        session.session_id, [{"type": "text", "text": "first"}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "second"}], stream=False
    )
    manager.writer.flush()

    entries = manager.list_entries(session.session_id)
    turn_events = [
        entry for entry in entries if entry.kind is SessionEntryKind.TURN_APPENDED
    ]
    call_events = [
        entry for entry in turn_events if entry.data["metadata"].get("tool_calls")
    ]
    result_events = [
        entry for entry in turn_events if entry.data["metadata"].get("tool_name")
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
                message=LLMMessage(
                    role="assistant", content='{"risk":"safe","reason":"read only"}'
                ),
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

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
                message=LLMMessage(
                    role="assistant", content='{"risk":"safe","reason":"ok"}'
                ),
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert llm_client.requests[0].model == "risk-model-x"
    assert llm_client.requests[0].session_id == session.session_id


async def test_hook_model_call_defaults_to_current_run_model(tmp_path: Path) -> None:
    """bugfix-429 fix-r1 #2: a hook model call with no explicit model uses the
    *current run's* model (the agent's selected model for this turn), not the
    build-time kernel default. Side-chain LLM calls must follow per-run model.
    """
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    llm_client = FakeLLMClient(
        responses=(
            LLMGenerateResponse(
                model="ignored",
                message=LLMMessage(role="assistant", content="ok"),
                finish_reason="stop",
            ),
            LLMGenerateResponse(
                model="ignored",
                message=LLMMessage(role="assistant", content="pong"),
                finish_reason="stop",
            ),
        )
    )
    hooks = HookRegistry()

    async def on_input(payload, ctx):  # noqa: ANN001
        # No explicit model → must inherit the current run's model.
        await ctx.call_model(system_prompt="s", user_prompt="u")
        return {"action": "continue", "text": payload["text"]}

    hooks.on("input", on_input, priority=10)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm_client,
        model="build-time-default",
        hook_runner=HookRunner(registry=hooks),
    )

    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "ping"}],
        stream=False,
        model="agent-selected-model",
    )

    # The hook's model call (first request) must use the run's model, not build default.
    assert llm_client.requests[0].model == "agent-selected-model"


async def test_runtime_skill_command_rewrite_runs_through_normal_pipeline(
    tmp_path: Path,
) -> None:
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

    rewritten = (
        'Use the "doc" skill for this request.\nUser input:\npolish this paragraph'
    )
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


async def test_task_tool_is_registered_and_validated_by_registry(
    tmp_path: Path,
) -> None:
    from agent.core.errors import ToolError
    from agent.platform.tools.loader import build_tool_registry

    registry = build_tool_registry(repo_root=tmp_path)

    with pytest.raises(ToolError, match="missing required argument: load_skills"):
        await registry.execute("agent", {})


async def test_single_part_creates_single_user_message_in_llm_history(
    tmp_path: Path,
) -> None:
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

    await runtime.run(
        session.session_id, [{"type": "text", "text": "hello"}], stream=False
    )
    await runtime.run(
        session.session_id, [{"type": "text", "text": "turn two"}], stream=False
    )

    # First call: 1 user message
    call1_user = [m for m in llm_client.requests[0].messages if m.role == "user"]
    assert len(call1_user) == 1
    assert call1_user[0].content == "hello"

    # Second call: history has prior turn + current user
    call2_user = [m for m in llm_client.requests[1].messages if m.role == "user"]
    assert call2_user[-1].content == "turn two"


async def test_multiple_parts_become_independent_user_messages_in_llm_history(
    tmp_path: Path,
) -> None:
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
    assert not any(
        m.content == "[alice] hello\n[bob] world\n[charlie] @agent go"
        for m in user_messages
    )


# ---------------------------------------------------------------------------
# bugfix-380: provider error → 合成 is_provider_error assistant 消息
# ---------------------------------------------------------------------------

from agent.core.errors import ModelError


class ErrorLLMClient:
    """LLM client that raises ModelError on generate."""

    def __init__(self, error_message: str = "upstream quota exceeded") -> None:
        self._error_message = error_message

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        raise ModelError(self._error_message, retryable=False)
        yield  # make this an async generator


async def test_runtime_provider_error_persists_error_assistant_message(
    tmp_path: Path,
) -> None:
    """ModelError 必须被合成为带 is_provider_error=True 的 assistant 消息并持久化。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=ErrorLLMClient("anthropic: upstream quota exceeded"),
        model="mock-model",
    )

    with pytest.raises(ModelError):
        await runtime.run(
            session.session_id, [{"type": "text", "text": "hi"}], stream=False
        )

    manager.writer.flush()
    entries = manager.list_entries(session.session_id)
    assistant_entries = [
        e
        for e in entries
        if e.kind is SessionEntryKind.TURN_APPENDED
        and e.data.get("role") == "assistant"
    ]
    assert len(assistant_entries) == 1, "应该有一条 assistant 错误消息被持久化"
    err_entry = assistant_entries[0]
    # is_provider_error is promoted into entry.data["metadata"] via _build_turn_metadata
    err_metadata = err_entry.data.get("metadata") or {}
    assert err_metadata.get("is_provider_error") is True, (
        "is_provider_error 必须为 True"
    )
    assert "模型调用失败" in str(err_entry.data.get("content", "")) or "⚠️" in str(
        err_entry.data.get("content", "")
    )


async def test_runtime_provider_error_message_content_contains_provider_text(
    tmp_path: Path,
) -> None:
    """错误消息正文必须含有 provider 原始文案。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=ErrorLLMClient("You've reached your usage limit"),
        model="mock-model",
    )

    with pytest.raises(ModelError):
        await runtime.run(
            session.session_id, [{"type": "text", "text": "hi"}], stream=False
        )

    manager.writer.flush()
    entries = manager.list_entries(session.session_id)
    assistant_entries = [
        e
        for e in entries
        if e.kind is SessionEntryKind.TURN_APPENDED
        and e.data.get("role") == "assistant"
    ]
    assert assistant_entries, "应该有 assistant 错误消息"
    content = str(assistant_entries[0].data.get("content", ""))
    assert (
        "usage limit" in content.lower()
        or "quota" in content.lower()
        or "usage" in content.lower()
        or "reached" in content.lower()
    )


async def test_runtime_provider_error_not_in_next_llm_history(tmp_path: Path) -> None:
    """is_provider_error=True 的 assistant 消息不应出现在下一轮 LLM history 中。"""
    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)

    # 第一轮：LLM 抛错
    runtime_err = AgentRuntime(
        session_manager=manager,
        llm_client=ErrorLLMClient("quota exceeded"),
        model="mock-model",
    )
    with pytest.raises(ModelError):
        await runtime_err.run(
            session.session_id, [{"type": "text", "text": "first"}], stream=False
        )
    manager.writer.flush()

    # 第二轮：LLM 正常，检查 history 里没有错误消息
    tracking_client = FakeLLMClient()
    runtime2 = AgentRuntime(
        session_manager=manager,
        llm_client=tracking_client,
        model="mock-model",
    )
    await runtime2.run(
        session.session_id, [{"type": "text", "text": "second"}], stream=False
    )

    messages_sent = tracking_client.requests[-1].messages
    # history 中不应有包含 "⚠️" 的 assistant 消息
    error_msgs = [
        m for m in messages_sent if m.role == "assistant" and "⚠️" in (m.content or "")
    ]
    assert not error_msgs, f"is_provider_error 消息泄漏到 LLM history: {error_msgs}"


# ---------------------------------------------------------------------------
# Multi-part message injection: each part becomes an independent user message
# ---------------------------------------------------------------------------


class _SimpleFakeLLMClient:
    """Records calls and returns a simple text response — minimal double for multi-part tests."""

    def __init__(self, response_text: str = "ok") -> None:
        self.calls: list[LLMGenerateRequest] = []
        self._response_text = response_text

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.calls.append(request)
        yield LLMMessage(role="assistant", content=self._response_text)
        yield LLMMessage(role="assistant", content="", finish_reason="end_turn")


def _make_simple_session_manager(
    tmp_path: Path, *, workspace_root: str | None = None
) -> tuple[SessionManager, str]:
    """Create a session manager via SessionService and return (manager, session_id)."""
    from agent.platform.persistence.session.service import SessionService
    from agent.core.session.jsonl_store import JsonlSessionStore as _JsonlStore

    service = SessionService(store=_JsonlStore(data_dir=tmp_path / "sessions"))
    root = Path(workspace_root) if workspace_root else tmp_path
    session = service.create_session(workspace_root=root)
    return service.manager, session.session_id


async def test_single_part_creates_single_user_message_in_llm_history(
    tmp_path: Path,
) -> None:
    """单条 part（向后兼容路径）→ LLM history 末尾只有一条 user message。"""
    manager, session_id = _make_simple_session_manager(tmp_path)
    llm = _SimpleFakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(session_id, [{"type": "text", "text": "hello"}])

    assert len(llm.calls) == 1
    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[-1].content == "hello"


async def test_multiple_parts_become_independent_user_messages_in_llm_history(
    tmp_path: Path,
) -> None:
    """多条 parts → LLM history 中每条 part 对应一条独立 user message（而非 \n join）。"""
    manager, session_id = _make_simple_session_manager(tmp_path)
    llm = _SimpleFakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "[alice] hello"},
            {"type": "text", "text": "[bob] world"},
            {"type": "text", "text": "[charlie] @agent go"},
        ],
    )

    assert len(llm.calls) == 1
    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    # 3 parts → 3 independent user messages
    assert len(user_messages) == 3
    assert user_messages[0].content == "[alice] hello"
    assert user_messages[1].content == "[bob] world"
    assert user_messages[2].content == "[charlie] @agent go"


async def test_two_parts_become_two_user_messages(tmp_path: Path) -> None:
    """2 parts → 2 user messages in LLM history。"""
    manager, session_id = _make_simple_session_manager(tmp_path)
    llm = _SimpleFakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "[user-1] buffered message"},
            {"type": "text", "text": "[user-2] @agent respond"},
        ],
    )

    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(user_messages) == 2
    assert user_messages[0].content == "[user-1] buffered message"
    assert user_messages[1].content == "[user-2] @agent respond"


async def test_multiple_parts_not_newline_joined(tmp_path: Path) -> None:
    """多 parts 不能被 \n join 成一条 user message，而是分开为独立条目。"""
    manager, session_id = _make_simple_session_manager(tmp_path)
    llm = _SimpleFakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(
        session_id,
        [
            {"type": "text", "text": "part one"},
            {"type": "text", "text": "part two"},
        ],
    )

    user_messages = [m for m in llm.calls[0].messages if m.role == "user"]
    # Must NOT be joined as "part one\npart two"
    assert not any(m.content == "part one\npart two" for m in user_messages)
    # Must be separate
    assert any(m.content == "part one" for m in user_messages)
    assert any(m.content == "part two" for m in user_messages)


async def test_single_part_user_text_unchanged_after_multi_turn(tmp_path: Path) -> None:
    """多轮对话中，单 part 的 user text 行为与之前完全一致。"""
    manager, session_id = _make_simple_session_manager(tmp_path)
    llm = _SimpleFakeLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="fake",
    )

    await runtime.run(session_id, [{"type": "text", "text": "turn one"}])
    await runtime.run(session_id, [{"type": "text", "text": "turn two"}])

    # First call: 1 user message
    call1_user = [m for m in llm.calls[0].messages if m.role == "user"]
    assert len(call1_user) == 1
    assert call1_user[0].content == "turn one"

    # Second call: history has 2 user messages + 1 assistant, plus current user
    call2_user = [m for m in llm.calls[1].messages if m.role == "user"]
    assert call2_user[-1].content == "turn two"


# ---------------------------------------------------------------------------
# bugfix-402: eager tool_call_recovery on abort
# ---------------------------------------------------------------------------


async def test_runtime_eager_recovery_on_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run() で abort 発生後、prepare を呼ばなくても JSONL に tool_call_recovery が即書かれる。

    Scenario: the _execute_loop yields an assistant message with an unclosed
    tool_call followed by turn_meta(stop_reason='aborted').  The runtime must
    eagerly write a tool_call_recovery entry into the JSONL immediately after
    the loop exits so the UI can show the cancellation result without waiting
    for the next run to call prepare_transcript_for_run.

    We inject the abort scenario directly via monkeypatch so the test is not
    sensitive to the exact loop-iteration timing of the abort signal.
    """
    from agent.core.types import Message
    from agent.core import ids

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    # Build the messages that _execute_loop would yield when aborted mid-tool.
    assistant_with_open_call = Message(
        message_id=ids.make_message_id(),
        role="assistant",
        content="",
        metadata={
            "tool_calls": [
                {"call_id": "tc_abort_1", "name": "echo", "arguments": {"text": "w"}}
            ]
        },
    )
    turn_meta_aborted = Message(
        message_id=ids.make_message_id(),
        role="turn_meta",
        content="",
        metadata={"stop_reason": "aborted", "completed": False, "tool_iterations": 1},
    )

    async def _fake_execute_loop(self_inner, *, controller=None, **_kwargs):  # noqa: ANN001
        yield assistant_with_open_call
        yield turn_meta_aborted

    from agent.core.agent import runtime as _runtime_mod

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    controller = RunController()
    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "do something"}],
        stream=False,
        controller=controller,
    )
    manager.writer.flush()

    # Read the raw JSONL and find recovery entries — without calling prepare.
    path = store.resolve_path(session.session_id, workspace_root=tmp_path / "workspace")
    lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    recovery_entries = [ln for ln in lines if ln.get("type") == "tool_call_recovery"]

    assert len(recovery_entries) == 1, (
        f"Expected 1 recovery entry, got {len(recovery_entries)}. "
        f"JSONL entries: {[ln.get('type') for ln in lines]}"
    )
    rec = recovery_entries[0]
    assert rec["tool_call_id"] == "tc_abort_1"
    assert rec["reason"] == "interrupted"
    assert rec.get("idempotency_key") == "tool-call-recovery:tc_abort_1"


async def test_runtime_eager_recovery_on_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stop_reason='cancelled' triggers eager recovery. bugfix-410-fix-r1: the synthesized
    badge reason is 'interrupted', not 'cancelled' — the IM badge's REASON_LABEL_KEYS only
    renders denied/timed_out/interrupted, so a bare 'cancelled' would have no label."""
    from agent.core.types import Message
    from agent.core import ids
    from agent.core.agent import runtime as _runtime_mod

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    assistant_msg = Message(
        message_id=ids.make_message_id(),
        role="assistant",
        content="",
        metadata={
            "tool_calls": [{"call_id": "tc_cancel_1", "name": "echo", "arguments": {}}]
        },
    )
    turn_meta_cancelled = Message(
        message_id=ids.make_message_id(),
        role="turn_meta",
        content="",
        metadata={"stop_reason": "cancelled", "completed": False, "tool_iterations": 1},
    )

    async def _fake_execute_loop(self_inner, *, controller=None, **_kwargs):  # noqa: ANN001
        yield assistant_msg
        yield turn_meta_cancelled

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "do something"}],
        stream=False,
    )
    manager.writer.flush()

    path = store.resolve_path(session.session_id, workspace_root=tmp_path / "workspace")
    lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    recovery_entries = [ln for ln in lines if ln.get("type") == "tool_call_recovery"]

    assert len(recovery_entries) == 1
    assert recovery_entries[0]["tool_call_id"] == "tc_cancel_1"
    assert recovery_entries[0]["reason"] == "interrupted"


async def test_runtime_cancelled_recovery_is_visible_to_next_cached_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next run in the same process must receive the synthetic tool result."""
    from agent.core import ids
    from agent.core.agent import runtime as _runtime_mod
    from agent.core.types import Message

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )
    histories: list[tuple[Message, ...]] = []

    async def _fake_execute_loop(
        self_inner,
        *,
        history=(),
        **_kwargs,  # noqa: ANN001
    ):
        histories.append(tuple(history))
        if len(histories) == 1:
            yield Message(
                message_id=ids.make_message_id(),
                role="assistant",
                content="",
                metadata={
                    "tool_calls": [
                        {
                            "call_id": "tc_cached_cancel",
                            "name": "echo",
                            "arguments": {},
                        }
                    ]
                },
            )
            yield Message(
                message_id=ids.make_message_id(),
                role="turn_meta",
                content="",
                metadata={"stop_reason": "cancelled", "completed": False},
            )
            return
        yield Message(
            message_id=ids.make_message_id(),
            role="assistant",
            content="recovered",
        )
        yield Message(
            message_id=ids.make_message_id(),
            role="turn_meta",
            content="",
            metadata={"stop_reason": "completed", "completed": True},
        )

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "cancel this"}],
        stream=False,
    )
    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "continue"}],
        stream=False,
    )

    second_history = histories[1]
    assert any(
        message.role == "tool"
        and message.tool_call_id == "tc_cached_cancel"
        and message.metadata.get("is_recovery") is True
        for message in second_history
    )


async def test_runtime_no_eager_recovery_on_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Completed runs must NOT write recovery entries even if tool_calls exist."""
    from agent.core.types import Message
    from agent.core import ids
    from agent.core.agent import runtime as _runtime_mod

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    assistant_msg = Message(
        message_id=ids.make_message_id(),
        role="assistant",
        content="",
        metadata={
            "tool_calls": [{"call_id": "tc_done_1", "name": "echo", "arguments": {}}]
        },
    )
    tool_result_msg = Message(
        message_id=ids.make_message_id(),
        role="tool",
        content="ok",
        tool_call_id="tc_done_1",
    )
    turn_meta_completed = Message(
        message_id=ids.make_message_id(),
        role="turn_meta",
        content="",
        metadata={"stop_reason": "completed", "completed": True, "tool_iterations": 1},
    )

    async def _fake_execute_loop(self_inner, *, controller=None, **_kwargs):  # noqa: ANN001
        yield assistant_msg
        yield tool_result_msg
        yield turn_meta_completed

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "do something"}],
        stream=False,
    )
    manager.writer.flush()

    path = store.resolve_path(session.session_id, workspace_root=tmp_path / "workspace")
    lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    recovery_entries = [ln for ln in lines if ln.get("type") == "tool_call_recovery"]
    assert recovery_entries == [], (
        f"Completed run should not write recovery: {recovery_entries}"
    )


# ---------------------------------------------------------------------------
# bugfix-410-M2 R1: recovery must also cover CancelledError pass-through, where
# an external cancel() unwinds the run at an `await` point inside _execute_loop
# *before* the loop reaches an iteration boundary. In that path NO turn_meta is
# ever yielded, so _run_stop_reason is None — the bugfix-402 eager-recovery
# (which keyed on stop_reason in ("aborted","cancelled")) was skipped, leaving
# an orphaned tool_call in JSONL *and* a dirty in-memory cache (#82 reopen).
# ---------------------------------------------------------------------------


async def test_runtime_recovery_on_cancellederror_passthrough(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CancelledError unwinding mid-tool (no turn_meta) must still close the call.

    The loop yields an assistant turn with an open tool_call, then raises
    asyncio.CancelledError at the next await — exactly what happens when the
    gateway run-idle watchdog calls kernel.cancel() while the run is parked in a
    tool/LLM await. The finally block must (1) drop the session cache and
    (2) append a tool_call_recovery for the orphan, with reason='interrupted'
    (synthesized since no turn_meta carried a stop_reason).
    """
    import asyncio
    from agent.core.types import Message
    from agent.core import ids
    from agent.core.agent import runtime as _runtime_mod

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )

    assistant_with_open_call = Message(
        message_id=ids.make_message_id(),
        role="assistant",
        content="",
        metadata={
            "tool_calls": [
                {"call_id": "tc_cancelled_err", "name": "echo", "arguments": {}}
            ]
        },
    )

    async def _fake_execute_loop(self_inner, *, controller=None, **_kwargs):  # noqa: ANN001
        yield assistant_with_open_call
        # External cancel() lands here, before any turn_meta is produced.
        raise asyncio.CancelledError()

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    with pytest.raises(asyncio.CancelledError):
        await runtime.run(
            session.session_id,
            [{"type": "text", "text": "do something"}],
            stream=False,
        )
    manager.writer.flush()

    path = store.resolve_path(session.session_id, workspace_root=tmp_path / "workspace")
    lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    recovery_entries = [ln for ln in lines if ln.get("type") == "tool_call_recovery"]
    assert len(recovery_entries) == 1, (
        f"CancelledError pass-through must still write recovery; got "
        f"{[ln.get('type') for ln in lines]}"
    )
    assert recovery_entries[0]["tool_call_id"] == "tc_cancelled_err"
    assert recovery_entries[0]["reason"] == "interrupted"

    # invalidate_session_cache is the load-bearing self-heal: the dirty in-memory
    # history must be dropped so the next run re-reads from JSONL (cache-miss).
    assert session.session_id not in runtime._session_histories, (
        "session cache must be invalidated after a cancelled run so the next "
        "turn does not reuse the orphaned tool_call from memory"
    )


async def test_runtime_recovery_on_cancellederror_visible_to_next_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a CancelledError-interrupted run, the next run in the SAME process
    must see the synthetic tool result (cache-hit path no longer serves the
    orphan). This is the #82-reopen brick that only a process restart used to
    clear.
    """
    import asyncio
    from agent.core import ids
    from agent.core.agent import runtime as _runtime_mod
    from agent.core.types import Message

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = _make_workspace_session(manager, tmp_path)
    runtime = AgentRuntime(
        session_manager=manager, llm_client=FakeLLMClient(), model="mock-model"
    )
    histories: list[tuple[Message, ...]] = []

    async def _fake_execute_loop(self_inner, *, history=(), **_kwargs):  # noqa: ANN001
        histories.append(tuple(history))
        if len(histories) == 1:
            yield Message(
                message_id=ids.make_message_id(),
                role="assistant",
                content="",
                metadata={
                    "tool_calls": [
                        {
                            "call_id": "tc_cancelled_cached",
                            "name": "echo",
                            "arguments": {},
                        }
                    ]
                },
            )
            raise asyncio.CancelledError()
        yield Message(
            message_id=ids.make_message_id(),
            role="assistant",
            content="recovered",
        )
        yield Message(
            message_id=ids.make_message_id(),
            role="turn_meta",
            content="",
            metadata={"stop_reason": "completed", "completed": True},
        )

    monkeypatch.setattr(_runtime_mod.AgentRuntime, "_execute_loop", _fake_execute_loop)

    with pytest.raises(asyncio.CancelledError):
        await runtime.run(
            session.session_id,
            [{"type": "text", "text": "cancel this"}],
            stream=False,
        )
    await runtime.run(
        session.session_id,
        [{"type": "text", "text": "continue"}],
        stream=False,
    )

    second_history = histories[1]
    assert any(
        message.role == "tool"
        and message.tool_call_id == "tc_cancelled_cached"
        and message.metadata.get("is_recovery") is True
        for message in second_history
    ), "next run must receive the synthetic recovery tool result from JSONL"
