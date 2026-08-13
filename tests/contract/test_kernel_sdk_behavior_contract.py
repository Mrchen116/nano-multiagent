"""Kernel SDK behavior contracts — migrated from HTTP contract tests (refactor-387-M4).

These tests verify internal kernel behaviors that were previously tested through
the HTTP API layer.  After M4 the HTTP layer is deleted; these SDK-driven tests
provide equivalent coverage by driving the kernel directly.

Behaviors covered:
- run cancel (running → cancelled, idempotent second cancel, cancel unknown run)
- session interrupt (interrupt queued run, interrupt unknown session)
- LLM config get and reconfigure shapes
- list_session_tools surface
- message sync (submit → run completes → messages stored in session)
- global capabilities / get_llm_config
- hook intercept (hook modifying tool input before execution)
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from agent.sdk import (
    USER_INTERRUPT_RECOVERY_CONTENT,
    Kernel,
    LLMConfig,
    LLMModel,
    LLMProvider,
    RunOrigin,
    build_kernel,
)
from agent.core.llm.interfaces import LLMMessage, LLMToolCall


def _lc_llm() -> LLMConfig:
    """The SDK LLMConfig the local-coding behavior contracts build against.

    Carries a two-provider catalog (openai_compat + anthropic) so the model
    registry resolves both — per-run model routing (bugfix-429) selects the
    client by the model's registered provider.
    """
    return LLMConfig(
        provider="openai_compat",
        model="codex_oauth:gpt-5.5",
        base_url="http://127.0.0.1:4000",
        default_model="codex_oauth:gpt-5.5",
        providers=(
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="codex_oauth:gpt-5.5"),),
            ),
            LLMProvider(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="test-model-xyz"),),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_agent_sdk_surface_contract.py)
# ---------------------------------------------------------------------------


async def _allow_all(tool, input, ctx) -> Any:  # noqa: ANN001
    from agent.platform.permissions.broker import PermissionDecision

    return PermissionDecision(behavior="allow")


def _fake_llm_client(*, content: str = "stub-response") -> Any:
    """Return a fake LLM client that yields one real LLMMessage per call.

    Uses a proper LLMMessage dataclass (not MagicMock) so session serialization
    works without 'not JSON serializable' errors.
    """

    class _FakeClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            return _async_stub_messages(content)

    return _FakeClient()


async def _async_stub_messages(content: str = "stub-response"):
    yield LLMMessage(
        role="assistant",
        content=content,
        finish_reason="stop",
        tool_calls=(),
        usage=None,
    )


def _build_kernel(tmp_path: Path, **kwargs: Any) -> Kernel:
    # refactor-406-M1 R7: built via the 2-layer surface (legacy product_profile
    # path removed). Built-in tools suffice for these behavior contracts.
    defaults: dict[str, Any] = dict(
        llm=_lc_llm(),
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        _llm_client_override=_fake_llm_client(),
    )
    defaults.update(kwargs)
    return build_kernel(**defaults)


async def _wait_for_terminal_run(
    kernel: Kernel, run_id: str, *, timeout: float = 3.0
) -> Any:
    """Poll kernel.get_run() until terminal status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record and record.status in {"completed", "failed", "cancelled"}:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach terminal status in {timeout}s")


async def _wait_for_run_status(
    kernel: Kernel, run_id: str, target_status: str, *, timeout: float = 3.0
) -> Any:
    """Poll until run reaches target_status."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        record = kernel.get_run(run_id)
        if record and record.status == target_status:
            return record
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach {target_status!r} in {timeout}s")


# ---------------------------------------------------------------------------
# Run cancel
# ---------------------------------------------------------------------------


async def test_run_cancel_cancels_running_run_idempotent(tmp_path: Path) -> None:
    """kernel.cancel(run_id) must cancel a running run; second cancel is idempotent."""
    blocking_event: asyncio.Event = asyncio.Event()

    class _BlockingClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            return _blocking_generate(blocking_event)

    async def _blocking_generate(event: asyncio.Event):
        await asyncio.wait_for(event.wait(), timeout=5.0)
        yield LLMMessage(
            role="assistant", content="unblocked", finish_reason="stop", tool_calls=()
        )

    kernel = _build_kernel(tmp_path, _llm_client_override=_BlockingClient())
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "blocking"}],
            workspace_root=tmp_path,
        )
        run_id = run.run_id

        # Wait for run to enter running state
        await _wait_for_run_status(kernel, run_id, "running")

        cancelled = kernel.cancel(run_id)
        assert cancelled is not None
        assert cancelled.run_id == run_id
        assert cancelled.status == "cancelled"

        # Second cancel is idempotent (already cancelled)
        idempotent = kernel.cancel(run_id)
        assert idempotent is not None
        assert idempotent.status == "cancelled"

        blocking_event.set()
    finally:
        kernel.close()


def test_cancel_unknown_run_returns_none(tmp_path: Path) -> None:
    """kernel.cancel() on unknown run_id returns None (not an exception)."""
    kernel = _build_kernel(tmp_path)
    try:
        result = kernel.cancel("run_unknown_xyz")
        assert result is None
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# Session interrupt
# ---------------------------------------------------------------------------


async def test_session_interrupt_returns_run_id(tmp_path: Path) -> None:
    """kernel.interrupt(session_id) must return the interrupted run_id when active."""
    kernel = _build_kernel(tmp_path)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
        )

        # Wait for run to complete (stub LLM is fast)
        record = await _wait_for_terminal_run(kernel, run.run_id)
        assert record.status == "completed"

        # interrupt on already-completed session: returns None (no active run)
        interrupted = kernel.interrupt(session.session_id)
        # None is fine (no active run to interrupt) — just verify it doesn't raise
        assert interrupted is None or isinstance(interrupted, str)
    finally:
        kernel.close()


async def test_session_interrupt_cancels_run_and_unblocks_next_turn(
    tmp_path: Path,
) -> None:
    """interrupt() must terminalize the run before the session can continue."""
    started = threading.Event()

    class _InterruptibleFirstClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request: Any):  # noqa: ANN001, ANN201
            self.calls += 1
            if self.calls == 1:
                return self._block_forever()
            return _async_stub_messages("continued-after-interrupt")

        async def _block_forever(self):  # noqa: ANN202
            started.set()
            await asyncio.Future()
            yield  # pragma: no cover - makes this an async generator

    kernel = _build_kernel(
        tmp_path,
        _llm_client_override=_InterruptibleFirstClient(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        interrupted_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "block forever"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(started.wait, 1.0)

        assert kernel.interrupt(session.session_id) == interrupted_run.run_id
        terminal = await _wait_for_terminal_run(kernel, interrupted_run.run_id)
        assert terminal.status == "cancelled"

        continued_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "continue"}],
            workspace_root=tmp_path,
        )
        continued = await _wait_for_terminal_run(kernel, continued_run.run_id)
        assert continued.status == "completed"
    finally:
        kernel.close()


async def test_session_interrupt_wins_when_provider_finishes_during_grace(
    tmp_path: Path,
) -> None:
    """A provider returning after interrupt must not commit a completed run."""
    started = threading.Event()
    release = threading.Event()

    class _GraceRaceClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request: Any):  # noqa: ANN001, ANN201
            self.calls += 1
            if self.calls == 1:
                return self._finish_when_released()
            return _async_stub_messages("continued-after-race")

        async def _finish_when_released(self):  # noqa: ANN202
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.001)
            yield LLMMessage(
                role="assistant",
                content="late-provider-result",
                finish_reason="stop",
                tool_calls=(),
            )

    kernel = _build_kernel(tmp_path, _llm_client_override=_GraceRaceClient())
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        interrupted_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "race interrupt"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(started.wait, 1.0)

        assert kernel.interrupt(session.session_id) == interrupted_run.run_id
        release.set()
        terminal = await _wait_for_terminal_run(kernel, interrupted_run.run_id)
        assert terminal.status == "cancelled"

        continued_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "continue"}],
            workspace_root=tmp_path,
        )
        continued = await _wait_for_terminal_run(kernel, continued_run.run_id)
        assert continued.status == "completed"
    finally:
        kernel.close()


async def test_session_interrupt_suppresses_chunk_blocked_in_message_hook(
    tmp_path: Path,
) -> None:
    """An accepted interrupt must prevent a hook-paused chunk from becoming history."""
    hook_started = threading.Event()
    release_hook = threading.Event()
    captured_requests: list[Any] = []

    class _HookRaceClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            captured_requests.append(request)
            content = (
                "racy-late-output"
                if len(captured_requests) == 1
                else "continued-after-hook-race"
            )
            return _async_stub_messages(content)

    async def _block_message_start(event: Any, _ctx: Any) -> None:
        if event.get("role") != "assistant" or hook_started.is_set():
            return
        hook_started.set()
        await asyncio.to_thread(release_hook.wait)

    def _setup_hooks(hooks: Any) -> None:
        hooks.on("message_start", _block_message_start, timeout_ms=None)

    kernel = _build_kernel(
        tmp_path,
        hooks=[_setup_hooks],
        _llm_client_override=_HookRaceClient(),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        interrupted_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "pause in hook"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(hook_started.wait, 1.0)

        assert kernel.interrupt(session.session_id) == interrupted_run.run_id
        release_hook.set()
        terminal = await _wait_for_terminal_run(kernel, interrupted_run.run_id)
        assert terminal.status == "cancelled"

        continued_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "continue"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal_run(kernel, continued_run.run_id)).status == (
            "completed"
        )
        continued_context = " ".join(
            _flatten_msg_text(message) for message in captured_requests[-1].messages
        )
        assert "racy-late-output" not in continued_context
    finally:
        release_hook.set()
        kernel.close()


async def test_session_interrupt_suppresses_message_end_wakeup_queued_before_cancel(
    tmp_path: Path,
) -> None:
    """A hook wakeup already queued before cancel cannot publish after /stop."""
    hook_started = threading.Event()
    loop_blocked = threading.Event()
    release_loop = threading.Event()
    hook_loop: list[asyncio.AbstractEventLoop] = []
    hook_future: list[asyncio.Future[None]] = []

    async def _park_first_message_end(event: Any, _ctx: Any) -> None:
        if event.get("role") != "assistant" or hook_started.is_set():
            return
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        hook_loop.append(loop)
        hook_future.append(future)
        hook_started.set()
        await future

    def _setup_hooks(hooks: Any) -> None:
        hooks.on("message_end", _park_first_message_end, timeout_ms=None)

    kernel = _build_kernel(
        tmp_path,
        hooks=[_setup_hooks],
        _llm_client_override=_fake_llm_client(content="queued-before-cancel-output"),
    )
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        interrupted_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "pause in message_end"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(hook_started.wait, 1.0)

        def _queue_wakeup_then_block_owner_loop() -> None:
            hook_future[0].set_result(None)
            loop_blocked.set()
            release_loop.wait()

        hook_loop[0].call_soon_threadsafe(_queue_wakeup_then_block_owner_loop)
        assert await asyncio.to_thread(loop_blocked.wait, 1.0)

        assert kernel.interrupt(session.session_id) == interrupted_run.run_id
        release_loop.set()
        assert (
            await _wait_for_terminal_run(kernel, interrupted_run.run_id)
        ).status == ("cancelled")

        continued_run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "continue"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal_run(kernel, continued_run.run_id)).status == (
            "completed"
        )

        events: list[dict[str, Any]] = []
        async for event in kernel.stream(session.session_id, after_sequence=0):
            events.append(event)
            if (
                event.get("event") == "run_status"
                and event.get("run_id") == continued_run.run_id
                and event.get("status") == "completed"
            ):
                break
        late_events = [
            event
            for event in events
            if event.get("event") == "assistant_message"
            and event.get("run_id") == interrupted_run.run_id
        ]
        assert late_events == []
    finally:
        release_loop.set()
        kernel.close()


# ---------------------------------------------------------------------------
# LLM config
# ---------------------------------------------------------------------------


def test_llm_config_get_shape(tmp_path: Path) -> None:
    """kernel.get_llm_config() must return an LLMFactoryConfig with required fields."""
    kernel = _build_kernel(tmp_path)
    try:
        config = kernel.get_llm_config()
        # LLMFactoryConfig has provider, model, base_url
        assert hasattr(config, "provider")
        assert hasattr(config, "model")
        assert hasattr(config, "base_url")
        assert isinstance(config.provider, str)
        assert isinstance(config.model, str)
    finally:
        kernel.close()


# bugfix-429: test_llm_config_reconfigure_updates_provider removed — reconfigure_llm
# retired. model is per-run now (submit(model=)); there is no kernel-level reconfigure.


# ---------------------------------------------------------------------------
# List session tools
# ---------------------------------------------------------------------------


def test_list_session_tools_returns_result(tmp_path: Path) -> None:
    """kernel.list_session_tools() exposes the CLI-facing public payload."""
    kernel = _build_kernel(tmp_path)
    try:
        # list_session_tools is sync; does not require an active session
        tools_result = kernel.list_session_tools(
            session_id="test-session", workspace_root=tmp_path
        )
        assert tools_result["session_id"] == "test-session"
        assert isinstance(tools_result["tools"], list)
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# Message sync (submit → run completes → messages stored)
# ---------------------------------------------------------------------------


async def test_message_sync_completes_and_updates_run(tmp_path: Path) -> None:
    """Submit a message; after run completes, the run record must show 'completed'."""
    kernel = _build_kernel(tmp_path)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello world"}],
            workspace_root=tmp_path,
        )
        run_id = run.run_id

        record = await _wait_for_terminal_run(kernel, run_id)
        assert record.status == "completed"
        # refactor-406 决策 6: get_run returns the SDK-owned RunInfo (run_id /
        # session_id / status only); turn_id is an internal RunRecord field, not
        # part of the curated boundary DTO and not consumed by any product.
    finally:
        kernel.close()


async def test_submit_accepts_string_workspace_root(tmp_path: Path) -> None:
    """The SDK path boundary must normalize the documented string form."""

    kernel = _build_kernel(tmp_path)
    try:
        session = await kernel.create_session(workspace_root=str(tmp_path))
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "string workspace"}],
            workspace_root=str(tmp_path),
        )

        assert (await _wait_for_terminal_run(kernel, run.run_id)).status == "completed"
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# append_message cache coherence (feat-394 cron awareness regression)
# ---------------------------------------------------------------------------


def _flatten_msg_text(message: Any) -> str:
    """Join an LLMMessage's content into a plain string (content may be str or parts)."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


async def test_append_message_visible_to_next_turn(tmp_path: Path) -> None:
    """A message appended out-of-band must be visible to the next turn's prompt.

    feat-394 cron awareness regression. ``Kernel.append_message`` writes the
    entry to the session JSONL, but the runtime serves history from an in-memory
    cache (``_session_histories``) populated by the previous turn. Without cache
    invalidation the appended message is persisted yet never reaches the model —
    the user asks a cron follow-up and the agent has no memory of its own report.

    This drives the REAL kernel (not a fake client recording append calls), so it
    fails on the pre-fix code (stale cache) and passes once append_message drops
    the cached history for the session.
    """
    captured_requests: list[Any] = []

    class _CapturingClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            captured_requests.append(request)
            return _async_stub_messages("ack")

    kernel = _build_kernel(tmp_path, _llm_client_override=_CapturingClient())
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        sid = session.session_id

        # Turn 1 populates the runtime in-memory history cache for this session.
        run1 = kernel.submit(
            session_id=sid,
            parts=[{"type": "text", "text": "first turn"}],
            workspace_root=tmp_path,
        )
        await _wait_for_terminal_run(kernel, run1.run_id)

        # Out-of-band append — the cron awareness injection path.
        marker = "CRON-AWARENESS-MARKER-42"
        kernel.append_message(
            sid,
            role="user",
            content=f"System (untrusted): [ts] {marker}",
            workspace_root=tmp_path,
            metadata={"is_cron_awareness": True},
        )

        # Turn 2 must assemble its prompt from a history that includes the append.
        run2 = kernel.submit(
            session_id=sid,
            parts=[{"type": "text", "text": "what did you just report?"}],
            workspace_root=tmp_path,
        )
        await _wait_for_terminal_run(kernel, run2.run_id)

        assert len(captured_requests) >= 2, "expected two model turns"
        second_turn_text = " ".join(
            _flatten_msg_text(m) for m in captured_requests[-1].messages
        )
        assert marker in second_turn_text, (
            "out-of-band appended message must be visible to the next turn's "
            "prompt; stale _session_histories cache hid the cron awareness entry"
        )
    finally:
        kernel.close()


async def test_append_message_during_active_turn_reloads_residual_output(
    tmp_path: Path,
) -> None:
    """A concurrent append must not detach the active turn from live history."""

    started = threading.Event()
    release = threading.Event()
    captured_requests: list[Any] = []

    class _BlockingFirstClient:
        async def generate(self, request: Any):  # noqa: ANN001, ANN201
            captured_requests.append(request)
            if len(captured_requests) == 1:
                started.set()
                await asyncio.to_thread(release.wait)
                content = "reply-after-external"
            else:
                content = "follow-up-reply"
            yield LLMMessage(
                role="assistant",
                content=content,
                finish_reason="stop",
                tool_calls=(),
            )

    kernel = _build_kernel(tmp_path, _llm_client_override=_BlockingFirstClient())
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "first"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(started.wait, 2)

        kernel.append_message(
            session.session_id,
            role="user",
            content="external-while-active",
            workspace_root=tmp_path,
        )
        release.set()
        assert (
            await _wait_for_terminal_run(kernel, first.run_id)
        ).status == "completed"

        second = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "second"}],
            workspace_root=tmp_path,
        )
        assert (
            await _wait_for_terminal_run(kernel, second.run_id)
        ).status == "completed"

        second_context = [
            (message.role, _flatten_msg_text(message))
            for message in captured_requests[-1].messages
        ]
        assert ("user", "external-while-active") in second_context
        assert ("assistant", "reply-after-external") in second_context
    finally:
        release.set()
        kernel.close()


@pytest.mark.parametrize("interrupt", [False, True], ids=["tool-result", "recovery"])
async def test_active_append_preserves_late_tool_or_recovery_for_next_turn(
    tmp_path: Path,
    interrupt: bool,
) -> None:
    tool_started = threading.Event()
    release_tool = threading.Event()
    captured_requests: list[Any] = []
    tool_requested = False

    class _BlockingTool:
        name = "blocking_tool"
        description = "Block until the test releases the tool."
        input_schema = {"type": "object", "properties": {}}

        def run(self, _args: Any, _ctx: Any) -> dict[str, str]:
            tool_started.set()
            release_tool.wait()
            return {"result": "LATE-TOOL-RESULT"}

    class _ToolClient:
        async def generate(self, request: Any):  # noqa: ANN201
            nonlocal tool_requested
            captured_requests.append(request)
            if not tool_requested:
                tool_requested = True
                yield LLMMessage(
                    role="assistant",
                    content="calling blocking tool",
                    tool_calls=(
                        LLMToolCall(
                            call_id="call_active_append",
                            name="blocking_tool",
                            arguments={},
                        ),
                    ),
                )
                return
            yield LLMMessage(
                role="assistant", content="after-tool", finish_reason="stop"
            )

    kernel = _build_kernel(
        tmp_path,
        tools=[_BlockingTool()],
        _llm_client_override=_ToolClient(),
    )
    try:
        session = await kernel.create_session(
            workspace_root=tmp_path,
            enabled_tools=["blocking_tool"],
        )
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "run blocking tool"}],
            workspace_root=tmp_path,
        )
        assert await asyncio.to_thread(tool_started.wait, 2)

        kernel.append_message(
            session.session_id,
            role="user",
            content="external-during-tool",
            workspace_root=tmp_path,
        )
        if interrupt:
            assert kernel.interrupt(session.session_id) == first.run_id
        release_tool.set()
        expected_status = "cancelled" if interrupt else "completed"
        assert (await _wait_for_terminal_run(kernel, first.run_id)).status == (
            expected_status
        )

        followup = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "after active append"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal_run(kernel, followup.run_id)).status == (
            "completed"
        )
        followup_context = " ".join(
            _flatten_msg_text(message) for message in captured_requests[-1].messages
        )
        assert "external-during-tool" in followup_context
        expected_residual = (
            USER_INTERRUPT_RECOVERY_CONTENT if interrupt else "LATE-TOOL-RESULT"
        )
        assert expected_residual in followup_context
    finally:
        release_tool.set()
        kernel.close()


async def test_whole_session_fork_copies_history_and_evolves_independently(
    tmp_path: Path,
) -> None:
    captured_requests: list[Any] = []

    class _CapturingClient:
        def generate(self, request: Any):  # noqa: ANN001, ANN201
            captured_requests.append(request)
            return _async_stub_messages(f"ack-{len(captured_requests)}")

    kernel = _build_kernel(tmp_path, _llm_client_override=_CapturingClient())
    try:
        source = await kernel.create_session(workspace_root=tmp_path)
        for text in ("source-first", "source-second"):
            run = kernel.submit(
                session_id=source.session_id,
                parts=[{"type": "text", "text": text}],
                workspace_root=tmp_path,
            )
            assert (await _wait_for_terminal_run(kernel, run.run_id)).status == (
                "completed"
            )

        forked = await kernel.fork_session(
            source.session_id,
            workspace_root=tmp_path,
            up_to=None,
        )
        assert forked.fork_id_map is not None
        assert len(forked.fork_id_map) == 4

        branch_run = kernel.submit(
            session_id=forked.session_id,
            parts=[{"type": "text", "text": "fork-only"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal_run(kernel, branch_run.run_id)).status == (
            "completed"
        )
        branch_context = " ".join(
            _flatten_msg_text(message) for message in captured_requests[-1].messages
        )
        assert "source-first" in branch_context
        assert "source-second" in branch_context

        source_run = kernel.submit(
            session_id=source.session_id,
            parts=[{"type": "text", "text": "source-after-fork"}],
            workspace_root=tmp_path,
        )
        assert (await _wait_for_terminal_run(kernel, source_run.run_id)).status == (
            "completed"
        )
        source_context = " ".join(
            _flatten_msg_text(message) for message in captured_requests[-1].messages
        )
        assert "fork-only" not in source_context
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# Global capabilities (get_llm_config ↔ capabilities parity)
# ---------------------------------------------------------------------------


# bugfix-429: test_global_capabilities_llm_config_round_trip removed — reconfigure_llm
# retired. get_llm_config() still reports the build-time active connection; per-run
# model selection is covered by submit(model=) transmission tests, not reconfigure.


def test_build_kernel_tolerates_empty_provider(tmp_path: Path) -> None:
    """bugfix-429: a provider declared with no models must not crash build_kernel.

    The multi-client path (no _llm_client_override) builds one client per provider;
    an empty provider is skipped (nothing routes to it) rather than resolving an
    empty model map and blowing up on next(iter(...)).
    """
    llm = LLMConfig(
        provider="anthropic",
        model="kimiCoding:K2.6",
        base_url="http://127.0.0.1:4000",
        default_model="kimiCoding:K2.6",
        providers=(
            LLMProvider(
                name="anthropic",
                base_url="http://127.0.0.1:4000",
                models=(LLMModel(name="kimiCoding:K2.6"),),
            ),
            # Empty provider — must be tolerated.
            LLMProvider(
                name="openai_compat",
                base_url="http://127.0.0.1:4000",
                models=(),
            ),
        ),
    )
    kernel = build_kernel(
        llm=llm,
        workspace_config_dirname=".nanocode",
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        # No _llm_client_override → exercise the per-provider client construction.
    )
    try:
        names = {m.name for m in kernel.list_models()}
        assert "kimiCoding:K2.6" in names
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# submit(steer=...) — mid-run message steering (bugfix-426 决策1/2)
# ---------------------------------------------------------------------------


async def test_submit_steer_idle_session_creates_new_run(tmp_path: Path) -> None:
    """submit(steer=True) with no active run falls back to a normal new run.

    injected must be False and the run must execute (steer path degrades to
    submit when the session is idle — no side effects vs. plain submit).
    """
    kernel = _build_kernel(tmp_path)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        run = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "hello"}],
            workspace_root=tmp_path,
            steer=True,
        )
        assert run.injected is False
        record = await _wait_for_terminal_run(kernel, run.run_id)
        assert record.status == "completed"
    finally:
        kernel.close()


class _ThreadGatedClient:
    """LLM client whose generate() blocks on a threading.Event before yielding.

    A threading.Event (not asyncio.Event) is used because the run executes on the
    registry's dedicated background loop while the test sets the gate from the main
    loop; threading.Event.is_set() is safe across both. Polled with asyncio.sleep
    so the run stays RUNNING (lets the test inject a steer) yet unblocks promptly.
    """

    def __init__(self, gate) -> None:  # noqa: ANN001
        self._gate = gate
        self.requests: list[Any] = []

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self.requests.append(request)
        return self._generate()

    async def _generate(self):
        while not self._gate.is_set():
            await asyncio.sleep(0.01)
        yield LLMMessage(
            role="assistant", content="unblocked", finish_reason="stop", tool_calls=()
        )


async def test_submit_steer_active_run_injects_not_new_run(tmp_path: Path) -> None:
    """submit(steer=True) during an active run injects into it (injected=True),
    reuses its run_id, and does NOT create a second run."""
    import threading

    gate = threading.Event()
    kernel = _build_kernel(tmp_path, _llm_client_override=_ThreadGatedClient(gate))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long task"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, first.run_id, "running")
        assert await kernel.discard_run_messages(first.run_id) is False

        runs_before = set(kernel._c.runs_registry._runs.keys())  # noqa: SLF001
        steered = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "actually use web_search"}],
            workspace_root=tmp_path,
            steer=True,
        )
        assert steered.injected is True
        assert steered.run_id == first.run_id
        # No new run was created by the steer call.
        assert set(kernel._c.runs_registry._runs.keys()) == runs_before  # noqa: SLF001

        gate.set()
        await _wait_for_terminal_run(kernel, first.run_id)
    finally:
        gate.set()
        kernel.close()


async def test_try_steer_without_active_run_is_inject_only(tmp_path: Path) -> None:
    """A rejected public steer attempt must never create a fallback run."""

    kernel = _build_kernel(tmp_path)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        runs_before = set(kernel._c.runs_registry._runs)  # noqa: SLF001

        result = kernel.try_steer(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "late steer"}],
        )

        assert result is None
        assert set(kernel._c.runs_registry._runs) == runs_before  # noqa: SLF001
    finally:
        kernel.close()


async def test_try_steer_active_run_reuses_existing_run(tmp_path: Path) -> None:
    """The public inject-only seam returns the active run when admission wins."""

    import threading

    gate = threading.Event()
    kernel = _build_kernel(tmp_path, _llm_client_override=_ThreadGatedClient(gate))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        active = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long task"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, active.run_id, "running")
        runs_before = set(kernel._c.runs_registry._runs)  # noqa: SLF001

        steered = kernel.try_steer(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "use the new constraint"}],
            expected_run_id=active.run_id,
        )

        assert steered is not None
        assert steered.injected is True
        assert steered.run_id == active.run_id
        assert steered.pending_id is not None
        assert steered.pending_id.startswith("pending_")
        assert set(kernel._c.runs_registry._runs) == runs_before  # noqa: SLF001
    finally:
        gate.set()
        kernel.close()


async def test_non_user_terminal_publishes_correlated_recovery_protocol(
    tmp_path: Path,
) -> None:
    """SDK stream closes an accepted steer handoff without consumer inference."""

    gate = threading.Event()
    kernel = _build_kernel(tmp_path, _llm_client_override=_ThreadGatedClient(gate))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        active = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long task"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, active.run_id, "running")
        steered = [
            kernel.try_steer(
                session_id=session.session_id,
                parts=[{"type": "text", "text": text}],
                origin=origin,
                expected_run_id=active.run_id,
            )
            for text, origin in (
                ("recover user one", RunOrigin.USER),
                ("recover background", RunOrigin.BACKGROUND_TASK),
                ("recover user two", RunOrigin.USER),
            )
        ]
        assert all(item is not None and item.pending_id for item in steered)

        kernel.cancel(active.run_id)
        events: list[dict[str, Any]] = []
        try:
            async with asyncio.timeout(3):
                async for event in kernel.stream(
                    session.session_id, after_sequence=active.start_sequence
                ):
                    events.append(event)
                    if event.get("event") == "recovery_settled":
                        break
        except TimeoutError:
            pytest.fail(f"recovery settlement missing; observed events={events!r}")

        terminal_index = next(
            index
            for index, event in enumerate(events)
            if event.get("event") == "run_status"
            and event.get("run_id") == active.run_id
            and event.get("status") == "cancelled"
        )
        continuation_indexes = [
            index
            for index, event in enumerate(events)
            if event.get("event") == "run_status" and event.get("continuation")
        ]
        settlement_index = next(
            index
            for index, event in enumerate(events)
            if event.get("event") == "recovery_settled"
        )
        assert len(continuation_indexes) == 3
        assert terminal_index < continuation_indexes[0] < settlement_index

        continuations = [events[index]["continuation"] for index in continuation_indexes]
        recovery_ids = {continuation["recovery_id"] for continuation in continuations}
        assert len(recovery_ids) == 1
        assert all(
            continuation["predecessor_run_id"] == active.run_id
            for continuation in continuations
        )
        assert [continuation["batch_index"] for continuation in continuations] == [
            0,
            1,
            2,
        ]
        assert [continuation["origin"] for continuation in continuations] == [
            "user",
            "background_task",
            "user",
        ]
        assert [continuation["pending_ids"] for continuation in continuations] == [
            [item.pending_id] for item in steered if item is not None
        ]
        settlement = events[settlement_index]
        assert settlement["recovery_id"] == continuations[0]["recovery_id"]
        assert settlement["predecessor_run_id"] == active.run_id
        assert settlement["outcome"] == "scheduled"
        assert settlement["successor_run_ids"] == [
            events[index]["run_id"] for index in continuation_indexes
        ]
    finally:
        gate.set()
        kernel.close()


async def test_try_steer_rejects_stale_expected_run_identity(tmp_path: Path) -> None:
    """The public inject-only seam never redirects an old marker to a new run."""

    import threading

    gate = threading.Event()
    kernel = _build_kernel(tmp_path, _llm_client_override=_ThreadGatedClient(gate))
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        current = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "replacement run"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, current.run_id, "running")

        steered = kernel.try_steer(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "stale follower"}],
            expected_run_id="run-that-already-ended",
        )

        assert steered is None
        assert kernel.get_run(current.run_id).status == "running"
    finally:
        gate.set()
        kernel.close()


async def test_submit_steer_preserves_structured_image_content(tmp_path: Path) -> None:
    """Active steer must preserve the same structured image blocks as normal submit."""
    import threading

    gate = threading.Event()
    client = _ThreadGatedClient(gate)
    kernel = _build_kernel(tmp_path, _llm_client_override=client)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "long task"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, first.run_id, "running")

        kernel.submit(
            session_id=session.session_id,
            parts=[
                {"type": "text", "text": "see this"},
                {"type": "image", "image_url": "data:image/png;base64,AAAA"},
            ],
            workspace_root=tmp_path,
            steer=True,
        )

        # The pending queue is the ownership boundary before the next model round.
        registry = kernel._c.runs_registry  # noqa: SLF001
        controller = registry._controllers[first.run_id]  # noqa: SLF001
        pending = controller.drain_pending()
        assert len(pending) == 1
        assert pending[0].message.content == [
            {"type": "text", "text": "see this"},
            {"type": "image", "image_url": "data:image/png;base64,AAAA"},
        ]
        for item in pending:
            assert controller.enqueue_message(item.message, item.origin)

        gate.set()
        await _wait_for_terminal_run(kernel, first.run_id)
        assert len(client.requests) == 2
        assert any(
            message.content
            == [
                {"type": "text", "text": "see this"},
                {"type": "image", "image_url": "data:image/png;base64,AAAA"},
            ]
            for message in client.requests[-1].messages
        )
    finally:
        gate.set()
        kernel.close()


async def test_discard_run_messages_preserves_later_history_and_parent_chain(
    tmp_path: Path,
) -> None:
    """Removing one terminal run must preserve later turns and future context."""

    responses = iter(("base-ack", "HEARTBEAT_OK", "later-ack", "after-ack"))
    captured_requests: list[Any] = []

    class _CapturingSequenceClient:
        def generate(self, request: Any):  # noqa: ANN201
            captured_requests.append(request)
            return _async_stub_messages(next(responses))

    kernel = _build_kernel(tmp_path, _llm_client_override=_CapturingSequenceClient())
    try:
        session = await kernel.create_session(workspace_root=tmp_path)

        async def _submit(text: str):
            run = kernel.submit(
                session_id=session.session_id,
                parts=[{"type": "text", "text": text}],
                workspace_root=tmp_path,
            )
            return await _wait_for_terminal_run(kernel, run.run_id)

        await _submit("base")
        heartbeat = await _submit("heartbeat prompt")
        await _submit("later user message")

        assert await kernel.discard_run_messages("unknown-run") is False
        assert await kernel.discard_run_messages(heartbeat.run_id)
        assert await kernel.discard_run_messages(heartbeat.run_id) is False
        await _submit("after cleanup")

        final_context = "\n".join(
            _flatten_msg_text(message) for message in captured_requests[-1].messages
        )
        assert "base" in final_context
        assert "base-ack" in final_context
        assert "later user message" in final_context
        assert "later-ack" in final_context
        assert "after cleanup" in final_context
        assert "heartbeat prompt" not in final_context
        assert "HEARTBEAT_OK" not in final_context
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# bugfix-426-M4 决策5/3: a steer landing in the run's terminal window is consumed
# by the SAME run (no continuation new run_id) — #140's root carrier removed.
# ---------------------------------------------------------------------------


class _TerminalWindowSteerClient:
    """Drives the #140 terminal window deterministically.

    Round 1: block on the gate (run stays RUNNING so the test injects a steer),
    then yield a terminal reply with NO tool calls — the loop is now at its
    terminal decision with a pending steer already enqueued.
    Round 2 onward: yield a final terminal reply (the steer-driven round).
    """

    def __init__(self, gate) -> None:  # noqa: ANN001
        self._gate = gate
        self._round = 0
        self.requests: list[Any] = []

    def generate(self, request: Any):  # noqa: ANN001, ANN201
        self.requests.append(request)
        return self._generate()

    async def _generate(self):
        self._round += 1
        if self._round == 1:
            while not self._gate.is_set():
                await asyncio.sleep(0.01)
            yield LLMMessage(
                role="assistant",
                content="answer-to-first",
                finish_reason="stop",
                tool_calls=(),
            )
        else:
            yield LLMMessage(
                role="assistant",
                content="answer-to-steer",
                finish_reason="stop",
                tool_calls=(),
            )


async def test_terminal_window_steer_continues_same_run_no_continuation(
    tmp_path: Path,
) -> None:
    """决策5/3: a steer enqueued just before the run finishes is consumed by the
    SAME run (injected=True, run_id unchanged) and produces NO continuation run.

    This is the #140 regression at the kernel level: before, the steer was
    stranded → re-submitted as a continuation with a new run_id → the gateway relay
    (anchored to the old run_id) dropped every continuation event. Decision 5 keeps
    it on one run; decision 3's continuation narrows to abnormal terminations only,
    so normal completion never strands.
    """
    import threading

    gate = threading.Event()
    client = _TerminalWindowSteerClient(gate)
    kernel = _build_kernel(tmp_path, _llm_client_override=client)
    try:
        session = await kernel.create_session(workspace_root=tmp_path)
        first = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "do the thing"}],
            workspace_root=tmp_path,
        )
        await _wait_for_run_status(kernel, first.run_id, "running")

        runs_before = set(kernel._c.runs_registry._runs.keys())  # noqa: SLF001
        # Steer enqueues while round 1 is blocked → guaranteed pending at the
        # loop's terminal re-drain.
        steered = kernel.submit(
            session_id=session.session_id,
            parts=[{"type": "text", "text": "actually do X instead"}],
            workspace_root=tmp_path,
            steer=True,
        )
        assert steered.injected is True
        assert steered.run_id == first.run_id

        gate.set()
        record = await _wait_for_terminal_run(kernel, first.run_id)
        assert record.status == "completed"

        # No continuation run was created: the same run consumed the steer.
        runs_after = set(kernel._c.runs_registry._runs.keys())  # noqa: SLF001
        assert runs_after == runs_before, (
            "decision 5 must keep the steer on one run — no continuation new run_id"
        )
        # The same run did a SECOND round (terminal re-drain → continue), and the
        # steer entered that round's context — proving it was consumed by this run,
        # not stranded into a continuation.
        assert len(client.requests) == 2, (
            "the run must re-loop once on the terminal-window steer (same run)"
        )
        second_round_texts = [
            _flatten_msg_text(m)
            for m in client.requests[1].messages
            if getattr(m, "role", None) == "user"
        ]
        assert any("actually do X instead" in t for t in second_round_texts)
    finally:
        gate.set()
        kernel.close()
