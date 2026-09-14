"""Durable member decisions stay bound to the original Agent execution."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from IM.infra.db import connect
from IM.infra.repositories.messages import MessageRepository
from tests.im_service.unit.test_repositories_user_conversation import (
    _build_repositories,
)


def _pending(tmp_path):
    users, conversations, messages, profiles, _, _ = _build_repositories(tmp_path)
    alice = users.create_user(username="a", display_name="A", password_hash="hash")
    bob = users.create_user(username="b", display_name="B", password_hash="hash")
    agent = users.create_user(username="agent:worker", display_name="Worker")
    profiles.upsert_profile(
        agent_id="worker",
        owner_id=alice.id,
        node_id="node",
        display_name="Worker",
        description="",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root=None,
    )
    chat = conversations.create_conversation(
        title="Team", participant_ids=[alice.id, bob.id, agent.id]
    )
    message = messages.create_message(
        conversation_id=chat.id,
        sender_user_id=agent.id,
        sender_type="agent",
        content="waiting",
        auto_complete_delivery=False,
    )
    request = {
        "request_id": "ask",
        "conversation_id": chat.id,
        "message_id": message.id,
        "agent_id": "worker",
        "node_id": "node",
        "run_id": "run",
        "status": "pending",
        "options": [{"id": "allow_once"}, {"id": "allow_always"}, {"id": "deny"}],
    }
    messages.append_permission_request(message_id=message.id, permission_data=request)
    return messages, conversations, chat, message, alice, bob, request


def test_first_member_decision_survives_retransmission_reopen_and_resolution(tmp_path):
    messages, _, chat, message, alice, bob, request = _pending(tmp_path)
    with pytest.raises(ValueError, match="not an option"):
        messages.claim_permission_decision(
            message_id=message.id,
            conversation_id=chat.id,
            request_id="ask",
            decision="invented",
            decided_by=bob.id,
        )
    claimed = messages.claim_permission_decision(
        message_id=message.id,
        conversation_id=chat.id,
        request_id="ask",
        decision="allow_always",
        decided_by=bob.id,
    )
    assert (claimed["status"], claimed["decided_by"]) == ("submitted", bob.id)
    messages.append_permission_request(message_id=message.id, permission_data=request)
    reopened = MessageRepository(connect(tmp_path / "im.db"))
    assert reopened.list_submitted_permissions(node_id="other") == []
    assert reopened.list_submitted_permissions(node_id="node") == [claimed]
    assert (
        reopened.claim_permission_decision(
            message_id=message.id,
            conversation_id=chat.id,
            request_id="ask",
            decision="deny",
            decided_by=alice.id,
        )
        == claimed
    )
    reopened.update_permission_resolution(
        message_id=message.id, request_id="ask", decision="allow_always"
    )
    messages.append_permission_request(message_id=message.id, permission_data=request)
    final = messages.get_message(message_id=message.id).permission_requests[0]
    assert final["status"] == "resolved"
    assert final["decided_by"] == bob.id
    assert final["node_id"] == "node" and final["run_id"] == "run"
    assert reopened.list_submitted_permissions(node_id="node") == []


def test_competing_database_connections_keep_one_decision(tmp_path):
    _, _, chat, message, alice, bob, _ = _pending(tmp_path)

    def submit(user, decision):
        connection = connect(tmp_path / "im.db")
        try:
            return MessageRepository(connection).claim_permission_decision(
                message_id=message.id,
                conversation_id=chat.id,
                request_id="ask",
                decision=decision,
                decided_by=user.id,
            )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(submit, alice, "deny")
        b = pool.submit(submit, bob, "allow_once")
        assert a.result() == b.result()
