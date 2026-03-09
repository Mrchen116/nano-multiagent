"""Verify platform/sdk is the canonical home for the shared HTTP client surface."""

from nano_multiagent.platform.sdk import ServerClient, ServerClientConfig
from nano_multiagent.platform.sdk.client import ServerClient as PlatformServerClient
from nano_multiagent.platform.sdk.client import ServerClientConfig as PlatformServerClientConfig
from nano_multiagent.sdk import ServerClient as LegacyServerClient
from nano_multiagent.sdk import ServerClientConfig as LegacyServerClientConfig
from nano_multiagent.sdk import client as legacy_sdk_client_module
from nano_multiagent.platform import sdk as platform_sdk_module


def test_platform_sdk_is_canonical_home() -> None:
    """Platform SDK exports must originate from platform-owned modules."""
    assert ServerClient is PlatformServerClient
    assert ServerClientConfig is PlatformServerClientConfig
    assert ServerClient.__module__ == "nano_multiagent.platform.sdk.client"
    assert ServerClientConfig.__module__ == "nano_multiagent.platform.sdk.client"
    assert platform_sdk_module.ServerClient is PlatformServerClient
    assert platform_sdk_module.ServerClientConfig is PlatformServerClientConfig


def test_old_sdk_shim_still_works() -> None:
    """Legacy sdk package must re-export the canonical platform SDK surface."""
    assert LegacyServerClient is PlatformServerClient
    assert LegacyServerClientConfig is PlatformServerClientConfig
    assert legacy_sdk_client_module.ServerClient is PlatformServerClient
    assert legacy_sdk_client_module.ServerClientConfig is PlatformServerClientConfig
