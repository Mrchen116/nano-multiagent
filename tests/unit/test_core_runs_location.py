"""Verify core/runs is the canonical home for async run registry surfaces."""

from importlib.util import find_spec

from nano_multiagent.core.runs import RunRecord, RunStatus, RunsRegistry
from nano_multiagent.core.runs.registry import RunRecord as CoreRunRecord
from nano_multiagent.core.runs.registry import RunStatus as CoreRunStatus
from nano_multiagent.core.runs.registry import RunsRegistry as CoreRunsRegistry


def test_core_runs_is_canonical_home() -> None:
    assert RunRecord is CoreRunRecord
    assert RunStatus is CoreRunStatus
    assert RunsRegistry is CoreRunsRegistry

    assert RunRecord.__module__ == "nano_multiagent.core.runs.registry"
    assert RunStatus.__module__ == "nano_multiagent.core.runs.registry"
    assert RunsRegistry.__module__ == "nano_multiagent.core.runs.registry"


def test_legacy_runs_root_is_removed() -> None:
    assert find_spec("nano_multiagent.runs") is None
