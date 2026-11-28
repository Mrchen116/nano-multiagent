"""Unit tests for DolphinBench runner slicing, timezones, and app workspace wiring."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, rel_path: str):
    path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


run_mod = _load_module("dolphinbench_run", "evals/dolphinbench/run.py")
suite_mod = _load_module("dolphinbench_run_suite", "evals/dolphinbench/run_suite.py")


def test_parse_range_bounds_and_defaults() -> None:
    """Slice bounds must accept 1-based inclusive ranges and reject inverted inputs."""
    assert run_mod.parse_range(None, 3400) == (1, 3400)
    assert run_mod.parse_range("1:10", 3400) == (1, 10)
    assert run_mod.parse_range(":25", 3400) == (1, 25)
    assert run_mod.parse_range("3390:", 3400) == (3390, 3400)
    with pytest.raises(ValueError, match="START:END"):
        run_mod.parse_range("10", 3400)
    with pytest.raises(ValueError, match="Invalid --session-range"):
        run_mod.parse_range("20:10", 3400)


def test_parse_iso_and_next_nightly_slot_respect_persona_timezone() -> None:
    """Date-only strings and nightly 03:05 cutoffs must follow persona local DST rules."""
    winter_ms = run_mod.parse_iso_ms("2023-01-09", "America/Los_Angeles")
    summer_ms = run_mod.parse_iso_ms("2023-07-10", "America/Los_Angeles")
    ny_winter_ms = run_mod.parse_iso_ms("2023-01-09", "America/New_York")
    # New York 09:00 EST is 3 hours earlier in UTC than Los Angeles 09:00 PST.
    assert winter_ms - ny_winter_ms == 3 * 3600 * 1000
    # PDT (-07:00) vs PST (-08:00) shifts local 09:00 by 1 hour modulo 24h.
    assert (winter_ms // 1000) % 86400 != (summer_ms // 1000) % 86400

    slot_ms = run_mod.next_nightly_slot_ms(
        "2023-01-09T14:20:00-08:00", "America/Los_Angeles"
    )
    from datetime import datetime

    slot_dt = datetime.fromtimestamp(slot_ms / 1000, tz=ZoneInfo("America/Los_Angeles"))
    assert (slot_dt.year, slot_dt.month, slot_dt.day, slot_dt.hour, slot_dt.minute) == (
        2023,
        1,
        10,
        3,
        5,
    )


def test_select_tests_for_window_filters_load_bearing_facts() -> None:
    """Truncated slices select only tests whose load-bearing facts fall inside [lo, hi]."""
    persona_release = {
        "sessions": [{"id": i} for i in range(1, 21)],
        "facts": {
            "f1": {"source_session_ids": [1, 3], "related_history_session_ids": [5]},
            "f2": {"source_session_ids": [2], "related_history_session_ids": [15]},
            "f3": {"source_session_ids": [8], "related_history_session_ids": []},
        },
        "tests": [
            {"id": 1, "load_bearing_facts": ["f1"]},
            {"id": 2, "load_bearing_facts": ["f1", "f2"]},
            {"id": 19, "load_bearing_facts": ["f3"]},
        ],
    }
    covered = run_mod.select_tests_for_window(persona_release, 1, 10, None)
    assert [t["id"] for t in covered] == [1, 19]

    full = run_mod.select_tests_for_window(persona_release, 1, 20, None)
    assert [t["id"] for t in full] == [1, 2, 19]

    explicit = run_mod.select_tests_for_window(persona_release, 1, 10, ["2"])
    assert [t["id"] for t in explicit] == [2]

    with pytest.raises(ValueError, match="Unknown test IDs"):
        run_mod.select_tests_for_window(persona_release, 1, 10, ["999"])


def test_build_apps_spec_handles_ingestion_and_repair_runtime(tmp_path: Path) -> None:
    """Ingestion reuses mutable state while tests reset state and wire repair_server."""
    dolphin = tmp_path / "dolphin"
    (dolphin / "mock_mcp/state").mkdir(parents=True)
    (dolphin / "mock_mcp/manifests").mkdir(parents=True)
    (dolphin / "mock_mcp/state/morgan_baseline.json").write_text(
        json.dumps({"coffee": "Blue Bottle"})
    )
    (dolphin / "mock_mcp/manifests/morgan.yaml").write_text(
        yaml.safe_dump({"tools": [{"name": "order_coffee"}]})
    )

    run_dir = tmp_path / "run"
    persona_release = {
        "runtime": {
            "manifest": {"tools": [{"name": "order_coffee"}, {"name": "list_orders"}]},
            "workspaces": {"ws_001": {"users": ["morgan"]}},
            "tests": {
                "001": {
                    "workspace": "ws_001",
                    "tool_config": {"active_tools": ["order_coffee", "list_orders"]},
                }
            },
        }
    }

    ingest_spec = run_mod.build_apps_spec(
        dolphin, run_dir, "morgan", "ingestion", "000001", {}, persona_release
    )
    assert ingest_spec["args"] == [str(dolphin / "mock_mcp/server.py")]
    assert json.loads(
        Path(ingest_spec["env"]["DOLPHINBENCH_STATE_PATH"]).read_text()
    ) == {"coffee": "Blue Bottle"}

    test_spec = run_mod.build_apps_spec(
        dolphin,
        run_dir,
        "morgan",
        "tests",
        "001",
        {"mock_state": {"coffee": "Sightglass"}, "tools": ["order_coffee"]},
        persona_release,
    )
    assert test_spec["args"] == [str(dolphin / "mock_mcp/repair_server.py")]
    assert "DOLPHINBENCH_WORKSPACE_DIRECTORY" in test_spec["env"]
    assert json.loads(
        Path(test_spec["env"]["DOLPHINBENCH_STATE_PATH"]).read_text()
    ) == {"coffee": "Sightglass"}
    assert json.loads(
        Path(test_spec["env"]["DOLPHINBENCH_TOOL_CONFIG_PATH"]).read_text()
    ) == {"active_tools": ["order_coffee", "list_orders"]}


def test_collect_persona_progress_aggregates_ingested_and_graded_counts(
    tmp_path: Path,
) -> None:
    """Suite live-status collector summarizes ingested sessions and per-arm pass rates."""
    p_out = tmp_path / "morgan"
    sess_dir = p_out / "ingestion/morgan/sessions"
    sess_dir.mkdir(parents=True)
    for idx in (1, 2, 3):
        (sess_dir / f"{idx:06d}.json").write_text("{}")
    arm_dir = p_out / "tests/product/morgan"
    arm_dir.mkdir(parents=True)
    (arm_dir / "001.json").write_text(json.dumps({"grade": {"passed": True}}))
    (arm_dir / "002.json").write_text(json.dumps({"grade": {"passed": False}}))

    progress = suite_mod.collect_persona_progress(
        p_out, "morgan", ["product", "memory-only"]
    )
    assert progress["ingestedSessions"] == 3
    assert progress["sealed"] is False
    assert progress["arms"]["product"] == {
        "completed": 2,
        "total": 200,
        "passed": 1,
        "accuracySoFar": 0.5,
    }
    assert progress["arms"]["memory-only"]["completed"] == 0
    assert progress["arms"]["memory-only"]["accuracySoFar"] is None
