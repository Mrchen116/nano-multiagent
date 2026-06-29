"""feat-445-M1 R1 (决策 4 地基): relay 把逐气泡 kernel message_id 落到 IM 消息行。

fork 的两侧对齐键是「逐气泡唯一的 kernel message_id」。一个 run 可产出多条
assistant_message = 多个 IM 气泡，每个气泡必须被标上「产出它的那条 assistant 消息」
的 kernel message_id（= JSONL turn uuid）。本测试在 gateway observer 层锁定：每个气泡
收尾的 message_completed 帧带的是它自己那条 assistant 消息的 kernel message_id，多气泡
不串味。
"""

import asyncio

import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_message_completed_carries_per_bubble_kernel_message_id() -> None:
    """一 run 产出两条 assistant 气泡（textA→textB，kernel id 不同触发 roll）→
    两个 message_completed 帧各带各自气泡的 kernel message_id。"""
    from personal_assistant.main import _build_kernel_event_observer

    send_calls: list[tuple] = []
    bubble_seq = {"n": 0}

    manager = MagicMock()
    manager.connected = True

    async def mock_send_json_await_ack(message_type, payload):
        send_calls.append((message_type, payload))
        bubble_seq["n"] += 1
        return {
            "type": "ack",
            "payload": {
                "message_type": "node.streaming_delta",
                "kind": "turn_start",
                "message_id": f"bubble-{bubble_seq['n']}",
            },
        }

    async def mock_send_json(message_type, payload):
        send_calls.append((message_type, payload))

    manager.send_json = mock_send_json
    manager.send_json_await_ack = mock_send_json_await_ack

    run_context_store: dict[str, dict[str, str]] = {
        "run-1": {
            "conversation_id": "conv-1",
            "message_id": "",
            "agent_id": "alpha",
        }
    }

    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
    )

    # run_status=running → turn_start (bubble-1)
    coro = observer({"event": "run_status", "status": "running", "run_id": "run-1"})
    if asyncio.iscoroutine(coro):
        await coro
    assert run_context_store["run-1"]["message_id"] == "bubble-1"

    # assistant_message A → delta to bubble-1, ctx.kernel_message_id = kmsg-A
    coro = observer(
        {
            "event": "assistant_message",
            "content": "text A",
            "message_id": "kmsg-A",
            "run_id": "run-1",
        }
    )
    if asyncio.iscoroutine(coro):
        await coro
    await asyncio.sleep(0)  # let scheduled delta task run

    # assistant_message B (different kernel id) → roll: close bubble-1, open bubble-2
    coro = observer(
        {
            "event": "assistant_message",
            "content": "text B",
            "message_id": "kmsg-B",
            "run_id": "run-1",
        }
    )
    if asyncio.iscoroutine(coro):
        await coro
    await asyncio.sleep(0)

    # turn_end → message_completed for the final bubble (bubble-2)
    coro = observer({"event": "turn_end", "completed": True, "run_id": "run-1"})
    if asyncio.iscoroutine(coro):
        await coro
    await asyncio.sleep(0)

    completed = [p for _, p in send_calls if p.get("kind") == "message_completed"]
    by_bubble = {p["message_id"]: p.get("kernel_message_id") for p in completed}

    # bubble-1 (textA) closed via roll carries kmsg-A; bubble-2 (textB) via turn_end carries kmsg-B
    assert by_bubble.get("bubble-1") == "kmsg-A", (
        f"bubble-1 must carry its own kernel id kmsg-A, frames={completed}"
    )
    assert by_bubble.get("bubble-2") == "kmsg-B", (
        f"bubble-2 must carry its own kernel id kmsg-B, frames={completed}"
    )


@pytest.mark.asyncio
async def test_single_bubble_completed_carries_kernel_message_id() -> None:
    """单气泡 run：turn_end 的 message_completed 带该气泡的 kernel message_id。"""
    from personal_assistant.main import _build_kernel_event_observer

    send_calls: list[tuple] = []
    manager = MagicMock()
    manager.connected = True

    async def mock_send_json_await_ack(message_type, payload):
        send_calls.append((message_type, payload))
        return {
            "type": "ack",
            "payload": {"kind": "turn_start", "message_id": "bubble-only"},
        }

    async def mock_send_json(message_type, payload):
        send_calls.append((message_type, payload))

    manager.send_json = mock_send_json
    manager.send_json_await_ack = mock_send_json_await_ack

    run_context_store: dict[str, dict[str, str]] = {
        "run-1": {"conversation_id": "conv-1", "message_id": "", "agent_id": "alpha"}
    }
    observer = _build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=run_context_store,
    )

    coro = observer({"event": "run_status", "status": "running", "run_id": "run-1"})
    if asyncio.iscoroutine(coro):
        await coro
    coro = observer(
        {
            "event": "assistant_message",
            "content": "only answer",
            "message_id": "kmsg-only",
            "run_id": "run-1",
        }
    )
    if asyncio.iscoroutine(coro):
        await coro
    await asyncio.sleep(0)
    coro = observer({"event": "turn_end", "completed": True, "run_id": "run-1"})
    if asyncio.iscoroutine(coro):
        await coro
    await asyncio.sleep(0)

    completed = [p for _, p in send_calls if p.get("kind") == "message_completed"]
    assert len(completed) == 1
    assert completed[0]["message_id"] == "bubble-only"
    assert completed[0].get("kernel_message_id") == "kmsg-only"
