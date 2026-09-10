"""Keep conversation snapshots stable across IM outages and recovery."""

import json

import pytest

from personal_assistant.gateway.global_inbox import GlobalInboxService, GlobalInboxStore
from personal_assistant.tools.conversations import ConversationsTool


class History:
    online = False

    async def __call__(self, agent, action, args):
        if not self.online:
            raise ConnectionError("offline")
        if action == "info":
            return {"members": []}
        offset = int(args.get("cursor", "remote-0").split("-")[-1])
        if action == "list":
            return {
                "conversations": [
                    {
                        "target": f"c_remote0{offset}",
                        "name": "Remote",
                        "latest_message_at": "2026-09-09T00:00:00Z",
                    }
                ],
                "has_more": offset == 0,
                "next_cursor": "remote-1" if offset == 0 else None,
            }
        return {
            "target": args["target"],
            "messages": [
                {
                    "message_id": f"remote-{offset}",
                    "content": [{"type": "text", "text": "remote"}],
                }
            ],
            "has_more": offset == 0,
            "next_cursor": "remote-1" if offset == 0 else None,
            "history_scope": "im_history",
        }


def service(tmp_path):
    store = GlobalInboxStore(tmp_path / "inbox.db")
    store.save_global_session("a", "main", str(tmp_path))
    remote = History()
    inbox = GlobalInboxService(store, conversation_reader=remote)
    for i in range(3):
        inbox.receive(
            agent_id="a",
            target=f"c_local00{i}",
            conversation_id=f"c_local00{i}",
            ingress_key=str(i),
            source_message_id=f"m{i}",
            sender={},
            content=[
                {"type": "text", "text": "part one"},
                {"type": "text", "text": "part two" * 4000},
            ],
            name=f"Local {i}",
        )
    return inbox, remote


async def query(inbox, action="list", **args):
    return await inbox.execute(
        "conversations",
        agent_id="a",
        session_id="main",
        tool_call_id="query",
        args={"action": action, "limit": 1, **args},
    )


@pytest.mark.asyncio
async def test_offline_list_cursor_stays_on_its_snapshot_after_reconnect(tmp_path):
    inbox, remote = service(tmp_path)
    first = await query(inbox)
    remote.online = True
    seen = [first["conversations"][0]["target"]]
    page = first
    while page["next_cursor"]:
        page = await query(inbox, cursor=page["next_cursor"])
        seen.extend(row["target"] for row in page["conversations"])
    assert len(seen) == len(set(seen)) == 3
    assert all(target.startswith("c_local") for target in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["list", "read"])
async def test_remote_cursor_can_retry_after_outage_without_restarting_page(
    tmp_path, action
):
    inbox, remote = service(tmp_path)
    remote.online = True
    args = {"target": "c_local000"} if action == "read" else {}
    first = await query(inbox, action, **args)
    remote.online = False
    with pytest.raises(ConnectionError, match="offline"):
        await query(inbox, action, **args, cursor=first["next_cursor"])
    remote.online = True
    second = await query(inbox, action, **args, cursor=first["next_cursor"])
    key, identity = (
        ("messages", "message_id") if action == "read" else ("conversations", "target")
    )
    assert second[key][0][identity] != first[key][0][identity]
    assert not second["next_cursor"]


@pytest.mark.asyncio
async def test_received_history_cursor_survives_recovery_and_keeps_scope_visible(
    tmp_path,
):
    inbox, remote = service(tmp_path)
    first = await query(inbox, "read", target="c_local000")
    assert first["next_cursor"]
    remote.online = True
    second = await query(
        inbox, "read", target="c_local000", cursor=first["next_cursor"]
    )
    assert second["messages"][0]["content"] != first["messages"][0]["content"]
    for page in (first, second):
        result = json.loads(ConversationsTool().serialize_result(page))
        assert result["history_scope"] == "received_only"
        assert result["permission_confirmed_at"]
