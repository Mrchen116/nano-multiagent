"""Compatibility shim re-exporting the canonical core session store contract."""

from nano_multiagent.core.session.store import LoadedSession, SessionStore

__all__ = ["LoadedSession", "SessionStore"]
