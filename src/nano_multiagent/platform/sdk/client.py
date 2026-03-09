"""Shim: platform/sdk/client re-exports canonical sdk.client surface."""

from nano_multiagent.sdk.client import ServerClient, ServerClientConfig  # noqa: F401

__all__ = ["ServerClient", "ServerClientConfig"]
