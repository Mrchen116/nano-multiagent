"""Public compact command preserves a tool-backed objective across node restart."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._im_client import IMClient, restart_gateway
from .test_agent_config_context_continuity_critical_path import (
    StubLLMStack,
    _wait_records,
    stub_llm_stack,
)

_SENTINEL = "COMPACTION-CONTINUITY-SENTINEL"


@pytest.mark.e2e
@pytest.mark.parametrize(
    "stub_llm_stack",
    (
        {
            "script": "anthropic_sse_compaction_recording.py",
            "context_window": 100_000,
            "env": {"NANO_FIXTURE_SENTINEL": _SENTINEL},
        },
    ),
    indirect=True,
)
def test_tool_history_compacts_and_survives_gateway_restart(
    stub_llm_stack: StubLLMStack,
) -> None:
    """Real HTTP and node processes compact, then resume with the actual summary."""
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    agent_id = client.first_agent_id()
    client.update_agent_config(agent_id, tool_allowlist=["read"])
    workspace = Path(stub_llm_stack.wt_dir) / ".gateway-workspace" / agent_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "compaction-source.txt").write_text(
        f"original objective: {_SENTINEL}\n", encoding="utf-8"
    )
    conversation_id = client.create_direct_conversation(agent_id)
    try:
        client.send_message(
            conversation_id,
            f"请记住目标 {_SENTINEL}，读取 compaction-source.txt 后继续这个任务。",
        )
        client.wait_for_agent_reply_with(conversation_id, "TOOL-COMPLETE", timeout=90)
        client.send_message(conversation_id, "/compact 保留原始目标和已读取的文件")
        client.wait_for_agent_reply_with(conversation_id, "已压缩", timeout=90)
        records = _wait_records(Path(stub_llm_stack.record_path), 3)
        summary = next(
            record["request"] for record in records if record["kind"] == "summary"
        )
        assert _SENTINEL in json.dumps(summary, ensure_ascii=False)
        assert "compaction-read-1" in json.dumps(summary)
        assert "保留原始目标和已读取的文件" in json.dumps(summary, ensure_ascii=False)
        client.send_message(conversation_id, "继续原任务，给出标记。")
        client.wait_for_agent_reply_with(
            conversation_id, f"CONTINUED {_SENTINEL}", timeout=90
        )
        restarted_at = restart_gateway(stub_llm_stack.wt_dir, stub_llm_stack.im_port)
        client.wait_for_node_reconnect(
            node_id=stub_llm_stack.node_id,
            replacement_started_after=restarted_at,
            timeout=40,
        )
        client.send_message(conversation_id, "重启后给出原目标标记。")
        client.wait_for_agent_reply_with(
            conversation_id, f"RESTARTED {_SENTINEL}", timeout=90
        )
        records = _wait_records(Path(stub_llm_stack.record_path), 5)
        resumed = [
            record["request"] for record in records if record["kind"] == "post_summary"
        ]
        assert len(resumed) == 2
        assert all(_SENTINEL in json.dumps(request["messages"]) for request in resumed)
    finally:
        client.close()
