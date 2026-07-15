"""Authenticated HTTP entrypoints for external agent channels."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from IM.api.deps import current_user, get_channel_control_service
from IM.application.channel_control_service import ChannelControlService
from IM.domain.models import User
from IM.infra.channel_control_store import (
    ChannelControlError,
    ChannelRemovalView,
    ChannelView,
)

router = APIRouter(tags=["agent-channels"])


class CredentialsRequest(BaseModel):
    """Explicitly retain or replace a provider credential."""

    mode: Literal["keep", "replace"]
    app_secret: str | None = None


class CreateChannelRequest(BaseModel):
    """Create a unique provider channel for an agent."""

    provider: str
    enabled: bool = True
    config: dict[str, object]
    credentials: CredentialsRequest


class UpdateChannelRequest(BaseModel):
    """Update channel desired state using an optimistic revision."""

    channel_revision: int = Field(ge=1)
    enabled: bool
    config: dict[str, object]
    credentials: CredentialsRequest


class ChannelResponse(BaseModel):
    """Secret-free desired and observed channel projection."""

    channel_id: str
    provider: str
    enabled: bool
    config: dict[str, object]
    secret_configured: bool
    channel_revision: int
    sync_state: str
    observed: dict[str, object] | None
    updated_at: str


class ChannelRemovalResponse(BaseModel):
    """Secret-free projection while runtime deletion awaits confirmation."""

    resource_type: Literal["removal"] = "removal"
    channel_id: str
    provider: str
    display_config: dict[str, object]
    deletion_manifest_revision: int
    apply_state: Literal["pending", "failed"]
    apply_error: dict[str, str] | None
    created_at: str


def _response(view: ChannelView) -> ChannelResponse:
    return ChannelResponse(
        channel_id=view.channel_id,
        provider=view.provider,
        enabled=view.enabled,
        config=view.config,
        secret_configured=view.secret_configured,
        channel_revision=view.channel_revision,
        sync_state=view.sync_state,
        observed=view.observed,
        updated_at=view.updated_at,
    )


def _removal_response(view: ChannelRemovalView) -> ChannelRemovalResponse:
    return ChannelRemovalResponse(
        channel_id=view.channel_id,
        provider=view.provider,
        display_config=view.display_config,
        deletion_manifest_revision=view.deletion_manifest_revision,
        apply_state=view.apply_state,
        apply_error=view.apply_error,
        created_at=view.created_at,
    )


def _resource_response(
    view: ChannelView | ChannelRemovalView,
) -> ChannelResponse | ChannelRemovalResponse:
    if isinstance(view, ChannelRemovalView):
        return _removal_response(view)
    return _response(view)


def _raise(error: ChannelControlError) -> None:
    detail: dict[str, object] = {"code": error.code}
    if error.code == "channel_revision_conflict" and error.current is not None:
        detail["current"] = _response(error.current).model_dump()
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get(
    "/im/v1/agents/{agent_id}/channels",
    response_model=list[ChannelResponse | ChannelRemovalResponse],
)
def list_agent_channels(
    agent_id: str,
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> list[ChannelResponse | ChannelRemovalResponse]:
    """List external channels for one authenticated owner's agent."""
    try:
        return [
            _resource_response(view)
            for view in service.list_channels(owner_id=user.owner_id, agent_id=agent_id)
        ]
    except ChannelControlError as error:
        _raise(error)


@router.delete(
    "/im/v1/agents/{agent_id}/channels/{channel_id}",
    response_model=ChannelRemovalResponse,
)
def delete_agent_channel(
    agent_id: str,
    channel_id: str,
    channel_revision: int = Query(ge=1),
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> ChannelRemovalResponse:
    """Persist desired deletion and return its durable removal receipt."""
    try:
        return _removal_response(
            service.delete_channel(
                owner_id=user.owner_id,
                agent_id=agent_id,
                channel_id=channel_id,
                channel_revision=channel_revision,
            )
        )
    except ChannelControlError as error:
        _raise(error)


@router.post(
    "/im/v1/agents/{agent_id}/channels/{channel_id}/actions/reconnect",
    response_model=ChannelResponse,
)
def reconnect_agent_channel(
    agent_id: str,
    channel_id: str,
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> ChannelResponse:
    """Issue an ephemeral reconnect command only to a connected node."""
    try:
        return _response(
            service.reconnect_channel(
                owner_id=user.owner_id,
                agent_id=agent_id,
                channel_id=channel_id,
            )
        )
    except ChannelControlError as error:
        _raise(error)


@router.post(
    "/im/v1/agents/{agent_id}/channel-removals/{channel_id}/actions/retry",
    response_model=ChannelRemovalResponse,
)
def retry_agent_channel_removal(
    agent_id: str,
    channel_id: str,
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> ChannelRemovalResponse:
    """Replay a failed removal without advancing the desired revision."""
    try:
        return _removal_response(
            service.retry_removal(
                owner_id=user.owner_id,
                agent_id=agent_id,
                channel_id=channel_id,
            )
        )
    except ChannelControlError as error:
        _raise(error)


@router.post(
    "/im/v1/agents/{agent_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_channel(
    agent_id: str,
    payload: CreateChannelRequest,
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> ChannelResponse:
    """Create and securely seal a provider channel without exposing its secret."""
    try:
        return _response(
            service.create_channel(
                owner_id=user.owner_id,
                agent_id=agent_id,
                provider=payload.provider,
                enabled=payload.enabled,
                config=payload.config,
                credential_mode=payload.credentials.mode,
                app_secret=payload.credentials.app_secret,
            )
        )
    except ChannelControlError as error:
        _raise(error)


@router.patch(
    "/im/v1/agents/{agent_id}/channels/{channel_id}",
    response_model=ChannelResponse,
)
def update_agent_channel(
    agent_id: str,
    channel_id: str,
    payload: UpdateChannelRequest,
    user: User = Depends(current_user),
    service: ChannelControlService = Depends(get_channel_control_service),
) -> ChannelResponse:
    """Update a provider channel using explicit credential semantics."""
    try:
        return _response(
            service.update_channel(
                owner_id=user.owner_id,
                agent_id=agent_id,
                channel_id=channel_id,
                channel_revision=payload.channel_revision,
                enabled=payload.enabled,
                config=payload.config,
                credential_mode=payload.credentials.mode,
                app_secret=payload.credentials.app_secret,
            )
        )
    except ChannelControlError as error:
        _raise(error)
