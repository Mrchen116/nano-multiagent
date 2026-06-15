"""Route-tree introspection helpers tolerant of nested fastapi routers.

fastapi >=0.116 stopped flattening ``include_router`` sub-routes into
``app.routes``. Instead each mounted sub-router appears as an opaque
``_IncludedRouter`` node whose real children are produced lazily by its
``effective_candidates()`` method (the leaves are ``_EffectiveRouteContext``
objects carrying the prefix-resolved ``.path`` / ``.endpoint``). Older versions
flattened the leaf routes directly. Tests that introspect registered paths /
endpoints must walk the tree recursively to stay version-agnostic; the runtime
behavior is identical (the TestClient end-to-end tests pass on both), only the
shape of ``app.routes`` changed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any


def walk_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Yield every leaf route, descending into nested router containers.

    Handles three container shapes so a single helper works across fastapi
    versions: the ``_IncludedRouter.effective_candidates()`` view (>=0.116),
    a plain ``.routes`` collection (Mount / older nested routers), and flat
    leaves. Each yielded leaf exposes ``.path`` / ``.endpoint`` where applicable.
    """
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            yield from walk_routes(candidates())
            continue
        nested = getattr(route, "routes", None)
        if nested:
            yield from walk_routes(nested)
            continue
        yield route
