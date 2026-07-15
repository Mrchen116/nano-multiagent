"""Application boundary for authenticated external-channel commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Mapping

from IM.infra.channel_control_store import (
    ChannelControlError,
    ChannelManifest,
    ChannelRemovalView,
    ChannelControlStore,
    ChannelView,
)


class ChannelControlService:
    """Validate owner scope and delegate mutations to the transaction owner."""

    def __init__(
        self,
        store: ChannelControlStore,
        *,
        manifest_notifier: Callable[[ChannelManifest], bool] | None = None,
        reconnect_notifier: Callable[[str, str, int], bool] | None = None,
    ) -> None:
        self._store = store
        self._manifest_notifier = manifest_notifier or (lambda _manifest: False)
        self._reconnect_notifier = reconnect_notifier or (
            lambda _node_id, _channel_id, _revision: False
        )

    def list_channels(
        self, *, owner_id: str, agent_id: str
    ) -> list[ChannelView | ChannelRemovalView]:
        """Return active channel and nonterminal removal projections."""
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
        result = self._store.create_channel(
            owner_id=owner_id,
            agent_id=agent_id,
            provider=provider,
            enabled=enabled,
            config=config,
            secret={"app_secret": app_secret},
        )
        self._manifest_notifier(result.manifest)
        return result.channel

    def delete_channel(
        self,
        *,
        owner_id: str,
        agent_id: str,
        channel_id: str,
        channel_revision: int,
    ) -> ChannelRemovalView:
        """Persist deletion before making a best-effort reconcile notification."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        result = self._store.delete_channel(
            owner_id=owner_id,
            agent_id=agent_id,
            channel_id=channel_id,
            expected_revision=channel_revision,
        )
        self._manifest_notifier(result.manifest)
        return result.removal

    def reconnect_channel(
        self, *, owner_id: str, agent_id: str, channel_id: str
    ) -> ChannelView:
        """Run a live-only reconnect command or report the node as offline."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        channel, node_id = self._store.channel_for_reconnect(
            owner_id=owner_id, agent_id=agent_id, channel_id=channel_id
        )
        if not self._reconnect_notifier(
            node_id, channel.channel_id, channel.channel_revision
        ):
            raise ChannelControlError("channel_node_offline", status_code=409)
        return channel

    def retry_removal(
        self, *, owner_id: str, agent_id: str, channel_id: str
    ) -> ChannelRemovalView:
        """Replay the unchanged manifest only while its node is connected."""
        self._require_agent(owner_id=owner_id, agent_id=agent_id)
        manifest = self._store.retry_removal(
            owner_id=owner_id, agent_id=agent_id, channel_id=channel_id
        )
        if not self._manifest_notifier(manifest):
            raise ChannelControlError("channel_node_offline", status_code=409)
        removal = next(
            (
                item
                for item in self._store.list_channels(
                    owner_id=owner_id, agent_id=agent_id
                )
                if isinstance(item, ChannelRemovalView)
                and item.channel_id == channel_id
            ),
            None,
        )
        if removal is None:
            raise ChannelControlError("channel_not_found", status_code=404)
        return removal

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
        result = self._store.update_channel(
            owner_id=owner_id,
            agent_id=agent_id,
            channel_id=channel_id,
            expected_revision=channel_revision,
            enabled=enabled,
            config=config,
            credential_mode=credential_mode,
            secret=secret,
        )
        self._manifest_notifier(result.manifest)
        return result.channel

    def _require_agent(self, *, owner_id: str, agent_id: str) -> None:
        if not self._store.agent_exists_for_owner(
            owner_id=owner_id, agent_id=agent_id
        ):
            raise ChannelControlError("channel_not_found", status_code=404)
