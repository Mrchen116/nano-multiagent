"""Verify platform/sdk is importable and mirrors existing SDK exports."""


def test_platform_sdk_importable() -> None:
    """After migration, SDK exports must be importable from platform/sdk."""
    from nano_multiagent.platform.sdk import ServerClient, ServerClientConfig  # noqa: F401



def test_old_sdk_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for sdk package."""
    from nano_multiagent.sdk import ServerClient, ServerClientConfig  # noqa: F401
