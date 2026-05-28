"""Unit tests for gateway heartbeat product reports and bootstrap failure reporting."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    HeartbeatConfig,
    KernelConfig,
    LocalConfig,
    NodeConfig,
)
from personal_assistant.main import (
    GatewayRuntime,
    GatewayStartupError,
)

from agent.core.llm.config import LLMConfigPayload, LLMModelPayload, LLMProviderPayload
from ._main_helpers import (
    _FakeHeartbeatRunner,
    _FakeIMManager,
    _FakeProcessManager,
)

_DEFAULT_TEST_LLM = LLMConfigPayload(
    default_model="kimiCoding:K2.6",
    providers=(
        LLMProviderPayload(
            name="anthropic",
            base_url="http://127.0.0.1:4000",
            models=(
                LLMModelPayload(name="kimiCoding:K2.6", extra_request_body={"thinking": {"type": "adaptive"}}),
            ),
        ),
    ),
)


def test_build_heartbeat_product_reports_maps_runs_to_main_agent_im_payloads() -> None:
    from personal_assistant.scheduler.heartbeat_scheduler import HeartbeatRunRecord, HeartbeatTickSummary
    from personal_assistant.main import _build_heartbeat_product_reports

    payloads = _build_heartbeat_product_reports(
        HeartbeatTickSummary(
            triggered_runs=(
                HeartbeatRunRecord(
                    agent_id="agent-a",
                    due_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
                    run_id="heartbeat-run-1",
                    session_id="session-heartbeat-1",
                ),
            ),
            skipped_agents=(),
        )
    )

    assert payloads == [
        {
            "run_id": "heartbeat-run-1",
            "status": "completed",
            "agent_id": "agent-a",
            "session_key": "agent-a::heartbeat",
            "conversation_id": "heartbeat:agent-a",
            "message_id": "heartbeat-run-1",
            "summary": "Heartbeat complete for main agent agent-a at 2026-03-13T09:00:00+00:00.",
            "guidance": "Open your main agent thread in Web IM to review the latest heartbeat result.",
        }
    ]


def test_gateway_runtime_publishes_heartbeat_product_reports_to_im(tmp_path: Path) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),),
        channels=(),
        kernel=KernelConfig(command="python -m agent.platform.http_api.app"),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )
    events: list[str] = []
    manager = _FakeIMManager(events)
    heartbeat_runner = _FakeHeartbeatRunner(
        events,
        report_payloads=[
            {
                "run_id": "heartbeat-run-1",
                "status": "completed",
                "agent_id": "agent-a",
                "summary": "Heartbeat complete: synced 3 tasks back to your main agent.",
                "conversation_id": "conv-main-agent",
                "message_id": "msg-heartbeat-1",
                "session_key": "agent-a::heartbeat",
            }
        ],
    )
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        heartbeat_runner=heartbeat_runner,
        im_connection_manager=manager,
    )

    thread = threading.Thread(target=runtime.run_forever)
    thread.start()
    assert runtime.wait_until_ready(timeout=1.0) is True
    runtime.request_shutdown()
    thread.join(timeout=2.0)

    assert ("node.report", {
        "run_id": "heartbeat-run-1",
        "status": "completed",
        "agent_id": "agent-a",
        "summary": "Heartbeat complete: synced 3 tasks back to your main agent.",
        "conversation_id": "conv-main-agent",
        "message_id": "msg-heartbeat-1",
        "session_key": "agent-a::heartbeat",
    }) in manager.sent_frames


def test_gateway_runtime_reports_actionable_bootstrap_failure_to_im(tmp_path: Path) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),),
        channels=(),
        kernel=KernelConfig(command="python -m agent.platform.http_api.app"),
        heartbeat=HeartbeatConfig(),
        im_service=None,
        llm=_DEFAULT_TEST_LLM,
        source_path=tmp_path / "node-config.yaml",
    )
    events: list[str] = []
    manager = _FakeIMManager(events)
    runtime = GatewayRuntime(
        config,
        _FakeProcessManager(events),
        heartbeat_runner=_FakeHeartbeatRunner(events),
        im_connection_manager=manager,
        post_im_connect=lambda: (_ for _ in ()).throw(
            GatewayStartupError(
                summary="node-local did not appear in IM bootstrap",
                next_step="Verify /im/v1/nodes on the configured IM API and rerun gateway.",
            )
        ),
    )

    import pytest
    with pytest.raises(GatewayStartupError, match="node-local did not appear in IM bootstrap"):
        runtime.run_forever()

    assert manager.sent_frames == [
        (
            "node.heartbeat",
            {
                "node_id": "node-local",
                "status": "degraded",
                "agent_count": 1,
                "last_error": (
                    "node-local did not appear in IM bootstrap Next: Verify /im/v1/nodes on the configured IM API "
                    "and rerun gateway."
                ),
            },
        )
    ]
