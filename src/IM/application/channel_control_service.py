"""Application boundary for authenticated external-channel commands."""

from __future__ import annotations

from typing import Literal, Mapping

from IM.infra.channel_control_store import (
    ChannelControlError,
    ChannelControlStore,
    ChannelView,
)


class ChannelControlService:
    """Validate owner scope and delegate mutations to the transaction owner."""

    def __init__(self, store: ChannelControlStore) -> None:
        self._store = store

    def list_channels(self, *, owner_id: str, agent_id: str) -> list[ChannelView]:
        """Return one owner's active channel projections for an agent."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        return self._store.list_channels(owner_id=owner_id, agent_id=agent_id)

    def create_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        provider: str,
        enabled: bool,
        config: Mapping[str, object],
        credential_mode: str,
        app_secret: str | None,
    ) -> ChannelView:
        """Create one provider instance using an explicit secret replacement."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        if credential_mode != "replace" or app_secret is None:
            raise ChannelControlError("channel_credentials_required", status_code=422)
        return self._store.create_channel(
            owner_id=owner_id,
            agent_id=agent_id,
            provider=provider,
            enabled=enabled,
            config=config,
            secret={"app_secret": app_secret},
        ).channel

    def update_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        channel_id: str,
        channel_revision: int,
        enabled: bool,
        config: Mapping[str, object],
        credential_mode: Literal["keep", "replace"],
        app_secret: str | None,
    ) -> ChannelView:
        """Update desired channel state under its current revision."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        secret = {"app_secret": app_secret} if app_secret is not None else None
        return self._store.update_channel(
            owner_id=owner_id,
            agent_id=agent_id,
            channel_id=channel_id,
            expected_revision=channel_revision,
            enabled=enabled,
            config=config,
            credential_mode=credential_mode,
            secret=secret,
        ).channel

    def _require_agent(self, *, owner_id: str, agent_id: str) -> None:
        if not self._store.agent_exists_for_owner(
            owner_id=owner_id, agent_id=agent_id
        ):
            raise ChannelControlError("channel_not_found", status_code=404)
