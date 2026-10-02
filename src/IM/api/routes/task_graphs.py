"""Read-only task graph endpoints authenticated by active company membership."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from IM.api.deps import current_user
from IM.application.task_graphs import TaskGraphActor
from IM.domain.models import User
from IM.domain.task_graphs import TaskGraphError

router = APIRouter(tags=["task-graphs"])


def _read(request: Request, user: User, action: str, args: dict) -> dict:
    try:
        return request.app.state.task_graphs.execute(
            TaskGraphActor("user", user.id), action, args
        )
    except TaskGraphError as exc:
        raise HTTPException(
            404 if exc.code == "not_found_or_forbidden" else 400, exc.as_dict()
        ) from None
    except sqlite3.Error:
        raise HTTPException(
            503,
            {
                "code": "source_unavailable",
                "message": "Task storage is temporarily unavailable",
            },
        ) from None


@router.get("/im/v1/task-graphs")
def list_task_graphs(
    request: Request,
    query: str = "",
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(current_user),
) -> dict:
    """List company task summaries without consuming chat state."""
    args = {"query": query, "limit": limit}
    if cursor is not None:
        args["cursor"] = cursor
    return _read(request, user, "list", args)


@router.get("/im/v1/task-graphs/{graph_id}")
def get_task_graph(
    graph_id: str,
    request: Request,
    scope_id: str | None = None,
    view: str = "scope",
    user: User = Depends(current_user),
) -> dict:
    """Return a current graph or local scope after checking active company membership."""
    args = {"graph_id": graph_id, "view": view}
    if scope_id is not None:
        args["scope_id"] = scope_id
    return _read(request, user, "get", args)


@router.get("/im/v1/conversations/{conversation_id}/task-activity")
def list_task_activity(
    conversation_id: str, request: Request, user: User = Depends(current_user)
) -> dict:
    """List nodes created or edited in an independently authorized conversation."""
    return _read(request, user, "activity", {"conversation_id": conversation_id})
