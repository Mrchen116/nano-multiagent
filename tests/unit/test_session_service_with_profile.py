"""Unit tests for SessionService path resolution via ProductProfile.

Verifies that SessionService uses ConfigResolver-derived db path when a profile
is provided, and falls back to legacy behavior when no profile is given.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nano_multiagent.products.base import ProductProfile
from nano_multiagent.session.service import SessionService
from nano_multiagent.session.stores.sqlite_store import SQLiteSessionStore


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


def test_session_service_uses_profile_db_path_when_profile_given(tmp_path: Path) -> None:
    """SessionService should open SQLite at profile's global_config_home/sessions.sqlite3."""
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    svc = SessionService(profile=profile)
    # The store should be at the profile-resolved path.
    store = svc.manager._store  # type: ignore[attr-defined]
    expected_db = (tmp_path / ".testprod" / "sessions.sqlite3").resolve()
    assert isinstance(store, SQLiteSessionStore)
    assert store._db_path.resolve() == expected_db


def test_session_service_falls_back_to_default_when_no_profile(tmp_path: Path) -> None:
    """SessionService without profile uses the legacy default path."""
    legacy_path = tmp_path / "sessions.sqlite3"
    with patch(
        "nano_multiagent.session.service._default_sqlite_store_path",
        return_value=legacy_path,
    ):
        svc = SessionService()
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, SQLiteSessionStore)
    assert store._db_path.resolve() == legacy_path.resolve()


def test_session_service_explicit_store_takes_priority(tmp_path: Path) -> None:
    """Explicit store kwarg overrides both profile and default path."""
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    explicit_path = tmp_path / "explicit.db"
    custom_store = SQLiteSessionStore(db_path=explicit_path)
    svc = SessionService(store=custom_store, profile=profile)
    store = svc.manager._store  # type: ignore[attr-defined]
    assert store._db_path.resolve() == explicit_path.resolve()
