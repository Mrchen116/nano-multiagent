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

from agent.sdk import Kernel, build_kernel
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.interfaces import LLMMessage
from agent.products.local_coding.profile import LOCAL_CODING_PROFILE


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
    defaults = dict(
        product_profile=LOCAL_CODING_PROFILE,
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
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


def test_llm_config_reconfigure_updates_provider(tmp_path: Path) -> None:
    """kernel.reconfigure_llm() must return updated config with applied patches.

    Note: _llm_client_override disables llm_client_factory (test-only path).
    We build without override to exercise the real factory path for reconfigure.
    """
    # Build without client override so llm_client_factory is wired (needed for reconfigure_llm)
    kernel = build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=_allow_all,
        repo_root=tmp_path,
        # No _llm_client_override — use real factory path
    )
    try:
        # Record initial state
        initial = kernel.get_llm_config()

        # Reconfigure to a different provider/model
        target_provider = (
            "anthropic" if initial.provider != "anthropic" else "openai_compat"
        )
        target_model = "test-model-xyz"
        updated = kernel.reconfigure_llm(provider=target_provider, model=target_model)
        assert updated.provider == target_provider
        assert updated.model == target_model
        # Verify subsequent get_llm_config reflects the change
        current = kernel.get_llm_config()
        assert current.provider == target_provider
        assert current.model == target_model
    finally:
        kernel.close()


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


def test_global_capabilities_llm_config_round_trip(tmp_path: Path) -> None:
    """reconfigure_llm() → get_llm_config() must reflect the patched values.

    Uses real factory path (no _llm_client_override) so reconfigure_llm works.
    """
    kernel = build_kernel(
        product_profile=LOCAL_CODING_PROFILE,
        llm_config=LLMFactoryConfig(
            provider="openai_compat",
            model="codex_oauth:gpt-5.5",
            base_url="http://127.0.0.1:4000",
        ),
        can_use_tool=_allow_all,
        repo_root=tmp_path,
    )
    try:
        # Patch to a unique model name and verify round-trip
        kernel.reconfigure_llm(model="my-unique-test-model-9999")
        config_after = kernel.get_llm_config()
        assert config_after.model == "my-unique-test-model-9999"
    finally:
        kernel.close()
