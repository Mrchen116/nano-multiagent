import pytest

from nano_multiagent.core.types import Message, TurnResult
from nano_multiagent.server.deps import APIError
from nano_multiagent.server.routes.session import _to_message_response


def test_to_message_response_uses_assistant_message_contract() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(
            Message(message_id="msg_user", role="user", content="hello"),
            Message(message_id="msg_assistant", role="assistant", content="hi"),
        ),
        completed=True,
        stop_reason="completed",
    )

    payload = _to_message_response(result)

    assert payload["session_id"] == "sess_unit"
    assert payload["turn_id"] == "turn_unit"
    assert payload["message"]["message_id"] == "msg_assistant"
    assert payload["message"]["role"] == "assistant"
    assert payload["message"]["content"] == "hi"
    assert payload["completed"] is True
    assert payload["stop_reason"] == "completed"


def test_to_message_response_raises_when_no_assistant_message() -> None:
    result = TurnResult(
        session_id="sess_unit",
        turn_id="turn_unit",
        messages=(Message(message_id="msg_user", role="user", content="only-user"),),
    )

    with pytest.raises(APIError) as exc_info:
        _to_message_response(result)

    assert exc_info.value.code == "invalid_runtime_response"
