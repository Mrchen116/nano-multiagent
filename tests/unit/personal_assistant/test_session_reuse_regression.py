"""Regression tests for refactor-387 session-reuse bug.

Root cause: Kernel.get_session returned {"session_id", "status", "metadata": {...}}
without a top-level "workspace_root" key.  _binding_matches_workspace_root read
metadata.get("workspace_root"), which was always None → checked False → every
inbound message created a new kernel session → conversation history never
accumulated.

Fix contract:
  1. Kernel.get_session must expose "workspace_root" as a top-level key in the
     returned dict (not inside metadata).
  2. _binding_matches_workspace_root must compare against that top-level key,
     not metadata["workspace_root"].
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Contract test 1: Kernel.get_session exposes top-level workspace_root
# ---------------------------------------------------------------------------


def test_kernel_get_session_exposes_workspace_root_as_top_level_key(
    tmp_path: Path,
) -> None:
    """SDK Kernel.get_session must include 'workspace_root' at the top level.

    This is the source-of-truth contract: _binding_matches_workspace_root relies
    on this key to decide whether an existing binding is valid.  Without it, the
    check always fails and every message creates a fresh kernel session.
    """
    from agent.sdk.kernel import build_kernel
    from agent.products.personal_assistant.profile import PERSONAL_ASSISTANT_PROFILE

    async def _allow(_tool: str, _input: Any, _ctx: Any) -> Any:
        from agent.platform.permissions.broker import PermissionDecision

        return PermissionDecision(behavior="allow")

    kernel = build_kernel(
        product_profile=PERSONAL_ASSISTANT_PROFILE,
        llm_config=MagicMock(),
        can_use_tool=_allow,
        repo_root=tmp_path,
        _llm_client_override=MagicMock(),
    )
    try:
        workspace_root = tmp_path / "my-workspace"
        workspace_root.mkdir()
        session = asyncio.run(kernel.create_session(workspace_root=workspace_root))
        session_id = session.session_id

        payload = kernel.get_session(session_id, workspace_root=workspace_root)

        # Top-level "workspace_root" must be present and match
        assert "workspace_root" in payload, (
            "Kernel.get_session must expose workspace_root as a top-level key; "
            "got keys: " + str(list(payload.keys()))
        )
        assert str(payload["workspace_root"]) == str(workspace_root), (
            f"workspace_root mismatch: {payload['workspace_root']!r} != {workspace_root!r}"
        )
        # metadata should NOT be the vehicle for workspace_root — it belongs at top level
        metadata = payload.get("metadata", {})
        assert "workspace_root" not in metadata, (
            "workspace_root must be a top-level key, not inside metadata — "
            "placing it in metadata creates two sources of truth that can drift"
        )
    finally:
        kernel.close()


# ---------------------------------------------------------------------------
# Contract test 2: _binding_matches_workspace_root reads top-level key
# ---------------------------------------------------------------------------


def test_binding_matches_workspace_root_reads_top_level_key(tmp_path: Path) -> None:
    """_binding_matches_workspace_root must succeed when get_session returns workspace_root
    at the top level (not in metadata).

    If the implementation reads metadata.get("workspace_root"), this test fails
    because the response has no metadata["workspace_root"] — reproducing the regression.
    """
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.channel_registry import ChannelRegistry
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline
    from personal_assistant.gateway.outbound_router import OutboundRouter
    from personal_assistant.gateway.run_queue import SessionRunQueue
    from personal_assistant.gateway.session_keys import SessionBindingStore

    workspace = tmp_path / "ws"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=workspace, title="A"
    )

    expected_workspace_root = str(workspace)

    # get_session response with workspace_root at TOP LEVEL only (not in metadata)
    class _StubKernel:
        def get_session(
            self, session_id: str, *, workspace_root: Any = None
        ) -> dict[str, Any]:
            return {
                "session_id": session_id,
                "status": "active",
                "workspace_root": expected_workspace_root,  # top-level key
                "metadata": {"agent_id": "agent-a"},  # no workspace_root here
            }

    class _FakeChan:
        name = "web"

    kernel_stub = _StubKernel()
    registry = ChannelRegistry((_FakeChan(),))  # type: ignore[arg-type]
    pipeline = InboundPipeline(
        kernel=kernel_stub,  # type: ignore[arg-type]
        agents=(agent,),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    result = pipeline._binding_matches_workspace_root(  # noqa: SLF001
        "sess-existing", expected_workspace_root=expected_workspace_root
    )

    assert result is True, (
        "_binding_matches_workspace_root returned False even though get_session "
        "provided workspace_root at the top level — implementation must read the "
        "top-level key, not metadata['workspace_root']"
    )


def test_session_reuse_across_consecutive_messages(tmp_path: Path) -> None:
    """Same session_key sends two consecutive messages → same kernel_session_id is reused.

    Uses a Kernel stub whose get_session returns workspace_root at the top level
    (the correct contract after the fix).  Before the fix _binding_matches_workspace_root
    read metadata["workspace_root"] which was always absent → returned False → every
    message created a fresh session → this assertion would fail with create_count == 2.
    """
    from personal_assistant.channels.base import InboundMessage
    from personal_assistant.config.local_store import AgentWorkspaceConfig
    from personal_assistant.gateway.channel_registry import ChannelRegistry
    from personal_assistant.gateway.inbound_pipeline import InboundPipeline
    from personal_assistant.gateway.outbound_router import OutboundRouter
    from personal_assistant.gateway.run_queue import SessionRunQueue
    from personal_assistant.gateway.session_keys import SessionBindingStore

    from tests.unit.personal_assistant._pipeline_helpers import (
        _FakeChannel,
        _FakeKernel,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=workspace, title="A"
    )

    kernel = _FakeKernel()
    chan = _FakeChannel("web")
    registry = ChannelRegistry((chan,))
    pipeline = InboundPipeline(
        kernel=kernel,
        agents=(agent,),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )

    msg = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="u1",
        external_chat_id="chat-1",
        is_group=False,
    )
    r1 = asyncio.run(pipeline.handle_inbound(msg))
    r2 = asyncio.run(pipeline.handle_inbound(msg))

    assert r1.kernel_session_id == r2.kernel_session_id, (
        f"Session reuse failed: first={r1.kernel_session_id}, second={r2.kernel_session_id}. "
        "Two consecutive messages on the same chat must reuse the same kernel session."
    )
    assert len(kernel.create_session_calls) == 1, (
        f"create_session called {len(kernel.create_session_calls)} times; expected exactly 1. "
        "Each chat must have a single persistent session."
    )
