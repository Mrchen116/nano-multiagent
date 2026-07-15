"""Integration coverage for explicit zero-tool Kernel sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent.core.llm.interfaces import LLMMessage
from agent.sdk import LLMConfig, build_kernel


class _CapturingClient:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def generate(self, request: Any):
        self.requests.append(request)

        async def _stream():
            yield LLMMessage(role="assistant", content="done", finish_reason=None)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")

        return _stream()


async def _wait_terminal(kernel: Any, run_id: str) -> None:
    while True:
        record = kernel.get_run(run_id)
        if record is not None and record.status in {"completed", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.01)


async def test_create_session_empty_allowlist_exposes_no_runtime_tools(
    tmp_path: Path,
) -> None:
    """Gateway's explicit empty enabled_tools remains empty at model request time."""

    client = _CapturingClient()
    kernel = build_kernel(
        llm=LLMConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://127.0.0.1:1",
        ),
        repo_root=tmp_path,
        _llm_client_override=client,
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=[],
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )
        await _wait_terminal(kernel, run.run_id)

        assert client.requests
        assert client.requests[-1].tools == ()
    finally:
        await kernel.aclose()
