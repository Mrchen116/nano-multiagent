"""Expose member-scoped chat commands without exposing Agent configuration."""

import asyncio
import hashlib
import hmac
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from IM.api.deps import current_user, get_gateway_control
from IM.api.routes.agents import AgentCommandResponse, coerce_allowlist_options
from IM.domain.models import Actor, AgentProfile, User
from IM.domain.skill_selection import DEFAULT_DISCOVERY, effective_skills_selection_mode
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.repositories.conversations import ConversationRepository
from IM.ws.gateway.control import GatewayControl

router = APIRouter(tags=["conversations"])


class ChatSkillResponse(BaseModel):
    """Describe a selectable Skill using an opaque source identity."""

    skill_key: str
    name: str
    description: str


class ChatAgentCommandsResponse(BaseModel):
    """Project one chat Agent's usable commands or temporary unavailability."""

    agent_id: str
    display_name: str
    status: Literal["available", "unavailable"] = "unavailable"
    skills: list[ChatSkillResponse] = Field(default_factory=list)
    commands: list[AgentCommandResponse] = Field(default_factory=list)


class ChatCommandsResponse(BaseModel):
    """Return independently available command catalogs for chat Agents."""

    items: list[ChatAgentCommandsResponse]


def _skill_key(secret: str, node_id: str, location: str | None, name: str) -> str:
    identity = json.dumps(
        [node_id, "location" if location else "name", location or name],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hmac.new(
        secret.encode(),
        b"nano-im:conversation-skill:v1\0" + identity.encode(),
        hashlib.sha256,
    ).hexdigest()


async def _agent_commands(
    actor: Actor,
    profile: AgentProfile | None,
    gateway: GatewayControl,
    secret: str,
) -> ChatAgentCommandsResponse:
    result = ChatAgentCommandsResponse(
        agent_id=actor.id,
        display_name=profile.display_name
        if profile
        else actor.display_name or actor.id,
    )
    if (
        profile is None
        or profile.is_stale
        or not profile.node_id
        or not profile.workspace_root
    ):
        return result
    try:
        config = await gateway.request_agent_config(
            target_node_id=profile.node_id, agent_id=profile.agent_id
        )
        if not isinstance(config, dict):
            return result
        capabilities = await gateway.request_agent_capabilities(
            target_node_id=profile.node_id,
            agent_id=profile.agent_id,
            workspace_root=profile.workspace_root,
        )
    except Exception:
        # A failed node must not hide other participants' available commands.
        return result
    if not isinstance(capabilities, dict):
        return result
    configured_skills = config.get("skills")
    allowed = (
        [item for item in configured_skills if isinstance(item, str)]
        if isinstance(configured_skills, list)
        else profile.skills
    )
    mode = effective_skills_selection_mode(
        config.get("skills_selection_mode") or profile.skills_selection_mode, allowed
    )
    result.skills = [
        ChatSkillResponse(
            skill_key=_skill_key(secret, profile.node_id, skill.location, skill.name),
            name=skill.name,
            description=skill.description,
        )
        for skill in coerce_allowlist_options(capabilities.get("skills"))
        if mode == DEFAULT_DISCOVERY or skill.name in allowed
    ]
    commands = capabilities.get("commands")
    for item in commands if isinstance(commands, list) else []:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
        ):
            continue
        description = item.get("description")
        result.commands.append(
            AgentCommandResponse(
                name=item["name"].strip(),
                description=description.strip() if isinstance(description, str) else "",
            )
        )
    result.status = "available"
    return result


@router.get(
    "/im/v1/conversations/{conversation_id}/commands",
    response_model=ChatCommandsResponse,
)
async def get_conversation_commands(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),
    gateway: GatewayControl = Depends(get_gateway_control),
) -> ChatCommandsResponse:
    """Read usable slash candidates after checking live chat membership.

    Args:
        conversation_id: Chat whose Agent members provide the commands.
        request: Current IM application request.
        user: Authenticated human identity.
        gateway: Existing Gateway config and capability RPC transport.

    Returns:
        Per-Agent command and Skill catalogs, without machine paths or configuration.
    """
    conversations = ConversationRepository(request.app.state.connection)
    conversation = conversations.get_conversation_for_member(
        conversation_id=conversation_id, user_id=user.id
    )
    if conversation is None:
        raise HTTPException(404, "conversation_not_accessible")
    profiles = AgentProfileRepository(request.app.state.connection)
    items = await asyncio.gather(
        *(
            _agent_commands(
                actor,
                profiles.get_profile(agent_id=actor.id),
                gateway,
                request.app.state.command_key_secret,
            )
            for actor in conversation.participants
            if actor.type == "agent"
        )
    )
    current = conversations.get_conversation_for_member(
        conversation_id=conversation_id, user_id=user.id
    )
    if current is None:
        raise HTTPException(404, "conversation_not_accessible")
    agent_ids = {actor.id for actor in current.participants if actor.type == "agent"}
    return ChatCommandsResponse(
        items=[item for item in items if item.agent_id in agent_ids]
    )
