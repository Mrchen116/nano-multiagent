"""Unit tests for messages.py group relay fan-out: per-agent enqueue + push."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.db import connect, initialize_schema
from IM.repositories import AgentProfileRepository, ConversationRepository, UserRepository


def _setup_group_conversation(tmp_path: Path) -> tuple[TestClient, str, str, MagicMock]:
    """Prepare app + DB with group conversation containing 2 agent participants.

    Returns:
        (app, db_path, conversation_id, auth_header, mock_gateway)

    Notes:
        alice is registered via API so her owner_id matches the JWT token used
        by the messages route's owner-scoped filter (R4 of feat-340). Agent users
        and profiles are seeded under alice's owner_id after registration.
    """
    db_path = tmp_path / "im.db"
    conn = connect(db_path)
    initialize_schema(conn)
    profiles = AgentProfileRepository(conn)
    conn.close()

    mock_gateway = MagicMock()
    mock_gateway.record_relay_failure = MagicMock()

    app = create_app(db_path=db_path)

    with TestClient(app) as client:
        # Register alice via API to get a JWT token in the correct tenant.
        reg = client.post(
            "/im/v1/auth/register",
            json={"username": "alice", "password": "pw12345678", "display_name": "Alice"},
        )
        assert reg.status_code in (200, 201), f"register failed: {reg.text}"
        token = reg.json()["access_token"]
        alice_id = reg.json()["user"]["id"]
        owner_id = reg.json()["user"]["owner_id"]
        auth = {"Authorization": f"Bearer {token}"}

        # Seed agent users and profiles under alice's owner via the live DB connection.
        conn2 = client.app.state.connection
        users_repo = UserRepository(conn2)
        conversations_repo = ConversationRepository(conn2)
        profiles_repo = AgentProfileRepository(conn2)

        agent_a_user = users_repo.create_user(username="agent:agent-a", display_name="Agent A")
        agent_b_user = users_repo.create_user(username="agent:agent-b", display_name="Agent B")
        # Place agent users in alice's tenant so the route can scope them.
        conn2.execute(
            "UPDATE users SET owner_id = ? WHERE id IN (?, ?)",
            (owner_id, agent_a_user.id, agent_b_user.id),
        )
        conn2.commit()

        for aid, aname in [("agent-a", "Agent A"), ("agent-b", "Agent B")]:
            profiles_repo.upsert_profile(
                agent_id=aid,
                owner_id=owner_id,
                display_name=aname,
                description=f"profile {aid}",
                system_prompt=f"You are {aid}.",
                skills=[],
                tool_allowlist=[],
                group_reply_policy="manual",
                default_model=None,
                workspace_root=None,
            )
        # Assign both agents to the same node so resolve_target_node_id returns a node.
        conn2.execute(
            "UPDATE agent_profiles SET node_id = 'node-1' WHERE agent_id IN ('agent-a', 'agent-b')",
        )
        conn2.commit()

        conversation = conversations_repo.create_conversation(
            title="group",
            participant_ids=[alice_id, agent_a_user.id, agent_b_user.id],
        )
        # Place conversation in alice's tenant.
        conn2.execute(
            "UPDATE conversations SET owner_id = ? WHERE id = ?",
            (owner_id, conversation.id),
        )
        conn2.commit()
        conv_id = conversation.id

    return app, db_path, conv_id, alice_id, auth, mock_gateway


def test_group_message_pushes_relay_to_each_agent(tmp_path: Path) -> None:
    """群聊消息路由对每个 participant agent 各调一次 push_relay_message。"""
    app, db_path, conv_id, alice_id, auth, mock_gateway = _setup_group_conversation(tmp_path)

    push_calls: list[dict] = []

    async def _fake_push(*, relay_task_id: str, target_node_id: str, payload: dict) -> bool:
        push_calls.append({"relay_task_id": relay_task_id, "agent_id": payload.get("agent_id")})
        return True

    mock_gateway.push_relay_message = _fake_push

    with TestClient(app) as client:
        # Replace gateway_handler in running app state after lifespan startup
        client.app.state.gateway_handler = mock_gateway
        resp = client.post(
            f"/im/v1/conversations/{conv_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello group"},
            headers=auth,
        )

    assert resp.status_code in (200, 201), f"unexpected status {resp.status_code}: {resp.text}"
    assert len(push_calls) == 2, f"expected 2 push calls, got {push_calls}"
    pushed_agent_ids = {c["agent_id"] for c in push_calls}
    assert pushed_agent_ids == {"agent-a", "agent-b"}


def test_group_message_partial_push_failure_continues(tmp_path: Path) -> None:
    """一个 agent 节点离线不阻断其他 agent 的 relay；所有 agent 均被尝试。"""
    app, db_path, conv_id, alice_id, auth, mock_gateway = _setup_group_conversation(tmp_path)

    push_calls: list[dict] = []

    async def _fake_push(*, relay_task_id: str, target_node_id: str, payload: dict) -> bool:
        agent_id = payload.get("agent_id", "")
        # agent-a offline, agent-b online
        result = agent_id != "agent-a"
        push_calls.append({"agent_id": agent_id, "result": result})
        return result

    mock_gateway.push_relay_message = _fake_push

    with TestClient(app) as client:
        client.app.state.gateway_handler = mock_gateway
        resp = client.post(
            f"/im/v1/conversations/{conv_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello group"},
            headers=auth,
        )

    # Both agents must have been attempted (no early exit on first failure)
    assert len(push_calls) == 2, f"expected 2 push calls, got {push_calls}"
    results = {c["agent_id"]: c["result"] for c in push_calls}
    assert results.get("agent-a") is False
    assert results.get("agent-b") is True
    # Failure must be recorded for the offline agent
    assert mock_gateway.record_relay_failure.called
    # Route succeeds because at least one relay was delivered
    assert resp.status_code in (200, 201), f"unexpected status {resp.status_code}: {resp.text}"


def test_group_message_all_push_failure_returns_503(tmp_path: Path) -> None:
    """群聊中所有 agent 均离线时返回 503。"""
    app, db_path, conv_id, alice_id, auth, mock_gateway = _setup_group_conversation(tmp_path)

    async def _fake_push(*, relay_task_id: str, target_node_id: str, payload: dict) -> bool:
        return False

    mock_gateway.push_relay_message = _fake_push

    with TestClient(app) as client:
        client.app.state.gateway_handler = mock_gateway
        resp = client.post(
            f"/im/v1/conversations/{conv_id}/messages",
            json={"sender_user_id": alice_id, "content": "hello group"},
            headers=auth,
        )

    assert resp.status_code == 503, (
        f"expected 503 when all agents offline, got {resp.status_code}: {resp.text}"
    )
