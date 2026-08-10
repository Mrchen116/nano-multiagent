"""Structural routing regressions for the controlled self-evolution LLM."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "fixtures"
    / "openai_self_evolution_recording.py"
)
_SPEC = importlib.util.spec_from_file_location("self_evolution_fixture", _SCRIPT)
assert _SPEC and _SPEC.loader
self_evolution_fixture = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(self_evolution_fixture)


def _request(*, tool_result_id: str | None = None) -> dict[str, object]:
    messages: list[dict[str, str]] = [{"role": "user", "content": "controlled"}]
    if tool_result_id is not None:
        messages.append(
            {
                "role": "tool",
                "content": "{}",
                "tool_call_id": tool_result_id,
            }
        )
    return {
        "messages": messages,
        "tools": [{"type": "function", "function": {"name": "memory"}}],
    }


@pytest.mark.parametrize("scenario", ["cli_memory", "cli_no_save", "cli_failure"])
def test_cli_memory_family_routes_seed_foreground_then_review(
    tmp_path: Path, scenario: str
) -> None:
    """CLI memory scenarios do not depend on private prompt wording."""
    state = self_evolution_fixture._ScenarioState(tmp_path / "record.jsonl")
    state.control({"scenario": scenario, "reset": True})

    assert state.classify(_request())["kind"] == "foreground"
    assert state.classify(_request())["kind"] == "foreground"
    assert state.classify(_request())["kind"] == "review"
    continued = state.classify(_request(tool_result_id="controlled-call"))
    assert continued["kind"] == "continuation"
    assert continued["latest_tool_result_id"] == "controlled-call"


@pytest.mark.parametrize("scenario", ["cli_skill", "cli_read"])
def test_cli_skill_family_routes_foreground_tool_then_review(
    tmp_path: Path, scenario: str
) -> None:
    """CLI skill scenarios use request index plus tool-result structure."""
    state = self_evolution_fixture._ScenarioState(tmp_path / "record.jsonl")
    state.control({"scenario": scenario, "reset": True})

    assert state.classify(_request())["kind"] == "foreground"
    assert (
        state.classify(_request(tool_result_id="foreground-list-call"))["kind"]
        == "continuation"
    )
    assert state.classify(_request())["kind"] == "review"


def test_cli_both_routes_seed_then_foreground_tool_then_review(
    tmp_path: Path,
) -> None:
    """Combined acceptance reaches both counters without prompt-text routing."""
    state = self_evolution_fixture._ScenarioState(tmp_path / "record.jsonl")
    state.control({"scenario": "cli_both", "reset": True})

    assert state.classify(_request())["kind"] == "foreground"
    assert state.classify(_request())["kind"] == "review"
    assert state.classify(_request())["kind"] == "foreground"
    assert (
        state.classify(_request(tool_result_id="foreground-list-call"))["kind"]
        == "continuation"
    )
    assert state.classify(_request())["kind"] == "review"
