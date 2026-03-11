"""Gateway channel system and inbound pipeline tests for milestone M100."""

from __future__ import annotations

import asyncio
from pathlib import Path


from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.bootstrap import start_channels, stop_channels
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore, build_session_key


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started_with = None
        self.stopped = 0
        self.sent: list[OutboundMessage] = []

    def start(self, on_inbound):
        self.started_with = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        self.sent.append(outbound)

    def stop(self) -> None:
        self.stopped += 1


class _FakeKernelClient:
    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, str | None]] = []
        self.send_calls: list[dict[str, str]] = []
        self.run_states: dict[str, dict[str, str]] = {}
        self._session_index = 0
        self._run_index = 0

    def create_session(self, *, workspace_root: str, product_id: str, title: str | None = None):
        self._session_index += 1
        self.create_session_calls.append(
            {"workspace_root": workspace_root, "product_id": product_id, "title": title}
        )
        return {"session_id": f"sess-{self._session_index}"}

    def send_message_async(self, *, session_id: str, text: str):
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        self.send_calls.append({"session_id": session_id, "text": text, "run_id": run_id})
        self.run_states[run_id] = {"run_id": run_id, "output_text": f"reply:{text}"}
        return {"run_id": run_id}

    def get_run(self, *, run_id: str):
        return self.run_states[run_id]


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    agent_a.mkdir()
    agent_b.mkdir()
    return (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=agent_a, title="Agent A"),
        AgentWorkspaceConfig(agent_id="agent-b", workspace_root=agent_b, title="Agent B"),
    )


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


def test_build_session_key_uses_chat_id_for_groups_and_user_id_for_direct_messages() -> None:
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
    assert build_session_key(direct_message, agent_id="agent-a") == "web:user-1:agent-a"


def test_inbound_pipeline_runs_four_steps_and_replies_via_origin_channel(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="ping",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    result = asyncio.run(pipeline.handle_inbound(inbound))

    assert result.agent_id == "agent-a"
    assert result.session_key == "web:user-1:agent-a"
    assert result.kernel_session_id == "sess-1"
    assert result.run_id == "run-1"
    assert result.reply_text == "reply:ping"
    assert channel.sent == [
        OutboundMessage(
            channel_name="web",
            text="reply:ping",
            target_chat_id="chat-1",
            thread_id=None,
            metadata={},
        )
    ]
    assert kernel_client.create_session_calls == [
        {
            "workspace_root": str(agents[0].workspace_root),
            "product_id": "personal_assistant",
            "title": "Agent A",
        }
    ]
    assert kernel_client.send_calls == [{"session_id": "sess-1", "text": "ping", "run_id": "run-1"}]


def test_inbound_pipeline_prefers_explicit_agent_then_channel_binding_then_default(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))

    explicit_kernel = _FakeKernelClient()
    explicit_pipeline = InboundPipeline(
        kernel_client=explicit_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(explicit_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="explicit",
            external_user_id="user-1",
            external_chat_id="chat-1",
            is_group=False,
            agent_id="agent-b",
        )
    ))

    bound_kernel = _FakeKernelClient()
    bound_pipeline = InboundPipeline(
        kernel_client=bound_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        channel_bindings={"web:chat-2": "agent-b"},
        default_agent_id="agent-a",
    )
    asyncio.run(bound_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="@agent-b bound",
            external_user_id="user-2",
            external_chat_id="chat-2",
            is_group=True,
            metadata={"mentioned_agent_ids": ["agent-b"], "trigger": "mention"},
        )
    ))

    default_kernel = _FakeKernelClient()
    default_pipeline = InboundPipeline(
        kernel_client=default_kernel,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=SessionBindingStore(),
        default_agent_id="agent-a",
    )
    asyncio.run(default_pipeline.handle_inbound(
        InboundMessage(
            channel_name="web",
            text="default",
            external_user_id="user-3",
            external_chat_id="chat-3",
            is_group=False,
        )
    ))

    assert explicit_kernel.create_session_calls[0]["workspace_root"] == str(agents[1].workspace_root)
    assert bound_kernel.create_session_calls[0]["workspace_root"] == str(agents[1].workspace_root)
    assert default_kernel.create_session_calls[0]["workspace_root"] == str(agents[0].workspace_root)


def test_inbound_pipeline_reuses_existing_session_binding_per_session_key(tmp_path: Path) -> None:
    agents = _agents(tmp_path)
    channel = _FakeChannel("web")
    registry = ChannelRegistry((channel,))
    kernel_client = _FakeKernelClient()
    store = SessionBindingStore()
    pipeline = InboundPipeline(
        kernel_client=kernel_client,
        agents=agents,
        outbound_router=OutboundRouter(registry),
        run_queue=SessionRunQueue(),
        session_store=store,
        default_agent_id="agent-a",
    )
    inbound = InboundMessage(
        channel_name="web",
        text="hello",
        external_user_id="user-1",
        external_chat_id="chat-1",
        is_group=False,
    )

    first = asyncio.run(pipeline.handle_inbound(inbound))
    second = asyncio.run(pipeline.handle_inbound(inbound))

    assert first.kernel_session_id == second.kernel_session_id == "sess-1"
    assert len(kernel_client.create_session_calls) == 1
    assert [call["run_id"] for call in kernel_client.send_calls] == ["run-1", "run-2"]


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
