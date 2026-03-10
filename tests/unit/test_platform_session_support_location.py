"""Verify platform session support modules are the canonical home for wiring helpers."""

from nano_multiagent.platform.persistence.session.serializers import (
    deserialize_entry,
    deserialize_snapshot,
    serialize_entry,
    serialize_snapshot,
)
from nano_multiagent.platform.persistence.session.service import SessionService
from nano_multiagent.session.serializers import (
    deserialize_entry as legacy_deserialize_entry,
)
from nano_multiagent.session.serializers import (
    deserialize_snapshot as legacy_deserialize_snapshot,
)
from nano_multiagent.session.serializers import serialize_entry as legacy_serialize_entry
from nano_multiagent.session.serializers import serialize_snapshot as legacy_serialize_snapshot
from nano_multiagent.session.service import SessionService as LegacySessionService


def test_platform_session_support_modules_are_canonical_home() -> None:
    assert SessionService.__module__ == "nano_multiagent.platform.persistence.session.service"
    assert serialize_entry.__module__ == "nano_multiagent.platform.persistence.session.serializers"
    assert deserialize_entry.__module__ == "nano_multiagent.platform.persistence.session.serializers"
    assert serialize_snapshot.__module__ == "nano_multiagent.platform.persistence.session.serializers"
    assert deserialize_snapshot.__module__ == "nano_multiagent.platform.persistence.session.serializers"



def test_old_session_support_paths_are_compat_shims() -> None:
    assert LegacySessionService is SessionService
    assert legacy_serialize_entry is serialize_entry
    assert legacy_deserialize_entry is deserialize_entry
    assert legacy_serialize_snapshot is serialize_snapshot
    assert legacy_deserialize_snapshot is deserialize_snapshot
