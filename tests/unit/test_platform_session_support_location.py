"""Verify retired session façades cannot reappear as alternate owners."""

from importlib.util import find_spec

def test_platform_session_service_is_retired() -> None:
    assert find_spec("agent.platform.persistence.session.service") is None


def test_legacy_session_root_is_removed() -> None:
    assert find_spec("agent.session") is None
