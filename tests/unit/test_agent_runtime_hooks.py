from collections.abc import AsyncIterator
from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMMessage,
)
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        self.requests.append(request)
        last_user_text = request.messages[-1].content
        response = LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user_text}"),
            finish_reason="stop",
        )
        yield response.message
        yield LLMMessage(
            role="assistant",
            content="",
            finish_reason=response.finish_reason,
            usage=response.usage,
        )


async def test_runtime_and_loop_emit_hook_events_in_expected_order() -> None:
    events: list[str] = []
    before_messages: list[str] = []
    registry = HookRegistry()

    async def on_input(event, ctx):
        del event, ctx
        events.append("input")
        return {"action": "continue"}

    async def on_before_agent_start(event, ctx):
        del ctx
        events.append("before_agent_start")
        before_messages.append(event["message"])
        return {}

    def _observe(name: str):
        async def _handler(event, ctx):
            del event, ctx
            events.append(name)

        return _handler

    registry.on("input", on_input)
    registry.on("before_agent_start", on_before_agent_start)
    registry.on("agent_start", _observe("agent_start"))
    registry.on("turn_start", _observe("turn_start"))
    registry.on("message_start", _observe("message_start"))
    registry.on("message_update", _observe("message_update"))
    registry.on("message_end", _observe("message_end"))
    registry.on("turn_end", _observe("turn_end"))
    registry.on("agent_end", _observe("agent_end"))

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert events == [
        "input",
        "before_agent_start",
        "agent_start",
        "turn_start",
        "message_start",
        "message_update",
        "message_end",
        "turn_end",
        "agent_end",
    ]
    assert before_messages == ["ping"]


async def test_input_transform_chain_affects_runtime_main_flow() -> None:
    registry = HookRegistry()

    async def add_prefix(event, ctx):
        del ctx
        return {"action": "transform", "text": f"prefix:{event['text']}"}

    async def add_suffix(event, ctx):
        del ctx
        return {"action": "transform", "text": f"{event['text']}:suffix"}

    registry.on("input", add_prefix, priority=10)
    registry.on("input", add_suffix, priority=20)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert llm.requests[-1].messages[-1].content == "prefix:ping:suffix"
    assert result.messages[0].content == "ack:prefix:ping:suffix"
    entries = manager.list_entries(session.session_id)
    user_event = [entry for entry in entries][1]
    assert user_event.data["content"] == "prefix:ping:suffix"


async def test_before_agent_start_message_override_affects_runtime_main_flow() -> None:
    registry = HookRegistry()

    async def rewrite_before_start(event, ctx):
        del ctx
        return {"message": f"before:{event['message']}"}

    registry.on("before_agent_start", rewrite_before_start)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert llm.requests[-1].messages[-1].content == "before:ping"
    assert result.messages[0].content == "ack:before:ping"
    entries = manager.list_entries(session.session_id)
    user_event = [entry for entry in entries][1]
    assert user_event.data["content"] == "before:ping"


async def test_session_metadata_system_prompt_is_used_for_every_turn() -> None:
    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(
        workspace_root=Path.cwd(),
        system_prompt="You are the prompt frozen for this chat.",
    )
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        repo_root=Path.cwd(),
    )

    first = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )
    second = await runtime.run(
        session.session_id, [{"type": "text", "text": "pong"}], stream=False
    )

    assert first.messages[0].content == "ack:ping"
    assert second.messages[0].content == "ack:pong"
    assert (
        llm.requests[0]
        .messages[0]
        .content.startswith("You are the prompt frozen for this chat.")
    )
    assert (
        llm.requests[1]
        .messages[0]
        .content.startswith("You are the prompt frozen for this chat.")
    )


async def test_before_agent_start_blank_override_does_not_drop_session_frozen_system_prompt() -> (
    None
):
    registry = HookRegistry()

    async def clear_prompt(event, ctx):
        del ctx
        return {**event, "system_prompt": "   "}

    registry.on("before_agent_start", clear_prompt)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(
        workspace_root=Path.cwd(),
        system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
    )
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert result.messages[0].content == "ack:ping"
    assert (
        llm.requests[-1]
        .messages[0]
        .content.startswith(
            "When mentioned in a group chat, reply exactly with NO_REPLY."
        )
    )


async def test_input_handled_short_circuits_runtime_flow() -> None:
    registry = HookRegistry()

    async def handled(event, ctx):
        del event, ctx
        return {"action": "handled"}

    registry.on("input", handled)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert result.messages == ()
    assert result.stop_reason == "handled_by_hook"
    assert llm.requests == []
    entries = manager.list_entries(session.session_id)
    assert len(entries) == 1


async def test_hook_exceptions_are_isolated_and_fail_open() -> None:
    registry = HookRegistry()

    async def exploding(event, ctx):
        del event, ctx
        raise RuntimeError("boom")

    registry.on("input", exploding)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=Path.cwd())
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = await runtime.run(
        session.session_id, [{"type": "text", "text": "ping"}], stream=False
    )

    assert result.messages[0].content == "ack:ping"
    assert llm.requests[-1].messages[-1].content == "ping"


async def test_runtime_create_session_emits_session_start_observe_hook() -> None:
    observed_session_ids: list[str] = []
    registry = HookRegistry()

    async def on_session_start(event, ctx):
        del ctx
        observed_session_ids.append(event["session_id"])

    registry.on("session_start", on_session_start)

    store = JsonlSessionStore(data_dir=Path.cwd() / "sessions")
    manager = SessionManager(store=store)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    session = await runtime.create_session(workspace_root=Path.cwd())

    assert observed_session_ids == [session.session_id]
