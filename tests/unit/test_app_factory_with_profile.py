"""Unit tests: create_app accepts an optional ProductProfile."""

from fastapi import FastAPI

from nano_multiagent.platform.product import ProductProfile
from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE
from nano_multiagent.server.app import create_app


def test_create_app_with_local_coding_profile_returns_fastapi() -> None:
    """create_app with explicit local_coding profile must return a FastAPI app."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert isinstance(app, FastAPI)


def test_create_app_with_profile_has_tool_registry() -> None:
    """app wired via profile must have a tool registry on its state."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert app.state.tool_registry is not None


def test_create_app_with_profile_has_hook_registry() -> None:
    """app wired via profile must have a hook registry on its state."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert app.state.hook_registry is not None


def test_create_app_without_profile_still_works() -> None:
    """Backward-compatible: create_app() without profile preserves existing behavior."""
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.state.tool_registry is not None


def test_create_app_with_minimal_profile() -> None:
    """create_app should accept a minimal custom profile."""
    profile = ProductProfile(
        product_id="test_product",
        display_name="Test",
        config_namespace="test",
    )
    app = create_app(product_profile=profile)
    assert isinstance(app, FastAPI)
    assert app.state.hook_registry is not None
