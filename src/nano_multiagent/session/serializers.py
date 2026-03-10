"""Compatibility shim for canonical platform session serializers."""

from nano_multiagent.platform.persistence.session.serializers import (
    ENTRY_SERIALIZATION_VERSION,
    SNAPSHOT_SERIALIZATION_VERSION,
    deserialize_entry,
    deserialize_snapshot,
    serialize_entry,
    serialize_snapshot,
)

__all__ = [
    "ENTRY_SERIALIZATION_VERSION",
    "SNAPSHOT_SERIALIZATION_VERSION",
    "serialize_entry",
    "deserialize_entry",
    "serialize_snapshot",
    "deserialize_snapshot",
]
