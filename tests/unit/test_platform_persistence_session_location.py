"""Verify platform/persistence/session is importable and re-exports correct symbols."""


def test_platform_persistence_session_imports_available() -> None:
    """After migration, session stores must be importable from the new platform path."""
    from nano_multiagent.platform.persistence.session import (  # noqa: F401
        JsonlSessionStore,
        LoadedSession,
        SessionStore,
        SQLiteSessionStore,
    )


def test_old_session_stores_shim_still_works() -> None:
    """Shim at old path must re-export all original symbols (backward compat)."""
    from nano_multiagent.session.stores import (  # noqa: F401
        JsonlSessionStore,
        LoadedSession,
        SessionStore,
        SQLiteSessionStore,
    )
