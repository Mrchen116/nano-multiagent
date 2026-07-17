"""Behavior tests for the live Agent catalog."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread

import pytest

from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog


def _agent(
    tmp_path: Path,
    *,
    title: str,
    model: str,
    heartbeat: bool,
) -> AgentWorkspaceConfig:
    workspace = tmp_path / title
    workspace.mkdir(exist_ok=True)
    return AgentWorkspaceConfig(
        agent_id="agent-a",
        workspace_root=workspace,
        title=title,
        default_model=model,
        features={"heartbeat": heartbeat},
    )


def test_publish_replaces_one_complete_snapshot_and_advances_revision(
    tmp_path: Path,
) -> None:
    initial = _agent(
        tmp_path,
        title="Agent A v1",
        model="model-v1",
        heartbeat=False,
    )
    catalog = LiveAgentCatalog((initial,))
    before = catalog.require("agent-a")

    after = catalog.publish(
        _agent(
            tmp_path,
            title="Agent A v2",
            model="model-v2",
            heartbeat=True,
        )
    )

    assert after.revision > before.revision
    assert catalog.require("agent-a") is after
    assert catalog.is_current(after)
    assert not catalog.is_current(before)
    assert before.config.title == "Agent A v1"
    assert before.config.default_model == "model-v1"
    assert not before.config.heartbeat_enabled
    assert after.config.title == "Agent A v2"
    assert after.config.default_model == "model-v2"
    assert after.config.heartbeat_enabled


def test_published_features_are_detached_from_mutable_input(tmp_path: Path) -> None:
    source = _agent(
        tmp_path,
        title="Agent A",
        model="model-a",
        heartbeat=True,
    )
    catalog = LiveAgentCatalog((source,))

    source.features["heartbeat"] = False

    assert catalog.require("agent-a").config.heartbeat_enabled
    with pytest.raises(TypeError):
        catalog.require("agent-a").config.features["heartbeat"] = False


def test_require_rejects_unknown_agent_without_fallback(tmp_path: Path) -> None:
    catalog = LiveAgentCatalog(
        (
            _agent(
                tmp_path,
                title="Agent A",
                model="model-a",
                heartbeat=False,
            ),
        )
    )

    assert catalog.get("missing") is None
    with pytest.raises(LookupError, match="unknown agent missing"):
        catalog.require("missing")


def test_readers_only_observe_complete_old_or_new_snapshot(tmp_path: Path) -> None:
    old = _agent(
        tmp_path,
        title="Agent A old",
        model="model-old",
        heartbeat=False,
    )
    new = _agent(
        tmp_path,
        title="Agent A new",
        model="model-new",
        heartbeat=True,
    )
    catalog = LiveAgentCatalog((old,))
    start = Event()
    reader_ready = Event()
    done = Event()
    observed: list[tuple[str | None, str | None, bool]] = []

    def _read() -> None:
        start.wait()
        first = catalog.require("agent-a")
        observed.append(
            (
                first.config.title,
                first.config.default_model,
                first.config.heartbeat_enabled,
            )
        )
        reader_ready.set()
        while not done.is_set():
            snapshot = catalog.require("agent-a")
            observed.append(
                (
                    snapshot.config.title,
                    snapshot.config.default_model,
                    snapshot.config.heartbeat_enabled,
                )
            )

    reader = Thread(target=_read)
    reader.start()
    start.set()
    assert reader_ready.wait(timeout=1), "catalog reader did not reach observation loop"
    for _ in range(100):
        catalog.publish(new)
        catalog.publish(old)
    done.set()
    reader.join(timeout=1)

    assert observed
    assert set(observed) <= {
        ("Agent A old", "model-old", False),
        ("Agent A new", "model-new", True),
    }
    assert len(catalog.values_snapshot()) == 1
