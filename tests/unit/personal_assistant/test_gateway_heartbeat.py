"""Unit tests for gateway heartbeat bootstrap failure reporting.

Note: The heartbeat-to-IM node.report bridge (_publish_heartbeat_product_reports /
_build_heartbeat_product_reports / HeartbeatRunner.build_product_reports) was removed in
fix/refactor-387-heartbeat-im-report because it constructed synthetic conversation_id and
message_id values that violated the IM events table FK constraints (messages table), causing
sqlite3.IntegrityError on every heartbeat tick. The bridge was confirmed to have never
successfully delivered a report since M138 introduced it — every invocation raised.

heartbeat/cron run *execution* (scheduler.tick → kernel session) is preserved and correct.
Displaying results in the IM conversation surface is a future feature requiring the heartbeat
run to be bound to a real IM conversation (and routed through the streaming pipeline),
tracked separately.

The test_build_heartbeat_product_reports_* and test_gateway_runtime_publishes_heartbeat_product_reports_to_im
tests that exercised the removed bridge used a mock IM (sent_frames list), which never hit
the real events table — this is exactly why the FK bug went undetected. Test removal serves
as documentation of that gap.
"""

from __future__ import annotations

import threading
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
                LLMModelPayload(
                    name="kimiCoding:K2.6",
                    extra_request_body={"thinking": {"type": "adaptive"}},
                ),
            ),
        ),
    ),
)


def test_gateway_runtime_reports_actionable_bootstrap_failure_to_im(
    tmp_path: Path,
) -> None:
    config = LocalConfig(
        node=NodeConfig(node_id="node-local"),
        agents=(AgentWorkspaceConfig(agent_id="agent-a", workspace_root=tmp_path),),
        channels=(),
        kernel=KernelConfig(),  # command empty: kernel now in-process (M4)
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

    with pytest.raises(
        GatewayStartupError, match="node-local did not appear in IM bootstrap"
    ):
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
