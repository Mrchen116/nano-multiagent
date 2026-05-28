"""Verify httpx.AsyncClient transport survives across RunsRegistry submissions.

feat-335: Previously RunsRegistry used asyncio.run() per submission, which closed
the event loop and destroyed the AsyncClient's TCP transport. The fix uses a
dedicated background async loop so the transport stays alive for all runs.
"""

import json
import time
from pathlib import Path

import httpx

from agent.core.agent.runtime import AgentRuntime
from agent.core.llm.factory import LLMFactoryConfig, create_llm_client
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.core.session.manager import SessionManager


_SSE_ACK = """\
data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"ack"},"finish_reason":null}]}

data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":1,"total_tokens":11}}

data: [DONE]
"""


def _make_sse_handler():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=_SSE_ACK)

    return handler, lambda: call_count


def _wait_for(predicate, *, timeout_seconds: float = 3.0) -> None:  # noqa: ANN001
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met before timeout")


def test_two_runs_through_registry_reuse_async_client_transport(tmp_path: Path) -> None:
    """Two RunsRegistry submissions must complete without TCPTransport closed error."""
    handler, get_call_count = _make_sse_handler()

    store = JsonlSessionStore(data_dir=tmp_path / "sessions")
    manager = SessionManager(store=store)
    session = manager.create_session(workspace_root=tmp_path)

    client = create_llm_client(
        config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        transport=httpx.MockTransport(handler),
    )
    runtime = AgentRuntime(
        session_manager=manager,
        llm_client=client,
        model="codex_oauth:gpt-5.5",
    )
    registry = RunsRegistry(runtime=runtime, session_manager=manager)

    try:
        first = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "Q1"}],
        )
        _wait_for(
            lambda: registry.get(first.run_id) is not None
            and registry.get(first.run_id).status in {RunStatus.COMPLETED, RunStatus.FAILED}
        )
        first_final = registry.get(first.run_id)
        assert first_final is not None
        assert first_final.status is RunStatus.COMPLETED, f"first run failed: {first_final.error}"

        second = registry.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "Q2"}],
        )
        _wait_for(
            lambda: registry.get(second.run_id) is not None
            and registry.get(second.run_id).status in {RunStatus.COMPLETED, RunStatus.FAILED}
        )
        second_final = registry.get(second.run_id)
        assert second_final is not None
        assert second_final.status is RunStatus.COMPLETED, f"second run failed: {second_final.error}"

        # Assert the mock handler was called twice (transport survived)
        assert get_call_count() == 2, f"expected 2 LLM calls, got {get_call_count()}"
    finally:
        registry.shutdown()
