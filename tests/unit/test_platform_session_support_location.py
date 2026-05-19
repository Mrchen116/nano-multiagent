"""Verify platform session support modules are the canonical home for wiring helpers."""

from importlib.util import find_spec

from agent.platform.persistence.session.service import SessionService


def test_platform_session_service_is_canonical_home() -> None:
    assert SessionService.__module__ == "agent.platform.persistence.session.service"


def test_legacy_session_root_is_removed() -> None:
    assert find_spec("agent.session") is None
