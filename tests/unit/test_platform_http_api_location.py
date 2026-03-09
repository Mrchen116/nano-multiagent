"""Verify platform/http_api is importable and mirrors server entrypoints."""


def test_platform_http_api_importable() -> None:
    """After migration, create_app must be importable from platform/http_api."""
    from nano_multiagent.platform.http_api import create_app  # noqa: F401



def test_old_server_shim_still_works() -> None:
    """Shim at old path must preserve backward compat for server package."""
    from nano_multiagent.server import create_app  # noqa: F401
