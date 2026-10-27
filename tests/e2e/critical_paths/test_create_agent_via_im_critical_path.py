"""IM creation and cold session recovery, observed at the provider boundary."""

from __future__ import annotations

import secrets
from pathlib import Path

import httpx
import pytest

from ._im_client import IMClient, restart_gateway
from ._recording import (
    StubLLMStack,
    _wait_records,
    _message_blob,
    _system_blob,
    stub_im_user,
    stub_llm_stack,
)


def _history_messages(request: dict) -> list[dict]:
    """Normalize only provider cache hints and equivalent text encodings."""

    def without_cache(value):
        if isinstance(value, dict):
            return {
                key: without_cache(item)
                for key, item in value.items()
                if key != "cache_control"
            }
        if isinstance(value, list):
            return [without_cache(item) for item in value]
        return value

    messages = without_cache(request["messages"])
    for message in messages:
        if isinstance(message["content"], str):
            message["content"] = [{"type": "text", "text": message["content"]}]
    return messages


@pytest.mark.e2e
def test_agent_created_via_im_preserves_context_across_restart(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """Creation/preview, real replies and cold recovery preserve the wire history."""
    im_user, e2e_stack = stub_im_user, stub_llm_stack
    node_id = im_user.wait_for_online_node(timeout=40)

    new_agent_id = "e2eNew" + secrets.token_hex(3)
    # The creation page reads capabilities and previews before any Agent workspace exists.
    with httpx.Client(
        base_url=im_user.im_url,
        headers={"Authorization": f"Bearer {im_user.token}"},
        timeout=40.0,
    ) as http:
        catalog = http.get(f"/im/v1/nodes/{node_id}/capabilities")
        catalog.raise_for_status()
        assert catalog.json()["tools"]
        preview_root = Path(
            catalog.json()["default_workspace_template"].replace(
                "{agent_id}", new_agent_id
            )
        )
        assert not preview_root.exists()
        preview = http.post(
            f"/im/v1/nodes/{node_id}/prompt-preview",
            json={
                "agent_id_hint": new_agent_id,
                "custom_prompt": "PREVIEW_WORKSPACE_SENTINEL",
                "features": dict.fromkeys(
                    [
                        "heartbeat",
                        "cron_scheduling",
                        "task_graph",
                        "intelligent_ui",
                        "memory_curation",
                        "skill_creation",
                    ],
                    False,
                ),
            },
        )
        preview.raise_for_status()
        assert "PREVIEW_WORKSPACE_SENTINEL" in preview.json()["prompt"]
        assert preview_root.is_dir()
        assert new_agent_id not in {
            agent["agent_id"] for agent in im_user.list_agents()
        }

    created = im_user.create_agent(
        node_id,
        new_agent_id,
        display_name=f"E2E New {new_agent_id}",
        custom_prompt="CREATED_AGENT_INSTRUCTIONS",
        default_model=e2e_stack.llm_model,
    )
    workspace_root = Path(created["workspace_root"]).resolve()
    assert workspace_root.is_relative_to(
        (Path(e2e_stack.wt_dir) / ".gateway-workspace").resolve()
    )
    assert workspace_root.is_dir()

    # 落地上线信号:新 agent 出现在 IM agent 列表。
    im_user.wait_for_agent_listed(new_agent_id, timeout=40)

    conversation_id = im_user.create_direct_conversation(new_agent_id)
    sentinel = "NEW" + secrets.token_hex(4).upper()

    record = Path(e2e_stack.record_path)
    im_user.send_message(conversation_id, sentinel)
    im_user.wait_for_agent_reply_with(conversation_id, "ACK-1")
    second = "SECOND" + secrets.token_hex(4).upper()
    im_user.send_message(conversation_id, second)
    im_user.wait_for_agent_reply_with(conversation_id, "ACK-2")
    before = _wait_records(record, 2)[-1]
    restarted_at = restart_gateway(e2e_stack.wt_dir, e2e_stack.im_port)
    im_user.wait_for_node_reconnect(
        node_id=node_id,
        replacement_started_after=restarted_at,
        timeout=40,
    )
    third = "AFTERRESTART" + secrets.token_hex(4).upper()
    im_user.send_message(conversation_id, third)
    im_user.wait_for_agent_reply_with(conversation_id, "ACK-3")
    after = _wait_records(record, 3)[-1]
    # Compare actual historical message structure, not whether a model recalls a token.
    assert _history_messages(after)[: len(before["messages"])] == _history_messages(
        before
    )
    blob = _message_blob(after)
    assert blob.index(sentinel) < blob.index(second) < blob.index(third)
    assert "ACK-1" in blob and "ACK-2" in blob
    assert "CREATED_AGENT_INSTRUCTIONS" in _system_blob(after)
    assert after.get("tools") == before.get("tools")
