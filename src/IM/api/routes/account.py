"""Account and device binding routes for IM HTTP APIs."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from IM.api.deps import current_user, get_bind_service
from IM.application.bind_service import BindService
from IM.domain.models import DeviceBindRequest, User

router = APIRouter(tags=["account"])


class MeResponse(BaseModel):
    """Serialized current-user object for account APIs."""

    id: str
    user_id: str
    username: str
    display_name: str
    owner_id: str
    owned_node_ids: list[str]
    default_entry_node_id: str | None
    created_at: str


class UpdateMeRequest(BaseModel):
    """Request payload for updating current-user settings."""

    display_name: str = Field(min_length=1)
    default_entry_node_id: str | None = None


class StartBindRequest(BaseModel):
    """Request payload for creating a pending device bind."""

    node_id: str = Field(min_length=1)


class ConfirmBindRequest(BaseModel):
    """Request payload for confirming one pending device bind."""

    bind_id: str = Field(min_length=1)


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
    """Union-like bind request envelope for start or confirm actions.

    ``user_id`` was removed for feat-340-M1 R4: the confirm action now takes the
    confirming user from the Bearer token (``current_user`` dependency).
    """

    action: str = Field(pattern="^(start|confirm)$")
    node_id: str | None = None
    bind_id: str | None = None
    bind_token: str | None = None


def to_me_response(user: User) -> MeResponse:
    """Convert a domain user to the account response model."""
    return MeResponse(
        id=user.id,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        owner_id=user.owner_id,
        owned_node_ids=user.owned_node_ids,
        default_entry_node_id=user.default_entry_node_id,
        created_at=user.created_at,
    )


def _resolve_bind_url(bind_url: str, *, request: Request) -> str:
    """Rebase one stored bind URL onto the current IM host while preserving query params."""
    parsed = urlsplit(bind_url)
    query = urlencode(parse_qsl(parsed.query, keep_blank_values=True))
    return urlunsplit((request.url.scheme, request.url.netloc, parsed.path, query, parsed.fragment))


def to_bind_response(bind: DeviceBindRequest, *, request: Request) -> BindResponse:
    """Convert a domain bind request to the API response model."""
    return BindResponse(
        bind_id=bind.bind_id,
        node_id=bind.node_id,
        user_id=bind.user_id,
        status=bind.status,
        bind_url=_resolve_bind_url(bind.bind_url, request=request),
        created_at=bind.created_at,
        confirmed_at=bind.confirmed_at,
    )


@router.get("/im/v1/me", response_model=MeResponse)
def get_me(
    user: User = Depends(current_user),
    service: BindService = Depends(get_bind_service),
) -> MeResponse:
    """Return the current user snapshot derived from the Bearer token subject."""
    # Refresh owned_node_ids / default_entry_node_id from the bind service so the
    # response stays consistent with mutations made through /im/v1/bind.
    refreshed = service.get_me(user_id=user.id)
    return to_me_response(refreshed or user)


@router.patch("/im/v1/me", response_model=MeResponse)
def update_me(
    payload: UpdateMeRequest,
    user: User = Depends(current_user),
    service: BindService = Depends(get_bind_service),
) -> MeResponse:
    """Update the current user's mutable settings."""
    try:
        updated = service.update_me(
            user_id=user.id,
            display_name=payload.display_name,
            default_entry_node_id=payload.default_entry_node_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "user_id not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return to_me_response(updated)


@router.post("/im/v1/bind", response_model=BindResponse, status_code=status.HTTP_201_CREATED)
def bind_device(
    payload: BindRequestEnvelope,
    request: Request,
    user: User = Depends(current_user),
    service: BindService = Depends(get_bind_service),
) -> BindResponse:
    """Start or confirm a device binding request.

    Confirm uses the authenticated user from the Bearer token; clients no longer
    pass ``user_id`` in the body (R4: token is the source of truth for identity).
    """
    try:
        if payload.action == "start":
            if not payload.node_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_id is required for start")
            bind = service.start_bind(node_id=payload.node_id)
            return to_bind_response(bind, request=request)
        if not payload.bind_id and not payload.bind_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="bind_id or bind_token is required for confirm",
            )
        bind = service.confirm_bind(bind_id=payload.bind_id, bind_token=payload.bind_token, user_id=user.id)
        return to_bind_response(bind, request=request)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if detail in {"node_id not found", "user_id not found", "bind_id not found", "bind_token not found"}:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
