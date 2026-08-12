"""Exact Workflow child-permission routing across foreground/background boundaries."""

from personal_assistant.gateway.workflow_permission_bindings import (
    WorkflowPermissionDeliveryAnchor,
    WorkflowPermissionDeliveryBindingRegistry,
)


def _anchor(call_id: str, message_id: str) -> WorkflowPermissionDeliveryAnchor:
    return WorkflowPermissionDeliveryAnchor(
        parent_session_id="session-1",
        parent_run_id=f"parent-{call_id}",
        parent_tool_call_id=call_id,
        conversation_id="conversation-1",
        message_id=message_id,
        external_metadata={"channel_name": "feishu:test", "target_chat_id": call_id},
    )


def _request(run_id: str, agent_call_id: str, request_id: str, seq: int) -> dict:
    return {
        "event": "permission_request",
        "workflow_parent_session_id": "session-1",
        "workflow_run_id": run_id,
        "agent_call_id": agent_call_id,
        "request_id": request_id,
        "tool_name": "bash",
        "tool_input": {"command": "pwd"},
        "question": "Allow bash?",
        "options": [{"id": "allow_once", "label": "Allow once"}],
        "_id": seq,
    }


def _resolved(run_id: str, agent_call_id: str, request_id: str, seq: int) -> dict:
    return {
        "event": "permission_resolved",
        "workflow_parent_session_id": "session-1",
        "workflow_run_id": run_id,
        "agent_call_id": agent_call_id,
        "request_id": request_id,
        "decision": "allow_once",
        "_id": seq,
    }


def test_two_workflows_in_one_session_keep_exact_launch_anchors() -> None:
    registry = WorkflowPermissionDeliveryBindingRegistry()
    registry.register_pre_anchor(_anchor("call-a", "message-a"))
    registry.register_pre_anchor(_anchor("call-b", "message-b"))
    assert (
        registry.bind_run(
            parent_session_id="session-1",
            parent_tool_call_id="call-a",
            workflow_run_id="wf_a",
        )
        == ()
    )
    assert (
        registry.bind_run(
            parent_session_id="session-1",
            parent_tool_call_id="call-b",
            workflow_run_id="wf_b",
        )
        == ()
    )

    request_a = registry.accept_event(
        parent_session_id="session-1",
        event=_request("wf_a", "agent-a", "request-a", 10),
    )
    request_b = registry.accept_event(
        parent_session_id="session-1",
        event=_request("wf_b", "agent-b", "request-b", 11),
    )
    resolved_a = registry.accept_event(
        parent_session_id="session-1",
        event=_resolved("wf_a", "agent-a", "request-a", 12),
    )
    resolved_b = registry.accept_event(
        parent_session_id="session-1",
        event=_resolved("wf_b", "agent-b", "request-b", 13),
    )

    assert request_a[0].anchor.message_id == "message-a"
    assert request_b[0].anchor.message_id == "message-b"
    assert resolved_a[0].anchor.message_id == "message-a"
    assert resolved_b[0].anchor.message_id == "message-b"


def test_request_before_anchor_flushes_once_after_machine_binding() -> None:
    registry = WorkflowPermissionDeliveryBindingRegistry()
    request = _request("wf_early", "agent-1", "request-1", 7)

    assert registry.accept_event(parent_session_id="session-1", event=request) == ()
    registry.register_pre_anchor(_anchor("call-early", "message-early"))
    deliveries = registry.bind_run(
        parent_session_id="session-1",
        parent_tool_call_id="call-early",
        workflow_run_id="wf_early",
    )

    assert [(item.event["event"], item.anchor.message_id) for item in deliveries] == [
        ("permission_request", "message-early")
    ]
    assert registry.accept_event(parent_session_id="session-1", event=request) == ()


def test_terminal_before_anchor_cleans_after_late_binding() -> None:
    registry = WorkflowPermissionDeliveryBindingRegistry()

    assert (
        registry.accept_event(
            parent_session_id="session-1",
            event={
                "event": "workflow_run_updated",
                "workflow_run_id": "wf_terminal_first",
                "status": "failed",
                "_id": 20,
            },
        )
        == ()
    )
    assert registry.has_run("wf_terminal_first") is True

    registry.register_pre_anchor(_anchor("call-late", "message-late"))
    assert (
        registry.bind_run(
            parent_session_id="session-1",
            parent_tool_call_id="call-late",
            workflow_run_id="wf_terminal_first",
        )
        == ()
    )
    assert registry.has_run("wf_terminal_first") is False


def test_resolved_before_anchor_waits_for_exact_request_binding() -> None:
    registry = WorkflowPermissionDeliveryBindingRegistry()
    resolved = _resolved("wf_reordered", "agent-1", "request-1", 9)
    request = _request("wf_reordered", "agent-1", "request-1", 8)

    assert registry.accept_event(parent_session_id="session-1", event=resolved) == ()
    assert registry.accept_event(parent_session_id="session-1", event=request) == ()
    registry.register_pre_anchor(_anchor("call-reordered", "message-reordered"))
    deliveries = registry.bind_run(
        parent_session_id="session-1",
        parent_tool_call_id="call-reordered",
        workflow_run_id="wf_reordered",
    )

    assert [item.event["event"] for item in deliveries] == [
        "permission_request",
        "permission_resolved",
    ]
    assert {item.anchor.message_id for item in deliveries} == {"message-reordered"}
