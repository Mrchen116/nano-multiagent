"""Browserless IM ↔ Gateway end-to-end integration: fake kernel client contract."""

from __future__ import annotations

from ._gateway_helpers import _FakeKernelClient


def test_fake_kernel_client_submit_message_seeds_terminal_run_snapshot() -> None:
    """The browserless fixture must mirror terminal run snapshots from the real kernel API."""
    kernel_client = _FakeKernelClient()

    created = kernel_client.create_session(
        workspace_root="/tmp/agent-a",
        product_id="personal_assistant",
        title="Agent-A",
    )
    submitted = kernel_client.submit_message(session_id=created["session_id"], texts=["hello gateway"])
    run_state = kernel_client.get_run(run_id=submitted["run_id"])

    assert run_state["status"] == "completed"
    assert run_state["output_text"] == "gateway-reply:hello gateway"
