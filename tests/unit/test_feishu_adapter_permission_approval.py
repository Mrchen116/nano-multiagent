"""Rendering and first-wins behavior for Feishu permission cards."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lark_oapi")

from personal_assistant.channels.feishu.adapter import FeishuAdapter
from personal_assistant.channels.feishu.client import FeishuCardActionEvent
from personal_assistant.gateway.group_context_store import GroupContextStore

_REASON_FIELD = "nano_permission_reason"


def _adapter(decision_callback: MagicMock) -> FeishuAdapter:
    adapter = FeishuAdapter(
        app_id="cli_a",
        app_secret="secret",
        name="feishu:plato",
        owner_open_id="ou_owner",
        permission_decision_callback=decision_callback,
        group_context_store=MagicMock(spec=GroupContextStore),
    )
    adapter.start(MagicMock())
    return adapter


def _request() -> dict[str, object]:
    return {
        "request_id": "request-1",
        "tool_name": "bash",
        "tool_input": {
            "command": "cat ~/.ssh/id_rsa",
            "path": ".gitconfig",
            "token": "secret-token-value",
        },
        "question": "Allow bash?",
        "options": [
            {"id": "allow_once", "label": "Allow once"},
            {"id": "deny", "label": "Deny"},
            {"id": "allow_session", "label": "Allow for session"},
        ],
        "status": "pending",
    }


def _long_tool_input() -> dict[str, str]:
    return {
        "path": (
            "/workspace/projects/example-service/config/releases/"
            "production/approval-policy.yaml"
        ),
        "oldText": (
            "## Existing approval policy\n"
            "- retry_count: 2; timeout_seconds: 30; preserve_atomic_writes: true\n"
            "- audit_mode: summary"
        ),
        "newText": (
            "## Updated approval policy\n"
            "- retry_count: 3\n"
            "- timeout_seconds: 45\n"
            "- preserve_atomic_writes: true\n"
            "- validate_schema: true\n"
            "- emit_audit_event: true\n"
            "- rollback_on_failure: true\n"
            "- audit_mode: full"
        ),
    }


def _action_value(card: object, decision: str) -> dict[str, object]:
    if isinstance(card, dict):
        value = card.get("value")
        if isinstance(value, dict) and value.get("decision") == decision:
            return value
        for child in card.values():
            try:
                return _action_value(child, decision)
            except LookupError:
                pass
    elif isinstance(card, list):
        for child in card:
            try:
                return _action_value(child, decision)
            except LookupError:
                pass
    raise LookupError(decision)


def _event(
    action_value: dict[str, object],
    *,
    operator_open_id: str = "ou_owner",
    reason: str = "",
) -> FeishuCardActionEvent:
    return FeishuCardActionEvent(
        action_value=action_value,
        operator_open_id=operator_open_id,
        operator_user_id="user-operator",
        open_chat_id="oc_group",
        form_value={_REASON_FIELD: reason} if reason else {},
    )


def _input_fields(card: dict[str, object]) -> list[dict[str, object]]:
    elements = card["elements"]
    assert isinstance(elements, list)
    return [
        element
        for element in elements
        if str(element.get("element_id", "")).startswith("inputField")
    ]


def _field_content(field: dict[str, object]) -> str:
    if field["tag"] == "collapsible_panel":
        return str(field["header"]["title"]["content"])
    return "\n".join(
        str(element["content"]) for element in field["columns"][0]["elements"]
    )


def _field_body(field: dict[str, object]) -> str:
    assert field["tag"] == "collapsible_panel"
    return str(field["elements"][0]["content"])


def _escaped_input_value(text: str) -> str:
    return "\n".join(
        "".join(
            char if char.isalnum() or char in " -." else f"&#{ord(char)};"
            for char in line
        )
        for line in text.split("\n")
    )


def _content_text(card: dict[str, object]) -> str:
    contents: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            content = value.get("content")
            if isinstance(content, str):
                contents.append(content)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(card)
    return "\n".join(contents)


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_is_idempotent_and_only_owner_can_decide(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=True)
    adapter = _adapter(callback)

    assert adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    assert adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    client.send_interactive_message.assert_called_once()
    card = client.send_interactive_message.call_args.kwargs["card"]
    allow = _action_value(card, "allow_once")

    assert (
        adapter._handle_card_action(_event(allow, operator_open_id="ou_not_owner"))
        is None
    )
    callback.assert_not_called()
    adapter._handle_card_action(_event(allow))
    adapter._handle_card_action(_event(allow))

    callback.assert_called_once()
    decision = callback.call_args.args[0]
    assert decision["request_id"] == "request-1"
    assert decision["decision"] == "allow_once"
    assert decision["operator_open_id"] == "ou_owner"


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_cards_render_any_tool_input_as_fields(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-1",
        request=_request(),
    )

    pending_card = client.send_interactive_message.call_args.kwargs["card"]
    pending_elements = pending_card["elements"]
    assert (
        "**Tool:** <text_tag color='neutral'>bash</text_tag>"
        in pending_elements[0]["content"]
    )
    assert pending_elements[1] == {"tag": "hr"}
    assert pending_elements[2]["content"] == "**Input**"
    pending_fields = _input_fields(pending_card)
    assert [field["tag"] for field in pending_fields] == [
        "column_set",
        "column_set",
        "column_set",
    ]
    assert [_field_content(field) for field in pending_fields] == [
        "**command · 1 line**\ncat &#126;&#47;.ssh&#47;id&#95;rsa",
        "**path · 1 line**\n.gitconfig",
        "**token · 1 line**\nsecret-token-value",
    ]
    assert all(field["background_style"] == "grey-50" for field in pending_fields)
    assert all(field["columns"][0]["padding"] == "8px 12px" for field in pending_fields)
    assert all(len(field["columns"][0]["elements"]) == 2 for field in pending_fields)
    assert '{"command":' not in str(pending_card)

    reason_card = adapter._handle_card_action(
        _event(_action_value(pending_card, "deny"))
    )
    assert reason_card is not None
    reason_elements = reason_card["elements"]
    assert reason_elements[1] == {"tag": "hr"}
    assert reason_elements[2]["content"] == "**Input**"
    assert [_field_content(field) for field in _input_fields(reason_card)] == [
        "**command · 1 line**\ncat &#126;&#47;.ssh&#47;id&#95;rsa",
        "**path · 1 line**\n.gitconfig",
        "**token · 1 line**\nsecret-token-value",
    ]


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_bounds_large_generic_input(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))
    request = _request()
    request["tool_input"] = {
        "payload": list(range(1000)),
        **{f"field_{index}": "x" * 200 for index in range(20)},
    }

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-1",
        request=request,
    )

    card = client.send_interactive_message.call_args.kwargs["card"]
    input_fields = _input_fields(card)
    assert len(input_fields) == 12
    assert "9 additional fields truncated" in str(card)
    assert "11 lines" in str(input_fields[0])
    assert input_fields[0]["tag"] == "collapsible_panel"
    assert len(str(card)) < 12_000


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_bounds_twelve_large_values_after_markdown_escaping(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))
    request = _request()
    patterns = [
        "a" * 5_000,
        ("**[danger](https://example.test/path)** @owner\n" * 120)[:5_000],
        "😀" * 5_000,
    ]
    request["tool_input"] = {
        f"field_{index}": patterns[index % len(patterns)] for index in range(12)
    }

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-1",
        request=request,
    )

    card = client.send_interactive_message.call_args.kwargs["card"]
    fields = _input_fields(card)
    assert len(fields) == 12
    assert all(field["tag"] == "collapsible_panel" for field in fields)
    assert all(_field_body(field).endswith("... truncated") for field in fields)
    serialized = json.dumps(card, ensure_ascii=False, separators=(",", ":")).encode()
    assert len(serialized) < 30_000


@pytest.mark.parametrize("tool_name", ["edit", "custom_transform"])
@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_compacts_realistic_long_input_for_every_tool(
    client_class: MagicMock,
    tool_name: str,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))
    request = _request()
    request["tool_name"] = tool_name
    request["tool_input"] = _long_tool_input()

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-1",
        request=request,
    )

    card = client.send_interactive_message.call_args.kwargs["card"]
    input_fields = _input_fields(card)
    visible_text = _content_text(card)
    metadata = card["elements"][0]["content"]
    assert f"<text_tag color='neutral'>{tool_name}</text_tag>" in metadata
    assert "&#95;" not in metadata
    assert len(input_fields) == 3
    assert all(field["tag"] == "collapsible_panel" for field in input_fields)
    assert all(field["expanded"] is False for field in input_fields)
    assert all(field["background_color"] == "grey" for field in input_fields)
    assert all(
        field["border"] == {"color": "grey", "corner_radius": "5px"}
        for field in input_fields
    )
    assert all("padding" not in field["header"] for field in input_fields)
    assert all(field["padding"] == "0px 12px 10px 12px" for field in input_fields)
    assert all(field["vertical_spacing"] == "4px" for field in input_fields)
    assert all(
        field["header"]["icon"]
        == {
            "tag": "standard_icon",
            "token": "down-small-ccm_outlined",
            "size": "16px 16px",
        }
        for field in input_fields
    )
    assert all(field["header"]["icon_position"] == "right" for field in input_fields)
    assert all(field["header"]["icon_expanded_angle"] == 180 for field in input_fields)
    assert [field["elements"][0]["content"] for field in input_fields] == [
        _escaped_input_value(value) for value in _long_tool_input().values()
    ]
    headers = [_field_content(field) for field in input_fields]
    assert "path · 1 line" in headers[0]
    assert "oldText · 3 lines" in headers[1]
    assert "newText · 8 lines" in headers[2]
    assert all(header.count("\n") <= 2 for header in headers)
    assert all(max(map(len, header.splitlines())) <= 48 for header in headers)
    assert "approval-policy.yaml" in visible_text
    assert "permission_input_detail" not in str(card)
    assert "Show full value" not in str(card)
    assert "Show less" not in str(card)
    assert "`" not in visible_text
    assert "↵" not in visible_text
    assert '{"path":' not in visible_text


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_card_preserves_newlines_and_markdown_literals_without_fences(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))
    request = _request()
    request["tool_input"] = {
        "before": "value",
        "after": "value\n",
        "command**\n**Decision:** approved": "echo `date`",
    }

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-1",
        request=request,
    )

    card = client.send_interactive_message.call_args.kwargs["card"]
    contents = [_field_content(field) for field in _input_fields(card)]
    assert contents[0] == "**before · 1 line**\nvalue"
    assert contents[1] == "**after · 2 lines**\nvalue\n"
    assert "**Decision:** approved" not in contents[2]
    assert "&#42;" in contents[2]
    assert contents[2].endswith("\necho &#96;date&#96;")
    assert "`" not in "\n".join(contents)
    assert "↵" not in "\n".join(contents)


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_group_permission_card_hides_input_values(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    adapter = _adapter(MagicMock(return_value=True))

    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )

    card = client.send_interactive_message.call_args.kwargs["card"]
    assert "secret-token-value" not in str(card)
    assert "cat ~/.ssh/id_rsa" not in str(card)
    assert "**command · 1 line**" in str(card)
    assert "hidden in group chat" in str(card)
    assert "internal IM approval" in str(card)
    assert "collapsible_panel" not in str(card)
    assert "permission_input_detail" not in str(card)
    assert "Show full value" not in str(card)


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_permission_metadata_is_literal_in_dm_and_private_in_group(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    question = (
        "Write **/private/approval-path.md** because [reason](https://example.test) "
        "@owner"
    )
    unsafe_tool_name = "custom</text_tag><text_tag color='red'>&"

    dm_request = _request()
    dm_request["request_id"] = "request-dm"
    dm_request["tool_name"] = unsafe_tool_name
    dm_request["question"] = question
    dm_adapter = _adapter(MagicMock(return_value=True))
    dm_adapter.send_permission_request(
        target_chat_id="feishu:cli_a:dm:ou_owner",
        run_id="run-dm",
        request=dm_request,
    )
    dm_pending = client.send_interactive_message.call_args.kwargs["card"]
    dm_metadata = dm_pending["elements"][0]["content"]
    assert question not in dm_metadata
    assert "&#42;&#42;&#47;private&#47;approval-path.md&#42;&#42;" in dm_metadata
    assert "&#64;owner" in dm_metadata
    assert "<text_tag" not in dm_metadata
    assert "</text_tag>" not in dm_metadata
    dm_reason = dm_adapter._handle_card_action(
        _event(_action_value(dm_pending, "deny"))
    )
    assert dm_reason is not None
    assert dm_reason["elements"][0]["content"] == dm_metadata

    group_request = _request()
    group_request["request_id"] = "request-group"
    group_request["tool_name"] = unsafe_tool_name
    group_request["question"] = question
    group_adapter = _adapter(MagicMock(return_value=True))
    group_adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-group",
        request=group_request,
    )
    group_pending = client.send_interactive_message.call_args.kwargs["card"]
    group_metadata = group_pending["elements"][0]["content"]
    assert "**Request:** Review details in internal IM." in group_metadata
    assert question not in group_metadata
    assert "/private/approval-path.md" not in group_metadata
    assert "reason" not in group_metadata
    assert "@owner" not in group_metadata
    assert "<text_tag" not in group_metadata
    assert "</text_tag>" not in group_metadata
    group_reason = group_adapter._handle_card_action(
        _event(_action_value(group_pending, "deny"))
    )
    assert group_reason is not None
    assert group_reason["elements"][0]["content"] == group_metadata


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_deny_reason_reaches_kernel_without_exposing_operator_identity(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=True)
    adapter = _adapter(callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    pending_card = client.send_interactive_message.call_args.kwargs["card"]
    reason_card = adapter._handle_card_action(
        _event(_action_value(pending_card, "deny"))
    )
    assert reason_card is not None

    resolved_card = adapter._handle_card_action(
        _event(_action_value(reason_card, "deny"), reason="  too risky  ")
    )

    decision = callback.call_args.args[0]
    assert decision["decision"] == "deny"
    assert decision["reason"] == "too risky"
    assert resolved_card is not None
    assert "ou_owner" not in str(resolved_card)
    assert "user-operator" not in str(resolved_card)


@patch("personal_assistant.channels.feishu.adapter.FeishuClient")
def test_im_resolution_or_kernel_rejection_prevents_later_card_decision(
    client_class: MagicMock,
) -> None:
    client = client_class.return_value
    client.send_interactive_message.return_value = "card-message-1"
    callback = MagicMock(return_value=False)
    adapter = _adapter(callback)
    adapter.send_permission_request(
        target_chat_id="feishu:cli_a:group:oc_group",
        run_id="run-1",
        request=_request(),
    )
    card = client.send_interactive_message.call_args.kwargs["card"]
    allow = _action_value(card, "allow_once")

    first_response = adapter._handle_card_action(_event(allow))
    adapter._handle_card_action(_event(allow))

    callback.assert_called_once()
    assert first_response is not None
    assert "already" in str(first_response).lower()
