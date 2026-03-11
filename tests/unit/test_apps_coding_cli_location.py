"""Verify apps/coding_cli exposes the stable CLI application surface."""

from importlib.util import find_spec

from coding_cli import coding_cli as coding_cli_app
from coding_cli.coding_cli import commands as app_commands
from coding_cli.coding_cli.client import ServerClient as AppsServerClient
from coding_cli.coding_cli.client import ServerClientConfig as AppsServerClientConfig
from coding_cli.coding_cli.main import run_cli as app_main_run_cli
from coding_cli.coding_cli.managed_server import ManagedServerConfig as AppsManagedServerConfig
from coding_cli.coding_cli.managed_server import ManagedServerError as AppsManagedServerError
from coding_cli.coding_cli.managed_server import ManagedServerProcess as AppsManagedServerProcess
from agent.platform.sdk.client import ServerClient as PlatformSDKServerClient
from agent.platform.sdk.client import ServerClientConfig as PlatformSDKServerClientConfig



def test_apps_coding_cli_commands_surface_matches_stable_entrypoints() -> None:
    assert app_main_run_cli is app_commands.run_cli
    assert app_commands.build_parser.__module__ == "coding_cli.coding_cli.commands"
    assert app_commands.run_cli.__module__ == "coding_cli.coding_cli.commands"



def test_apps_coding_cli_client_surface_matches_platform_sdk() -> None:
    assert AppsServerClient is PlatformSDKServerClient
    assert AppsServerClientConfig is PlatformSDKServerClientConfig



def test_apps_coding_cli_package_root_exports_stable_application_surface() -> None:
    assert coding_cli_app.build_parser is app_commands.build_parser
    assert coding_cli_app.run_cli is app_commands.run_cli
    assert coding_cli_app.ServerClient is PlatformSDKServerClient
    assert coding_cli_app.ServerClientConfig is PlatformSDKServerClientConfig
    assert coding_cli_app.ManagedServerConfig is AppsManagedServerConfig
    assert coding_cli_app.ManagedServerError is AppsManagedServerError
    assert coding_cli_app.ManagedServerProcess is AppsManagedServerProcess
    assert AppsManagedServerConfig.__module__ == "coding_cli.coding_cli.managed_server"
    assert AppsManagedServerError.__module__ == "coding_cli.coding_cli.managed_server"
    assert AppsManagedServerProcess.__module__ == "coding_cli.coding_cli.managed_server"



def test_legacy_cli_and_sdk_roots_are_removed() -> None:
    assert find_spec("agent.cli") is None
    assert find_spec("agent.sdk") is None
