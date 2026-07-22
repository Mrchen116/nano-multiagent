"""Channel registry lifecycle, session key routing, run queue, and drop_agent tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from personal_assistant.channels.base import InboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from tests.helpers.inbound_pipeline import build_inbound_pipeline, inbound_graph
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import (
    SessionBindingStore,
    build_session_key,
)

from ._pipeline_helpers import _FakeChannel, _FakeKernel, _agents


def test_channel_registry_and_bootstrap_manage_adapter_lifecycle() -> None:
    channel_a = _FakeChannel("web")
    channel_b = _FakeChannel("qq")
    registry = ChannelRegistry((channel_a, channel_b))
    seen: list[InboundMessage] = []

    started = start_channels(registry, seen.append)
    stopped = stop_channels(registry)

    assert started == ("web", "qq")
    assert channel_a.started_with is not None
    assert channel_b.started_with is not None
    assert stopped == ("qq", "web")
    assert channel_a.stopped == 1
    assert channel_b.stopped == 1


def test_build_session_key_uses_chat_id_for_groups_and_direct_messages() -> None:
    group_message = InboundMessage(
        channel_name="web",
        text="hello group",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=True,
    )
    direct_message = InboundMessage(
        channel_name="web",
        text="hello dm",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    assert build_session_key(group_message, agent_id="agent-a") == "web:chat-1:agent-a"
    assert build_session_key(direct_message, agent_id="agent-a") == "web:chat-1:agent-a"


def test_build_session_key_prefers_external_identity_metadata() -> None:
    shadow_relay_message = InboundMessage(
        channel_name="web_relay",
        text="continue from IM shadow",
        external_user_id="im-user-1",
        external_chat_id="im-conv-1",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:cli_a:dm:ou_user1",
        },
    )
    feishu_message = InboundMessage(
        channel_name="feishu:agent-a",
        text="continue from feishu",
        external_user_id="ou_user1",
        external_chat_id="feishu:cli_a:dm:ou_user1",
        is_group=False,
        agent_id="agent-a",
        metadata={
            "external_source": "feishu",
            "external_chat_id": "feishu:cli_a:dm:ou_user1",
        },
    )

    expected = "feishu:feishu:cli_a:dm:ou_user1:agent-a"
    assert build_session_key(shadow_relay_message, agent_id="agent-a") == expected
    assert build_session_key(feishu_message, agent_id="agent-a") == expected


def test_config_publish_reconfigures_group_session_without_changing_address(
    tmp_path: Path,
) -> None:
    agent_a_dir = tmp_path / "agent-a"
    agent_a_dir.mkdir()
    initial_agent = AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=agent_a_dir,
        title="Agent A",
        system_prompt="Reply with ALPHA_ACK_M170.",
    )
    channel = _FakeChannel("web_relay")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernel()
    store = SessionBindingStore()
    pipeline = build_inbound_pipeline(
        kernel=kernel_client,
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

    # Simulate configuration publication; the next new run reconfigures this address.
    current = inbound_graph(pipeline).catalog.publish(
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=agent_a_dir,
            title="Agent A",
            system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY.",
        )
    )
    inbound_graph(pipeline).binder.invalidate_stale(
        "agent-a", current_revision=current.revision
    )

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
    assert second.kernel_session_id == "sess-1"
    assert len(kernel_client.create_session_calls) == 1
    runtime = kernel_client._session_runtime["sess-1"]  # noqa: SLF001
    assert any(
        item.text == "When mentioned in a group chat, reply exactly with NO_REPLY."
        for item in runtime.runtime.prompt.custom
    )


def test_session_run_queue_serializes_same_session_and_allows_cross_session_parallelism() -> (
    None
):
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
        first_task = asyncio.create_task(
            queue.submit("sess-a", lambda: same_session_job("one"))
        )
        await asyncio.sleep(0)
        second_task = asyncio.create_task(
            queue.submit("sess-a", lambda: same_session_job("two"))
        )
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
        return (
            events,
            same_session_peak,
            cross_session_peak,
            [first_result, second_result, *parallel_results],
        )

    recorded_events, same_peak, cross_peak, results = asyncio.run(exercise_queue())

    assert same_peak == 1
    assert recorded_events == ["start:one", "end:one", "start:two", "end:two"]
    assert results == ["one", "two", "b", "c"]
    assert cross_peak >= 2
