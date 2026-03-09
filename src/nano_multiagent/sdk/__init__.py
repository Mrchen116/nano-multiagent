"""Shim package: canonical SDK surface now lives under platform/sdk."""

from .client import ServerClient, ServerClientConfig

__all__ = ["ServerClient", "ServerClientConfig"]
