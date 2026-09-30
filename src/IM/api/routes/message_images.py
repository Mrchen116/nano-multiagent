"""Member-gated HTTP delivery of immutable chat resources."""

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from IM.api.deps import (
    GatewayPrincipal,
    current_data_principal,
    current_gateway,
    current_company_admin,
    require_conversation_access,
)
from IM.api.routes.messages import AttachmentPayload
from IM.domain.models import User
from IM.api.attachment_upload import image_content_type, upload_chunks, upload_error
from IM.infra.repositories.agents import AgentProfileRepository
from IM.infra.gateway_persistence import GatewayConversationPersistence

router = APIRouter(tags=["message-images"])
_MAX_BYTES = 10 * 1024 * 1024


@router.post(
    "/im/v1/conversations/{conversation_id}/images",
    response_model=AttachmentPayload,
    status_code=201,
)
async def create_image(
    conversation_id: str,
    request: Request,
    response: Response,
    file_name: str = Query(min_length=1),
    idempotency_key: str = Header(min_length=1, alias="Idempotency-Key"),
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
) -> AttachmentPayload:
    """Upload raw raster bytes within the caller's conversation membership.

    Returns:
        A stable private URL, with 201 for creation or 200 for a same-byte retry.

    Raises:
        HTTPException: 401/404 for access, 409 for key conflicts, 413 for size,
            or 415 for unsupported or mismatching image types.
    """
    require_conversation_access(request, user, conversation_id, agent_id)
    safe_name = Path(file_name.strip()).name
    if not safe_name or not idempotency_key.strip():
        raise HTTPException(400, "file_name and Idempotency-Key must be non-empty")
    mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise HTTPException(415, "unsupported image type")

    def validate(data: bytes) -> None:
        if image_content_type(data) != mime:
            raise HTTPException(415, "image content does not match content type")

    async def reauthorize() -> None:
        fresh = await current_data_principal(request)
        require_conversation_access(request, fresh, conversation_id, agent_id)

    try:
        image, created = await request.app.state.message_image_repository.put_stream(
            conversation_id=conversation_id,
            source_key=idempotency_key,
            chunks=upload_chunks(request),
            owner_id=user.owner_id if isinstance(user, GatewayPrincipal) else user.id,
            content_type=mime,
            file_name=safe_name,
            max_bytes=_MAX_BYTES,
            validate=validate,
            authorize=reauthorize,
            commit_guard=request.app.state.company_gate,
        )
    except ValueError as exc:
        raise upload_error(exc) from exc
    response.status_code = 201 if created else 200
    return AttachmentPayload(
        url=image.url, content_type=image.content_type, file_name=image.file_name
    )


@router.get("/im/v1/conversations/{conversation_id}/images/{image_id}")
def get_image(
    conversation_id: str,
    image_id: str,
    request: Request,
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
) -> FileResponse:
    """Read a private image only within the caller's existing conversation scope."""
    require_conversation_access(request, user, conversation_id, agent_id)
    repository = request.app.state.message_image_repository
    image = repository.get(conversation_id=conversation_id, image_id=image_id)
    if image is None or not (repository.directory / image.storage_name).is_file():
        raise HTTPException(404, "image not found")
    return FileResponse(
        repository.directory / image.storage_name,
        media_type=image.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/im/v1/conversations/{conversation_id}/attachments/{resource_id}")
def get_attachment(
    conversation_id: str,
    resource_id: str,
    request: Request,
    agent_id: str | None = None,
    user: User | GatewayPrincipal = Depends(current_data_principal),
) -> FileResponse:
    """Read a conversation's ordinary file using the same private snapshot store."""
    require_conversation_access(request, user, conversation_id, agent_id)
    repository = request.app.state.message_image_repository
    resource = repository.get(conversation_id=conversation_id, image_id=resource_id)
    if resource is None or not (repository.directory / resource.storage_name).is_file():
        raise HTTPException(404, "attachment not found")
    return FileResponse(
        repository.directory / resource.storage_name,
        media_type=resource.content_type,
        filename=resource.file_name,
        content_disposition_type="inline"
        if resource.content_type
        in {"image/png", "image/jpeg", "image/webp", "image/gif"}
        else "attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


class ImageDeliveryTarget(BaseModel):
    """Identify a node-owned sender and its intended image recipient."""

    agent_id: str = Field(min_length=1)
    target: str = Field(min_length=1)


@router.post("/im/v1/image-delivery/target")
def resolve_image_delivery_target(
    payload: ImageDeliveryTarget,
    request: Request,
    principal: GatewayPrincipal = Depends(current_gateway),
) -> dict[str, str]:
    """Resolve the private image destination before Gateway reads any local bytes."""
    profile = AgentProfileRepository(request.app.state.connection).get_profile(
        agent_id=payload.agent_id
    )
    if (
        profile is None
        or profile.is_stale
        or profile.node_id != principal.node_id
        or profile.owner_id != principal.owner_id
    ):
        raise HTTPException(404, "target not accessible")
    try:
        resolution = GatewayConversationPersistence(
            request.app.state.connection
        ).resolve_send_target(
            source_agent_id=payload.agent_id,
            target=payload.target,
            # Match the existing agent.message route's direct-chat ownership policy.
            caller_owner_id=None,
        )
    except ValueError as exc:
        raise HTTPException(404, "target not accessible") from exc
    require_conversation_access(
        request, principal, resolution.conversation_id, payload.agent_id
    )
    return {"conversation_id": resolution.conversation_id}


@router.get("/im/v1/attachments/capacity")
def attachment_capacity(
    request: Request,
    user: User = Depends(current_company_admin),
) -> dict:
    """Expose current storage capacity only to company administrators."""
    return request.app.state.message_image_repository.capacity()
