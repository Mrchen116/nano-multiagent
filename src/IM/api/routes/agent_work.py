"""Owner-scoped durable Agent work and permission HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from IM.api.deps import current_user
from IM.domain.models import User
from IM.infra.repositories.agents import AgentProfileRepository

router = APIRouter(tags=["agent-work"])


def _profile(request: Request, user: User, agent_id: str):
    profile = AgentProfileRepository(request.app.state.connection).get_profile(
        agent_id=agent_id
    )
    if profile is None or profile.owner_id != user.owner_id or profile.is_stale:
        raise HTTPException(404, "agent_not_accessible")
    return profile


@router.get("/im/v1/agents/{agent_id}/work")
async def get_work(
    agent_id: str,
    request: Request,
    before_turn: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(current_user),
) -> dict:
    """Read the main timeline and actual linked execution summaries."""
    profile = _profile(request, user, agent_id)
    try:
        view = request.app.state.work_repository.view(agent_id, before_turn, limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    online = (
        await request.app.state.gateway_sessions.snapshot_connection(
            node_id=profile.node_id
        )
        if profile.node_id
        else None
    )
    view["node_connection_state"] = "online" if online else "offline"
    if not online and view["main_execution"] in {"running", "waiting_permission"}:
        view["main_execution"] = "unknown"
    return view


@router.get("/im/v1/agents/{agent_id}/work/sessions/{session_id}/turns")
def get_turns(
    agent_id: str,
    session_id: str,
    request: Request,
    before_turn: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(current_user),
) -> dict:
    """Read turns belonging to one proven child or main Session."""
    _profile(request, user, agent_id)
    try:
        return request.app.state.work_repository.turns(
            agent_id, session_id, before_turn, limit
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None


@router.get("/im/v1/agents/{agent_id}/work/sessions/{session_id}/turns/{turn_id}/items")
def get_items(
    agent_id: str,
    session_id: str,
    turn_id: str,
    request: Request,
    after_seq: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(current_user),
) -> dict:
    """Read the next durable item page in stable observed order."""
    _profile(request, user, agent_id)
    try:
        return request.app.state.work_repository.items(
            agent_id, session_id, turn_id, after_seq, limit
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None


class WorkPermissionDecision(BaseModel):
    """Carry only a decision; execution identity is resolved on the server."""

    decision: str
    reason: str = ""


@router.post("/im/v1/agents/{agent_id}/work/permissions/{request_id}")
async def decide_permission(
    agent_id: str,
    request_id: str,
    body: WorkPermissionDecision,
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    """Apply an offered option to the live broker's actual pending request."""
    profile = _profile(request, user, agent_id)
    try:
        pending = request.app.state.work_repository.pending_permission(
            agent_id, request_id
        )
        if body.decision not in {o["id"] for o in pending.get("options", [])}:
            raise ValueError("invalid_decision")
        result = await request.app.state.gateway_work.permission(
            node_id=profile.node_id,
            root=agent_id,
            request_id=request_id,
            session_id=pending["session_id"],
            decision=body.decision,
            reason=body.reason,
        )
        if not result.get("ok"):
            raise ValueError(result.get("error") or "request_ended")
        return {"ok": True, "request_id": request_id}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
