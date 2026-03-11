"""Verify platform session support modules are the canonical home for wiring helpers."""

from importlib.util import find_spec

from agent.platform.persistence.session.serializers import (
    deserialize_entry,
    deserialize_snapshot,
    serialize_entry,
    serialize_snapshot,
)
from agent.platform.persistence.session.service import SessionService



def test_platform_session_support_modules_are_canonical_home() -> None:
    assert SessionService.__module__ == "agent.platform.persistence.session.service"
    assert serialize_entry.__module__ == "agent.platform.persistence.session.serializers"
    assert deserialize_entry.__module__ == "agent.platform.persistence.session.serializers"
    assert serialize_snapshot.__module__ == "agent.platform.persistence.session.serializers"
    assert deserialize_snapshot.__module__ == "agent.platform.persistence.session.serializers"



def test_legacy_session_root_is_removed() -> None:
    assert find_spec("agent.session") is None
