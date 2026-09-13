"""Cross-account contact discovery, conversation membership, and personal state."""

from .conftest import authorize, make_app_client, register_user
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.users import UserRepository
from IM.infra.repositories.nodes import NodeRepository


def _agent(client, owner, agent_id, *, stale=False):
    connection = client.app.state.connection
    user = UserRepository(connection).create_user(
        username=f"agent:{agent_id}", display_name=agent_id
    )
    AgentProfileRepository(connection).upsert_profile(
        agent_id=agent_id,
        owner_id=owner.owner_id,
        node_id=f"node-{agent_id}",
        display_name=agent_id,
        description="private",
        skills=[],
        tool_allowlist=[],
        group_reply_policy="manual",
        default_model=None,
        workspace_root="/private/workspace",
    )
    if stale:
        connection.execute(
            "UPDATE agent_profiles SET is_stale = 1 WHERE agent_id = ?", (agent_id,)
        )
        connection.commit()
    return user


def test_public_contacts_exclude_shadow_and_configuration_and_page_stably(tmp_path):
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        authorize(client, alice)
        bob = register_user(client, username="bob")
        agent = _agent(client, bob, "bob-agent")
        _agent(client, alice, "stale-agent", stale=True)
        users = UserRepository(client.app.state.connection)
        users.create_user(username="shadow-person", display_name="Shadow")
        for i in range(51):
            users.create_user(
                username=f"person-{i}", display_name=f"Person {i}", password_hash="hash"
            )
        response = client.get("/im/v1/contacts")
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) == 50
        second = client.get(
            "/im/v1/contacts", params={"cursor": page["next_cursor"]}
        ).json()
        items = page["items"] + second["items"]
        assert len(items) == 54
        assert len({item["user_id"] for item in items}) == 54
        assert [item["user_id"] for item in items] == sorted(
            item["user_id"] for item in items
        )
        assert second["next_cursor"] is None
        NodeRepository(client.app.state.connection).upsert_node(
            node_id="node-bob-agent", node_name="Private node", status="online"
        )
        public_agent = client.get(f"/im/v1/contacts/{agent.id}").json()
        assert public_agent["status"] == "offline"
        assert set(public_agent) == {
            "user_id",
            "kind",
            "display_name",
            "agent_id",
            "owner_id",
            "owner_display_name",
            "node_name",
            "status",
            "work_mode",
        }
        assert public_agent["owner_id"] == bob.owner_id
        found = client.get(
            "/im/v1/contacts", params={"q": "bob-agent", "kind": "agent"}
        ).json()
        assert found["items"] == [public_agent]
        assert (
            client.get("/im/v1/contacts", params={"kind": "system"}).status_code == 400
        )


def test_people_share_group_but_keep_personal_preferences_and_membership(tmp_path):
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        bob = register_user(client, username="bob")
        carol = register_user(client, username="carol")
        authorize(client, alice)
        created = client.post(
            "/im/v1/conversations",
            json={
                "type": "group",
                "title": "Team",
                "participants": [{"type": "user", "id": bob.id}],
            },
        )
        assert created.status_code == 201, created.text
        chat = created.json()
        assert chat["type"] == "group"
        assert set(chat["participant_ids"]) == {alice.id, bob.id}
        assert chat["creator_id"] == alice.id
        authorize(client, bob)
        assert client.get("/im/v1/conversations").json()["items"][0]["id"] == chat["id"]
        updated = client.patch(
            f"/im/v1/conversations/{chat['id']}",
            json={"title": "Shared title", "is_pinned": True, "is_muted": True},
        )
        assert updated.status_code == 200
        assert (
            client.delete(
                f"/im/v1/conversations/{chat['id']}/participants/{alice.id}"
            ).status_code
            == 403
        )
        assert client.delete(f"/im/v1/conversations/{chat['id']}").status_code == 403
        added = client.post(
            f"/im/v1/conversations/{chat['id']}/participants",
            json={"participants": [{"type": "user", "id": carol.id}]},
        )
        assert added.status_code == 200
        authorize(client, alice)
        own = client.get(f"/im/v1/conversations/{chat['id']}").json()
        assert own["title"] == "Shared title"
        assert (own["is_pinned"], own["is_muted"]) == (False, False)
        assert (
            client.delete(
                f"/im/v1/conversations/{chat['id']}/participants/{bob.id}"
            ).status_code
            == 204
        )
        authorize(client, bob)
        assert client.get(f"/im/v1/conversations/{chat['id']}").status_code == 404
        assert client.get("/im/v1/sync").json()["items"] == []
        assert (
            client.patch(
                f"/im/v1/conversations/{chat['id']}", json={"title": "no"}
            ).status_code
            == 404
        )
        authorize(client, alice)
        assert client.delete(f"/im/v1/conversations/{chat['id']}").status_code == 204
        authorize(client, carol)
        assert client.get("/im/v1/conversations").json()["items"] == []


def test_other_agent_can_be_contacted_but_only_manager_adds_it_to_group(tmp_path):
    with make_app_client(tmp_path) as client:
        alice = register_user(client, username="alice")
        bob = register_user(client, username="bob")
        agent = _agent(client, bob, "agent-b")
        authorize(client, alice)
        payload = {
            "type": "direct",
            "title": "Agent",
            "participants": [{"type": "agent", "id": "agent-b"}],
        }
        direct = client.post("/im/v1/conversations", json=payload)
        assert direct.status_code == 201, direct.text
        assert (
            client.post("/im/v1/conversations", json=payload).json()["id"]
            == direct.json()["id"]
        )
        authorize(client, bob)
        assert (
            client.get(f"/im/v1/conversations/{direct.json()['id']}").status_code == 404
        )
        authorize(client, alice)
        assert (
            client.post(
                "/im/v1/conversations", json={**payload, "type": "group"}
            ).status_code
            == 403
        )
        group = client.post(
            "/im/v1/conversations",
            json={"type": "group", "title": "Group", "participant_ids": [bob.id]},
        ).json()
        assert (
            client.post(
                f"/im/v1/conversations/{group['id']}/participants",
                json={"participants": payload["participants"]},
            ).status_code
            == 403
        )
        authorize(client, bob)
        result = client.post(
            f"/im/v1/conversations/{group['id']}/participants",
            json={"participants": payload["participants"]},
        )
        assert result.status_code == 200
        assert agent.id in result.json()["participant_ids"]
