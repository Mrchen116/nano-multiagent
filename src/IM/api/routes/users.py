"""User routes for IM HTTP APIs."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from IM.api.deps import get_user_service
from IM.application.user_service import UserService
from IM.domain.models import User

router = APIRouter(tags=["users"])


class CreateUserRequest(BaseModel):
    """Request payload for creating a chat user."""

    username: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class UserResponse(BaseModel):
    """Serialized user object returned by API endpoints."""

    id: str
    username: str
    display_name: str
    owner_id: str
    owned_node_ids: list[str]
    created_at: str


def to_user_response(user: User) -> UserResponse:
    """Convert domain user to API response model."""
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        owner_id=user.owner_id,
        owned_node_ids=user.owned_node_ids,
        created_at=user.created_at,
    )


@router.post("/im/v1/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Create a chat user persisted in SQLite."""
    try:
        created = service.create_user(
            username=payload.username,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return to_user_response(created)


@router.get("/im/v1/users", response_model=list[UserResponse])
def list_users(service: UserService = Depends(get_user_service)) -> list[UserResponse]:
    """List all users in creation order."""
    return [to_user_response(item) for item in service.list_users()]
