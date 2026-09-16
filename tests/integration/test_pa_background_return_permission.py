"""Unsupported task returns cannot prevent IM from showing delivery approval."""

import asyncio
from dataclasses import replace
import shlex

import pytest

from agent.core.llm.interfaces import LLMMessage, LLMToolCall
from IM.ws.gateway.protocol import parse_background_returns
from personal_assistant.channels.base import IMRelayIngress, InboundIngress
from tests.integration.test_pa_candidate_delivery import Model, build, close, deltas
from tests.integration.test_pa_delivery_manual_permission import ApprovalTransport
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class StrictReturnTransport(ApprovalTransport):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.protocol_errors = []

    def validate(self, payload):
        try:
            parse_background_returns(payload.get("background_returns"))
        except ValueError as error:
            self.protocol_errors.append(str(error))
            raise

    async def send_json_await_ack(self, kind, payload):
        self.validate(payload)
        return await super().send_json_await_ack(kind, payload)

    async def send_json(self, kind, payload):
        self.validate(payload)
        await super().send_json(kind, payload)


class BashReturnModel(Model):
    def __init__(self, image, release):
        super().__init__([])
        self.image = image
        self.release = release

    async def generate(self, request):
        if request.stop_sequences:
            self.permission_requests.append(request)
            image_operation = "host_operation" in str(request.messages)
            yield LLMMessage(
                role="assistant",
                content=f"<block>{'yes' if image_operation else 'no'}</block><reason>Confirm image publication</reason>",
            )
            yield LLMMessage(role="assistant", content="", finish_reason="stop")
            return
        self.requests.append(request)
        if len(self.requests) == 1:
            command = f"while [ ! -f {shlex.quote(str(self.release))} ]; do sleep 0.02; done; echo finished"
            yield LLMMessage(
                role="assistant",
                content="",
                tool_calls=(
                    LLMToolCall(
                        call_id="bash-bg",
                        name="bash",
                        arguments={"command": command, "run_in_background": True},
                    ),
                ),
            )
            yield LLMMessage(role="assistant", content="", finish_reason="tool_calls")
        else:
            text = (
                "Background work started"
                if len(self.requests) == 2
                else f"Finished ![image](<{self.image}>)"
            )
            yield LLMMessage(role="assistant", content=text)
            yield LLMMessage(role="assistant", content="", finish_reason="stop")


@pytest.mark.asyncio
async def test_real_bash_background_return_keeps_manual_image_approval_reachable(
    tmp_path, monkeypatch
):
    image = tmp_path.resolve() / "result.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    release = tmp_path.resolve() / "release-bash"
    model = BashReturnModel(image, release)
    rt, _, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [],
        model=model,
        transport=StrictReturnTransport,
        manual_approval=True,
        enabled_tools=("bash",),
    )
    raw_events = []
    collector = None
    try:
        message = replace(
            inbound(chat_id="c_chat", text="Run background bash then show the image"),
            ingress=InboundIngress(im_relay=IMRelayIngress("relay", "key", "input")),
        )
        initial = await asyncio.wait_for(
            rt._on_inbound._pipeline.handle_inbound(message), 10
        )

        async def collect():
            async for event in rt._kernel.stream(initial.kernel_session_id):
                raw_events.append(event)

        collector = asyncio.create_task(collect())
        release.touch()
        transport = rt._im_connection_manager
        await asyncio.wait_for(transport.requested.wait(), 10)
        cards = [
            p for _, p in transport.frames if p.get("kind") == "permission_request"
        ]
        assert len(cards) == 1
        assert not uploads
        assert rt._kernel.submit_permission_decision(
            request_id=cards[0]["permission_request"]["request_id"],
            decision="allow_once",
        )
        async with asyncio.timeout(10):
            while not uploads or rt._run_coordinator.is_session_busy(
                initial.session_key
            ):
                await asyncio.sleep(0.01)
        assert any(
            item.get("task_type") == "bash"
            for event in raw_events
            for item in event.get("background_returns", [])
        )
        assert any(
            "<task-notification>" in str(request.messages) for request in model.requests
        )
        assert not transport.protocol_errors
        assert len(uploads) == 1
        assert "http://im.test/im/v1/images/image123" in deltas(rt)[-1]["delta_text"]
    finally:
        release.touch()
        if collector is not None:
            collector.cancel()
            await asyncio.gather(collector, return_exceptions=True)
        await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
        await close(rt)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["run_status", "injection_consumed"])
async def test_supported_return_cards_survive_each_observer_entry(entry):
    from personal_assistant.gateway.runtime_delivery.observer import (
        build_kernel_event_observer,
    )
    from personal_assistant.gateway.runtime_delivery.task_tracker import (
        RuntimeDeliveryTaskTracker,
    )
    from tests.helpers.runtime_delivery import delivery_context_store

    transport = StrictReturnTransport()
    tracker = RuntimeDeliveryTaskTracker()
    contexts = delivery_context_store(
        {"run": {"agent_id": "agent", "conversation_id": "c_chat"}}
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: transport,
        run_context_store=contexts,
        task_tracker=tracker,
    )
    sidecars = [
        {
            "task_id": kind,
            "task_type": kind,
            "status": "completed",
            "description": f"{kind} done",
        }
        for kind in ("bash", "subagent", "workflow")
    ]
    event = {
        "event": entry,
        "run_id": "run",
        "status": "running",
        "background_returns": sidecars,
        "content": "Background work completed",
        "message_id": "kernel-message",
    }
    pending = observer(event)
    if pending is not None:
        await pending
    await tracker.drain_run("run")
    assert not transport.protocol_errors
    cards = [
        item
        for _, payload in transport.frames
        for item in payload.get("background_returns", [])
    ]
    assert [item["task_type"] for item in cards] == ["subagent", "workflow"]
    assert [item["task_type"] for item in event["background_returns"]] == [
        "bash",
        "subagent",
        "workflow",
    ]
