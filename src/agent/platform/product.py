"""Compatibility shim for the canonical product contract module.

The canonical home of ``ProductProfile`` and ``ResolvedProductConfig`` is now
``agent.products.base``. This module remains importable so existing
platform-layer callers keep working during the migration.
"""

from agent.products.base import ProductProfile, ResolvedProductConfig

__all__ = ["ProductProfile", "ResolvedProductConfig"]
