"""关键路径：含工具历史的 threshold 压缩在重启前后保持任务连续。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from ._im_client import IMClient, restart_gateway
from .test_agent_config_context_continuity_critical_path import (
    StubLLMStack,
    _wait_records,
    stub_llm_stack,
)

_SENTINEL = "COMPACTION-CONTINUITY-SENTINEL"


def _tool_pair_ids(request: dict) -> tuple[set[str], set[str]]:
    tool_uses: set[str] = set()
    tool_results: set[str] = set()
    for message in request.get("messages") or []:
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_uses.add(str(block.get("id") or ""))
            elif block.get("type") == "tool_result":
                tool_results.add(str(block.get("tool_use_id") or ""))
    return tool_uses, tool_results


def _session_entries(stack: StubLLMStack, agent_id: str) -> list[dict]:
    sessions_dir = (
        Path(stack.wt_dir)
        / ".gateway-workspace"
        / agent_id
        / ".nanoassistant"
        / "sessions"
    )
    matching = [
        path
        for path in sessions_dir.glob("*.jsonl")
        if _SENTINEL in path.read_text(encoding="utf-8")
    ]
    assert len(matching) == 1, (
        f"expected one isolated sentinel session, got {[str(path) for path in matching]}"
    )
    return [
        json.loads(line)
        for line in matching[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.e2e
@pytest.mark.parametrize(
    "stub_llm_stack",
    (
        {
            "script": "anthropic_sse_compaction_recording.py",
            "context_window": 60_000,
            "env": {"NANO_FIXTURE_SENTINEL": _SENTINEL},
        },
    ),
    indirect=True,
)
def test_tool_history_compacts_and_survives_gateway_restart(
    stub_llm_stack: StubLLMStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 IM 会话经工具、threshold compact 和 Gateway restart 后仍记得目标。"""

    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    agent_id = client.first_agent_id()
    client.update_agent_config(agent_id, tool_allowlist=["read"])
    workspace = Path(stub_llm_stack.wt_dir) / ".gateway-workspace" / agent_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "compaction-source.txt").write_text(
        f"original objective: {_SENTINEL}\n",
        encoding="utf-8",
    )
    conversation_id = client.create_direct_conversation(agent_id)
    record_path = Path(stub_llm_stack.record_path)

    ws = client.connect_ws()
    try:
        client.send_message(
            conversation_id,
            f"请记住目标 {_SENTINEL}，读取 compaction-source.txt 后继续这个任务。",
        )
        first = ws.wait_for_event(
            "message.completed",
            lambda frame: frame.conversation_id == conversation_id,
        )
        assert _SENTINEL in str(first.data.get("content") or "")

        client.send_message(conversation_id, "现在继续原任务，并原样给出目标标记。")
        second = ws.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation_id
                and _SENTINEL in str(frame.data.get("content") or "")
            ),
        )
        assert _SENTINEL in str(second.data.get("content") or "")
    finally:
        ws.close()

    records = _wait_records(record_path, 4)
    summary_records = [record for record in records if record.get("kind") == "summary"]
    assert len(summary_records) == 1
    summary_request = summary_records[0]["request"]
    call_ids, result_ids = _tool_pair_ids(summary_request)
    assert call_ids == result_ids == {"compaction-read-1"}
    assert _SENTINEL in json.dumps(summary_request, ensure_ascii=False)

    entries = _session_entries(stub_llm_stack, agent_id)
    boundaries = [entry for entry in entries if entry.get("type") == "compact_boundary"]
    assert len(boundaries) == 1
    summary_uuid = boundaries[0]["summary_uuid"]
    summaries = [
        entry
        for entry in entries
        if entry.get("type") == "turn" and entry.get("uuid") == summary_uuid
    ]
    assert len(summaries) == 1
    assert _SENTINEL in str(summaries[0].get("content") or "")

    monkeypatch.setenv(
        "PATH", f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"
    )
    replacement_started_after = restart_gateway(
        stub_llm_stack.wt_dir, stub_llm_stack.im_port
    )
    client.wait_for_node_reconnect(
        node_id=stub_llm_stack.node_id,
        replacement_started_after=replacement_started_after,
        timeout=40,
    )

    ws_after_restart = client.connect_ws()
    try:
        client.send_message(conversation_id, "重启后再次原样给出之前的目标标记。")
        restarted = ws_after_restart.wait_for_event(
            "message.completed",
            lambda frame: (
                frame.conversation_id == conversation_id
                and _SENTINEL in str(frame.data.get("content") or "")
            ),
        )
        assert _SENTINEL in str(restarted.data.get("content") or "")
    finally:
        ws_after_restart.close()
        client.close()

    final_records = _wait_records(record_path, len(records) + 1)
    post_summary_requests = [
        record["request"]
        for record in final_records
        if record.get("kind") == "post_summary"
    ]
    assert len(post_summary_requests) == 2
    assert all(
        _SENTINEL in json.dumps(request.get("messages") or [], ensure_ascii=False)
        for request in post_summary_requests
    )
