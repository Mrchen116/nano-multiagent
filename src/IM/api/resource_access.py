"""Authorize and rebind private resource references at the message write boundary."""

import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from IM.api.deps import GatewayPrincipal, require_conversation_access
from IM.domain.models import User

_RESOURCE = re.compile(
    r"(?:(https?://[^\s/]+))?"
    r"(/im/v1/conversations/([^/\s?#]+)/"
    r"(?:images|attachments)/([0-9a-f]{32}))(?![0-9a-f])"
)


def authorize_resource_references(
    request: Request,
    principal: User | GatewayPrincipal,
    conversation_id: str,
    text: str,
    agent_id: str | None = None,
) -> str:
    """Rebind same-IM resource links only when the caller can read their source.

    External URLs remain external. A URL by itself never grants access to a local
    resource, including when it appears in Markdown rather than an attachment field.
    """
    repository = request.app.state.message_image_repository
    origin = urlsplit(str(request.base_url)).netloc.lower()

    def replace(match: re.Match[str]) -> str:
        if match[1] and urlsplit(match[1]).netloc.lower() != origin:
            return match[0]
        source_id = match[3]
        require_conversation_access(request, principal, source_id, agent_id)
        if repository.get(conversation_id=source_id, image_id=match[4]) is None:
            raise HTTPException(404, "resource not found")
        if source_id == conversation_id:
            return match[0]
        return repository.copy_references(
            source_conversation_id=source_id,
            target_conversation_id=conversation_id,
            content=match[2],
        )

    return _RESOURCE.sub(replace, text)
