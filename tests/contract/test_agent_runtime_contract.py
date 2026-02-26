from dataclasses import fields

from nano_multiagent.agent.runtime import AgentRuntime
from nano_multiagent.session.entries import SessionEntry, new_turn_appended_entry


def test_runtime_public_methods_are_stable() -> None:
    assert callable(getattr(AgentRuntime, "run", None))
    assert callable(getattr(AgentRuntime, "continue_turn", None))
    assert callable(getattr(AgentRuntime, "get_session", None))


def test_turn_appended_entry_payload_contract() -> None:
    entry = new_turn_appended_entry(
        session_id="sess_contract",
        turn_id="turn_1",
        role="assistant",
        content="ok",
        message_id="msg_1",
    )

    assert isinstance(entry, SessionEntry)
    assert entry.kind.value == "session.turn.appended"
    assert entry.data == {
        "turn_id": "turn_1",
        "message_id": "msg_1",
        "role": "assistant",
        "content": "ok",
        "parts": [],
        "metadata": {},
    }


def test_session_entry_fields_are_stable_for_turn_event() -> None:
    assert [field.name for field in fields(SessionEntry)] == [
        "entry_id",
        "session_id",
        "created_at",
        "kind",
        "data",
    ]
