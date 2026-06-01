"""Unit tests for SessionService store construction (bugfix-348: stateless kernel).

The fallback store (no explicit ``store``/``manager`` given) must be **stateless**
— ``data_dir is None`` — so callers pass ``workspace_root`` per request and each
session JSONL lands under its own ``{workspace_root}/.nano/sessions/``. The only
escape hatch is the explicit ``NANO_MULTIAGENT_DATA_DIR`` env var. There is
deliberately no silent ``.nano``-relative-to-cwd fallback: that silent cwd
fallback was the bugfix-348 root cause.
"""

from pathlib import Path

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


def test_session_service_fallback_store_is_stateless_with_profile(
    tmp_path: Path,
) -> None:
    """SessionService(profile=...) without explicit store builds a stateless store.

    The profile is currently not used for store construction; the fallback is a
    stateless store (data_dir=None), not a cwd-relative ``.nano``.
    """
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    svc = SessionService(profile=profile)
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, JsonlSessionStore)
    assert store._data_dir is None


def test_session_service_fallback_store_is_stateless_without_profile() -> None:
    """SessionService() with no args builds a stateless fallback store."""
    svc = SessionService()
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, JsonlSessionStore)
    assert store._data_dir is None


def test_session_service_fallback_honours_env_data_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """NANO_MULTIAGENT_DATA_DIR is the one explicit opt-in for a fixed flat base."""
    env_dir = tmp_path / "env-sessions"
    monkeypatch.setenv("NANO_MULTIAGENT_DATA_DIR", str(env_dir))
    svc = SessionService()
    store = svc.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, JsonlSessionStore)
    assert store._data_dir is not None
    assert store._data_dir.resolve() == env_dir.resolve()


def test_session_service_explicit_store_takes_priority(tmp_path: Path) -> None:
    """Explicit store kwarg overrides both profile and the fallback."""
    profile = _make_profile(global_home=str(tmp_path / ".testprod"))
    explicit_data_dir = tmp_path / "explicit_sessions"
    custom_store = JsonlSessionStore(data_dir=explicit_data_dir)
    svc = SessionService(store=custom_store, profile=profile)
    store = svc.manager._store  # type: ignore[attr-defined]
    assert store._data_dir.resolve() == explicit_data_dir.resolve()
