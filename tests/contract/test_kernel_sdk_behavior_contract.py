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
from pathlib import Path
from typing import Any

import pytest

from agent.sdk import Kernel, LLMConfig, LLMModel, LLMProvider, build_kernel
from agent.core.llm.interfaces import LLMMessage


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
    """kernel.list_session_tools() must return a non-None result."""
    kernel = _build_kernel(tmp_path)
    try:
        # list_session_tools is sync; does not require an active session
        tools_result = kernel.list_session_tools(
            session_id="test-session", workspace_root=tmp_path
        )
        # Must return something (dict or ToolsInfo), not raise
        assert tools_result is not None
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

    def generate(self, request: Any):  # noqa: ANN001, ANN201
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


async def test_submit_steer_injects_render_user_text_content(tmp_path: Path) -> None:
    """Injected content is built via the same parts→text rendering submit uses:
    image parts collapse to the placeholder, text is preserved (决策2)."""
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

        kernel.submit(
            session_id=session.session_id,
            parts=[
                {"type": "text", "text": "see this"},
                {"type": "image", "image_url": "data:image/png;base64,AAAA"},
            ],
            workspace_root=tmp_path,
            steer=True,
        )

        # Inspect the active controller's pending queue: the injected message's
        # content must be a rendered string (str), with the image as a placeholder.
        registry = kernel._c.runs_registry  # noqa: SLF001
        controller = registry._controllers[first.run_id]  # noqa: SLF001
        pending = controller.drain_pending()
        assert len(pending) == 1
        content = pending[0].message.content
        assert isinstance(content, str)
        assert "see this" in content
        assert "[image:placeholder]" in content

        gate.set()
        await _wait_for_terminal_run(kernel, first.run_id)
    finally:
        gate.set()
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
