"""Config sync notification state tests."""

from __future__ import annotations

from personal_assistant.config.sync_client import ConfigSyncClient


def test_config_sync_client_records_latest_versions() -> None:
    seen: list[tuple[str, int]] = []
    client = ConfigSyncClient(
        fetcher=lambda agent_id, profile_version: seen.append(
            (agent_id, profile_version)
        )
    )

    request = client.handle_notification({"agent_id": "agent-a", "profile_version": 3})

    assert request.agent_id == "agent-a"
    assert client.latest_profile_version("agent-a") == 3
    assert seen == [("agent-a", 3)]
