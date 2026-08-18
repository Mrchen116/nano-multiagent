"""Chat failover follows run_status.error.kind and does not resubmit user parts."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from personal_assistant.gateway.inbound_models import InboundRunRequest, RoutedInbound
from personal_assistant.gateway.session_keys import build_session_key
from personal_assistant.gateway.session_run_coordinator import SessionRunCoordinator
from personal_assistant.gateway.model_fallback import (
    ModelStickyStore,
    StickyModelOverride,
)
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.outbound_router import OutboundRouter

from ._pipeline_helpers import _FakeChannel
from ._session_run_coordinator_helpers import build_dependencies, inbound


def _request(message, catalog) -> InboundRunRequest:
    agent = catalog.require("agent-a")
    return InboundRunRequest(
        routed=RoutedInbound(message=message),
        agent=agent,
        session_key=build_session_key(message, agent_id=agent.agent_id),
        sender_label="Alice",
    )


def _publish_fallbacks(catalog, *models: str) -> None:
    current = catalog.require("agent-a").config
    catalog.publish(replace(current, model_fallbacks=models))


@pytest.mark.asyncio
async def test_quota_failure_replays_without_copying_user_parts(tmp_path: Path) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-model")
    sticky = ModelStickyStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        sticky_store=sticky,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="⚠️ 模型调用失败（test-model）: quota",
        error={"kind": "quota", "code": "run_execution_failed", "message": "quota"},
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="backup reply")
    result = await running

    assert result.reply_text == "backup reply"
    assert len(kernel.submit_calls) == 1
    assert kernel.submit_calls[0]["parts"][0]["text"] == "hello"
    assert kernel.replay_calls[0]["run_id"] == "run-2"
    assert sticky.get(result.kernel_session_id).model == "backup-model"
    assert sticky.get(result.kernel_session_id).noticed is True
    assert coordinator.is_session_busy(result.session_key) is False


@pytest.mark.asyncio
async def test_rejected_replay_closes_the_turn_and_sticks_next_candidate(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-model")
    kernel.reject_replay = True
    sticky = ModelStickyStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        sticky_store=sticky,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="partial answer then quota",
        error={"kind": "quota", "message": "quota"},
    )
    with pytest.raises(RuntimeError, match="quota"):
        await running
    binding = binder.lookup("web_relay:chat-a:agent-a")
    assert sticky.get(binding.kernel_session_id) == StickyModelOverride(
        "backup-model", noticed=False
    )
    assert kernel.replay_calls == []
    assert len(kernel.submit_calls) == 1


@pytest.mark.asyncio
async def test_context_length_does_not_replay(tmp_path: Path) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-model")
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="too long",
        error={"kind": "context_length", "message": "context window"},
    )
    with pytest.raises(RuntimeError, match="context window"):
        await running
    assert kernel.replay_calls == []


@pytest.mark.asyncio
async def test_sticky_is_used_on_the_next_admit(tmp_path: Path) -> None:
    kernel, catalog, binder, router, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-model")
    sticky = ModelStickyStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=router,
        group_context_store=group_store,
        sticky_store=sticky,
    )
    first = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="one"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="fail",
        error={"kind": "auth", "message": "invalid_api_key"},
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="backup reply")
    first_result = await first
    session_id = first_result.kernel_session_id
    assert sticky.get(session_id).model == "backup-model"

    second = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="two"), catalog))
    )
    await kernel.wait_stream("run-3")
    assert kernel.reconfigure_calls[-1][1].model == "backup-model"
    kernel.finish("run-3", text="still backup")
    await second
    assert sticky.get(session_id).noticed is True


@pytest.mark.asyncio
async def test_switch_notice_is_sent_once_before_backup_reply(tmp_path: Path) -> None:
    kernel, catalog, binder, _, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-model")
    channel = _FakeChannel("web_relay")
    sticky = ModelStickyStore()
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        group_context_store=group_store,
        sticky_store=sticky,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="⚠️ 模型调用失败（test-model）: quota",
        error={"kind": "quota", "message": "quota"},
    )
    await kernel.wait_stream("run-2")
    kernel.finish("run-2", text="backup reply")
    await running

    texts = [item.text for item in channel.sent]
    assert texts.count("已改用 backup-model，因为主模型不可用。") == 1
    assert texts[-1] == "backup reply"
    notice_at = texts.index("已改用 backup-model，因为主模型不可用。")
    assert notice_at < texts.index("backup reply")


@pytest.mark.asyncio
async def test_exhausted_chain_stays_failed_without_switch_notice(
    tmp_path: Path,
) -> None:
    kernel, catalog, binder, _, group_store = build_dependencies(tmp_path)
    _publish_fallbacks(catalog, "backup-a", "backup-b")
    channel = _FakeChannel("web_relay")
    observed: list[dict[str, object]] = []
    coordinator = SessionRunCoordinator(
        kernel=kernel,
        session_binder=binder,
        outbound_router=OutboundRouter(ChannelRegistry((channel,))),
        group_context_store=group_store,
        sticky_store=ModelStickyStore(),
        kernel_event_observer=observed.append,
    )
    running = asyncio.create_task(
        coordinator.dispatch(_request(inbound(chat_id="chat-a", text="hello"), catalog))
    )
    await kernel.wait_stream("run-1")
    kernel.finish(
        "run-1",
        status="failed",
        text="⚠️ 模型调用失败（test-model）: quota",
        error={"kind": "quota", "message": "quota"},
    )
    await kernel.wait_stream("run-2")
    kernel.finish(
        "run-2",
        status="failed",
        text="⚠️ 模型调用失败（backup-a）: quota",
        error={"kind": "quota", "message": "quota"},
    )
    await kernel.wait_stream("run-3")
    kernel.finish(
        "run-3",
        status="failed",
        text="⚠️ 模型调用失败（backup-b）: quota",
        error={"kind": "quota", "message": "quota"},
    )
    with pytest.raises(RuntimeError, match="quota"):
        await running

    assert [call["run_id"] for call in kernel.replay_calls] == ["run-2", "run-3"]
    texts = [item.text for item in channel.sent]
    assert all("已改用" not in text for text in texts)
    assert texts == [
        "⚠️ 模型调用失败（backup-a）: quota",
        "⚠️ 模型调用失败（backup-b）: quota",
    ]
    observed_failures = [
        event["content"]
        for event in observed
        if event.get("event") == "assistant_message"
    ]
    assert observed_failures == [
        "⚠️ 模型调用失败（test-model）: quota",
        "⚠️ 模型调用失败（backup-a）: quota",
        "⚠️ 模型调用失败（backup-b）: quota",
    ]
    for run_id in ("run-2", "run-3"):
        names = [
            event["event"]
            for event in observed
            if event.get("run_id") == run_id
            and event["event"] in {"assistant_message", "run_terminal_reconcile"}
        ]
        assert names[:2] == ["assistant_message", "run_terminal_reconcile"]
    assert len(kernel.submit_calls) == 1
    assert coordinator.is_session_busy("web_relay:chat-a:agent-a") is False
