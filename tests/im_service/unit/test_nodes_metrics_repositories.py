"""Unit tests for M99 node and usage repositories."""

from pathlib import Path

from IM.infra.db import connect, initialize_schema
from IM.infra.repositories import NodeRepository, UsageMetricsRepository


def test_node_repository_aggregates_degraded_and_offline_states(tmp_path: Path) -> None:
    """Collapse heartbeat status and disconnects into canonical board states."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    repo = NodeRepository(connection)

    registered = repo.record_gateway_registration(
        node_id="node-1",
        node_name="MacBook",
        version="1.2.3",
        agent_count=2,
    )
    assert registered.status == "online"
    assert registered.agent_count == 2

    degraded = repo.record_heartbeat(
        node_id="node-1",
        reported_status="healthy",
        agent_count=3,
        last_error="llm timeout",
        version="1.2.4",
    )
    assert degraded.status == "degraded"
    assert degraded.agent_count == 3
    assert degraded.version == "1.2.4"
    assert degraded.last_error == "llm timeout"

    offline = repo.mark_disconnected(node_id="node-1")
    assert offline is not None
    assert offline.status == "offline"


def test_usage_metrics_repository_groups_by_scope(tmp_path: Path) -> None:
    """Aggregate persisted usage samples by owner, conversation, and agent identity."""
    connection = connect(tmp_path / "im.db")
    initialize_schema(connection)
    repo = UsageMetricsRepository(connection)

    repo.record_usage(
        owner_id="owner-1",
        conversation_id="conv-1",
        agent_id=None,
        prompt_tokens=5,
        completion_tokens=0,
        turns=1,
    )
    repo.record_usage(
        owner_id="owner-1",
        conversation_id="conv-1",
        agent_id="agent-1",
        prompt_tokens=2,
        completion_tokens=7,
        turns=1,
    )

    rows = repo.list_usage_metrics(conversation_id="conv-1")
    assert len(rows) == 2
    by_scope = {item.scope: item for item in rows}
    assert by_scope["conversation"].total_tokens == 5
    assert by_scope["conversation"].turns == 1
    assert by_scope["agent"].agent_id == "agent-1"
    assert by_scope["agent"].total_tokens == 9
