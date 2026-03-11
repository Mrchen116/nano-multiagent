"""Stable application surface for the coding CLI package.

This package exposes the supported apps-level entrypoints for the coding CLI.
"""

from coding_cli.coding_cli.client import ServerClient, ServerClientConfig
from coding_cli.coding_cli.commands import build_parser, run_cli
from coding_cli.coding_cli.managed_server import ManagedServerConfig, ManagedServerError, ManagedServerProcess

__all__ = [
    "ManagedServerConfig",
    "ManagedServerError",
    "ManagedServerProcess",
    "ServerClient",
    "ServerClientConfig",
    "build_parser",
    "run_cli",
]
