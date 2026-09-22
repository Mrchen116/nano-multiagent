"""Protect account ownership and independent last-update chats per node."""

import pytest

from IM.application.task_graphs import TaskGraphActor
from IM.domain.task_graphs import TaskGraphError
from IM.infra.repositories.conversations import ConversationRepository
from .conftest import authorize
from .task_graph_support import command, task_stack as task_stack


def test_goals_belong_to_account_with_optional_source_and_no_agent_assignment(
    task_stack,
):
    client, ws, owner, stranger, chat, agent_user = task_stack
    created = command(
        ws, "create", title="Independent", mode="dag", request_key="no-chat"
    )
    assert created["ok"], created
    graph = created["result"]
    assert (
        command(ws, "get", graph_id=graph["graph_id"])["result"]["root"]["last_chat_id"]
        is None
    )
    graph_id = graph["graph_id"]
    assert command(ws, "list", agent_id="peer")["result"]["total"] == 1
    assert command(ws, "get", agent_id="peer", graph_id=graph_id)["ok"]
    updated = command(
        ws,
        "apply",
        agent_id="peer",
        graph_id=graph_id,
        base_revision=1,
        request_key="peer-edit",
        change_note="Shared plan",
        operations=[
            {"op": "update_task", "node_id": "n1", "patch": {"title": "Together"}}
        ],
    )
    assert updated["ok"], updated
    forged = command(
        ws,
        "create",
        title="Forged",
        mode="dag",
        request_key="forged",
        owner_id=stranger.owner_id,
    )
    assert forged["error"]["code"] == "invalid_arguments"
    sourced = command(
        ws,
        "create",
        conversation_id=chat.id,
        title="With source",
        mode="dag",
        request_key="source",
    )["result"]
    source_id = sourced["graph_id"]
    peer_read = command(ws, "get", agent_id="peer", graph_id=source_id)["result"]
    assert peer_read["root"]["last_chat_id"] is None
    assert peer_read["root"]["last_chat_title"] is None
    db = client.app.state.connection
    db.execute(
        "INSERT INTO conversation_participants (conversation_id,user_id) VALUES (?,?)",
        (chat.id, stranger.id),
    )
    db.commit()
    authorize(client, stranger)
    assert client.get("/im/v1/task-graphs").json()["total"] == 0
    assert client.get(f"/im/v1/task-graphs/{source_id}").status_code == 404
    authorize(client, owner)
    db.execute("DELETE FROM conversations WHERE id=?", (chat.id,))
    db.commit()
    remaining = client.get(f"/im/v1/task-graphs/{source_id}").json()
    assert remaining["root"]["last_chat_id"] is None
    assert remaining["title"] == "With source"
    assert command(ws, "get", agent_id="peer", graph_id=source_id)["ok"]
    # Replaying the original creation cannot resurrect the deleted chat reference.
    replay = command(
        ws,
        "create",
        conversation_id=chat.id,
        title="With source",
        mode="dag",
        request_key="source",
    )
    assert replay["ok"] and replay["result"]["graph_id"] == source_id
    # A profile transferred to another owner cannot replay its old creation receipt.
    db.execute(
        "UPDATE agent_profiles SET owner_id=? WHERE agent_id='nano'",
        (stranger.owner_id,),
    )
    db.execute("UPDATE nodes SET owner_id=? WHERE node_id='node'", (stranger.owner_id,))
    db.execute(
        "UPDATE users SET owner_id=? WHERE id=?", (stranger.owner_id, agent_user)
    )
    db.commit()
    # The old WebSocket has a different owner after transfer, so exercise the
    # service receipt check with the newly resolved Agent identity directly.
    with pytest.raises(TaskGraphError) as denied:
        client.app.state.task_graphs.execute(
            TaskGraphActor("agent", "nano", "node"),
            "create",
            dict(title="Independent", mode="dag", request_key="no-chat"),
        )
    assert denied.value.code == "not_found_or_forbidden"


def test_each_changed_node_records_its_last_chat_without_retries_moving_it(task_stack):
    client, ws, owner, stranger, chat, agent_user = task_stack
    other = ConversationRepository(client.app.state.connection).create_conversation(
        title="Another discussion",
        participant_ids=[owner.id, agent_user],
        caller_owner_id=owner.owner_id,
    )
    graph = command(
        ws,
        "create",
        conversation_id=chat.id,
        title="Per-node chats",
        mode="dag",
        request_key="per-node",
    )["result"]
    gid = graph["graph_id"]
    command(
        ws,
        "apply",
        graph_id=gid,
        conversation_id=chat.id,
        base_revision=1,
        request_key="children",
        change_note="Split",
        operations=[
            {
                "op": "add_task",
                "container_id": "n1",
                "client_ref": "a",
                "title": "First",
            },
            {
                "op": "add_task",
                "container_id": "n1",
                "client_ref": "b",
                "title": "Second",
            },
        ],
    )
    change = dict(
        graph_id=gid,
        conversation_id=other.id,
        base_revision=2,
        request_key="move-first",
        change_note="Next chat",
        operations=[
            {"op": "update_task", "node_id": "n2", "patch": {"status": "doing"}}
        ],
    )
    assert command(ws, "apply", **change)["ok"]
    assert command(ws, "apply", **{**change, "conversation_id": chat.id})["ok"]
    full = client.get(f"/im/v1/task-graphs/{gid}", params={"view": "all"}).json()
    assert [(n["id"], n["last_chat_id"]) for n in full["nodes"]] == [
        ("n1", chat.id),
        ("n2", other.id),
        ("n3", chat.id),
    ]
    assert full["nodes"][1]["last_chat_title"] == "Another discussion"
    assert command(
        ws,
        "apply",
        graph_id=gid,
        base_revision=3,
        request_key="without-chat",
        change_note="Unbound",
        operations=[
            {"op": "update_task", "node_id": "n3", "patch": {"status": "doing"}}
        ],
    )["ok"]
    full = client.get(f"/im/v1/task-graphs/{gid}", params={"view": "all"}).json()
    assert full["nodes"][2]["last_chat_id"] is None
    assert full["nodes"][1]["last_chat_id"] == other.id
