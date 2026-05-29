"""Stable application surface for the coding CLI package.

This package exposes the supported apps-level entrypoints for the coding CLI.

Architecture (refactor-387 M2): CLI is now async-native and communicates with
the agent kernel in-process via agent.sdk.  ServerClient / ManagedServerProcess
are removed from the public surface; client.py and managed_server.py are kept
for the transition period and deleted in M4.
"""

from coding_cli.commands import build_parser, run_cli

__all__ = [
    "build_parser",
    "run_cli",
]
