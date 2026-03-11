"""Account and device binding routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_bind_service
from IM.application.bind_service import BindService
from IM.domain.models import DeviceBindRequest, User

router = APIRouter(tags=["account"])


class MeResponse(BaseModel):
    """Serialized current-user object for account APIs."""

    id: str
    username: str
    display_name: str
    owner_id: str
    owned_node_ids: list[str]
    created_at: str


class UpdateMeRequest(BaseModel):
    """Request payload for updating current-user settings."""

    display_name: str = Field(min_length=1)


class StartBindRequest(BaseModel):
    """Request payload for creating a pending device bind."""

    node_id: str = Field(min_length=1)


class ConfirmBindRequest(BaseModel):
    """Request payload for confirming one pending device bind."""

    bind_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class BindResponse(BaseModel):
    """Serialized device bind state returned by bind APIs."""

    bind_id: str
    node_id: str
    user_id: str | None
    status: str
    bind_url: str
    created_at: str
    confirmed_at: str | None


class BindRequestEnvelope(BaseModel):
    """Union-like bind request envelope for start or confirm actions."""

    action: str = Field(pattern="^(start|confirm)$")
    node_id: str | None = None
    bind_id: str | None = None
    user_id: str | None = None


def to_me_response(user: User) -> MeResponse:
    """Convert a domain user to the account response model."""
    return MeResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        owner_id=user.owner_id,
        owned_node_ids=user.owned_node_ids,
        created_at=user.created_at,
    )


def to_bind_response(bind: DeviceBindRequest) -> BindResponse:
    """Convert a domain bind request to the API response model."""
    return BindResponse(
        bind_id=bind.bind_id,
        node_id=bind.node_id,
        user_id=bind.user_id,
        status=bind.status,
        bind_url=bind.bind_url,
        created_at=bind.created_at,
        confirmed_at=bind.confirmed_at,
    )


@router.get("/im/v1/me", response_model=MeResponse)
def get_me(user_id: str, service: BindService = Depends(get_bind_service)) -> MeResponse:
    """Return the current user snapshot with owned node ids."""
    user = service.get_me(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_id not found")
    return to_me_response(user)


@router.patch("/im/v1/me", response_model=MeResponse)
def update_me(
    user_id: str,
    payload: UpdateMeRequest,
    service: BindService = Depends(get_bind_service),
) -> MeResponse:
    """Update the current user's mutable settings."""
    try:
        user = service.update_me(user_id=user_id, display_name=payload.display_name)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "user_id not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return to_me_response(user)


@router.post("/im/v1/bind", response_model=BindResponse, status_code=status.HTTP_201_CREATED)
def bind_device(
    payload: BindRequestEnvelope,
    service: BindService = Depends(get_bind_service),
) -> BindResponse:
    """Start or confirm a device binding request."""
    try:
        if payload.action == "start":
            if not payload.node_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_id is required for start")
            bind = service.start_bind(node_id=payload.node_id)
            return to_bind_response(bind)
        if not payload.bind_id or not payload.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="bind_id and user_id are required for confirm",
            )
        bind = service.confirm_bind(bind_id=payload.bind_id, user_id=payload.user_id)
        return to_bind_response(bind)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if detail in {"node_id not found", "user_id not found", "bind_id not found"}:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
