"""Freeze intentional reply artifacts and project their durable channel receipts."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import errno
import hashlib
import json
import inspect
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from threading import RLock
from typing import Any, Callable
from urllib.parse import quote, urlsplit
import uuid

import httpx

from personal_assistant.gateway.reply_image_stream import (
    mask_reply_images,
    transform_images,
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024


def external_retry_allowed(
    receipt: dict[str, Any], *, now: float | None = None
) -> bool:
    """Keep automatic Feishu replay inside its one-hour UUID deduplication window."""
    first = receipt.get("first_attempt_at")
    return (
        isinstance(first, (int, float))
        and (time.time() if now is None else now) - first < 3600
    )


@dataclass(frozen=True)
class ReplyImageContext:
    """Identify a bubble and its workspace for relative source paths."""

    output_key: str
    owner_id: str
    agent_id: str
    run_id: str
    bubble_id: str
    workspace: Path


@dataclass
class ReplyImage:
    """Persist one source snapshot and separately scoped delivery receipts."""

    ordinal: int
    source_identity: str
    snapshot_id: str = ""
    content_type: str = ""
    file_name: str = "image.png"
    sha256: str = ""
    status: str = "ready"
    error_code: str = ""
    im_receipts: dict[str, str] = field(default_factory=dict)
    feishu_receipts: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class PreparedReply:
    """Hold ordered Markdown placeholders backed by immutable local resources."""

    output_key: str
    markdown_template: str
    images: list[ReplyImage]


class ImageDeliveryError(ValueError):
    """Report private preparation failures without publishing any draft text."""

    def __init__(self, images: list[dict[str, Any]]) -> None:
        self.images = images
        super().__init__("Image preparation failed")

    def as_result(self, *, target: str, draft_id: str) -> dict[str, Any]:
        """Return the short structured result shared by explicit dispatch paths."""
        first = self.images[0]
        return {
            "ok": False,
            "status": "delivery_failed",
            "target": target,
            "draft_id": draft_id,
            "images": self.images,
            "message": f"This message was not sent. Image {first['ordinal']} failed: {first['error_code']}. Correct the image source or retry the upload before sending again.",
        }


def has_image_references(markdown: str) -> bool:
    """Recognize complete or malformed image syntax outside escaped/code examples."""
    return mask_reply_images(markdown) != markdown


def image_sources(markdown: str) -> tuple[str, ...]:
    """Enumerate distinct actual image references without reading any bytes."""
    sources: dict[str, None] = {}

    def collect(match: re.Match[str]) -> str:
        sources[match.group(2) or match.group(3)] = None
        return match.group(0)

    transform_images(markdown, collect)
    return tuple(sources)


def _failure(image: ReplyImage, code: str) -> ImageDeliveryError:
    return ImageDeliveryError(
        [
            {
                "ordinal": image.ordinal + 1,
                "source": image.source_identity,
                "error_code": code,
            }
        ]
    )


def image_failure(reason: str) -> str:
    """Return a safe channel-visible failure without source paths."""

    reasons = {
        "limit": "超过图片数量或大小限制",
        "source": "图片来源不可用",
        "type": "图片格式不支持",
        "upload": "图片上传失败",
        "missing": "图片快照不可用",
        "legacy": "此图片仅可在飞书查看",
    }
    return f"（图片未能展示：{reasons.get(reason, '图片处理失败')}）"


def _open_local_image(workspace: Path, source: str) -> int:
    path = Path(source)
    if not path.is_absolute():
        path = workspace.absolute() / path
    components = Path(os.path.abspath(path)).parts[1:]
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in components[:-1]:
            next_fd = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = next_fd
        image_fd = os.open(
            components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
        )
        if not stat.S_ISREG(os.fstat(image_fd).st_mode):
            os.close(image_fd)
            raise ValueError("not_regular_file")
        return image_fd
    finally:
        os.close(fd)


def _read_local_image(image_fd: int) -> tuple[bytes, str]:
    if os.fstat(image_fd).st_size > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")
    data = os.pread(image_fd, MAX_IMAGE_BYTES + 1, 0)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("image_too_large")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "image/webp"
    raise ValueError("unsupported_image_type")


def _local_image(workspace: Path, source: str) -> tuple[bytes, str]:
    fd = _open_local_image(workspace, source)
    try:
        return _read_local_image(fd)
    finally:
        os.close(fd)


@contextmanager
def open_local_sources(workspace: Path, markdown: str):
    """Bind regular local sources before authorization without reading their bytes.

    Keep this context open through permission resolution and pass the returned
    mapping to prepare so a path replacement cannot substitute another file.
    """
    descriptors: dict[str, int] = {}
    try:
        for ordinal, source in enumerate(image_sources(markdown), 1):
            if urlsplit(source).scheme or source.startswith(("img_", "/im/v1/")):
                continue
            try:
                descriptors[source] = _open_local_image(workspace, source)
            except (OSError, ValueError) as exc:
                raise ImageDeliveryError(
                    [
                        {
                            "ordinal": ordinal,
                            "source": source,
                            "error_code": _source_error(exc),
                        }
                    ]
                ) from exc
        yield descriptors
    finally:
        for fd in descriptors.values():
            os.close(fd)


def _source_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "file_not_found"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, OSError) and exc.errno in {errno.ELOOP, errno.ENOTDIR}:
        return "symlink_not_allowed"
    return str(exc) if isinstance(exc, ValueError) else "file_read_failed"


class ReplyImages:
    """Own durable snapshots and channel projections for existing bubble IDs."""

    def __init__(
        self,
        state_root: Path,
        *,
        im_base_url: str = "",
        token_getter: Callable[[], str | None] | None = None,
    ) -> None:
        self.root = state_root
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = self.root / "reply_images.sqlite3"
        self._lock = RLock()
        self._im_base_url = im_base_url.rstrip("/")
        self._token_getter = token_getter
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_dispatch_inputs (input_key TEXT PRIMARY KEY, call_id TEXT NOT NULL, output_key TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_image_aliases (alias_key TEXT PRIMARY KEY, output_key TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_deliveries (output_key TEXT, channel TEXT, receipt_json TEXT NOT NULL, PRIMARY KEY(output_key, channel))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reply_image_outputs (output_key TEXT PRIMARY KEY, owner_id TEXT, agent_id TEXT, run_id TEXT, bubble_id TEXT, manifest_json TEXT NOT NULL)"
            )

    def load(self, output_key: str) -> PreparedReply | None:
        """Load the existing manifest without opening any original source."""

        with self._lock, sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT manifest_json FROM reply_image_outputs WHERE output_key=COALESCE((SELECT output_key FROM reply_image_aliases WHERE alias_key=?), ?)",
                (output_key, output_key),
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        data["images"] = [ReplyImage(**item) for item in data["images"]]
        return PreparedReply(**data)

    def bind_output(self, alias_key: str, output_key: str) -> None:
        """Bind a durable shadow bubble to its already-authorized candidate manifest."""
        if alias_key == output_key:
            return
        with self._lock, sqlite3.connect(self._db) as conn:
            if self.load(output_key) is None:
                raise ValueError("prepared image manifest is missing")
            conn.execute(
                "INSERT OR REPLACE INTO reply_image_aliases VALUES (?, ?)",
                (alias_key, output_key),
            )

    def prepare(
        self,
        context: ReplyImageContext,
        markdown: str,
        *,
        im_conversation_id: str | None = None,
        local_files: dict[str, int] | None = None,
    ) -> PreparedReply:
        """Snapshot sources or reuse protected references in the same IM chat.

        Args:
            context: Immutable output identity and source workspace.
            markdown: Original reply text containing at most five distinct images.
            im_conversation_id: Current target whose hosted images may be reused;
                their existing IM read authorization remains authoritative.
            local_files: File descriptors bound before ordinary reply authorization.

        Returns:
            Saved immutable image preparation.

        Raises:
            ImageDeliveryError: A source cannot be safely read or snapshotted.
        """

        with self._lock:
            existing = self.load(context.output_key)
            if existing is not None:
                self.ensure_ready(existing)
                return existing
            images: list[ReplyImage] = []
            by_source: dict[str, ReplyImage] = {}

            def replace(match: re.Match[str]) -> str:
                source = match.group(2) or match.group(3)
                resource = by_source.get(source)
                if resource is None:
                    resource = ReplyImage(len(images), source)
                    by_source[source] = resource
                    images.append(resource)
                    try:
                        if len(images) > 5:
                            raise ValueError("too_many_images")
                        if im_conversation_id and re.fullmatch(
                            re.escape(
                                f"/im/v1/conversations/{quote(im_conversation_id, safe='')}/images/"
                            )
                            + r"[0-9a-f]{32}",
                            source,
                        ):
                            resource.status = "im"
                            resource.error_code = "source"
                            resource.im_receipts[im_conversation_id] = source
                        elif source.startswith("img_"):
                            resource.status = "legacy"
                        else:
                            if urlsplit(source).scheme in {"http", "https", "data"}:
                                from personal_assistant.channels.feishu.client import (
                                    OutboundImageReadError,
                                    read_outbound_image,
                                )

                                try:
                                    data, mime = read_outbound_image(source)
                                except OutboundImageReadError as exc:
                                    raise ValueError(exc.error_code) from exc
                            else:
                                data, mime = (
                                    _read_local_image(local_files[source])
                                    if local_files is not None and source in local_files
                                    else _local_image(context.workspace, source)
                                )
                            resource.content_type = mime
                            resource.file_name = "image." + {
                                "image/jpeg": "jpg",
                                "image/webp": "webp",
                                "image/gif": "gif",
                            }.get(mime, "png")
                            resource.sha256 = hashlib.sha256(data).hexdigest()
                            resource.snapshot_id = uuid.uuid4().hex
                            temporary = self.root / (resource.snapshot_id + ".tmp")
                            with temporary.open("xb") as stream:
                                stream.write(data)
                                stream.flush()
                                os.fsync(stream.fileno())
                            temporary.replace(self.root / resource.snapshot_id)
                    except (ValueError, OSError) as exc:
                        resource.status = "failed"
                        resource.error_code = _source_error(exc)
                if resource.status == "failed":
                    return f"![{match.group(1)}](nano-image-pending:{resource.ordinal})"
                return f"![{match.group(1)}](nano-image-pending:{resource.ordinal})"

            result = PreparedReply(
                context.output_key, transform_images(markdown, replace), images
            )
            if "（图片未能展示：图片引用不完整）" in result.markdown_template:
                raise ImageDeliveryError(
                    [
                        {
                            "ordinal": len(images) + 1,
                            "error_code": "invalid_image_reference",
                            "source": "",
                        }
                    ]
                )
            self.ensure_ready(result)
            try:
                with sqlite3.connect(self._db) as conn:
                    conn.execute(
                        "INSERT INTO reply_image_outputs VALUES (?,?,?,?,?,?)",
                        (
                            context.output_key,
                            context.owner_id,
                            context.agent_id,
                            context.run_id,
                            context.bubble_id,
                            json.dumps(asdict(result)),
                        ),
                    )
            except (OSError, sqlite3.Error):
                raise ImageDeliveryError(
                    [
                        {
                            "ordinal": 1,
                            "source": "",
                            "error_code": "snapshot_write_failed",
                        }
                    ]
                )
            return result

    @staticmethod
    def ensure_ready(reply: PreparedReply) -> None:
        """Reject the entire draft if any source could not be prepared."""
        errors = [
            {
                "ordinal": item.ordinal + 1,
                "source": item.source_identity,
                "error_code": item.error_code,
            }
            for item in reply.images
            if item.status == "failed"
        ]
        if errors:
            raise ImageDeliveryError(errors)

    def delivery_receipt(self, output_key: str, channel: str) -> dict[str, Any] | None:
        """Load durable delivery state for one stable output and destination."""
        with self._lock, sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT receipt_json FROM reply_deliveries WHERE output_key=? AND channel=?",
                (output_key, channel),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def dispatch_identity(
        self, *, agent_id: str, session_id: str, target: str, text: str, call_id: str
    ) -> str:
        """Reuse an unresolved send identity while allowing later intentional sends."""
        input_key = hashlib.sha256(
            json.dumps(
                [agent_id, session_id, target, text], ensure_ascii=False
            ).encode()
        ).hexdigest()
        with self._lock, sqlite3.connect(self._db) as conn:
            previous = conn.execute(
                "SELECT call_id, output_key FROM reply_dispatch_inputs WHERE input_key=?",
                (input_key,),
            ).fetchone()
            if previous:
                receipts = [
                    json.loads(row[0])
                    for row in conn.execute(
                        "SELECT receipt_json FROM reply_deliveries WHERE output_key=?",
                        (previous[1],),
                    ).fetchall()
                ]
                if receipts and any(
                    item.get("state", item.get("status")) != "delivered"
                    for item in receipts
                ):
                    return previous[0]
            output_key = f"dispatch:{agent_id}:{session_id}:{call_id}"
            conn.execute(
                "INSERT OR REPLACE INTO reply_dispatch_inputs VALUES (?,?,?)",
                (input_key, call_id, output_key),
            )
            return call_id

    def unresolved_deliveries(
        self, *, limit: int = 100
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """List bounded unresolved channel publications that have replay payloads."""
        with self._lock, sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT output_key, channel, receipt_json FROM reply_deliveries "
                "WHERE json_extract(receipt_json, '$.recovery') IS NOT NULL "
                "AND COALESCE(json_extract(receipt_json, '$.state'), json_extract(receipt_json, '$.status'), '') != 'delivered' "
                "ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        return [(key, channel, json.loads(receipt)) for key, channel, receipt in rows]

    def record_delivery(
        self, output_key: str, channel: str, receipt: dict[str, Any]
    ) -> None:
        """Persist confirmed or uncertain delivery before another attempt."""
        with self._lock, sqlite3.connect(self._db) as conn:
            previous = conn.execute(
                "SELECT receipt_json FROM reply_deliveries WHERE output_key=? AND channel=?",
                (output_key, channel),
            ).fetchone()
            prior = json.loads(previous[0]) if previous else {}
            receipt = dict(receipt)
            if "first_attempt_at" in prior:
                receipt["first_attempt_at"] = prior["first_attempt_at"]
            elif receipt.get("recovery", {}).get("kind") == "external_prepared":
                receipt.setdefault("first_attempt_at", time.time())
            conn.execute(
                "INSERT OR REPLACE INTO reply_deliveries VALUES (?,?,?)",
                (output_key, channel, json.dumps(receipt)),
            )

    def image_bytes(self, image: ReplyImage) -> bytes:
        """Read only the saved immutable snapshot, verifying its stored digest."""

        data = (self.root / image.snapshot_id).read_bytes()
        if hashlib.sha256(data).hexdigest() != image.sha256:
            raise ValueError("missing")
        return data

    @staticmethod
    def render(reply: PreparedReply, replacements: dict[int, str]) -> str:
        """Project placeholders only when every image has a complete destination."""

        def replace(match: re.Match[str]) -> str:
            source = match.group(2) or match.group(3)
            if not source.startswith("nano-image-pending:"):
                return match.group(0)
            ordinal = int(source.split(":")[1])
            value = replacements.get(ordinal)
            if value is None:
                image = next(item for item in reply.images if item.ordinal == ordinal)
                raise _failure(image, "snapshot_unavailable")
            if value.startswith("（图片未能展示"):
                image = next(item for item in reply.images if item.ordinal == ordinal)
                raise _failure(image, "upload_failed")
            return f"![{match.group(1)}]({value})"

        return transform_images(reply.markdown_template, replace)

    def _save(self, reply: PreparedReply) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "UPDATE reply_image_outputs SET manifest_json=? WHERE output_key=?",
                (json.dumps(asdict(reply)), reply.output_key),
            )

    def record_provider_receipts(self, output_key: str, preparation: Any) -> None:
        """Persist partial provider success before any chat message is published."""

        with self._lock:
            reply = self.load(output_key)
            if reply is None:
                raise ValueError("reply manifest missing")
            scope = f"{preparation.connector_account_id}:{preparation.app_id}"
            for entry in preparation.entries:
                image = next(
                    item for item in reply.images if item.ordinal == entry.ordinal
                )
                image.feishu_receipts[scope] = {
                    "image_key": entry.image_key or "",
                    "error_code": entry.error_code or "",
                }
            self._save(reply)

    def outbound_images(self, reply: PreparedReply, app_id: str) -> tuple[Any, ...]:
        """Materialize provider inputs from snapshots and same-account receipts."""

        from personal_assistant.channels.base import OutboundImage

        result = []
        for item in (self.load(reply.output_key) or reply).images:
            if item.status == "failed":
                continue
            receipt = item.feishu_receipts.get(f"{app_id}:{app_id}", {})
            key = (
                item.source_identity
                if item.status == "legacy"
                else receipt.get("image_key")
            )
            try:
                if item.status == "im":
                    # A protected chat reference grants no cross-channel export.
                    data, error = b"", "missing"
                else:
                    data = b"" if key else self.image_bytes(item)
                    error = (
                        None  # Failed uploads are retryable; only successes are cached.
                    )
            except (OSError, ValueError):
                data, error = b"", "missing"
            result.append(
                OutboundImage(
                    item.ordinal, data, item.content_type, item.file_name, key, error
                )
            )
        return tuple(result)

    async def resolve_target(self, target: str, *, agent_id: str) -> str:
        """Resolve and authorize an image destination before reading local bytes."""
        token = self._token_getter() if self._token_getter else None
        if inspect.isawaitable(token):
            token = await token
        if not token:
            raise ImageDeliveryError(
                [{"ordinal": 1, "source": "", "error_code": "target_unavailable"}]
            )
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
                response = await client.post(
                    f"{self._im_base_url}/im/v1/image-delivery/target",
                    json={"agent_id": agent_id, "target": target},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                return response.json()["conversation_id"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ImageDeliveryError(
                [{"ordinal": 1, "source": "", "error_code": "target_not_accessible"}]
            ) from exc

    async def project_im(
        self, prepared: PreparedReply, conversation_id: str, *, agent_id: str
    ) -> str:
        """Upload absent conversation resources and return durable private URLs.

        Args:
            prepared: Immutable source snapshots for this reply.
            conversation_id: Target chat to associate with the resources.
            agent_id: Executing Agent used for this node's resource authorization.

        Returns:
            Reply Markdown containing protected resource URLs.
        """

        reply = self.load(prepared.output_key) or prepared
        if not reply.images:
            return reply.markdown_template
        replacements: dict[int, str] = {}
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            for item in reply.images:
                if item.status == "im" and conversation_id in item.im_receipts:
                    replacements[item.ordinal] = item.im_receipts[conversation_id]
                    continue
                if item.status != "ready":
                    raise _failure(item, item.error_code or "unsupported_channel_image")
                url = item.im_receipts.get(conversation_id)
                if not url:
                    try:
                        token = self._token_getter() if self._token_getter else None
                        if inspect.isawaitable(token):
                            token = await token
                        if not token:
                            raise httpx.ConnectError(
                                "IM image upload requires a registered Gateway connection"
                            )
                        data = await asyncio.to_thread(self.image_bytes, item)
                        response = await client.post(
                            f"{self._im_base_url}/im/v1/conversations/{quote(conversation_id, safe='')}/images",
                            params={"file_name": item.file_name, "agent_id": agent_id},
                            content=data,
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": item.content_type,
                                "Idempotency-Key": f"{reply.output_key}:{item.ordinal}",
                            },
                        )
                        if response.status_code >= 500 or response.status_code in {
                            401,
                            404,
                        }:
                            response.raise_for_status()
                        if response.is_success:
                            url = response.json()["url"]
                            with self._lock:
                                latest = self.load(reply.output_key) or reply
                                latest.images[item.ordinal].im_receipts[
                                    conversation_id
                                ] = url
                                self._save(latest)
                    except (OSError, ValueError, httpx.HTTPError) as exc:
                        raise _failure(
                            item,
                            "upload_failed"
                            if isinstance(exc, httpx.HTTPError)
                            else "snapshot_unavailable",
                        ) from exc
                if not url:
                    raise _failure(item, "upload_failed")
                replacements[item.ordinal] = url
        return self.render(reply, replacements)
