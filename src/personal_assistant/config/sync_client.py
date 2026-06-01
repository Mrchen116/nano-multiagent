"""Optional config-sync client that reacts to IM config.sync pushes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ConfigSyncRequest:
    """Describe one requested config refresh.

    Args:
        agent_id: Agent whose profile changed upstream.
        profile_version: Version announced by IM.
    """

    agent_id: str
    profile_version: int


class ConfigSyncClient:
    """Track config sync notifications and expose refresh hooks.

    Args:
        fetcher: Optional callback used to pull the latest config snapshot.

    Notes:
        M102 only needs the gateway-side reaction boundary. Fetching remains optional,
        so this client records announced versions even when no remote pull hook exists.
    """

    def __init__(self, *, fetcher=None) -> None:  # noqa: ANN001
        self._fetcher = fetcher
        self._latest_versions: dict[str, int] = {}
        self._history: list[ConfigSyncRequest] = []

    def handle_notification(self, payload: Mapping[str, object]) -> ConfigSyncRequest:
        """Record one ``config.sync`` notification and optionally fetch config."""

        agent_id = _require_text(payload.get("agent_id"), field_name="agent_id")
        profile_version = _require_int(
            payload.get("profile_version"), field_name="profile_version"
        )
        request = ConfigSyncRequest(agent_id=agent_id, profile_version=profile_version)
        self._latest_versions[agent_id] = profile_version
        self._history.append(request)
        if self._fetcher is not None:
            self._fetcher(agent_id=agent_id, profile_version=profile_version)
        return request

    def latest_profile_version(self, agent_id: str) -> int | None:
        """Return the newest announced version for one agent."""

        return self._latest_versions.get(agent_id)

    def history(self) -> tuple[ConfigSyncRequest, ...]:
        """Return all seen config sync notifications in arrival order."""

        return tuple(self._history)


def _require_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
