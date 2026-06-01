"""Session metadata sourcing tests: local config fields vs. relay message.metadata."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


def test_build_session_metadata_reads_system_prompt_from_local_agent_config(
    tmp_path: Path,
) -> None:
    """system_prompt in session metadata must come from the local AgentWorkspaceConfig,
    not from the relay-pushed message.metadata."""
    agent_dir = tmp_path / "agent-x"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="agent-x",
            workspace_root=agent_dir,
            title="Agent X",
            system_prompt="Local system prompt from config.",
        ),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-x",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "conversation_id": "conv-1",
            "system_prompt": "Stale relay prompt that should be ignored.",
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert created_metadata["system_prompt"] == "Local system prompt from config."


def test_build_session_metadata_reads_skills_and_tool_allowlist_from_local_agent_config(
    tmp_path: Path,
) -> None:
    """skills and tool_allowlist in session metadata must come from local config."""
    agent_dir = tmp_path / "agent-y"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="agent-y",
            workspace_root=agent_dir,
            title="Agent Y",
            skills=("web_search", "code_exec"),
            tool_allowlist=("read_file", "write_file"),
        ),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-y",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "skills": ["old_skill"],
            "tool_allowlist": ["old_tool"],
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert created_metadata["skills"] == ["web_search", "code_exec"]
    assert created_metadata["tool_allowlist"] == ["read_file", "write_file"]


def test_build_session_metadata_ignores_message_metadata_for_prompt_fields(
    tmp_path: Path,
) -> None:
    """When local agent config has no system_prompt/skills/tool_allowlist,
    message.metadata values must still be ignored (not leaked through)."""
    agent_dir = tmp_path / "agent-z"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="agent-z",
            workspace_root=agent_dir,
            title="Agent Z",
        ),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-z",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "system_prompt": "Should NOT appear in session metadata.",
            "skills": ["leaked_skill"],
            "tool_allowlist": ["leaked_tool"],
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert "system_prompt" not in created_metadata
    assert "skills" not in created_metadata
    assert "tool_allowlist" not in created_metadata


def test_build_session_metadata_still_reads_conversation_id_from_message_metadata(
    tmp_path: Path,
) -> None:
    """conversation_id and config_profile_version should still come from message.metadata."""
    agent_dir = tmp_path / "agent-w"
    agent_dir.mkdir()
    agents = (
        AgentWorkspaceConfig(
            agent_id="agent-w",
            workspace_root=agent_dir,
            title="Agent W",
            system_prompt="Local prompt.",
        ),
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-w",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        metadata={
            "conversation_id": "conv-42",
            "config_profile_version": 7,
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert created_metadata["agent_id"] == "agent-w"
    assert created_metadata["conversation_id"] == "conv-42"
    assert created_metadata["config_profile_version"] == 7
    assert created_metadata["system_prompt"] == "Local prompt."


def test_session_metadata_group_fields(tmp_path: Path) -> None:
    """Group-chat session metadata contains conversation_type, participant_agent_ids, external_chat_id."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="@agent:agent-a hello group",
        external_user_id="user-1",
        external_chat_id="grp-42",
        is_group=True,
        metadata={
            "mentioned_agent_ids": ["agent-a"],
            "participant_agent_ids": ["agent-a", "agent-b"],
            "conversation_id": "grp-42",
        },
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert created_metadata["conversation_type"] == "group"
    assert created_metadata["participant_agent_ids"] == ["agent-a", "agent-b"]
    assert created_metadata["external_chat_id"] == "grp-42"


def test_session_metadata_direct_fields(tmp_path: Path) -> None:
    """Direct-chat session metadata contains conversation_type='direct' and no participant_agent_ids."""
    agents = _agents(tmp_path)
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    pipeline = InboundPipeline(
        kernel=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web_relay",
        text="hello direct",
        external_user_id="user-1",
        external_chat_id="dm-1",
        is_group=False,
    )

    asyncio.run(pipeline.handle_inbound(inbound))

    created_metadata = kernel_client.create_session_calls[0]["metadata"]
    assert created_metadata["conversation_type"] == "direct"
    assert "participant_agent_ids" not in created_metadata
