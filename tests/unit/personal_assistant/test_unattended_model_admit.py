"""Heartbeat/cron admit the first candidate explicitly through submit_message."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.kernel_client import InProcessKernelClient
from personal_assistant.gateway.model_fallback import ModelStickyStore, StickyModelOverride


def test_submit_message_uses_explicit_candidate_not_saved_primary(tmp_path: Path) -> None:
    captured: list[str | None] = []

    def _submit(**kwargs: object) -> object:
        captured.append(kwargs.get("model"))  # type: ignore[arg-type]
        return MagicMock(run_id="run-1")

    kernel = MagicMock()
    kernel.submit.side_effect = _submit
    catalog = LiveAgentCatalog(
        (
            AgentWorkspaceConfig(
                agent_id="agent-a",
                workspace_root=tmp_path / "a",
                default_model="primary",
                model_fallbacks=("backup",),
            ),
        )
    )
    sticky = ModelStickyStore()
    sticky.set("sess-1", "agent-a", StickyModelOverride("backup", noticed=True))
    client = InProcessKernelClient(
        kernel,
        agent_catalog=catalog,
        product_default_model="prod",
        sticky_store=sticky,
    )

    admitted = client.admit_model(agent_id="agent-a", session_id="sess-1")
    client.submit_message(
        session_id="sess-1",
        texts=["tick"],
        workspace_root=str(tmp_path / "a"),
        origin="heartbeat",
        agent_id="agent-a",
        model=admitted,
    )

    assert admitted == "backup"
    assert captured == ["backup"]
