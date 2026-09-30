"""Admin-only admission; suspension closes company transports before returning."""

from fastapi import APIRouter, Depends, HTTPException, Request, Query

from IM.api.deps import current_company_admin
from IM.api.routes.auth import _to_user_response
from IM.application.company_service import CompanyError, CompanyService
from IM.domain.models import User

router = APIRouter(prefix="/im/v1/company", tags=["company"])


@router.get("/members")
def list_members(
    request: Request,
    cursor: str = Query(default="", max_length=128),
    admin: User = Depends(current_company_admin),
) -> dict:
    """List humans without disclosing their session or machine credentials."""
    return CompanyService(request.app.state.db_path).list_members(cursor=cursor)


@router.post("/members/{user_id}/{action}")
async def change_member(
    user_id: str,
    action: str,
    request: Request,
    admin: User = Depends(current_company_admin),
):
    """Apply a membership transition, then remove every old live connection."""
    if action not in {"approve", "suspend"}:
        raise HTTPException(404, "unknown membership operation")
    try:
        user = CompanyService(request.app.state.db_path).transition(
            actor_id=admin.id, user_id=user_id, action=action
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except CompanyError as exc:
        raise HTTPException(409, str(exc)) from exc
    if action == "suspend":
        await request.app.state.user_stream_registry.close_user(
            user_id, membership_status="suspended"
        )
        await request.app.state.gateway_sessions.revoke_owner(owner_id=user_id)
    return _to_user_response(user)
