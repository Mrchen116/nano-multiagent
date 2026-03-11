import re

from agent.core.ids import IdGenerator, make_message_id, make_session_id, make_tool_call_id, make_turn_id


def test_default_id_factory_generates_prefixed_ids() -> None:
    assert re.match(r"^sess_[0-9a-f]{16}$", make_session_id())
    assert re.match(r"^turn_[0-9a-f]{16}$", make_turn_id())
    assert re.match(r"^msg_[0-9a-f]{16}$", make_message_id())
    assert re.match(r"^call_[0-9a-f]{16}$", make_tool_call_id())


def test_id_generator_supports_custom_token_factory() -> None:
    generator = IdGenerator(token_factory=lambda: "fixedtoken")

    assert generator.make_session_id() == "sess_fixedtoken"
    assert generator.make_turn_id() == "turn_fixedtoken"
