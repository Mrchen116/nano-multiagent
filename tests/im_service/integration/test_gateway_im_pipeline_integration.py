"""Browserless IM ↔ Gateway end-to-end integration: fake kernel stub contract.

refactor-387 M3: _FakeKernelClient renamed to _FakeKernel (Kernel SDK interface).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from ._gateway_helpers import _FakeKernel


def test_fake_kernel_submit_seeds_terminal_run_snapshot() -> None:
    """The browserless fixture must mirror terminal run snapshots from the real Kernel SDK."""
    kernel = _FakeKernel()

    # create_session is async in the SDK (returns _FakeSession with .session_id).
    session = asyncio.run(kernel.create_session(
        title="Agent-A",
        workspace_root=Path("/tmp/agent-a"),
    ))
    record = kernel.submit(
        session_id=session.session_id,
        parts=[{"type": "text", "text": "hello gateway"}],
    )
    run_state = kernel.run_states[record.run_id]

    assert run_state["status"] == "completed"
    assert run_state["output_text"] == "gateway-reply:hello gateway"
