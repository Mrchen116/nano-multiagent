from pathlib import Path

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.interfaces import LLMGenerateRequest, LLMGenerateResponse, LLMMessage
from agent.core.session.store import LoadedSession, SessionStore
from agent.core.session.manager import SessionManager


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []
        self.snapshots: dict[str, dict[str, object]] = {}

    def append_event(self, session_id: str, entry: object) -> None:
        self.events.append((session_id, entry))

    def load_session(self, session_id: str) -> LoadedSession | None:
        session_events = tuple(entry for sid, entry in self.events if sid == session_id)
        if not session_events and session_id not in self.snapshots:
            return None
        return LoadedSession(
            session_id=session_id,
            events=session_events,
            snapshot=self.snapshots.get(session_id),
        )

    def save_snapshot(self, session_id: str, snapshot: dict[str, object]) -> None:
        self.snapshots[session_id] = snapshot


class EchoLLMClient:
    def __init__(self) -> None:
        self.requests: list[LLMGenerateRequest] = []

    def generate(self, request: LLMGenerateRequest) -> LLMGenerateResponse:
        self.requests.append(request)
        last_user_text = request.messages[-1].content
        return LLMGenerateResponse(
            model=request.model,
            message=LLMMessage(role="assistant", content=f"ack:{last_user_text}"),
            finish_reason="stop",
        )


def test_runtime_and_loop_emit_hook_events_in_expected_order() -> None:
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

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

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


def test_input_transform_chain_affects_runtime_main_flow() -> None:
    registry = HookRegistry()

    async def add_prefix(event, ctx):
        del ctx
        return {"action": "transform", "text": f"prefix:{event['text']}"}

    async def add_suffix(event, ctx):
        del ctx
        return {"action": "transform", "text": f"{event['text']}:suffix"}

    registry.on("input", add_prefix, priority=10)
    registry.on("input", add_suffix, priority=20)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm.requests[-1].messages[-1].content == "prefix:ping:suffix"
    assert result.messages[0].content == "ack:prefix:ping:suffix"
    user_event = [entry for _, entry in store.events][1]
    assert user_event.data["content"] == "prefix:ping:suffix"


def test_before_agent_start_message_override_affects_runtime_main_flow() -> None:
    registry = HookRegistry()

    async def rewrite_before_start(event, ctx):
        del ctx
        return {"message": f"before:{event['message']}"}

    registry.on("before_agent_start", rewrite_before_start)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert llm.requests[-1].messages[-1].content == "before:ping"
    assert result.messages[0].content == "ack:before:ping"
    user_event = [entry for _, entry in store.events][1]
    assert user_event.data["content"] == "before:ping"


def test_session_metadata_system_prompt_is_used_for_every_turn() -> None:
    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session(metadata={"system_prompt": "You are the prompt frozen for this chat."})
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        repo_root=Path.cwd(),
    )

    first = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)
    second = runtime.run(session.session_id, [{"type": "text", "text": "pong"}], stream=False)

    assert first.messages[0].content == "ack:ping"
    assert second.messages[0].content == "ack:pong"
    assert llm.requests[0].messages[0].content == "You are the prompt frozen for this chat."
    assert llm.requests[1].messages[0].content == "You are the prompt frozen for this chat."


def test_before_agent_start_blank_override_does_not_drop_session_frozen_system_prompt() -> None:
    registry = HookRegistry()

    async def clear_prompt(event, ctx):
        del ctx
        return {**event, "system_prompt": "   "}

    registry.on("before_agent_start", clear_prompt)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session(metadata={"system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY."})
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.messages[0].content == "ack:ping"
    assert llm.requests[-1].messages[0].content == "When mentioned in a group chat, reply exactly with NO_REPLY."


def test_input_handled_short_circuits_runtime_flow() -> None:
    registry = HookRegistry()

    async def handled(event, ctx):
        del event, ctx
        return {"action": "handled"}

    registry.on("input", handled)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.messages == ()
    assert result.stop_reason == "handled_by_hook"
    assert llm.requests == []
    assert len(store.events) == 1


def test_hook_exceptions_are_isolated_and_fail_open() -> None:
    registry = HookRegistry()

    async def exploding(event, ctx):
        del event, ctx
        raise RuntimeError("boom")

    registry.on("input", exploding)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    session = manager.create_session()
    llm = EchoLLMClient()
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=llm,
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    result = runtime.run(session.session_id, [{"type": "text", "text": "ping"}], stream=False)

    assert result.messages[0].content == "ack:ping"
    assert llm.requests[-1].messages[-1].content == "ping"


def test_runtime_create_session_emits_session_start_observe_hook() -> None:
    observed_session_ids: list[str] = []
    registry = HookRegistry()

    async def on_session_start(event, ctx):
        del ctx
        observed_session_ids.append(event["session_id"])

    registry.on("session_start", on_session_start)

    store = InMemorySessionStore()
    manager = SessionManager(store=store)
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=EchoLLMClient(),
        model="mock-model",
        hook_runner=HookRunner(registry=registry),
        repo_root=Path.cwd(),
    )

    session = runtime.create_session()

    assert observed_session_ids == [session.session_id]
