"""Verify apps/coding_cli exposes the stable CLI application surface (refactor-387-M4).

client.py, managed_server.py, kernel_app.py, session_stream.py are deleted in M4;
this file no longer verifies their presence.
"""

from importlib.util import find_spec

import coding_cli as coding_cli_app
from coding_cli import commands as app_commands
from coding_cli.main import run_cli as app_main_run_cli



def test_apps_coding_cli_commands_surface_matches_stable_entrypoints() -> None:
    assert app_main_run_cli is app_commands.run_cli
    assert app_commands.build_parser.__module__ == "coding_cli.commands"
    assert app_commands.run_cli.__module__ == "coding_cli.commands"



def test_apps_coding_cli_package_root_exports_agent_sdk_surface() -> None:
    """M4: coding_cli.__init__ exposes only build_parser and run_cli.

    HTTP client and managed server exports were removed in M2; files deleted in M4.
    """
    assert coding_cli_app.build_parser is app_commands.build_parser
    assert coding_cli_app.run_cli is app_commands.run_cli
    assert not hasattr(coding_cli_app, "ServerClient"), (
        "ServerClient should not be re-exported from coding_cli"
    )
    assert not hasattr(coding_cli_app, "ManagedServerProcess"), (
        "ManagedServerProcess should not be re-exported from coding_cli"
    )



def test_legacy_cli_root_is_removed() -> None:
    """agent.cli was a legacy root removed in M89; must not re-emerge."""
    assert find_spec("agent.cli") is None


def test_agent_sdk_is_the_new_public_surface() -> None:
    """agent.sdk is now the canonical product-facing surface (refactor-387-M1).

    The old test_legacy_cli_and_sdk_roots_are_removed checked that agent.sdk did
    not exist (because a prior legacy 'sdk' root had been removed). Now agent.sdk
    is intentional: products import only from here.
    """
    assert find_spec("agent.sdk") is not None
