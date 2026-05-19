import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

import agent.core.agent.prompting as prompting_module
import agent.core.session.manager as session_manager_module
from agent.core.agent.prompting import CODING_SYSTEM_PROMPT
from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.session.entries import SessionEntryKind
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.persistence.session.service import SessionService


def _sse_response(model: str, content: str) -> httpx.Response:
    """Return an OpenAI-compatible SSE mock response."""
    sse_body = (
        f'data: {{"id":"chatcmpl_mock","object":"chat.completion.chunk","model":"{model}",'
        f'"choices":[{{"index":0,"delta":{{"content":"{content}"}},"finish_reason":null}}]}}\n\n'
        f'data: {{"id":"chatcmpl_mock","object":"chat.completion.chunk","model":"{model}",'
        f'"choices":[{{"index":0,"delta":{{}},"finish_reason":"stop"}}],'
        f'"usage":{{"prompt_tokens":10,"completion_tokens":1,"total_tokens":11}}}}\n\n'
        "data: [DONE]\n\n"
    )
    return httpx.Response(200, text=sse_body)


def _anthropic_sse_response(content: str) -> httpx.Response:
    """Return an Anthropic-formatted SSE mock response."""
    import json as _json
    events = [
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": content}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}},
        {"type": "message_stop"},
    ]
    sse_body = "".join(f"data: {_json.dumps(e)}\n\n" for e in events)
    return httpx.Response(200, text=sse_body)


def _extract_prompt_timestamp(prompt: str) -> str:
    prefix = "Current date and time: "
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError("Current date and time line missing in system prompt")


class _AdvancingPromptDateTime:
    _calls = 0

    @classmethod
    def now(cls) -> datetime:
        value = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC) + timedelta(minutes=cls._calls)
        cls._calls += 1
        return value


class _FixedPromptDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2040, 1, 1, 0, 0, 0, tzinfo=UTC)


class _AdvancingSessionDateTime:
    _calls = 0

    @classmethod
    def now(cls, tz: object = None) -> datetime:
        value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC) + timedelta(minutes=cls._calls)
        cls._calls += 1
        if tz is None:
            return value
        if isinstance(tz, UTC.__class__):
            return value.astimezone(tz)
        return value


async def test_runtime_persists_turn_events_and_reuses_history(tmp_path: Path) -> None:
    observed_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_bodies.append(json.loads(request.read().decode("utf-8")))
        return _sse_response("codex_oauth:gpt-5.4", "ack")

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.4",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )
    runtime = AgentRuntime(session_manager=manager, llm_client=client, model="codex_oauth:gpt-5.4")

    await runtime.run(session.session_id, [{"type": "text", "text": "Q1"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "Q2"}], stream=False)

    turn_events = [event for event in manager.list_entries(session.session_id) if event.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 4
    assert turn_events[0].data["content"] == "Q1"
    assert turn_events[1].data["content"] == "ack"

    second_payload = observed_bodies[-1]
    messages = second_payload["messages"]
    assert [message["role"] for message in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1]["content"] == "Q2"


async def test_runtime_keeps_same_prompt_timestamp_within_one_session(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(prompting_module, "datetime", _AdvancingPromptDateTime)

    observed_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_bodies.append(json.loads(request.read().decode("utf-8")))
        return _sse_response("codex_oauth:gpt-5.4", "ack")

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.4",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )
    # CODING_SYSTEM_PROMPT injected so "Current date and time:" placeholder is present.
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=client,
        model="codex_oauth:gpt-5.4",
        system_prompt=CODING_SYSTEM_PROMPT,
    )

    await runtime.run(session.session_id, [{"type": "text", "text": "Q1"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "Q2"}], stream=False)

    first_system_prompt = observed_bodies[0]["messages"][0]["content"]
    second_system_prompt = observed_bodies[1]["messages"][0]["content"]
    assert _extract_prompt_timestamp(first_system_prompt) == _extract_prompt_timestamp(second_system_prompt)


async def test_runtime_uses_distinct_prompt_timestamps_across_sessions(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(prompting_module, "datetime", _FixedPromptDateTime)
    monkeypatch.setattr(session_manager_module, "datetime", _AdvancingSessionDateTime)

    observed_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_bodies.append(json.loads(request.read().decode("utf-8")))
        return _sse_response("codex_oauth:gpt-5.4", "ack")

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    first_session = service.create_session(workspace_root=tmp_path)
    second_session = service.create_session(workspace_root=tmp_path)

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.4",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )
    # CODING_SYSTEM_PROMPT injected so "Current date and time:" placeholder is present.
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=client,
        model="codex_oauth:gpt-5.4",
        system_prompt=CODING_SYSTEM_PROMPT,
    )

    await runtime.run(first_session.session_id, [{"type": "text", "text": "Q1"}], stream=False)
    await runtime.run(second_session.session_id, [{"type": "text", "text": "Q2"}], stream=False)

    first_system_prompt = observed_bodies[0]["messages"][0]["content"]
    second_system_prompt = observed_bodies[1]["messages"][0]["content"]
    first_timestamp = _extract_prompt_timestamp(first_system_prompt)
    second_timestamp = _extract_prompt_timestamp(second_system_prompt)
    assert first_timestamp == first_session.created_at
    assert second_timestamp == second_session.created_at
    assert first_timestamp != second_timestamp


async def test_runtime_persists_turn_events_with_anthropic_client(tmp_path: Path) -> None:
    observed_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_bodies.append(json.loads(request.read().decode("utf-8")))
        return _anthropic_sse_response("ack")

    service = SessionService(store=JsonlSessionStore(data_dir=tmp_path / "sessions"))
    manager = service.manager
    session = service.create_session(workspace_root=tmp_path)

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="anthropic",
            model="moonshotAnthropic:kimi-k2.5",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )
    runtime = AgentRuntime(session_manager=manager, llm_client=client, model="moonshotAnthropic:kimi-k2.5")

    await runtime.run(session.session_id, [{"type": "text", "text": "Q1"}], stream=False)
    await runtime.run(session.session_id, [{"type": "text", "text": "Q2"}], stream=False)

    turn_events = [event for event in manager.list_entries(session.session_id) if event.kind is SessionEntryKind.TURN_APPENDED]
    assert len(turn_events) == 4
    assert turn_events[0].data["content"] == "Q1"
    assert turn_events[1].data["content"] == "ack"

    second_payload = observed_bodies[-1]
    assert isinstance(second_payload.get("system"), str)
    assert second_payload["system"].strip()
    messages = second_payload["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == [{"type": "text", "text": "Q2"}]
