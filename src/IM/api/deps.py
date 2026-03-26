"""Dependency helpers for IM API routes."""

import os

from fastapi import HTTPException, Request, status

from IM.application.bind_service import BindService
from IM.application.config_service import ConfigService
from IM.application.event_service import EventService
from IM.application.metrics_service import MetricsService
from IM.application.node_service import NodeService
from IM.application.policy_service import PolicyService
from IM.application.relay_service import RelayService
from IM.application.user_service import UserService
from IM.application.web_im_service import WebIMService
from IM.infra.repositories import AgentProfileRepository, BindRepository, ConversationRepository, EventRepository, MessageRepository, NodeRepository, SettingsPolicyRepository, UsageMetricsRepository, UserRepository
from IM.ws.gateway_handler import GatewayHandler


class _ConfigEnabledConversationRepository(ConversationRepository):
    """Enable M96 config profile snapshots without forking the canonical repository."""

    def _resolve_config_profile_version(self, *, owner_id: str, participant_ids: list[str]) -> int | None:
        if not participant_ids:
            return None
        rows = self._connection.execute(
            f"SELECT profile_version FROM agent_profiles WHERE agent_id IN ({','.join('?' for _ in participant_ids)}) ORDER BY rowid LIMIT 1",  # noqa: S608
            tuple(participant_ids),
        ).fetchall()
        if not rows:
            return None
        return int(rows[0]["profile_version"])

    def get_conversation(self, *, conversation_id: str):  # type: ignore[override]
        row = self._connection.execute(
            """
            SELECT id, title, type, owner_id, is_pinned, is_muted, unread_count, last_message_at, config_profile_version, created_at
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_conversation(row)

    def update_conversation(
        self,
        *,
        conversation_id: str,
        title: str | None,
        is_pinned: bool | None,
        is_muted: bool | None,
    ):
        existing = self.get_conversation(conversation_id=conversation_id)
        if existing is None:
            raise ValueError("conversation_id not found")
        next_title = existing.title if title is None else title.strip()
        if not next_title:
            raise ValueError("title must be non-empty")
        next_is_pinned = existing.is_pinned if is_pinned is None else is_pinned
        next_is_muted = existing.is_muted if is_muted is None else is_muted
        with self._connection:
            self._connection.execute(
                """
                UPDATE conversations
                SET title = ?, is_pinned = ?, is_muted = ?
                WHERE id = ?
                """,
                (next_title, int(next_is_pinned), int(next_is_muted), conversation_id),
            )
        updated = self.get_conversation(conversation_id=conversation_id)
        assert updated is not None
        return updated

    def list_conversations(self):  # type: ignore[override]
        rows = self._connection.execute(
            """
            SELECT id, title, type, owner_id, creator_id, is_pinned, is_muted, unread_count, last_message_preview, last_message_at, config_profile_version, created_at
            FROM conversations
            ORDER BY is_pinned DESC, COALESCE(last_message_at, created_at) DESC, rowid DESC
            """
        ).fetchall()
        return [self._row_to_conversation(row) for row in rows]


def _build_conversation_repository(request: Request) -> ConversationRepository:
    """Return the canonical conversation repository with M96 snapshot behavior enabled."""
    return _ConfigEnabledConversationRepository(request.app.state.connection)


def _build_message_repository(request: Request) -> MessageRepository:
    """Return the canonical message repository for the running IM app."""
    return MessageRepository(request.app.state.connection)


def _build_user_repository(request: Request) -> UserRepository:
    """Return the canonical user repository for the running IM app."""
    return UserRepository(request.app.state.connection)


def _build_profile_repository(request: Request) -> AgentProfileRepository:
    """Return the canonical agent profile repository for the running IM app."""
    return AgentProfileRepository(request.app.state.connection)


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
        relay_service=RelayService(request.app.state.connection),
        metrics_service=MetricsService(metrics=UsageMetricsRepository(request.app.state.connection)),
    )


def get_event_service(request: Request) -> EventService:
    """Build the event application service from app-scoped dependencies."""
    return EventService(events=EventRepository(request.app.state.connection))


def get_config_service(request: Request) -> ConfigService:
    """Build the agent config application service from app-scoped dependencies."""
    gateway_handler = get_gateway_handler(request)
    return ConfigService(
        profiles=_build_profile_repository(request),
        nodes=_build_node_repository(request),
        config_sync_notifier=lambda node_id, agent_id, profile_version: gateway_handler.push_config_sync(
            target_node_id=node_id,
            agent_id=agent_id,
            profile_version=profile_version,
        ),
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
        bind_base_url=os.getenv("IM_BIND_BASE_URL", "http://127.0.0.1:8011/bind/confirm"),
    )


def get_relay_service(request: Request) -> RelayService:
    """Build the relay application service from app-scoped dependencies."""
    return RelayService(request.app.state.connection)


def get_gateway_handler(request: Request) -> GatewayHandler:
    """Return the singleton gateway websocket handler for the running IM app."""
    return request.app.state.gateway_handler


def assert_conversation_exists(request: Request, *, conversation_id: str) -> None:
    """Raise 404 when target conversation does not exist."""
    row = request.app.state.connection.execute(
        "SELECT 1 FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation_id not found",
        )
