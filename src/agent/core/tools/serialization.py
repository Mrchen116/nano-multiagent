"""Serialization helpers for tool results."""

import json
from typing import Any


def json_serialize(output: Any) -> str:
    """Serialize output as compact JSON. Falls back to str() on non-serializable data."""
    try:
        return json.dumps(
            output, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
    except TypeError:
        return str(output)
