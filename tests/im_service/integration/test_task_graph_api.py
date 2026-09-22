"""Protect task graph persistence and membership at the real HTTP/WS boundary."""

import pytest
from fastapi.testclient import TestClient

from IM.app import create_app
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.infra.repositories.nodes import NodeRepository
from .conftest import authorize, register_user, seed_user_under_owner


@pytest.fixture(params=["global", "single_thread"])
def task_stack(tmp_path, request):
    app = create_app(db_path=tmp_path / "tasks.db")
    with TestClient(app) as client:
        owner = register_user(client, username="owner")
        stranger = register_user(client, username="stranger")
        authorize(client, owner)
        db = app.state.connection
        NodeRepository(db).upsert_node(
            node_id="node", node_name="Node", owner_id=owner.owner_id
        )
        AgentProfileRepository(db).create_profile(
            agent_id="nano",
            owner_id=owner.owner_id,
            node_id="node",
            display_name="Nano",
            description="",
            skills=[],
            tool_allowlist=[],
            group_reply_policy="ALWAYS",
            default_model=None,
            workspace_root=None,
            work_mode=request.param,
        )
        agent_user = seed_user_under_owner(
            client, username="agent:nano", owner_id=owner.owner_id
        )
        chat = ConversationRepository(db).create_conversation(
            title="Project chat",
            participant_ids=[owner.id, agent_user],
            caller_owner_id=owner.owner_id,
        )
        with client.websocket_connect("/im/ws/gateway") as ws:
            ws.send_json(
                {
                    "type": "node.register",
                    "payload": {
                        "node_id": "node",
                        "agents": ["nano"],
                        "agent_work_modes": {"nano": request.param},
                        "capabilities": {},
                    },
                }
            )
            assert ws.receive_json()["type"] == "ack"
            yield client, ws, owner, stranger, chat, agent_user


def command(ws, action, **args):
    ws.send_json(
        {
            "type": "task_graph.command",
            "payload": {
                "node_id": "node",
                "agent_id": "nano",
                "request_id": "rpc",
                "action": action,
                "args": args,
            },
        }
    )
    response = ws.receive_json()
    assert response["type"] == "task_graph.result", response
    assert response["payload"]["request_id"] == "rpc"
    return response["payload"]


def test_agent_writes_browser_reads_same_graph_and_atomic_replay(task_stack):
    client, ws, owner, stranger, chat, agent_user = task_stack
    empty = client.get("/im/v1/task-graphs", params={"conversation_id": chat.id})
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "next_cursor": None, "total": 0}
    creation = dict(
        conversation_id=chat.id,
        title="Product",
        description="Discuss first",
        mode="dag",
        request_key="create",
    )
    created = command(ws, "create", **creation)
    assert created["ok"], created
    graph = created["result"]
    graph_id, root = graph["graph_id"], graph["root_node_id"]
    assert command(ws, "create", **creation)["result"] == graph
    assert client.get("/im/v1/task-graphs").json()["total"] == 1
    operations = [
        {
            "op": "add_task",
            "client_ref": "A",
            "container_id": root,
            "title": "Choose",
            "mode": "explore",
        },
        {"op": "add_task", "client_ref": "B", "container_id": root, "title": "Build"},
        {"op": "add_dependency", "from": "@A", "to": "@B"},
        {
            "op": "add_task",
            "client_ref": "X",
            "container_id": "@A",
            "title": "X",
            "status": "done",
            "result": "Too costly",
        },
        {
            "op": "add_task",
            "client_ref": "Y",
            "container_id": "@A",
            "title": "Y",
            "order": 1,
        },
        {
            "op": "add_task",
            "client_ref": "Z",
            "order": 2,
            "container_id": "@A",
            "title": "Z",
            "derived_from_id": "@X",
            "mode": "dag",
        },
        {
            "op": "add_task",
            "client_ref": "P",
            "container_id": "@Z",
            "title": "Prototype",
        },
        {
            "op": "select_candidate",
            "scope_id": "@A",
            "node_id": "@Z",
            "reason": "Promising",
        },
    ]
    mutation = dict(
        graph_id=graph_id,
        base_revision=1,
        request_key="plan",
        operations=operations,
        change_note="User approved",
    )
    result = command(ws, "apply", **mutation)
    assert result["ok"], result
    assert command(ws, "apply", **mutation)["result"] == result["result"]
    ids = result["result"]["client_refs"]
    full = client.get(f"/im/v1/task-graphs/{graph_id}", params={"view": "all"}).json()
    assert full["revision"] == 2 and len(full["nodes"]) == 7
    nodes = {n["id"]: n for n in full["nodes"]}
    assert nodes[ids["Z"]]["container_id"] == ids["A"]
    assert nodes[ids["Z"]]["derived_from_id"] == ids["X"]
    assert nodes[ids["A"]]["status"] == nodes[ids["B"]]["status"] == "todo"
    assert nodes[ids["A"]]["selected_candidate_id"] == ids["Z"]
    assert nodes[ids["A"]]["change_note"] == "User approved"
    scope = command(ws, "get", graph_id=graph_id, scope_id=ids["A"])["result"]
    assert [n["id"] for n in scope["children"]] == [ids["X"], ids["Y"], ids["Z"]]
    assert [n["id"] for n in scope["breadcrumbs"]] == [root, ids["A"]]
    invalid = command(
        ws,
        "apply",
        graph_id=graph_id,
        base_revision=2,
        request_key="bad",
        change_note="Bad batch",
        operations=[
            {
                "op": "update_task",
                "node_id": ids["B"],
                "patch": {"title": "Must roll back"},
            },
            {"op": "add_dependency", "from": ids["B"], "to": ids["A"]},
        ],
    )
    assert not invalid["ok"] and invalid["error"]["code"] == "invalid_graph"
    assert (
        client.get(f"/im/v1/task-graphs/{graph_id}", params={"view": "all"}).json()
        == full
    )
    conflict = command(ws, "apply", **{**mutation, "request_key": "old-revision"})
    assert conflict["error"]["code"] == "version_conflict"
    assert conflict["error"]["current_revision"] == 2
    # Work visibility does not grant the stranger access to the graph or its summaries.
    authorize(client, stranger)
    assert client.get("/im/v1/task-graphs").json()["items"] == []
    assert client.get(f"/im/v1/task-graphs/{graph_id}").status_code == 404
    authorize(client, owner)
    # A lost-ACK retry must recheck membership before returning the old success.
    db = client.app.state.connection
    db.execute(
        "DELETE FROM conversation_participants WHERE conversation_id=? AND user_id=?",
        (chat.id, agent_user),
    )
    db.commit()
    revoked = command(ws, "apply", **mutation)
    assert revoked["error"]["code"] == "not_found_or_forbidden"
    assert client.get(f"/im/v1/task-graphs/{graph_id}").status_code == 200


def test_write_conflict_is_atomic_across_connections_and_survives_reopen(task_stack):
    from concurrent.futures import ThreadPoolExecutor
    from IM.application.task_graphs import TaskGraphActor
    from IM.domain.task_graphs import TaskGraphError

    client, ws, owner, stranger, chat, agent_user = task_stack
    created = command(
        ws,
        "create",
        conversation_id=chat.id,
        title="Concurrent",
        mode="dag",
        request_key="concurrent",
    )["result"]
    service = client.app.state.task_graphs
    actor = TaskGraphActor("agent", "nano", "node")

    def update(title):
        try:
            return service.execute(
                actor,
                "apply",
                {
                    "graph_id": created["graph_id"],
                    "base_revision": 1,
                    "request_key": title,
                    "change_note": "Concurrent edit",
                    "operations": [
                        {
                            "op": "update_task",
                            "node_id": created["root_node_id"],
                            "patch": {"title": title},
                        }
                    ],
                },
            )
        except TaskGraphError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["First writer", "Second writer"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("version_conflict") == 1
    path = f"/im/v1/task-graphs/{created['graph_id']}"
    before = client.get(path, params={"view": "all"}).json()
    with TestClient(create_app(db_path=client.app.state.db_path)) as reopened:
        login = reopened.post(
            "/im/v1/auth/login",
            json={"username": owner.username, "password": "hunter2-strong"},
        )
        assert login.status_code == 200
        reopened.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        assert reopened.get(path, params={"view": "all"}).json() == before


def test_list_pagination_preserves_membership_and_request_keys_cannot_change_meaning(
    task_stack,
):
    client, ws, owner, stranger, chat, agent_user = task_stack
    for index in range(3):
        result = command(
            ws,
            "create",
            conversation_id=chat.id,
            title=f"Plan {index}",
            mode="explore",
            request_key=f"list-{index}",
        )
        assert result["ok"]
    first = client.get(
        "/im/v1/task-graphs", params={"query": "Plan", "limit": 2}
    ).json()
    assert first["total"] == 3 and len(first["items"]) == 2
    second = client.get(
        "/im/v1/task-graphs",
        params={"query": "Plan", "limit": 2, "cursor": first["next_cursor"]},
    ).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    assert len({item["graph_id"] for item in [*first["items"], *second["items"]]}) == 3
    assert (
        client.get(
            "/im/v1/task-graphs",
            params={"query": "Different", "cursor": first["next_cursor"]},
        ).status_code
        == 400
    )
    changed = command(
        ws,
        "create",
        conversation_id=chat.id,
        title="Wrong reuse",
        mode="explore",
        request_key="list-0",
    )
    assert changed["error"]["code"] == "request_key_reused"
    authorize(client, stranger)
    assert (
        client.get(
            "/im/v1/task-graphs", params={"conversation_id": chat.id}
        ).status_code
        == 404
    )
