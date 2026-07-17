"""Own immutable live Agent configuration snapshots for Gateway consumers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
from types import MappingProxyType
from typing import Iterable, Mapping

from personal_assistant.config.local_store import AgentWorkspaceConfig


@dataclass(frozen=True, slots=True)
class LiveAgentSnapshot:
    """Capture one complete Agent configuration at a catalog revision.

    Args:
        config: Detached runtime configuration for one Agent.
        revision: Monotonic catalog publication revision.
    """

    config: AgentWorkspaceConfig
    revision: int

    @property
    def agent_id(self) -> str:
        """Return the stable Agent identifier carried by this snapshot."""

        return self.config.agent_id


class LiveAgentCatalog:
    """Publish copy-on-write Agent snapshots to all Gateway consumers.

    Args:
        agents: Initial Agent configurations, published in iteration order.

    Notes:
        Publication replaces the complete immutable mapping in one short critical
        section. Readers therefore retain a complete old snapshot or observe the
        complete new snapshot; mutable caller-owned feature dictionaries never
        become catalog state.
    """

    def __init__(self, agents: Iterable[AgentWorkspaceConfig] = ()) -> None:
        self._lock = Lock()
        self._revision = 0
        self._snapshots: Mapping[str, LiveAgentSnapshot] = MappingProxyType({})
        for agent in agents:
            self.publish(agent)

    def get(self, agent_id: str) -> LiveAgentSnapshot | None:
        """Return the current snapshot for an Agent, or ``None`` when absent."""

        with self._lock:
            return self._snapshots.get(agent_id)

    def require(self, agent_id: str) -> LiveAgentSnapshot:
        """Return the current snapshot for an Agent.

        Raises:
            LookupError: When the Agent is not registered.
        """

        snapshot = self.get(agent_id)
        if snapshot is None:
            raise LookupError(f"unknown agent {agent_id}")
        return snapshot

    def publish(self, agent: AgentWorkspaceConfig) -> LiveAgentSnapshot:
        """Atomically publish a detached configuration as the next revision.

        Args:
            agent: Complete runtime configuration replacing this Agent's snapshot.

        Returns:
            The newly published current snapshot.
        """

        detached = replace(
            agent,
            features=MappingProxyType(dict(agent.features)),  # type: ignore[arg-type]
        )
        with self._lock:
            self._revision += 1
            snapshot = LiveAgentSnapshot(
                config=detached,
                revision=self._revision,
            )
            snapshots = dict(self._snapshots)
            snapshots[agent.agent_id] = snapshot
            self._snapshots = MappingProxyType(snapshots)
            return snapshot

    def is_current(self, snapshot: LiveAgentSnapshot) -> bool:
        """Return whether a snapshot is still current for its Agent."""

        with self._lock:
            return self._snapshots.get(snapshot.agent_id) is snapshot

    def values_snapshot(self) -> tuple[LiveAgentSnapshot, ...]:
        """Return a stable tuple of all current snapshots in publication order."""

        with self._lock:
            return tuple(self._snapshots.values())
