"""Compatibility shim for the shared HTTP client contract."""

from nano_multiagent.platform.sdk.client import ServerClient, ServerClientConfig, _should_trust_env

__all__ = ["ServerClient", "ServerClientConfig"]
