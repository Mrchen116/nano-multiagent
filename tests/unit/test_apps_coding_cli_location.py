"""Verify apps/coding_cli exposes the stable CLI application surface."""

from nano_multiagent.apps import coding_cli as coding_cli_app
from nano_multiagent.apps.coding_cli import commands as app_commands
from nano_multiagent.apps.coding_cli.client import ServerClient as AppsServerClient
from nano_multiagent.apps.coding_cli.client import ServerClientConfig as AppsServerClientConfig
from nano_multiagent.apps.coding_cli.main import run_cli as app_main_run_cli
from nano_multiagent.apps.coding_cli.managed_server import ManagedServerConfig as AppsManagedServerConfig
from nano_multiagent.apps.coding_cli.managed_server import ManagedServerError as AppsManagedServerError
from nano_multiagent.apps.coding_cli.managed_server import ManagedServerProcess as AppsManagedServerProcess
from nano_multiagent.cli import commands as legacy_cli_commands
from nano_multiagent.cli.http_client import ServerClient as LegacyCliServerClient
from nano_multiagent.cli.http_client import ServerClientConfig as LegacyCliServerClientConfig
from nano_multiagent.cli.main import run_cli as legacy_cli_main_run_cli
from nano_multiagent.sdk.client import ServerClient as SDKServerClient
from nano_multiagent.sdk.client import ServerClientConfig as SDKServerClientConfig


def test_apps_coding_cli_commands_surface_matches_legacy_cli_entrypoints() -> None:
    assert legacy_cli_commands.build_parser is app_commands.build_parser
    assert legacy_cli_commands.run_cli is app_commands.run_cli
    assert legacy_cli_main_run_cli is app_commands.run_cli
    assert app_main_run_cli is app_commands.run_cli



def test_apps_coding_cli_client_surface_matches_sdk_and_legacy_cli() -> None:
    assert AppsServerClient is SDKServerClient
    assert AppsServerClientConfig is SDKServerClientConfig
    assert LegacyCliServerClient is SDKServerClient
    assert LegacyCliServerClientConfig is SDKServerClientConfig



def test_apps_coding_cli_package_root_exports_stable_application_surface() -> None:
    assert coding_cli_app.build_parser is app_commands.build_parser
    assert coding_cli_app.run_cli is app_commands.run_cli
    assert coding_cli_app.ServerClient is SDKServerClient
    assert coding_cli_app.ServerClientConfig is SDKServerClientConfig
    assert coding_cli_app.ManagedServerConfig is AppsManagedServerConfig
    assert coding_cli_app.ManagedServerError is AppsManagedServerError
    assert coding_cli_app.ManagedServerProcess is AppsManagedServerProcess
