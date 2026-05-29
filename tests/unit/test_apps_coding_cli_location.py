"""Verify apps/coding_cli exposes the stable CLI application surface."""

from importlib.util import find_spec

import coding_cli as coding_cli_app
from coding_cli import commands as app_commands
from coding_cli.client import ServerClient as AppsServerClient
from coding_cli.client import ServerClientConfig as AppsServerClientConfig
from coding_cli.main import run_cli as app_main_run_cli
from coding_cli.managed_server import ManagedServerConfig as AppsManagedServerConfig
from coding_cli.managed_server import ManagedServerError as AppsManagedServerError
from coding_cli.managed_server import ManagedServerProcess as AppsManagedServerProcess
from coding_cli import client as coding_cli_client



def test_apps_coding_cli_commands_surface_matches_stable_entrypoints() -> None:
    assert app_main_run_cli is app_commands.run_cli
    assert app_commands.build_parser.__module__ == "coding_cli.commands"
    assert app_commands.run_cli.__module__ == "coding_cli.commands"



def test_apps_coding_cli_client_surface_stays_on_package_owned_module() -> None:
    assert AppsServerClient is coding_cli_client.ServerClient
    assert AppsServerClientConfig is coding_cli_client.ServerClientConfig
    assert AppsServerClient.__module__ == "coding_cli.client"
    assert AppsServerClientConfig.__module__ == "coding_cli.client"



def test_apps_coding_cli_package_root_exports_stable_application_surface() -> None:
    """M2: coding_cli.__init__ exposes only build_parser and run_cli.

    ServerClient / ManagedServerProcess are no longer part of the public surface —
    they are HTTP/subprocess-era artefacts kept for M4 cleanup.
    """
    assert coding_cli_app.build_parser is app_commands.build_parser
    assert coding_cli_app.run_cli is app_commands.run_cli
    # M2: HTTP client exports removed from __init__ (kept in client.py for M4 deletion)
    assert not hasattr(coding_cli_app, "ServerClient"), (
        "ServerClient should not be re-exported from coding_cli after M2"
    )
    assert not hasattr(coding_cli_app, "ManagedServerProcess"), (
        "ManagedServerProcess should not be re-exported from coding_cli after M2"
    )
    # client.py and managed_server.py files still exist (deleted in M4)
    assert AppsManagedServerConfig.__module__ == "coding_cli.managed_server"
    assert AppsManagedServerError.__module__ == "coding_cli.managed_server"
    assert AppsManagedServerProcess.__module__ == "coding_cli.managed_server"



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
