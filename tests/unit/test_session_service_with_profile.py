"""Unit tests for SessionService path resolution via ProductProfile.

Verifies that SessionService uses ConfigResolver-derived data dir when a profile
is provided, and falls back to legacy behavior when no profile is given.
"""

from pathlib import Path
from unittest.mock import patch

from agent.core.session.jsonl_store import JsonlSessionStore
from agent.products.base import ProductProfile
from agent.platform.persistence.session.service import SessionService


def _make_profile(global_home: str = "~/.testservice") -> ProductProfile:
    return ProductProfile(
        product_id="test",
        display_name="Test",
        config_namespace="test",
        global_config_home=Path(global_home),
        workspace_config_dirname=".test",
        session_db_filename="sessions.sqlite3",
        compat_skill_roots=[],
    )


def test_session_service_uses_workspace_local_data_dir_when_profile_given(tmp_path: Path) -> None:
    """SessionService with profile uses workspace-local .nano directory."""
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    svc = SessionService(profile=profile)
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, JsonlSessionStore)
    assert store._data_dir == Path(".nano")


def test_session_service_falls_back_to_default_when_no_profile(tmp_path: Path) -> None:
    """SessionService without profile uses the legacy default data directory."""
    legacy_data_dir = tmp_path / "sessions"
    with patch(
        "agent.platform.persistence.session.service._resolve_data_dir",
        return_value=legacy_data_dir,
    ):
        svc = SessionService()
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, JsonlSessionStore)
    assert store._data_dir.resolve() == legacy_data_dir.resolve()


def test_session_service_explicit_store_takes_priority(tmp_path: Path) -> None:
    """Explicit store kwarg overrides both profile and default path."""
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    explicit_data_dir = tmp_path / "explicit_sessions"
    custom_store = JsonlSessionStore(data_dir=explicit_data_dir)
    svc = SessionService(store=custom_store, profile=profile)
    store = svc.manager._store  # type: ignore[attr-defined]
    assert store._data_dir.resolve() == explicit_data_dir.resolve()
