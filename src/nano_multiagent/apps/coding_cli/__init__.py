"""Stable application surface for the coding CLI package.

This package exposes the supported apps-level entrypoints for the coding CLI.
"""

from nano_multiagent.apps.coding_cli.client import ServerClient, ServerClientConfig
from nano_multiagent.apps.coding_cli.commands import build_parser, run_cli
from nano_multiagent.apps.coding_cli.managed_server import ManagedServerConfig, ManagedServerError, ManagedServerProcess

__all__ = [
    "ManagedServerConfig",
    "ManagedServerError",
    "ManagedServerProcess",
    "ServerClient",
    "ServerClientConfig",
    "build_parser",
    "run_cli",
]
