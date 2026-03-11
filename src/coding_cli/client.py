"""Application-layer alias for the shared HTTP client contract."""

from agent.platform.sdk.client import ServerClient, ServerClientConfig, _should_trust_env

__all__ = ["ServerClient", "ServerClientConfig"]
