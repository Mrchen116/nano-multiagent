"""Permission events remain visible on IM and external approval surfaces."""

from __future__ import annotations

from tests.helpers.runtime_delivery import delivery_context_store
import asyncio
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest

from personal_assistant.gateway.runtime_delivery.observer import (
    build_kernel_event_observer,
)
from personal_assistant.gateway.runtime_delivery.background import (
    build_workflow_permission_delivery,
)
from personal_assistant.gateway.workflow_permission_bindings import (
    WorkflowPermissionDelivery,
    WorkflowPermissionDeliveryAnchor,
    WorkflowPermissionDeliveryBindingRegistry,
)


class _Manager:
    def __init__(self) -> None:
        self.connected = True
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._sent_tasks: list[object] = []

    async def send_json(
        self,
        message_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        self.sent.append((message_type, dict(payload)))

    async def send_json_await_ack(
        self,
        message_type: str,
        payload: Mapping[str, Any],
    ) -> dict[str, object]:
        self.sent.append((message_type, dict(payload)))
        return {"payload": {"message_id": "message-from-ack"}}


async def _observe(observer: Any, event: Mapping[str, object]) -> None:
    result = observer(event)
    if asyncio.iscoroutine(result):
        await result
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_permission_request_and_resolution_are_forwarded_to_im() -> None:
    manager = _Manager()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "conversation-1",
                    "message_id": "message-1",
                    "agent_id": "agent-a",
                }
            }
        ),
    )

    await _observe(
        observer,
        {
            "run_id": "run-1",
            "event": "permission_request",
            "request_id": "request-1",
            "tool_name": "bash",
            "tool_input": {"command": "pwd"},
            "question": "Allow bash?",
            "options": [{"id": "allow_once", "label": "Allow once"}],
        },
    )
    await _observe(
        observer,
        {
            "run_id": "run-1",
            "event": "permission_resolved",
            "request_id": "request-1",
            "decision": "allow_once",
        },
    )

    deltas = [
        payload for kind, payload in manager.sent if kind == "node.streaming_delta"
    ]
    request = next(item for item in deltas if item["kind"] == "permission_request")
    resolved = next(item for item in deltas if item["kind"] == "permission_resolved")
    assert request["message_id"] == "message-1"
    assert request["permission_request"]["request_id"] == "request-1"
    assert request["permission_request"]["tool_name"] == "bash"
    assert resolved["message_id"] == "message-1"
    assert resolved["run_id"] == "run-1"
    assert resolved["request_id"] == "request-1"
    assert resolved["decision"] == "allow_once"


@pytest.mark.asyncio
async def test_workflow_child_permission_waits_for_exact_launch_binding() -> None:
    manager = _Manager()
    registry = WorkflowPermissionDeliveryBindingRegistry()
    delivered: list[WorkflowPermissionDelivery] = []

    async def _deliver(item: WorkflowPermissionDelivery) -> None:
        delivered.append(item)

    context_store = delivery_context_store(
        {
            "parent-run": {
                "conversation_id": "conversation-1",
                "message_id": "workflow-launch-message",
                "agent_id": "agent-a",
                "kernel_session_id": "parent-session",
                "discard_empty_completion": True,
            }
        }
    )
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=context_store,
        workflow_permission_bindings=registry,
        workflow_permission_delivery=_deliver,
    )
    await _observe(
        observer,
        {
            "run_id": "parent-run",
            "event": "tool_start",
            "call_id": "workflow-call",
            "name": "Workflow",
            "arguments": {"script": "async def main(): pass"},
        },
    )
    buffered = registry.accept_event(
        parent_session_id="parent-session",
        event={
            "event": "permission_request",
            "workflow_run_id": "wf_123",
            "agent_call_id": "agent-call-1",
            "request_id": "request-child",
            "tool_name": "bash",
            "tool_input": {"command": "pwd"},
            "question": "Allow bash?",
            "options": [{"id": "allow_once", "label": "Allow once"}],
            "_id": 8,
        },
    )
    assert buffered == ()

    await _observe(
        observer,
        {
            "run_id": "parent-run",
            "event": "tool_end",
            "call_id": "workflow-call",
            "name": "Workflow",
            "event_metadata": {
                "parent_session_id": "parent-session",
                "parent_run_id": "parent-run",
                "parent_tool_call_id": "workflow-call",
                "workflow_run_id": "wf_123",
            },
        },
    )

    assert len(delivered) == 1
    assert delivered[0].event["request_id"] == "request-child"
    assert delivered[0].anchor.message_id == "workflow-launch-message"
    context = context_store.get("parent-run")
    assert context is not None
    assert context.visible_reply_committed is True


@pytest.mark.asyncio
async def test_foreground_observer_skips_tagged_workflow_child_permission() -> None:
    manager = _Manager()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "parent-run": {
                    "conversation_id": "conversation-1",
                    "message_id": "workflow-launch-message",
                    "agent_id": "agent-a",
                    "kernel_session_id": "parent-session",
                }
            }
        ),
    )

    await _observe(
        observer,
        {
            "run_id": "parent-run",
            "event": "permission_request",
            "workflow_run_id": "wf_123",
            "agent_call_id": "agent-call-1",
            "request_id": "request-child",
            "tool_name": "bash",
        },
    )

    assert all(
        payload.get("kind") != "permission_request" for _, payload in manager.sent
    )


@pytest.mark.asyncio
async def test_bound_workflow_child_permission_reuses_web_and_external_surfaces() -> (
    None
):
    manager = _Manager()
    external_request = MagicMock()
    external_resolved = MagicMock()
    deliver = build_workflow_permission_delivery(
        im_connection_manager_factory=lambda: manager,
        external_permission_request_sender=external_request,
        external_permission_resolved_sender=external_resolved,
    )
    anchor = WorkflowPermissionDeliveryAnchor(
        parent_session_id="parent-session",
        parent_run_id="parent-run",
        parent_tool_call_id="workflow-call",
        conversation_id="conversation-1",
        message_id="workflow-launch-message",
        external_metadata={
            "channel_name": "feishu:agent-a",
            "target_chat_id": "feishu:group-1",
        },
    )
    request_event = {
        "event": "permission_request",
        "workflow_run_id": "wf_123",
        "agent_call_id": "agent-call-1",
        "request_id": "request-child",
        "tool_name": "bash",
        "tool_input": {"command": "pwd"},
        "question": "Allow bash?",
        "options": [{"id": "allow_once", "label": "Allow once"}],
    }
    resolved_event = {
        "event": "permission_resolved",
        "workflow_run_id": "wf_123",
        "agent_call_id": "agent-call-1",
        "request_id": "request-child",
        "decision": "allow_once",
    }

    await deliver(WorkflowPermissionDelivery(anchor=anchor, event=request_event))
    await deliver(WorkflowPermissionDelivery(anchor=anchor, event=resolved_event))

    request_frame = next(
        payload
        for _, payload in manager.sent
        if payload["kind"] == "permission_request"
    )
    resolved_frame = next(
        payload
        for _, payload in manager.sent
        if payload["kind"] == "permission_resolved"
    )
    assert request_frame["message_id"] == "workflow-launch-message"
    assert request_frame["permission_request"]["request_id"] == "request-child"
    assert resolved_frame == {
        "kind": "permission_resolved",
        "message_id": "workflow-launch-message",
        "request_id": "request-child",
        "decision": "allow_once",
        "run_id": "parent-run",
    }
    external_request.assert_called_once()
    external_resolved.assert_called_once_with(
        "request-child",
        "allow_once",
        {
            "channel_name": "feishu:agent-a",
            "target_chat_id": "feishu:group-1",
        },
    )


@pytest.mark.asyncio
async def test_external_permission_request_does_not_require_im_message_anchor() -> None:
    manager = _Manager()
    external_sender = MagicMock()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "conversation-1",
                    "message_id": "",
                    "agent_id": "agent-a",
                    "trigger_source": "feishu",
                    "reply_channel_name": "feishu:agent-a",
                    "reply_target_chat_id": "feishu:cli_a:group:oc_group",
                    "feishu_message_id": "message-origin",
                }
            }
        ),
        external_permission_request_sender=external_sender,
    )

    await _observe(
        observer,
        {
            "run_id": "run-1",
            "event": "permission_request",
            "request_id": "request-1",
            "tool_name": "bash",
            "tool_input": {"command": "pwd"},
            "question": "Allow bash?",
            "options": [{"id": "allow_once", "label": "Allow once"}],
        },
    )

    assert [
        payload
        for kind, payload in manager.sent
        if kind == "node.streaming_delta"
        and payload.get("kind") == "permission_request"
    ] == []
    request, metadata = external_sender.call_args.args
    assert request["request_id"] == "request-1"
    assert request["tool_name"] == "bash"
    assert metadata["channel_name"] == "feishu:agent-a"
    assert metadata["target_chat_id"] == "feishu:cli_a:group:oc_group"


@pytest.mark.asyncio
async def test_external_permission_resolution_updates_channel_surface() -> None:
    manager = _Manager()
    external_resolver = MagicMock()
    observer = build_kernel_event_observer(
        im_connection_manager_factory=lambda: manager,
        run_context_store=delivery_context_store(
            {
                "run-1": {
                    "conversation_id": "conversation-1",
                    "message_id": "message-1",
                    "agent_id": "agent-a",
                    "trigger_source": "feishu",
                    "reply_channel_name": "feishu:agent-a",
                    "reply_target_chat_id": "feishu:cli_a:group:oc_group",
                }
            }
        ),
        external_permission_resolved_sender=external_resolver,
    )

    await _observe(
        observer,
        {
            "run_id": "run-1",
            "event": "permission_resolved",
            "request_id": "request-1",
            "decision": "deny",
        },
    )

    external_resolver.assert_called_once_with(
        "request-1",
        "deny",
        {
            "channel_name": "feishu:agent-a",
            "target_chat_id": "feishu:cli_a:group:oc_group",
        },
    )
