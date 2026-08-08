"""关键路径: Gateway 把高输入、低缓存命中的单次模型调用记为可关联 warning。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._im_client import IMClient
from ._im_polling import poll_until
from .test_agent_config_context_continuity_critical_path import (
    StubLLMStack,
    stub_llm_stack,
)


def _latest_cache_alert(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        if "low prompt cache hit rate" in line:
            return line
    return None


@pytest.mark.e2e
@pytest.mark.parametrize(
    "stub_llm_stack",
    (
        {
            "message_start_usage": {
                "input_tokens": 30_001,
                "cache_read_input_tokens": 0,
            },
            "message_delta_usage": {"output_tokens": 1},
        },
    ),
    indirect=True,
)
def test_gateway_logs_low_prompt_cache_hit_with_session_jsonl(
    stub_llm_stack: StubLLMStack,
) -> None:
    """真实 Gateway 日志能以 agent_id + session_id 定位此次昂贵缓存未命中。"""
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    agent_id = client.first_agent_id()
    conversation_id = client.create_direct_conversation(agent_id)
    prompt_sentinel = "CACHE-ALERT-PROMPT-MUST-NOT-LEAK"

    ws = client.connect_ws()
    try:
        client.send_message(conversation_id, prompt_sentinel)
        ws.wait_for_event("message.completed")
    finally:
        ws.close()

    try:
        replies = client.agent_messages(conversation_id, agent_id)
        assert any(reply.get("content") == "ACK-1" for reply in replies)
    finally:
        client.close()

    warning = poll_until(
        lambda: _latest_cache_alert(Path(stub_llm_stack.wt_dir) / ".gateway.log"),
        lambda line: line is not None,
        timeout=30.0,
        interval=0.2,
        desc="low prompt cache hit warning in gateway log",
    )
    assert warning is not None
    assert f"model={stub_llm_stack.llm_model!r}" in warning
    assert f"agent_id={agent_id!r}" in warning
    assert "input_tokens=30001" in warning
    assert "cache_read_tokens=0" in warning
    assert "cache_hit_rate_percent=0.0" in warning
    assert prompt_sentinel not in warning

    matched = re.search(r"session_id='([^']+)'", warning)
    assert matched is not None, f"warning has no session_id: {warning}"
    session_jsonl = (
        Path(stub_llm_stack.wt_dir)
        / ".gateway-workspace"
        / agent_id
        / ".nanoassistant"
        / "sessions"
        / f"{matched.group(1)}.jsonl"
    )
    assert session_jsonl.is_file(), (
        "warning agent_id + session_id did not locate the persisted session JSONL: "
        f"{session_jsonl}"
    )
