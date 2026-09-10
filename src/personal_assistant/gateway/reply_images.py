"""Freeze intentional reply artifacts and project their durable channel receipts."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import hashlib
import json
import inspect
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from typing import Any, Callable
from urllib.parse import quote, urlsplit
import uuid

import httpx

from personal_assistant.gateway.reply_image_stream import transform_images

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ReplyImageContext:
    """Identify a bubble and its explicitly exportable workspace."""

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


def _local_image(workspace: Path, source: str) -> tuple[bytes, str]:
    root = workspace.absolute()
    path = Path(source)
    if not path.is_absolute():
        path = root / path
    # Normalize dot segments without following any link. All subsequent traversal
    # uses directory descriptors and O_NOFOLLOW, including the final bounded read.
    path = Path(os.path.abspath(path))
    export = root / ".nanoassistant" / "exports"
    relative = path.relative_to(export)
    components = (*export.parts[1:], *relative.parts)
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
        try:
            info = os.fstat(image_fd)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("source")
            if info.st_size > MAX_IMAGE_BYTES:
                raise ValueError("limit")
            with os.fdopen(image_fd, "rb", closefd=False) as stream:
                data = stream.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("limit")
        finally:
            os.close(image_fd)
    finally:
        os.close(fd)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "image/webp"
    raise ValueError("type")


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
                "CREATE TABLE IF NOT EXISTS reply_image_outputs (output_key TEXT PRIMARY KEY, owner_id TEXT, agent_id TEXT, run_id TEXT, bubble_id TEXT, manifest_json TEXT NOT NULL)"
            )

    def load(self, output_key: str) -> PreparedReply | None:
        """Load the existing manifest without opening any original source."""

        with self._lock, sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT manifest_json FROM reply_image_outputs WHERE output_key=?",
                (output_key,),
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        data["images"] = [ReplyImage(**item) for item in data["images"]]
        return PreparedReply(**data)

    def prepare(self, context: ReplyImageContext, markdown: str) -> PreparedReply:
        """Snapshot at most five distinct sources; represent per-image errors inline."""

        with self._lock:
            existing = self.load(context.output_key)
            if existing is not None:
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
                            raise ValueError("limit")
                        if source.startswith("img_"):
                            resource.status = "legacy"
                        else:
                            if urlsplit(source).scheme in {"http", "https", "data"}:
                                from personal_assistant.channels.feishu.client import (
                                    read_outbound_image,
                                )

                                data, mime = read_outbound_image(source)
                            else:
                                data, mime = _local_image(context.workspace, source)
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
                        resource.error_code = (
                            str(exc) if str(exc) in {"limit", "type"} else "source"
                        )
                if resource.status == "failed":
                    return image_failure(resource.error_code)
                return f"![{match.group(1)}](nano-image-pending:{resource.ordinal})"

            result = PreparedReply(
                context.output_key, transform_images(markdown, replace), images
            )
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
                result.markdown_template = self.render(
                    result, {item.ordinal: image_failure("missing") for item in images}
                )
                for item in images:
                    item.status, item.error_code = "failed", "missing"
            return result

    def image_bytes(self, image: ReplyImage) -> bytes:
        """Read only the saved immutable snapshot, verifying its stored digest."""

        data = (self.root / image.snapshot_id).read_bytes()
        if hashlib.sha256(data).hexdigest() != image.sha256:
            raise ValueError("missing")
        return data

    @staticmethod
    def render(reply: PreparedReply, replacements: dict[int, str]) -> str:
        """Project placeholders into complete image destinations or failure text."""

        def replace(match: re.Match[str]) -> str:
            source = match.group(2) or match.group(3)
            if not source.startswith("nano-image-pending:"):
                return match.group(0)
            value = replacements.get(
                int(source.split(":")[1]), image_failure("missing")
            )
            return (
                value
                if value.startswith("（图片未能展示")
                else f"![{match.group(1)}]({value})"
            )

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
                data = b"" if key else self.image_bytes(item)
                error = receipt.get("error_code")
            except (OSError, ValueError):
                data, error = b"", "missing"
            result.append(
                OutboundImage(
                    item.ordinal, data, item.content_type, item.file_name, key, error
                )
            )
        return tuple(result)

    async def project_im(self, prepared: PreparedReply, conversation_id: str) -> str:
        """Upload absent conversation resources and return durable private URLs."""

        reply = self.load(prepared.output_key) or prepared
        if not reply.images:
            return reply.markdown_template
        replacements: dict[int, str] = {}
        token = self._token_getter() if self._token_getter else None
        if inspect.isawaitable(token):
            token = await token
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            for item in reply.images:
                if item.status != "ready":
                    replacements[item.ordinal] = image_failure(
                        item.error_code or "legacy"
                    )
                    continue
                url = item.im_receipts.get(conversation_id)
                if not url:
                    try:
                        data = await asyncio.to_thread(self.image_bytes, item)
                        response = await client.post(
                            f"{self._im_base_url}/im/v1/conversations/{quote(conversation_id, safe='')}/images",
                            params={"file_name": item.file_name},
                            content=data,
                            headers={
                                "Authorization": f"Bearer {token or ''}",
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
                    except (OSError, ValueError):
                        replacements[item.ordinal] = image_failure("missing")
                        continue
                replacements[item.ordinal] = url or image_failure("upload")
        return self.render(reply, replacements)
