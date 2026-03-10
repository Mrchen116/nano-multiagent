"""Verify platform/sdk is the canonical home for the shared HTTP client surface."""

from importlib.util import find_spec

from nano_multiagent.platform.sdk import ServerClient, ServerClientConfig
from nano_multiagent.platform.sdk.client import ServerClient as PlatformServerClient
from nano_multiagent.platform.sdk.client import ServerClientConfig as PlatformServerClientConfig
from nano_multiagent.platform import sdk as platform_sdk_module



def test_platform_sdk_is_canonical_home() -> None:
    """Platform SDK exports must originate from platform-owned modules."""
    assert ServerClient is PlatformServerClient
    assert ServerClientConfig is PlatformServerClientConfig
    assert ServerClient.__module__ == "nano_multiagent.platform.sdk.client"
    assert ServerClientConfig.__module__ == "nano_multiagent.platform.sdk.client"
    assert platform_sdk_module.ServerClient is PlatformServerClient
    assert platform_sdk_module.ServerClientConfig is PlatformServerClientConfig



def test_legacy_sdk_root_is_removed() -> None:
    assert find_spec("nano_multiagent.sdk") is None
