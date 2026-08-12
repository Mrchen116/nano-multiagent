"""Claude-compatible chained-v2 Workflow resume signatures."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_options(options: Mapping[str, Any]) -> str:
    """Serialize behavior options canonically while omitting absent values."""

    present = {key: value for key, value in options.items() if value is not None}
    return json.dumps(
        present, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def chained_resume_key(
    previous_key: str, prompt: str, options: Mapping[str, Any]
) -> str:
    """Return the next v2 key in a run-global Agent call signature chain."""

    value = f"{previous_key}\0{prompt}\0{canonical_options(options)}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
