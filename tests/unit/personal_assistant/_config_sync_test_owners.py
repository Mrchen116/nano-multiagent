"""Concrete Gateway owner graph for config-sync behavior tests."""

from __future__ import annotations

from dataclasses import dataclass

from personal_assistant.config.local_store import LocalConfig
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.session_keys import SessionBindingStore


@dataclass(frozen=True)
class ConfigSyncTestOwners:
    """Expose the production catalog and binder used by one test sync client."""

    catalog: LiveAgentCatalog
    binder: GatewaySessionBinder
    store: SessionBindingStore

    def kwargs(self) -> dict[str, object]:
        """Return constructor keywords without replacing either concrete owner."""

        return {"agent_catalog": self.catalog, "session_binder": self.binder}


def build_config_sync_test_owners(config: LocalConfig) -> ConfigSyncTestOwners:
    """Build the same concrete ownership pair used by Gateway composition."""

    catalog = LiveAgentCatalog(config.agents)
    store = SessionBindingStore()
    binder = GatewaySessionBinder(
        catalog=catalog,
        repository=store,
        kernel=object(),
    )
    return ConfigSyncTestOwners(catalog=catalog, binder=binder, store=store)
