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
from nano_multiagent.platform.sdk.client import ServerClient as PlatformSDKServerClient
from nano_multiagent.platform.sdk.client import ServerClientConfig as PlatformSDKServerClientConfig
from nano_multiagent.sdk.client import ServerClient as LegacySDKServerClient
from nano_multiagent.sdk.client import ServerClientConfig as LegacySDKServerClientConfig


def test_apps_coding_cli_commands_surface_matches_legacy_cli_entrypoints() -> None:
    assert legacy_cli_commands.build_parser is app_commands.build_parser
    assert legacy_cli_commands.run_cli is app_commands.run_cli
    assert legacy_cli_main_run_cli is app_commands.run_cli
    assert app_main_run_cli is app_commands.run_cli
    assert app_commands.build_parser.__module__ == "nano_multiagent.apps.coding_cli.commands"
    assert app_commands.run_cli.__module__ == "nano_multiagent.apps.coding_cli.commands"



def test_apps_coding_cli_client_surface_matches_platform_sdk_and_legacy_cli() -> None:
    assert AppsServerClient is PlatformSDKServerClient
    assert AppsServerClientConfig is PlatformSDKServerClientConfig
    assert LegacySDKServerClient is PlatformSDKServerClient
    assert LegacySDKServerClientConfig is PlatformSDKServerClientConfig
    assert LegacyCliServerClient is PlatformSDKServerClient
    assert LegacyCliServerClientConfig is PlatformSDKServerClientConfig



def test_apps_coding_cli_package_root_exports_stable_application_surface() -> None:
    assert coding_cli_app.build_parser is app_commands.build_parser
    assert coding_cli_app.run_cli is app_commands.run_cli
    assert coding_cli_app.ServerClient is PlatformSDKServerClient
    assert coding_cli_app.ServerClientConfig is PlatformSDKServerClientConfig
    assert coding_cli_app.ManagedServerConfig is AppsManagedServerConfig
    assert coding_cli_app.ManagedServerError is AppsManagedServerError
    assert coding_cli_app.ManagedServerProcess is AppsManagedServerProcess
    assert AppsManagedServerConfig.__module__ == "nano_multiagent.apps.coding_cli.managed_server"
    assert AppsManagedServerError.__module__ == "nano_multiagent.apps.coding_cli.managed_server"
    assert AppsManagedServerProcess.__module__ == "nano_multiagent.apps.coding_cli.managed_server"
