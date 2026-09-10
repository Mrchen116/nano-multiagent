"""Owner-gated HTTP delivery of immutable Agent reply images."""

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from IM.api.deps import current_user, get_web_im_service
from IM.api.routes.messages import AttachmentPayload
from IM.application.web_im_service import WebIMService
from IM.domain.models import User
from IM.infra.repositories.message_images import ImageConflictError

router = APIRouter(tags=["message-images"])
_MAX_BYTES = 10 * 1024 * 1024


def _assert_owner(service: WebIMService, conversation_id: str, owner_id: str) -> None:
    if (
        service.get_conversation_for_owner(
            conversation_id=conversation_id, owner_id=owner_id
        )
        is None
    ):
        raise HTTPException(404, "conversation_id not found")


def _content_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


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
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> AttachmentPayload:
    """Upload raw raster bytes under the authenticated conversation owner.

    Returns:
        A stable private URL, with 201 for creation or 200 for a same-byte retry.

    Raises:
        HTTPException: 401/404 for access, 409 for key conflicts, 413 for size,
            or 415 for unsupported or mismatching image types.
    """
    _assert_owner(service, conversation_id, user.owner_id)
    safe_name = Path(file_name.strip()).name
    if not safe_name or not idempotency_key.strip():
        raise HTTPException(400, "file_name and Idempotency-Key must be non-empty")
    mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise HTTPException(415, "unsupported image type")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_BYTES:
            raise HTTPException(413, "image exceeds 10 MiB")
        body.extend(chunk)
    data = bytes(body)
    if _content_type(data) != mime:
        raise HTTPException(415, "image content does not match content type")
    try:
        image, created = await run_in_threadpool(
            request.app.state.message_image_repository.put,
            conversation_id=conversation_id,
            source_key=idempotency_key,
            data=data,
            content_type=mime,
            file_name=safe_name,
        )
    except ImageConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    response.status_code = 201 if created else 200
    return AttachmentPayload(
        url=image.url, content_type=image.content_type, file_name=image.file_name
    )


@router.get("/im/v1/conversations/{conversation_id}/images/{image_id}")
def get_image(
    conversation_id: str,
    image_id: str,
    request: Request,
    user: User = Depends(current_user),
    service: WebIMService = Depends(get_web_im_service),
) -> FileResponse:
    """Read a private image only within the caller's existing conversation scope."""
    _assert_owner(service, conversation_id, user.owner_id)
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
