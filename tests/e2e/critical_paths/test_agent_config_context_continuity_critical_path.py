"""Agent configuration and fork history through the real provider HTTP boundary."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
import yaml

from ._im_client import IMClient
from ._recording import (
    StubLLMStack,
    _message_blob,
    _system_blob,
    _tool_names,
    _wait_gateway_custom_prompt,
    _wait_records,
    stub_im_user,
    stub_llm_stack,
)

_LEGACY_PROMPT = "BUGFIX-507 LEGACY VISIBLE ROLE"
_UPDATED_PROMPT = "BUGFIX-507 UPDATED VISIBLE ROLE"


@pytest.mark.e2e
def test_agent_config_update_keeps_chat_context_with_stub_llm(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """Custom Instructions 的 preview/新回复同源且既有聊天连续。"""
    agent_id = stub_im_user.first_agent_id()
    stub_im_user.update_agent_config(agent_id, custom_prompt=_LEGACY_PROMPT)
    _wait_gateway_custom_prompt(
        Path(stub_llm_stack.wt_dir) / ".gateway-config.yaml", _LEGACY_PROMPT
    )
    initial_config = stub_im_user.get_agent_config(agent_id)
    assert initial_config["custom_prompt"] == _LEGACY_PROMPT
    assert "system_prompt" not in initial_config
    initial_preview = stub_im_user.preview_agent_prompt(
        agent_id,
        custom_prompt=initial_config["custom_prompt"],
        features=initial_config.get("features"),
        tool_ids=initial_config.get("tool_allowlist"),
        skill_ids=initial_config.get("skills"),
    )
    assert _LEGACY_PROMPT in initial_preview
    # 起点清空工具,确保后续 PATCH 真的改变 effective runtime。
    stub_im_user.update_agent_config(agent_id, tool_allowlist=[])
    conversation_id = stub_im_user.create_direct_conversation(agent_id)

    first = "CTXA" + secrets.token_hex(4).upper()
    second = "CTXB" + secrets.token_hex(4).upper()
    record = Path(stub_llm_stack.record_path)

    ws = stub_im_user.connect_ws()
    try:
        stub_im_user.send_message(
            conversation_id,
            f"请记住这个标记:{first}。先简短确认即可。",
        )
        ws.wait_for_event("message.completed")
        first_records = _wait_records(record, 1)
        assert _LEGACY_PROMPT in _system_blob(first_records[-1])

        stub_im_user.update_agent_config(
            agent_id,
            tool_allowlist=["read"],
            custom_prompt=_UPDATED_PROMPT,
        )
        updated_preview = stub_im_user.preview_agent_prompt(
            agent_id,
            custom_prompt=_UPDATED_PROMPT,
            features=initial_config.get("features"),
            tool_ids=["read"],
            skill_ids=initial_config.get("skills"),
        )
        assert _UPDATED_PROMPT in updated_preview
        assert _LEGACY_PROMPT not in updated_preview

        stub_im_user.send_message(
            conversation_id,
            f"继续刚才的对话。新标记是:{second}。",
        )
        ws.wait_for_event("message.completed")
        records = _wait_records(record, 2)
    finally:
        ws.close()

    last = records[-1]
    blob = _message_blob(last)
    system = _system_blob(last)
    assert first in blob, (
        "post-config-update LLM request lost earlier chat context; "
        f"missing {first!r} in last request messages. blob={blob!r}"
    )
    assert second in blob, (
        f"last LLM request missing the new user turn {second!r}; blob={blob!r}"
    )
    assert _UPDATED_PROMPT in system
    assert _LEGACY_PROMPT not in system
    # 运行配置确实换了:最后一次请求应带上新增的 read 工具。
    assert "read" in _tool_names(last), (
        f"expected read tool after config update; tools={_tool_names(last)!r}"
    )
    saved_agents = yaml.safe_load(
        (Path(stub_llm_stack.wt_dir) / ".gateway-config.yaml").read_text(
            encoding="utf-8"
        )
    )["agents"]
    saved_agent = next(agent for agent in saved_agents if agent["agent_id"] == agent_id)
    assert saved_agent["custom_prompt"] == _UPDATED_PROMPT
    assert "system_prompt" not in saved_agent


@pytest.mark.e2e
def test_fork_after_config_update_preserves_historical_runtime(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """A native fork restores the configuration at its historical reply point."""

    agent_id = stub_im_user.first_agent_id()
    old_prompt = "BUGFIX-547 OLD CONFIG"
    new_prompt = "BUGFIX-547 CURRENT CONFIG"
    source_sentinel = "FORKSRC" + secrets.token_hex(4).upper()
    branch_sentinel = "FORKBRANCH" + secrets.token_hex(4).upper()
    later_sentinel = "AFTERFORK" + secrets.token_hex(4).upper()
    source_followup = "SOURCEONLY" + secrets.token_hex(4).upper()
    record = Path(stub_llm_stack.record_path)

    stub_im_user.update_agent_config(
        agent_id,
        custom_prompt=old_prompt,
        tool_allowlist=[],
    )
    conversation_id = stub_im_user.create_direct_conversation(agent_id)
    ws = stub_im_user.connect_ws()
    try:
        stub_im_user.send_message(
            conversation_id,
            f"请记住这个标记:{source_sentinel}。",
        )
        ws.wait_for_event("message.completed")
        _wait_records(record, 1)
        source_reply = stub_im_user.agent_messages(conversation_id, agent_id)[-1]

        stub_im_user.update_agent_config(
            agent_id,
            custom_prompt=new_prompt,
            tool_allowlist=["read"],
        )
        _wait_gateway_custom_prompt(
            Path(stub_llm_stack.wt_dir) / ".gateway-config.yaml", new_prompt
        )
        stub_im_user.send_message(conversation_id, later_sentinel)
        stub_im_user.wait_for_agent_reply_with(conversation_id, "ACK-2")
        source_before = stub_im_user.list_messages(conversation_id)
        branch_id = stub_im_user.fork_conversation(
            conversation_id,
            source_reply["id"],
        )

        stub_im_user.send_message(
            branch_id,
            f"继续分支，新标记是:{branch_sentinel}。",
        )
        ws.wait_for_event("message.completed")
        records = _wait_records(record, 3)
        branch_request = records[-1]
        branch_history = stub_im_user.list_messages(branch_id)
        assert source_sentinel in str(branch_history)
        assert later_sentinel not in str(branch_history)
        assert stub_im_user.list_messages(conversation_id) == source_before
        stub_im_user.send_message(conversation_id, source_followup)
        stub_im_user.wait_for_agent_reply_with(conversation_id, "ACK-4")
        source_request = _wait_records(record, 4)[-1]
        source_blob = _message_blob(source_request)
        assert source_sentinel in source_blob and later_sentinel in source_blob
        assert source_followup in source_blob and branch_sentinel not in source_blob
        assert new_prompt in _system_blob(source_request)
    finally:
        ws.close()

    last = branch_request
    blob = _message_blob(last)
    system = _system_blob(last)
    assert later_sentinel not in blob
    assert source_sentinel in blob
    assert branch_sentinel in blob
    assert old_prompt in system
    assert new_prompt not in system
    assert "read" not in _tool_names(last)
