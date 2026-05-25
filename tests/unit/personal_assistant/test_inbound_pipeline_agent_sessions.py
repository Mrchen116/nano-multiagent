"""Inbound pipeline agent session registration, drop, and run queue tests."""

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

from ._pipeline_helpers import _FakeChannel, _FakeKernelClient, _agents


def test_register_agent_keeps_existing_direct_sessions_and_uses_new_workspace_for_new_conversations(tmp_path: Path) -> None:
    agent_a_dir = tmp_path / "agent-a"
    agent_a_dir.mkdir()
    initial_agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=agent_a_dir, title="Agent A",
        system_prompt="You are Agent A v1.",
    )
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=(initial_agent,),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )
    old_conversation = InboundMessage(
        channel_name="web",
        text="hello old",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "conversation_id": "chat-1",
            "config_profile_version": 1,
        },
    )

    first = asyncio.run(pipeline.handle_inbound(old_conversation))

    refreshed_workspace = tmp_path / "agent-a-v2"
    refreshed_workspace.mkdir()
    pipeline.register_agent(
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=refreshed_workspace, title="Agent A v2",
            system_prompt="You are Agent A v2.",
        )
    )

    second_old = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="hello old again",
                external_user_id="user-1",
                external_chat_id="chat-1",
                is_group=False,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "chat-1",
                    "config_profile_version": 2,
                },
            )
        )
    )
    new_conversation = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web",
                text="hello new",
                external_user_id="user-1",
                external_chat_id="chat-2",
                is_group=False,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "chat-2",
                    "config_profile_version": 2,
                },
            )
        )
    )

    assert first is not None
    assert second_old is not None
    assert new_conversation is not None
    assert first.kernel_session_id == "sess-1"
    assert second_old.kernel_session_id == "sess-2"
    assert new_conversation.kernel_session_id == "sess-3"
    assert [call["workspace_root"] for call in kernel_client.create_session_calls] == [
        str(agent_a_dir),
        str(refreshed_workspace),
        str(refreshed_workspace),
    ]
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agent_a_dir),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-1",
                "config_profile_version": 1,
                "system_prompt": "You are Agent A v1.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
        {
            "workspace_root": str(refreshed_workspace),
            "product_id": "personal_assistant",
            "title": "Agent A v2",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-1",
                "config_profile_version": 2,
                "system_prompt": "You are Agent A v2.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
        {
            "workspace_root": str(refreshed_workspace),
            "product_id": "personal_assistant",
            "title": "Agent A v2",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "chat-2",
                "config_profile_version": 2,
                "system_prompt": "You are Agent A v2.",
                "conversation_type": "direct",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
    ]
    # Outbound metadata passes through message.metadata verbatim (routing fields only).
    assert channel.sent[1].metadata == {
        "conversation_id": "chat-1",
        "config_profile_version": 2,
    }
    assert channel.sent[2].metadata == {
        "conversation_id": "chat-2",
        "config_profile_version": 2,
    }


def test_drop_agent_sessions_forces_group_mentions_to_create_a_fresh_kernel_session(tmp_path: Path) -> None:
    agent_a_dir = tmp_path / "agent-a"
    agent_a_dir.mkdir()
    initial_agent = AgentWorkspaceConfig(
        agent_id="agent-a", workspace_root=agent_a_dir, title="Agent A",
        system_prompt="Reply with ALPHA_ACK_M170.",
    )
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=(initial_agent,),
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )

    first = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent-a first pass",
                external_user_id="user-1",
                external_chat_id="conv-group-1",
                is_group=True,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "conv-group-1",
                    "mentioned_agent_ids": ["agent-a"],
                    "trigger": "mention",
                    "config_profile_version": 1,
                },
            )
        )
    )

    # Simulate config sync: update system_prompt via register_agent + drop stale sessions.
    pipeline.register_agent(
        AgentWorkspaceConfig(
            agent_id="agent-a", workspace_root=agent_a_dir, title="Agent A",
            system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
        )
    )
    pipeline.drop_agent_sessions("agent-a")

    second = asyncio.run(
        pipeline.handle_inbound(
            InboundMessage(
                channel_name="web_relay",
                text="@agent-a second pass",
                external_user_id="user-1",
                external_chat_id="conv-group-1",
                is_group=True,
                agent_id="agent-a",
                metadata={
                    "conversation_id": "conv-group-1",
                    "mentioned_agent_ids": ["agent-a"],
                    "trigger": "mention",
                    "config_profile_version": 2,
                },
            )
        )
    )

    assert first is not None
    assert second is not None
    assert first.kernel_session_id == "sess-1"
    assert second.kernel_session_id == "sess-2"
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agent_a_dir),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "conv-group-1",
                "config_profile_version": 1,
                "system_prompt": "Reply with ALPHA_ACK_M170.",
                "conversation_type": "group",
                "participant_agent_ids": ["agent-a"],
                "external_chat_id": "conv-group-1",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
        {
            "workspace_root": str(agent_a_dir),
            "product_id": "personal_assistant",
            "title": "Agent A",
            "metadata": {
                "agent_id": "agent-a",
                "conversation_id": "conv-group-1",
                "config_profile_version": 2,
                "system_prompt": "When mentioned in a group chat, reply exactly with NO_REPLY.",
                "conversation_type": "group",
                "participant_agent_ids": ["agent-a"],
                "external_chat_id": "conv-group-1",
                "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch",
                "agent_features": {},
            },
        },
    ]


def test_session_run_queue_serializes_same_session_and_allows_cross_session_parallelism() -> None:
    queue = SessionRunQueue()
    events: list[str] = []
    same_session_active = 0
    same_session_peak = 0
    cross_session_active = 0
    cross_session_peak = 0
    gate = asyncio.Event()
    second_started = asyncio.Event()

    async def same_session_job(name: str) -> str:
        nonlocal same_session_active, same_session_peak
        same_session_active += 1
        same_session_peak = max(same_session_peak, same_session_active)
        events.append(f"start:{name}")
        if name == "one":
            await gate.wait()
        else:
            second_started.set()
        await asyncio.sleep(0)
        events.append(f"end:{name}")
        same_session_active -= 1
        return name

    async def exercise_queue() -> tuple[list[str], int, int, list[str]]:
        first_task = asyncio.create_task(queue.submit("sess-a", lambda: same_session_job("one")))
        await asyncio.sleep(0)
        second_task = asyncio.create_task(queue.submit("sess-a", lambda: same_session_job("two")))
        await asyncio.sleep(0.01)
        assert not second_started.is_set()
        gate.set()
        first_result = await first_task
        second_result = await second_task

        async def cross_session_job(name: str) -> str:
            nonlocal cross_session_active, cross_session_peak
            cross_session_active += 1
            cross_session_peak = max(cross_session_peak, cross_session_active)
            await asyncio.sleep(0.02)
            cross_session_active -= 1
            return name

        parallel_results = await asyncio.gather(
            queue.submit("sess-b", lambda: cross_session_job("b")),
            queue.submit("sess-c", lambda: cross_session_job("c")),
        )
        return events, same_session_peak, cross_session_peak, [first_result, second_result, *parallel_results]

    recorded_events, same_peak, cross_peak, results = asyncio.run(exercise_queue())

    assert same_peak == 1
    assert recorded_events == ["start:one", "end:one", "start:two", "end:two"]
    assert results == ["one", "two", "b", "c"]
    assert cross_peak >= 2
