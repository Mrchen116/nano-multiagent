"""Company task transactions retain activity and independently protect sources."""

import pytest
from IM.application.task_graphs import TaskGraphActor, TaskGraphService
from IM.domain.task_graphs import TaskGraphError
from IM.infra.db import connect, initialize_schema
from IM.infra.task_graph_schema import migrate_task_graph_company


@pytest.fixture
def company_tasks(tmp_path):
    db_path = tmp_path / "company.db"
    db = connect(db_path)
    initialize_schema(db)
    migrate_task_graph_company(db)
    columns = {r[1] for r in db.execute("PRAGMA table_info(users)")}
    if "membership_status" not in columns:
        db.execute(
            "ALTER TABLE users ADD COLUMN membership_status TEXT DEFAULT 'active'"
        )
    for user in ("a", "b", "agent:nano"):
        db.execute(
            "INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES (?,?,?,?,?,'active')",
            (user, user, user, "a" if user.startswith("agent:") else user, "now"),
        )
    db.execute(
        "INSERT INTO nodes(node_id,node_name,owner_id,status) VALUES ('node','node','a','online')"
    )
    db.execute(
        "INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,tool_allowlist_json,features_json,created_at,updated_at) VALUES ('nano','a','node','Nano','[\"task_graph\"]','{}','now','now')"
    )
    for chat in ("A", "B"):
        db.execute(
            "INSERT INTO conversations(id,title,created_at) VALUES (?,?,'now')",
            (chat, "Private " + chat),
        )
        for user in ("a", "agent:nano"):
            db.execute(
                "INSERT INTO conversation_participants(conversation_id,user_id) VALUES (?,?)",
                (chat, user),
            )
    db.commit()
    service = TaskGraphService(db_path)
    agent = TaskGraphActor("agent", "nano", "node")
    yield db, service, agent
    db.close()


def test_company_activity_and_active_membership(company_tasks):
    db, service, agent = company_tasks
    graph = service.execute(
        agent,
        "create",
        dict(title="Goal", mode="dag", request_key="create", conversation_id="A"),
    )
    gid = graph["graph_id"]
    assert service.execute(TaskGraphActor("user", "b"), "list", {})["total"] == 1
    assert (
        service.execute(TaskGraphActor("user", "b"), "get", dict(graph_id=gid))["root"][
            "last_chat_id"
        ]
        is None
    )
    service.execute(
        agent,
        "apply",
        dict(
            graph_id=gid,
            base_revision=1,
            request_key="edit",
            change_note="",
            conversation_id="B",
            operations=[
                dict(op="update_task", node_id="n1", patch=dict(title="Updated"))
            ],
        ),
    )
    for chat in ("A", "B"):
        assert (
            service.execute(
                TaskGraphActor("user", "a"), "activity", dict(conversation_id=chat)
            )["items"][0]["node_id"]
            == "n1"
        )
    with pytest.raises(TaskGraphError):
        service.execute(
            TaskGraphActor("user", "b"), "activity", dict(conversation_id="A")
        )
    db.execute("DELETE FROM conversations WHERE id='A'")
    db.execute("UPDATE users SET membership_status='suspended' WHERE id='a'")
    db.commit()
    assert (
        service.execute(TaskGraphActor("user", "b"), "get", dict(graph_id=gid))["root"][
            "title"
        ]
        == "Updated"
    )
    with pytest.raises(TaskGraphError):
        service.execute(agent, "get", dict(graph_id=gid))


def test_deletion_requires_human_scope_and_preserves_receipts_and_ids(company_tasks):
    db, service, agent = company_tasks
    graph = service.execute(
        agent, "create", dict(title="Goal", mode="dag", request_key="create")
    )
    gid = graph["graph_id"]
    service.execute(
        agent,
        "apply",
        dict(
            graph_id=gid,
            base_revision=1,
            request_key="child",
            change_note="",
            operations=[
                dict(
                    op="add_task", container_id="n1", client_ref="child", title="Child"
                )
            ],
        ),
    )
    args = dict(graph_id=gid, node_id="n2", base_revision=2, request_key="delete")
    with pytest.raises(TaskGraphError, match="explicitly request"):
        service.execute(agent, "delete", args)
    db.execute(
        "INSERT INTO messages(id,conversation_id,sender_user_id,content,delivery_status,created_at) VALUES ('request','A','a','删除 Child','sent','now')"
    )
    db.commit()
    sourced = TaskGraphActor("agent", "nano", "node", "request")
    db.execute("UPDATE messages SET content='Do not delete Child' WHERE id='request'")
    db.commit()
    with pytest.raises(TaskGraphError, match="explicitly request"):
        service.execute(sourced, "delete", args)
    db.execute(
        "UPDATE messages SET content=? WHERE id='request'",
        ('<mention type="user" target_id="nano"/> 确认删除 Child',),
    )
    db.commit()
    removed = service.execute(sourced, "delete", args)
    assert removed["deleted_ids"] == ["n2"]
    assert service.execute(sourced, "delete", args) == removed
    added = service.execute(
        agent,
        "apply",
        dict(
            graph_id=gid,
            base_revision=3,
            request_key="another",
            change_note="",
            operations=[
                dict(
                    op="add_task", container_id="n1", client_ref="another", title="New"
                )
            ],
        ),
    )
    assert added["client_refs"]["another"] == "n3"
    db.execute("UPDATE messages SET content='删除 Goal' WHERE id='request'")
    db.commit()
    delete_graph = dict(graph_id=gid, base_revision=4, request_key="delete-graph")
    receipt = service.execute(sourced, "delete", delete_graph)
    assert receipt["deleted"]
    assert service.execute(sourced, "delete", delete_graph) == receipt
    with pytest.raises(TaskGraphError):
        service.execute(agent, "get", dict(graph_id=gid))


def test_task_capability_and_protected_provenance(company_tasks):
    db, service, agent = company_tasks
    db.execute("UPDATE conversations SET external_source='feishu' WHERE id='A'")
    db.execute(
        "INSERT INTO messages(id,conversation_id,sender_user_id,sender_source_id,content,delivery_status,created_at) VALUES ('external','A','a','ou_real_speaker','Save the plan','sent','now')"
    )
    db.commit()
    sourced = TaskGraphActor("agent", "nano", "node", "external")
    graph = service.execute(
        sourced,
        "create",
        dict(title="Company", mode="dag", request_key="external", conversation_id="A"),
    )
    gid = graph["graph_id"]
    service.execute(
        sourced,
        "apply",
        dict(
            graph_id=gid,
            base_revision=1,
            request_key="links",
            change_note="",
            conversation_id="A",
            operations=[
                dict(
                    op="update_task",
                    node_id="n1",
                    patch=dict(
                        links=[
                            "/im/v1/conversations/A/attachments/secret",
                            "https://example.com/public",
                        ]
                    ),
                )
            ],
        ),
    )
    own = service.execute(TaskGraphActor("user", "a"), "get", dict(graph_id=gid))[
        "root"
    ]
    assert own["provenance"]["initiator_id"] == "ou_real_speaker"
    outside = service.execute(TaskGraphActor("user", "b"), "get", dict(graph_id=gid))[
        "root"
    ]
    assert outside["links"] == ["https://example.com/public"]
    assert outside["provenance"]["source_message_id"] is None
    assert outside["provenance"]["initiator_id"] is None
    assert outside["provenance"]["agent_id"] == "nano"
    for update in (
        "features_json='{\"task_graph\":false}'",
        "features_json='{}',tool_allowlist_json='[]'",
    ):
        db.execute("UPDATE agent_profiles SET " + update)
        db.commit()
        with pytest.raises(TaskGraphError):
            service.execute(agent, "get", dict(graph_id=gid))
    # Model-supplied confirmation is not accepted as business input.
    with pytest.raises(TaskGraphError) as invalid:
        service.execute(
            agent,
            "delete",
            dict(graph_id=gid, base_revision=2, request_key="forged", confirmed=True),
        )
    assert invalid.value.code == "invalid_arguments"
