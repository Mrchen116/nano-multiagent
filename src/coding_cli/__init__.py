"""Stable application surface for the coding CLI package.

This package exposes the supported apps-level entrypoints for the coding CLI.

Architecture: CLI is async-native and communicates with the agent kernel
in-process via agent.sdk.  No HTTP server, no subprocess.
"""

from coding_cli.commands import build_parser, run_cli

__all__ = [
    "build_parser",
    "run_cli",
]
