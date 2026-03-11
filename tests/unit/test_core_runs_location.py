"""Verify core/runs is the canonical home for async run registry surfaces."""

from importlib.util import find_spec

from agent.core.runs import RunRecord, RunStatus, RunsRegistry
from agent.core.runs.registry import RunRecord as CoreRunRecord
from agent.core.runs.registry import RunStatus as CoreRunStatus
from agent.core.runs.registry import RunsRegistry as CoreRunsRegistry


def test_core_runs_is_canonical_home() -> None:
    assert RunRecord is CoreRunRecord
    assert RunStatus is CoreRunStatus
    assert RunsRegistry is CoreRunsRegistry

    assert RunRecord.__module__ == "agent.core.runs.registry"
    assert RunStatus.__module__ == "agent.core.runs.registry"
    assert RunsRegistry.__module__ == "agent.core.runs.registry"


def test_legacy_runs_root_is_removed() -> None:
    assert find_spec("agent.runs") is None
