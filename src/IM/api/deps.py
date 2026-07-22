"""Dependency helpers for IM API routes."""

import asyncio
import concurrent.futures
import os
from collections.abc import Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from IM.application.auth_service import AuthService, InvalidTokenError
from IM.application.bind_service import BindService
from IM.application.channel_control_service import ChannelControlService
from IM.application.config_service import ConfigService
from IM.application.event_service import EventService
from IM.application.metrics_service import MetricsService
from IM.application.node_service import NodeService
from IM.application.policy_service import PolicyService
from IM.application.relay_service import RelayService
from IM.application.user_service import UserService
from IM.application.web_im_service import WebIMService
from IM.domain.models import User
from IM.infra.repositories import (
    AgentProfileRepository,
    BindRepository,
    ConversationRepository,
    MessageRepository,
    NodeRepository,
    SettingsPolicyRepository,
    UsageMetricsRepository,
    UserRepository,
)
from IM.infra.binding_store import BindingStore
from IM.infra.channel_control_store import ChannelManifest
from IM.ws.gateway_handler import GatewayHandler


def _build_conversation_repository(request: Request) -> ConversationRepository:
    """Return the canonical conversation repository for the running IM app."""
    return ConversationRepository(request.app.state.connection)


def _build_message_repository(request: Request) -> MessageRepository:
    """Return the canonical message repository for the running IM app."""
    return request.app.state.message_repository


def _build_user_repository(request: Request) -> UserRepository:
    """Return the canonical user repository for the running IM app."""
    return UserRepository(request.app.state.connection)


def _build_profile_repository(request: Request) -> AgentProfileRepository:
    """Return the canonical agent profile repository for the running IM app."""
    return AgentProfileRepository(request.app.state.connection)


def get_profile_repository(request: Request) -> AgentProfileRepository:
    """Provide agent profile reads to HTTP route composition."""
    return _build_profile_repository(request)


def _build_node_repository(request: Request) -> NodeRepository:
    """Return the canonical node repository for the running IM app."""
    return NodeRepository(request.app.state.connection)


def _build_bind_repository(request: Request) -> BindRepository:
    """Return the canonical bind repository for the running IM app."""
    return BindRepository(request.app.state.connection)


def _build_settings_policy_repository(request: Request) -> SettingsPolicyRepository:
    """Return the singleton settings-policy repository for the running IM app."""
    return SettingsPolicyRepository(request.app.state.connection)


def get_user_service(request: Request) -> UserService:
    """Build the user application service from app-scoped dependencies."""
    return UserService(users=_build_user_repository(request))


def get_web_im_service(request: Request) -> WebIMService:
    """Build the Web IM application service from app-scoped dependencies."""
    return WebIMService(
        conversations=_build_conversation_repository(request),
        messages=_build_message_repository(request),
        boundaries=request.app.state.boundary_repository,
        relay_service=RelayService(request.app.state.connection),
        metrics_service=MetricsService(
            metrics=UsageMetricsRepository(request.app.state.connection)
        ),
    )


def get_event_service(request: Request) -> EventService:
    """Build the event application service from app-scoped dependencies."""
    return EventService(events=request.app.state.event_repository)


def get_config_service(request: Request) -> ConfigService:
    """Build the agent config application service from app-scoped dependencies."""
    gateway_handler = get_gateway_handler(request)
    # feat-394 bugfix: update_agent_config is a sync route (runs in a thread pool).
    # asyncio.get_running_loop() fails in the thread, so the previous code fell back to
    # asyncio.run(push_config_sync(...)), creating an isolated event loop that cannot
    # drive the main loop's WebSocket transport — the config.sync WS frame was never sent.
    # Fix: use asyncio.run_coroutine_threadsafe with the main event loop stored at
    # app startup so the coroutine is submitted to the correct loop from any thread.
    event_loop: asyncio.AbstractEventLoop | None = getattr(
        request.app.state, "event_loop", None
    )

    def _push_config_sync(node_id: str, agent_id: str, profile_version: int) -> None:
        coro = gateway_handler.push_config_sync(
            target_node_id=node_id,
            agent_id=agent_id,
            profile_version=profile_version,
        )
        if event_loop is not None and not event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, event_loop)
        # When no loop is available (e.g. TestClient without lifespan), fall back to
        # asyncio.run so the WS frame is still sent synchronously in the test context.
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(coro)
            else:
                loop.create_task(coro)

    return ConfigService(
        profiles=_build_profile_repository(request),
        nodes=_build_node_repository(request),
        users=_build_user_repository(request),
        config_sync_notifier=_push_config_sync,
    )


def get_node_service(request: Request) -> NodeService:
    """Build the node board application service from app-scoped dependencies."""
    return NodeService(nodes=_build_node_repository(request))


def get_policy_service(request: Request) -> PolicyService:
    """Build the settings-policy application service from app-scoped dependencies."""
    return PolicyService(policies=_build_settings_policy_repository(request))


def get_metrics_service(request: Request) -> MetricsService:
    """Build the usage metrics application service from app-scoped dependencies."""
    return MetricsService(metrics=UsageMetricsRepository(request.app.state.connection))


def get_bind_service(request: Request) -> BindService:
    """Build the account and bind application service from app-scoped dependencies."""
    return BindService(
        users=_build_user_repository(request),
        nodes=_build_node_repository(request),
        binds=_build_bind_repository(request),
        profiles=_build_profile_repository(request),
        binding_store=getattr(
            request.app.state,
            "binding_store",
            BindingStore(request.app.state.db_path),
        ),
        bind_base_url=os.getenv(
            "IM_BIND_BASE_URL", "http://127.0.0.1:8011/bind/confirm"
        ),
    )


def get_channel_control_service(request: Request) -> ChannelControlService:
    """Return the app's independent external-channel control boundary."""
    handler = get_gateway_handler(request)
    event_loop: asyncio.AbstractEventLoop | None = getattr(
        request.app.state, "event_loop", None
    )

    def run_live(coroutine: Coroutine[Any, Any, bool]) -> bool:
        if event_loop is None or event_loop.is_closed():
            return False
        future = asyncio.run_coroutine_threadsafe(coroutine, event_loop)
        try:
            return bool(future.result(timeout=5))
        except (concurrent.futures.TimeoutError, RuntimeError):
            return False

    def notify(manifest: ChannelManifest) -> bool:
        return run_live(handler.push_channel_reconcile(manifest))

    def reconnect(node_id: str, channel_id: str, channel_revision: int) -> bool:
        return run_live(
            handler.push_channel_reconnect(
                target_node_id=node_id,
                channel_id=channel_id,
                channel_revision=channel_revision,
            )
        )

    return ChannelControlService(
        request.app.state.channel_control_store,
        manifest_notifier=notify,
        reconnect_notifier=reconnect,
    )


def get_relay_service(request: Request) -> RelayService:
    """Build the relay application service from app-scoped dependencies."""
    return RelayService(request.app.state.connection)


def get_gateway_handler(request: Request) -> GatewayHandler:
    """Return the singleton gateway websocket handler for the running IM app."""
    return request.app.state.gateway_handler


def assert_conversation_exists(request: Request, *, conversation_id: str) -> None:
    """Raise 404 when target conversation does not exist."""
    if not _build_conversation_repository(request).exists(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation_id not found",
        )


def get_auth_service(request: Request) -> AuthService:
    """Return the singleton AuthService bound to the running IM app."""
    return request.app.state.auth_service


def _extract_bearer_token(request: Request) -> str:
    """Pull a Bearer access token from the Authorization header; raise 401 when missing."""
    raw = request.headers.get("Authorization") or request.headers.get("authorization")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid authorization scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def current_user(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> User:
    """FastAPI dep: resolve the authenticated user from the Authorization header.

    Raises:
        HTTPException 401: when the header is missing, the token is invalid, or the
            user no longer exists. ``WWW-Authenticate: Bearer`` is included so clients
            can react to challenge-style 401s.
    """
    token = _extract_bearer_token(request)
    try:
        user_id = service.verify_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = service.get_user(user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token subject no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
