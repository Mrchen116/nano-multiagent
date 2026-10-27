"""Declarative PA scenarios; no product imports or model-generated verdicts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ASSETS = Path(__file__).resolve().parents[3] / "evals" / "general-personal-agent"
SMOKE = "M01 M02 M06 M09 P01 P02 P03 P04 I05 W01 W03 W04 W06 D08 U01 S03".split()


def digest(path: Path) -> str:
    """Return the SHA-256 of the exact evidence bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog() -> dict:
    """Load and validate one explicit adapter for every source scenario."""
    scenarios = yaml.safe_load((ASSETS / "scenarios.yaml").read_text())["cases"]
    adapters = json.loads((ASSETS / "adapters.json").read_text())["cases"]
    ids = [case["id"] for case in scenarios]
    if len(ids) != 58 or len(set(ids)) != 58 or set(ids) != set(adapters):
        raise ValueError("source scenarios and adapters must map exactly 58 unique IDs")
    for case in scenarios:
        adapter = adapters[case["id"]]
        if not adapter["steps"] or not adapter["review"]:
            raise ValueError(f"empty adapter: {case['id']}")
        keys = []
        for step in adapter["steps"]:
            if step["op"] not in {
                "send",
                "observe",
                "checkpoint",
                "disable_memory",
                "exclude_source",
            }:
                raise ValueError(f"unknown operation: {step}")
            if step["op"] == "send" and (
                not step["text"]
                or step["actor"] not in {"owner", "colleague", "family", "external"}
            ):
                raise ValueError(f"invalid message: {step}")
            if step["op"] == "checkpoint":
                keys.append(step["key"])
                if not step["instruction"]:
                    raise ValueError(
                        "checkpoint requires a real-world action description"
                    )
        if len(set(keys)) != len(keys):
            raise ValueError("checkpoint keys must be unique within each case")
    return {case["id"]: {**case, **adapters[case["id"]]} for case in scenarios}


def select(value: str) -> list[str]:
    """Resolve an explicit ID list, smoke, or all in source order."""
    cases = catalog()
    ids = (
        list(cases)
        if value == "all"
        else SMOKE
        if value == "smoke"
        else value.split(",")
    )
    if not ids or len(set(ids)) != len(ids) or set(ids) - cases.keys():
        raise ValueError("unknown or duplicated scenario ID")
    return ids


def write_json(path: Path, value: object) -> None:
    """Persist a complete JSON evidence object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
