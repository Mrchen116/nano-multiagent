"""Human approval remains reachable while a complete reply waits for delivery."""

import asyncio
from dataclasses import replace

import pytest
from agent.core.llm.interfaces import LLMMessage
from personal_assistant.channels.base import IMRelayIngress, InboundIngress
from tests.integration.test_pa_candidate_delivery import (
    Model,
    Transport,
    build,
    close,
    deltas,
    receive,
)
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class AskModel(Model):
    async def generate(self, request):
        if request.stop_sequences:
            self.permission_requests.append(request)
            yield LLMMessage(
                role="assistant", content="<block>yes</block>", finish_reason="stop"
            )
            return
        async for message in super().generate(request):
            yield message


class ApprovalTransport(Transport):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.requested = asyncio.Event()

    async def send_json(self, kind, payload):
        await super().send_json(kind, payload)
        if payload.get("kind") == "permission_request":
            self.requested.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["allow_once", "deny", "stop"])
async def test_complete_candidate_presents_manual_card_before_waiting_for_decision(
    tmp_path, monkeypatch, decision
):
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    model = AskModel([f"![image](<{image}>)", "Permission was denied; no image sent."])
    rt, _, uploads, _ = build(
        tmp_path,
        monkeypatch,
        [],
        model=model,
        transport=ApprovalTransport,
        manual_approval=True,
    )
    receiving = asyncio.create_task(receive(rt))
    try:
        transport = rt._im_connection_manager
        await asyncio.wait_for(transport.requested.wait(), 5)
        cards = [
            p for _, p in transport.frames if p.get("kind") == "permission_request"
        ]
        assert len(cards) == 1
        request_id = cards[0]["permission_request"]["request_id"]
        assert not uploads and not deltas(rt)
        assert not receiving.done()
        if decision == "stop":
            message = replace(
                inbound(chat_id="c_chat", text="/stop"),
                ingress=InboundIngress(
                    im_relay=IMRelayIngress("stop-relay", "stop-key", "stop-input")
                ),
            )
            await asyncio.wait_for(rt._on_inbound._pipeline.handle_inbound(message), 5)
        else:
            assert rt._kernel.submit_permission_decision(
                request_id=request_id, decision=decision
            )
        await asyncio.wait_for(receiving, 5)
        cards = [
            p for _, p in transport.frames if p.get("kind") == "permission_request"
        ]
        assert len(cards) == 1
        assert len(uploads) == (1 if decision == "allow_once" else 0)
        if decision != "stop":
            resolved = [
                p for _, p in transport.frames if p.get("kind") == "permission_resolved"
            ]
            assert len(resolved) == 1
        else:
            assert not rt._kernel.submit_permission_decision(
                request_id=request_id, decision="allow_once"
            )
            assert len(model.requests) == 1
    finally:
        receiving.cancel()
        await asyncio.gather(receiving, return_exceptions=True)
        await close(rt)
