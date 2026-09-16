"""Ordinary replies cross the real composed PA, kernel and IM observer chain."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import sqlite3

import httpx
import pytest

from agent.core.llm.interfaces import LLMMessage
from agent.sdk import PermissionDecision
from personal_assistant.channels.base import IMRelayIngress, InboundIngress
from personal_assistant.config.local_store import ChannelConfig, IMServiceConfig
from personal_assistant.gateway.composition import compose_gateway
from tests.unit.personal_assistant._main_helpers import make_minimal_config
from tests.unit.personal_assistant._session_run_coordinator_helpers import inbound


class Transport:
    connected = True
    im_user_url = "http://im.test/"
    gateway_access_token = "test-token"

    def __init__(self, **kwargs):
        self.frames = []

    async def send_json(self, kind, payload):
        self.frames.append((kind, dict(payload)))

    async def send_json_await_ack(self, kind, payload):
        self.frames.append((kind, dict(payload)))
        return {"message_id": payload.get("message_id") or "im-bubble"}

    def finish_external_shadow_run(self, run_id):
        pass


class Model:
    def __init__(self, texts):
        self.texts = texts
        self.requests = []
        self.permission_requests = []

    async def generate(self, request):
        if request.stop_sequences:
            self.permission_requests.append(request)
            yield LLMMessage(
                role="assistant", content="<block>no</block>", finish_reason="stop"
            )
            return
        self.requests.append(request)
        yield LLMMessage(
            role="assistant",
            content=self.texts[min(len(self.requests) - 1, len(self.texts) - 1)],
        )
        yield LLMMessage(role="assistant", content="", finish_reason="stop")


def build(tmp_path, monkeypatch, texts):
    from personal_assistant import product
    from personal_assistant.gateway import composition
    from personal_assistant.gateway import reply_images

    config = make_minimal_config(tmp_path)
    config = replace(
        config,
        node=replace(config.node, user_id="u_owner"),
        channels=(ChannelConfig(name="web_relay", enabled=True),),
        im_service=IMServiceConfig(url="http://im.test"),
    )
    model = Model(texts)
    original = product.build_kernel
    permissions = []

    async def allow(name, arguments, context):
        permissions.append((name, arguments))
        return PermissionDecision(behavior="allow")

    def kernel(**kwargs):
        kwargs.update(
            _llm_client_override=model,
            can_use_tool=allow,
            repo_root=tmp_path,
            global_config_root=tmp_path / "global",
            skill_search_roots=(),
            global_skill_root=None,
            tool_search_roots=(),
            hook_search_roots=(),
        )
        return original(**kwargs)

    monkeypatch.setattr(product, "build_kernel", kernel)
    monkeypatch.setattr(composition, "IMConnectionManager", Transport)
    uploads = []

    def respond(request):
        if request.url.path == "/im/v1/image-delivery/target":
            return httpx.Response(200, json={"conversation_id": "c_chat"})
        if request.url.path.endswith("/images"):
            uploads.append(request.content)
            return httpx.Response(
                200, json={"url": "http://im.test/im/v1/images/image123"}
            )
        return httpx.Response(404)

    client = httpx.AsyncClient
    monkeypatch.setattr(
        reply_images.httpx,
        "AsyncClient",
        lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    rt = compose_gateway(config)
    # Bind only this test's delivery owner; no listener, scheduler or network loop.
    rt._startup_collaborators[0].start()
    return rt, model, uploads, permissions


async def receive(rt, text="send image", number=1):
    message = replace(
        inbound(chat_id="c_chat", text=text),
        ingress=InboundIngress(
            im_relay=IMRelayIngress(
                f"relay-{number}", f"key-{number}", f"input-{number}"
            )
        ),
    )
    result = await asyncio.wait_for(
        rt._on_inbound._pipeline.handle_inbound(message), 10
    )
    await rt._run_coordinator.drain(asyncio.get_running_loop().time() + 5)
    return result


async def close(rt):
    await rt._kernel.aclose()
    for closer in rt._resource_closers:
        closer()


def deltas(rt):
    return [
        payload
        for kind, payload in rt._im_connection_manager.frames
        if kind == "node.streaming_delta" and payload.get("kind") == "message_delta"
    ]


@pytest.mark.asyncio
async def test_composed_image_success_has_one_upload_and_one_observer_publication(
    tmp_path, monkeypatch
):
    image = tmp_path / "outside-workspace.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    rt, model, uploads, permissions = build(
        tmp_path, monkeypatch, [f"Here ![image](<{image}>)"]
    )
    try:
        result = await receive(rt)
        assert result.run_id
        assert len(model.requests) == 1
        assert len(uploads) == 1
        assert len(model.permission_requests) == 1
        assert len(deltas(rt)) == 1
        assert "http://im.test/im/v1/images/image123" in deltas(rt)[0]["delta_text"]
        with sqlite3.connect(tmp_path / "reply-images/reply_images.sqlite3") as db:
            receipts = db.execute(
                "SELECT receipt_json FROM reply_deliveries WHERE channel = 'im'"
            ).fetchall()
        assert len(receipts) == 1
        assert '"delivered"' in receipts[0][0]
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_composed_failed_image_is_private_and_model_corrects_same_run(
    tmp_path, monkeypatch
):
    missing = tmp_path / "missing.png"
    rt, model, uploads, permissions = build(
        tmp_path,
        monkeypatch,
        [f"Private draft ![image](<{missing}>)", "I could not read that image."],
    )
    try:
        result = await receive(rt)
        assert len(model.requests) == 2
        assert not uploads
        assert "never delivered" in str(model.requests[1].messages)
        assert str(missing) not in str(rt._im_connection_manager.frames)
        assert len(deltas(rt)) == 1
        assert deltas(rt)[0]["delta_text"] == "I could not read that image."
        assert {p["run_id"] for p in deltas(rt)} == {result.run_id}
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_composed_text_passes_through_without_image_permissions(
    tmp_path, monkeypatch
):
    rt, model, uploads, permissions = build(tmp_path, monkeypatch, ["Plain reply"])
    try:
        await receive(rt)
        assert len(model.requests) == 1
        assert not permissions and not uploads and not model.permission_requests
        assert [p["delta_text"] for p in deltas(rt)] == ["Plain reply"]
    finally:
        await close(rt)


@pytest.mark.asyncio
async def test_composed_restored_session_gains_output_feature_without_rebinding(
    tmp_path, monkeypatch
):
    from personal_assistant.channels.base import ReplyContext
    from personal_assistant.gateway.session_keys import build_session_key

    image = tmp_path / "restored.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    rt, model, uploads, permissions = build(
        tmp_path, monkeypatch, [f"Restored ![image](<{image}>)"]
    )
    try:
        workspace = tmp_path / "agent-a"
        session = await rt._kernel.create_session(
            workspace_root=workspace, metadata={"agent_id": "agent-a"}, enabled_tools=[]
        )
        assert not session.metadata.get("output_handler_enabled")
        binder = rt._run_coordinator._session_binder
        message = inbound(chat_id="c_chat", text="send image")
        binder._repository.bind(
            session_key=build_session_key(message, agent_id="agent-a"),
            kernel_session_id=session.session_id,
            reply_context=ReplyContext(
                channel_name="web_relay", target_chat_id="c_chat"
            ),
        )
        result = await receive(rt)
        assert result.kernel_session_id == session.session_id
        current = await rt._kernel.get_session_runtime(
            session_id=session.session_id, workspace_root=workspace
        )
        assert current.runtime.features["output_handler_enabled"] is True
        assert len(uploads) == 1
        assert len(deltas(rt)) == 1
        assert "http://im.test/im/v1/images/image123" in deltas(rt)[0]["delta_text"]
    finally:
        await close(rt)
