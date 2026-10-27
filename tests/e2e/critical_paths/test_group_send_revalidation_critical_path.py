"""Delayed model responses must reread group messages before dispatching stale drafts."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from ._recording import StubLLMStack, _load_records, stub_im_user, stub_llm_stack


def _results(request: dict) -> dict[str, dict]:
    return {
        block["tool_use_id"]: json.loads(block["content"])
        for message in request["messages"]
        if isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    }


@pytest.mark.parametrize(
    "stub_llm_stack",
    [{"script": "anthropic_sse_send_revalidation_recording.py"}],
    indirect=True,
)
def test_delayed_group_sends_reread_new_messages_before_counting(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """Four stale 1s become 1/2/3/4; D also revalidates a subsequently stale 2."""
    client = stub_im_user
    node = client.wait_for_online_node()
    record_path = Path(stub_llm_stack.record_path)
    with (
        httpx.Client(
            base_url=client.im_url,
            headers={"Authorization": f"Bearer {client.token}"},
            timeout=20,
        ) as http,
        httpx.Client(
            base_url=f"http://127.0.0.1:{stub_llm_stack.stub_port}", timeout=5
        ) as control,
    ):
        for role in "ABCD":
            response = http.post(
                f"/im/v1/nodes/{node}/agents",
                json={
                    "agent_id": f"counter-{role.lower()}",
                    "owner_id": client.owner_id,
                    "display_name": f"Counter {role}",
                    "work_mode": "global",
                    "group_reply_policy": "ALWAYS",
                    "default_model": stub_llm_stack.llm_model,
                    "tool_allowlist": ["inbox", "conversations", "send_message"],
                    "skills": [],
                    "features": dict.fromkeys(
                        [
                            "memory_curation",
                            "skill_creation",
                            "task_graph",
                            "intelligent_ui",
                            "cron_scheduling",
                            "heartbeat",
                        ],
                        False,
                    ),
                    "custom_prompt": f"COUNTING_AGENT {role}",
                },
            )
            assert response.is_success, response.text
            client.wait_for_agent_listed(f"counter-{role.lower()}")
        chat = client.create_group_conversation(
            [f"counter-{role.lower()}" for role in "ABCD"]
        )
        initial = client.send_message(chat, "COUNTING_START")

        def pending(keys: set[str]) -> None:
            poll_until(
                lambda: set(control.get("/").json()),
                lambda seen: keys <= seen,
                timeout=25,
                interval=0.1,
                desc=f"model responses waiting: {keys}",
            )

        def release(key: str) -> None:
            control.post(f"/release/{key}").raise_for_status()

        def messages() -> list[dict]:
            return [
                m
                for m in client.list_messages(chat)
                if (m.get("sender") or {}).get("id", "").startswith("counter-")
            ]

        def delivered(number: int) -> list[dict]:
            return poll_until(
                messages,
                lambda rows: len(rows) >= number,
                timeout=25,
                interval=0.1,
                desc=f"public count {number}",
            )

        def requests(role: str) -> list[dict]:
            return [
                row["request"]
                for row in _load_records(record_path)
                if row["role"] == role and not row["guardian"]
            ]

        def snapshots(role: str) -> list[dict]:
            return [_results(request) for request in requests(role)]

        pending({f"{role}:0" for role in "ABCD"})
        assert messages() == []
        for role in "ABCD":
            assert [m["id"] for m in snapshots(role)[-1]["read-0"]["messages"]] == [
                initial
            ]
        release("A:0")
        first = delivered(1)[0]
        assert first["content"] == "1"
        release("D:0")
        pending({"D:1"})
        delayed = snapshots("D")[-1]
        assert delayed["draft-0"]["status"] == "held_for_revalidation"
        assert [m["id"] for m in delayed["read-1"]["messages"]] == [first["id"]]
        release("B:0")
        delivered(2)
        release("C:0")
        delivered(3)
        release("D:1")
        final = delivered(4)
        assert len({m["id"] for m in final}) == 4
        assert [m["content"] for m in final] == ["1", "2", "3", "4"]
        assert [(m["sender"]["id"]) for m in final] == [
            f"counter-{role.lower()}" for role in "ABCD"
        ]
        for role, rounds in [("A", 0), ("B", 1), ("C", 1), ("D", 2)]:
            complete = poll_until(
                lambda: snapshots(role),
                lambda rows: any(
                    row.get(f"draft-{rounds}", {}).get("status") == "sent"
                    for row in rows
                ),
                timeout=15,
                interval=0.1,
                desc=f"{role} confirmed actual send",
            )[-1]
            for index in range(rounds):
                assert complete[f"draft-{index}"]["status"] == "held_for_revalidation"
            drafts = [
                block["input"]["text"]
                for message in requests(role)[-1]["messages"]
                if isinstance(message["content"], list)
                for block in message["content"]
                if block.get("type") == "tool_use" and block["name"] == "send_message"
            ]
            assert (
                drafts
                == {"A": ["1"], "B": ["1", "2"], "C": ["1", "3"], "D": ["1", "2", "4"]}[
                    role
                ]
            )
            received = {
                m["id"]: m
                for index in range(rounds + 1)
                for m in complete[f"read-{index}"]["messages"]
            }
            for prior in final[: "ABCD".index(role)]:
                assert prior["id"] in received
                assert received[prior["id"]]["content"] == [
                    {"type": "text", "text": prior["content"]}
                ]
        assert len(messages()) == 4
