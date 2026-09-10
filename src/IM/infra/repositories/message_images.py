"""Persist immutable private image snapshots and conversation-scoped references."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3
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


class ImageConflictError(ValueError):
    """The caller reused a source identity for different snapshot bytes."""


class MessageImageRepository:
    """Store snapshots separately from the legacy public upload directory."""

    def __init__(self, connection: sqlite3.Connection, directory: Path) -> None:
        """Bind metadata and private immutable file storage."""
        self._connection = connection
        self.directory = directory

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
            re.escape(f"/im/v1/conversations/{source_conversation_id}/images/")
            + r"([0-9a-f]{32})(?![0-9a-f])"
        )

        def copy(match: re.Match[str]) -> str:
            image = self.get(conversation_id=source_conversation_id, image_id=match[1])
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
            return copied.url

        return pattern.sub(copy, content)
