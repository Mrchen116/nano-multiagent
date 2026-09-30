"""Persist immutable private image snapshots and conversation-scoped references."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3
import threading
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, nullcontext

from IM.infra import attachment_quota
from uuid import uuid4


@dataclass(frozen=True)
class MessageImage:
    """A completed image reference; storage names never come from clients."""

    image_id: str
    conversation_id: str
    source_key: str
    sha256: str
    content_type: str
    file_name: str
    byte_size: int
    storage_name: str

    @property
    def url(self) -> str:
        """Return the stable owner-gated relative resource URL."""
        return f"/im/v1/conversations/{self.conversation_id}/images/{self.image_id}"

    @property
    def attachment_url(self) -> str:
        """Return the ordinary attachment address for the same private snapshot."""
        return (
            f"/im/v1/conversations/{self.conversation_id}/attachments/{self.image_id}"
        )


class ImageConflictError(ValueError):
    """The caller reused a source identity for different snapshot bytes."""


class AttachmentCapacityError(ValueError):
    """The service cannot currently accept more attachment bytes."""


class AttachmentBusyError(ValueError):
    """An owner already has two uploads in progress."""


class AttachmentTooLargeError(ValueError):
    """A stream exceeded its per-file size bound."""


class MessageImageRepository:
    """Store snapshots separately from the legacy public upload directory."""

    def __init__(self, connection: sqlite3.Connection, directory: Path) -> None:
        """Bind metadata and private immutable file storage."""
        self._connection = connection
        self.directory = directory
        self._quota_lock = threading.RLock()

    def reconcile_storage(self) -> None:
        """Reclaim interrupted uploads at startup before accepting new traffic."""
        self.directory.mkdir(parents=True, exist_ok=True)
        for path in self.directory.glob(".*.tmp"):
            path.unlink(missing_ok=True)
        with self._connection:
            rows = self._connection.execute(
                "SELECT storage_name FROM attachment_storage WHERE state = 'reserved'"
            ).fetchall()
            for row in rows:
                (self.directory / row["storage_name"]).unlink(missing_ok=True)
            self._connection.execute(
                "DELETE FROM attachment_storage WHERE state = 'reserved'"
            )
        self.collect_unreferenced()

    def collect_unreferenced(self) -> None:
        """Release billing only after the last reference's physical file is deleted."""
        with self._quota_lock, self._connection:
            rows = self._connection.execute(
                "SELECT storage_name FROM attachment_storage WHERE state = 'stored' "
                "AND storage_name NOT IN (SELECT storage_name FROM message_images)"
            ).fetchall()
            for row in rows:
                (self.directory / row["storage_name"]).unlink(missing_ok=True)
                self._connection.execute(
                    "DELETE FROM attachment_storage WHERE storage_name = ?",
                    (row["storage_name"],),
                )

    def capacity(self) -> dict:
        """Return current service usage and owner capacity warnings for administrators."""
        rows = self._connection.execute(
            "SELECT owner_id, state, SUM(byte_size) AS size FROM attachment_storage GROUP BY owner_id, state"
        ).fetchall()
        service = {
            "used_bytes": 0,
            "reserved_bytes": 0,
            "limit_bytes": attachment_quota.SERVICE_LIMIT_BYTES,
        }
        owners: dict[str, dict] = {}
        for row in rows:
            key = "used_bytes" if row["state"] == "stored" else "reserved_bytes"
            service[key] += row["size"]
            if row["owner_id"] is not None:
                owner = owners.setdefault(
                    row["owner_id"],
                    {
                        "owner_id": row["owner_id"],
                        "used_bytes": 0,
                        "reserved_bytes": 0,
                        "limit_bytes": attachment_quota.OWNER_LIMIT_BYTES,
                    },
                )
                owner[key] += row["size"]
        for item in [service, *owners.values()]:
            item["full"] = (
                item["used_bytes"] + item["reserved_bytes"] >= item["limit_bytes"]
            )
        return {"service": service, "owners": list(owners.values())}

    def _reserve(self, storage_name: str, owner_id: str, size: int) -> None:
        # BEGIN IMMEDIATE serializes the check and reservation across connections.
        with self._quota_lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            if size == 0:
                count = self._connection.execute(
                    "SELECT COUNT(*) FROM attachment_storage WHERE owner_id = ? AND state = 'reserved'",
                    (owner_id,),
                ).fetchone()[0]
                if count >= 2:
                    raise AttachmentBusyError("attachment upload busy")
                self._connection.execute(
                    "INSERT INTO attachment_storage VALUES (?, ?, 0, 'reserved')",
                    (storage_name, owner_id),
                )
            totals = self._connection.execute(
                "SELECT COALESCE(SUM(byte_size), 0), COALESCE(SUM(CASE WHEN owner_id = ? THEN byte_size ELSE 0 END), 0) FROM attachment_storage",
                (owner_id,),
            ).fetchone()
            if (
                totals[0] + size > attachment_quota.SERVICE_LIMIT_BYTES
                or totals[1] + size > attachment_quota.OWNER_LIMIT_BYTES
            ):
                raise AttachmentCapacityError("attachment upload unavailable")
            self._connection.execute(
                "UPDATE attachment_storage SET byte_size = byte_size + ? WHERE storage_name = ?",
                (size, storage_name),
            )

    async def put_stream(
        self,
        *,
        conversation_id: str,
        source_key: str,
        chunks: AsyncIterable[bytes],
        owner_id: str,
        content_type: str,
        file_name: str,
        max_bytes: int,
        validate: Callable[[bytes], None] | None = None,
        authorize: Callable[[], Awaitable[object]] | None = None,
        commit_guard: AbstractAsyncContextManager | None = None,
    ) -> tuple[MessageImage, bool]:
        """Reserve each chunk before writing and atomically publish a bounded upload.

        Args:
            conversation_id: Authorized destination conversation.
            source_key: Idempotency identity within that conversation.
            chunks: Incoming request stream.
            owner_id: Authenticated human or machine administrator to bill.
            content_type: Validated declared media type.
            file_name: Safe display filename.
            max_bytes: Inclusive single-file size limit.
            validate: Optional validator for the bounded file prefix.
            authorize: Recheck access immediately before publication.
            commit_guard: Serialize final publication with company revocation.

        Returns:
            Completed reference and whether it was newly created.
        """
        storage_name = uuid4().hex
        self._reserve(storage_name, owner_id, 0)
        retrying = self._by_source(conversation_id, source_key) is not None
        temporary = self.directory / f".{storage_name}.tmp"
        destination = self.directory / storage_name
        digest = hashlib.sha256()
        size = 0
        prefix = bytearray()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with temporary.open("wb") as handle:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise AttachmentTooLargeError("attachment exceeds 10 MiB")
                    if not retrying:
                        self._reserve(storage_name, owner_id, len(chunk))
                    handle.write(chunk)
                    digest.update(chunk)
                    prefix.extend(chunk[: max(0, 32 - len(prefix))])
            async with commit_guard or nullcontext():
                if validate:
                    validate(bytes(prefix))
                if authorize:
                    await authorize()
                with self._quota_lock, self._connection:
                    existing = self._by_source(conversation_id, source_key)
                    if existing:
                        return self._same_snapshot(existing, digest.hexdigest()), False
                    image = MessageImage(
                        uuid4().hex,
                        conversation_id,
                        source_key,
                        digest.hexdigest(),
                        content_type,
                        file_name,
                        size,
                        storage_name,
                    )
                    temporary.replace(destination)
                    self._insert(image)
                    self._connection.execute(
                        "UPDATE attachment_storage SET state = 'stored' WHERE storage_name = ?",
                        (storage_name,),
                    )
                return image, True
        finally:
            temporary.unlink(missing_ok=True)
            with self._quota_lock, self._connection:
                row = self._connection.execute(
                    "SELECT state FROM attachment_storage WHERE storage_name = ?",
                    (storage_name,),
                ).fetchone()
                if row is not None and row["state"] == "reserved":
                    destination.unlink(missing_ok=True)
                    self._connection.execute(
                        "DELETE FROM attachment_storage WHERE storage_name = ?",
                        (storage_name,),
                    )

    def get(self, *, conversation_id: str, image_id: str) -> MessageImage | None:
        """Return a completed reference in this conversation, or None."""
        row = self._connection.execute(
            "SELECT * FROM message_images WHERE conversation_id = ? AND image_id = ?",
            (conversation_id, image_id),
        ).fetchone()
        return MessageImage(**dict(row)) if row else None

    def _by_source(self, conversation_id: str, source_key: str) -> MessageImage | None:
        row = self._connection.execute(
            "SELECT * FROM message_images WHERE conversation_id = ? AND source_key = ?",
            (conversation_id, source_key),
        ).fetchone()
        return MessageImage(**dict(row)) if row else None

    def put(
        self,
        *,
        conversation_id: str,
        source_key: str,
        data: bytes,
        content_type: str,
        file_name: str,
    ) -> tuple[MessageImage, bool]:
        """Commit an immutable snapshot after atomic file publication.

        Returns:
            Image and whether it was newly created; same-key retries reuse it.

        Raises:
            ImageConflictError: The same key names different bytes.
            OSError: Storage failed; no incomplete resource is published.
        """
        digest = hashlib.sha256(data).hexdigest()
        existing = self._by_source(conversation_id, source_key)
        if existing:
            return self._same_snapshot(existing, digest), False
        self.directory.mkdir(parents=True, exist_ok=True)
        image = MessageImage(
            uuid4().hex,
            conversation_id,
            source_key,
            digest,
            content_type,
            file_name,
            len(data),
            uuid4().hex,
        )
        destination = self.directory / image.storage_name
        temporary = self.directory / f".{image.storage_name}.tmp"
        try:
            temporary.write_bytes(data)
            temporary.replace(destination)
            with self._connection:
                self._insert(image)
                self._connection.execute(
                    "INSERT INTO attachment_storage VALUES (?, NULL, ?, 'stored')",
                    (image.storage_name, image.byte_size),
                )
        except BaseException as exc:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            if isinstance(exc, sqlite3.IntegrityError):
                existing = self._by_source(conversation_id, source_key)
                if existing:
                    return self._same_snapshot(existing, digest), False
            raise
        return image, True

    def _same_snapshot(self, image: MessageImage, digest: str) -> MessageImage:
        if image.sha256 != digest:
            raise ImageConflictError("image source key already has different content")
        return image

    def _insert(self, image: MessageImage) -> None:
        self._connection.execute(
            "INSERT INTO message_images "
            "(image_id, conversation_id, source_key, sha256, content_type, file_name, byte_size, storage_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                image.image_id,
                image.conversation_id,
                image.source_key,
                image.sha256,
                image.content_type,
                image.file_name,
                image.byte_size,
                image.storage_name,
            ),
        )

    def copy_references(
        self,
        *,
        source_conversation_id: str,
        target_conversation_id: str,
        content: str,
    ) -> str:
        """Rebind copied body URLs while sharing immutable files with the source.

        Called inside the fork workflow's rollback boundary. References belong to
        the branch, so deleting the source conversation cannot revoke branch reads.
        """
        pattern = re.compile(
            re.escape(f"/im/v1/conversations/{source_conversation_id}/")
            + r"(images|attachments)/([0-9a-f]{32})(?![0-9a-f])"
        )

        def copy(match: re.Match[str]) -> str:
            image = self.get(conversation_id=source_conversation_id, image_id=match[2])
            if image is None:
                return match[0]
            source_key = f"fork:{source_conversation_id}:{image.image_id}"
            copied = self._by_source(target_conversation_id, source_key)
            if copied is None:
                copied = MessageImage(
                    uuid4().hex,
                    target_conversation_id,
                    source_key,
                    image.sha256,
                    image.content_type,
                    image.file_name,
                    image.byte_size,
                    image.storage_name,
                )
                with self._connection:
                    self._insert(copied)
            return copied.url if match[1] == "images" else copied.attachment_url

        return pattern.sub(copy, content)
