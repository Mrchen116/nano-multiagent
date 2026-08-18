"""Kernel seams for provider-error bubbles, error.kind, and replay-last-user."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent.core.errors import ModelError
from agent.core.llm.interfaces import LLMMessage
from agent.core.session.types import SessionRef
from agent.platform.permissions.broker import PermissionDecision
from agent.sdk import (
    Kernel,
    LLMConfig,
    LLMModel,
    LLMProvider,
    ReplayLastUserRejected,
    SessionRuntimeConfig,
    build_kernel,
)
from agent.sdk.prompt import PromptSlots


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    return PermissionDecision(behavior="allow")


def _llm() -> LLMConfig:
    return LLMConfig(
        provider="openai_compat",
        model="primary-model",
        base_url="http://127.0.0.1:4000",
        default_model="primary-model",
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(
                    LLMModel(name="primary-model"),
                    LLMModel(name="backup-model"),
                ),
            ),
        ),
    )


def _runtime(model: str) -> SessionRuntimeConfig:
    return SessionRuntimeConfig(
        model=model,
        prompt=PromptSlots(),
        skills=None,
        enabled_tools=[],
        features=None,
    )


class _ScriptedClient:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[Any] = []

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self.requests.append(request)
        return self._outcomes.pop(0)


async def _fail_quota():
    raise ModelError(
        "insufficient balance",
        details={"status_code": 403, "provider_code": "insufficient_quota"},
    )
    yield LLMMessage(
        role="assistant", content="", finish_reason="stop"
    )  # pragma: no cover


async def _succeed(text: str = "backup-ok"):
    yield LLMMessage(
        role="assistant",
        content=text,
        finish_reason="stop",
        tool_calls=(),
        usage=None,
    )


async def _partial_then_fail():
    yield LLMMessage(
        role="assistant",
        content="partial answer",
        finish_reason=None,
        tool_calls=(),
        usage=None,
    )
    raise ModelError("overloaded", details={"status_code": 503})


def _build_kernel(tmp_path: Path, client: _ScriptedClient) -> Kernel:
    return build_kernel(
        llm=_llm(),
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=client,
    )


async def _wait_terminal(kernel: Kernel, run_id: str, *, timeout: float = 5.0) -> Any:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record and record.status in {"completed", "failed", "cancelled"}:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach terminal status")


async def _events_until_terminal(
    kernel: Kernel, session_id: str, run_id: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for event in kernel.stream(session_id, after_sequence=0):
        events.append(event)
        if (
            event.get("event") == "run_status"
            and event.get("run_id") == run_id
            and event.get("status") in {"completed", "failed", "cancelled"}
        ):
            break
    return events


def _user_contents(kernel: Kernel, session_id: str, workspace_root: Path) -> list[str]:
    conversation = kernel._c.directory.open(  # noqa: SLF001
        SessionRef(session_id=session_id, workspace_root=workspace_root)
    )
    return [
        str(message.content)
        for message in conversation.history_snapshot()
        if getattr(message, "role", None) == "user"
    ]


async def test_provider_error_bubble_includes_model_id(tmp_path: Path) -> None:
    client = _ScriptedClient([_fail_quota()])
    kernel = _build_kernel(tmp_path, client)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, runtime=_runtime("primary-model")
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )
        events = await _events_until_terminal(kernel, session.session_id, run.run_id)
        texts = [
            event.get("content")
            for event in events
            if event.get("event") == "assistant_message"
        ]
        assert any(
            isinstance(text, str)
            and text.startswith("⚠️ 模型调用失败（primary-model）:")
            and "insufficient balance" in text
            for text in texts
        )
    finally:
        kernel.close()


async def test_failed_run_status_exposes_kind_on_stream(tmp_path: Path) -> None:
    client = _ScriptedClient([_fail_quota()])
    kernel = _build_kernel(tmp_path, client)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, runtime=_runtime("primary-model")
        )
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )
        events = await _events_until_terminal(kernel, session.session_id, run.run_id)
        terminal = next(
            event
            for event in events
            if event.get("event") == "run_status"
            and event.get("run_id") == run.run_id
            and event.get("status") == "failed"
        )
        error = terminal.get("error")
        assert isinstance(error, dict)
        assert error.get("kind") == "quota"
        assert error.get("code") == "run_execution_failed"
        assert "insufficient balance" in str(error.get("message"))
    finally:
        kernel.close()


async def test_replay_last_user_does_not_append_another_user(tmp_path: Path) -> None:
    client = _ScriptedClient([_fail_quota(), _succeed()])
    kernel = _build_kernel(tmp_path, client)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, runtime=_runtime("primary-model")
        )
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "only-once"}],
            workspace_root=tmp_path,
        )
        await _wait_terminal(kernel, first.run_id)
        await kernel.reconfigure_session(
            session_id=session.session_id,
            workspace_root=tmp_path,
            runtime=_runtime("backup-model"),
        )
        replay = kernel.replay_last_user(
            session_id=session.session_id, workspace_root=tmp_path
        )
        terminal = await _wait_terminal(kernel, replay.run_id)
        assert terminal.status == "completed"
        assert _user_contents(kernel, session.session_id, tmp_path) == ["only-once"]
        replay_users = [
            message.content
            for message in client.requests[-1].messages
            if getattr(message, "role", None) == "user"
        ]
        assert replay_users.count("only-once") == 1
    finally:
        kernel.close()


async def test_replay_last_user_rejects_non_provider_error_output(
    tmp_path: Path,
) -> None:
    client = _ScriptedClient([_partial_then_fail()])
    kernel = _build_kernel(tmp_path, client)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, runtime=_runtime("primary-model")
        )
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )
        await _wait_terminal(kernel, first.run_id)
        try:
            kernel.replay_last_user(
                session_id=session.session_id, workspace_root=tmp_path
            )
        except ReplayLastUserRejected:
            return
        raise AssertionError("expected ReplayLastUserRejected")
    finally:
        kernel.close()


async def test_empty_submit_parts_remain_illegal(tmp_path: Path) -> None:
    client = _ScriptedClient([])
    kernel = _build_kernel(tmp_path, client)
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path, runtime=_runtime("primary-model")
        )
        try:
            kernel.submit(
                session_id=session.session_id,
                parts=[],
                workspace_root=tmp_path,
            )
        except ValueError as exc:
            assert "empty input parts" in str(exc)
            return
        raise AssertionError("empty submit parts must stay illegal")
    finally:
        kernel.close()
