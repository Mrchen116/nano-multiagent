"""Append-only JSONL writer with background batching."""

import asyncio
import json
import os
import queue
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_STOP = object()


@dataclass(frozen=True, slots=True)
class _AtomicAppendBatch:
    """Entries that must become visible together or not at all."""

    path: Path
    entries: tuple[dict[str, Any], ...]


class JsonlWriter:
    """Append-only JSONL writer with background batching.

    - enqueue: 入内存 buffer，立即返回，不阻塞 caller
    - _run:    后台线程，每 100ms 或 buffer 满 50 条时批量 flush
    - flush:   强制刷盘，asyncio-safe（内部用 run_in_executor）

    > NOTE: JSONL 文件只追加不删，长期运行会无限增长。清理由 product 层决定。
    """

    _BATCH_SIZE = 50
    _FLUSH_INTERVAL_MS = 100

    def __init__(self) -> None:
        self._queue: queue.Queue[Any] = queue.Queue()
        self._lifecycle_guard = threading.Lock()
        self._closed = False
        self._last_error: Exception | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def enqueue_raw(self, path: Path, entry: dict) -> None:
        """Queue one raw JSONL object for ordered append."""

        with self._lifecycle_guard:
            if self._closed:
                raise RuntimeError("JsonlWriter is closed")
            self._queue.put((path, entry))

    def enqueue_atomic_batch(self, path: Path, entries: list[dict]) -> None:
        """Queue one replace-backed JSONL append that is all-or-nothing.

        Compaction boundaries reference replacement turn records. A plain sequence of
        append calls can persist the boundary before its summary, so this narrow API
        makes that linked set visible with one atomic file replacement instead.
        """

        if not entries:
            return
        with self._lifecycle_guard:
            if self._closed:
                raise RuntimeError("JsonlWriter is closed")
            self._queue.put(
                _AtomicAppendBatch(path, tuple(dict(entry) for entry in entries))
            )

    def durable_barrier(self, path: Path, timeout: float = 10.0) -> None:
        """Block until all writes ordered before this path barrier are durable."""

        del path  # The shared FIFO makes a global flush a stronger path barrier.
        with self._lifecycle_guard:
            if self._last_error is not None:
                raise self._last_error
            if self._closed:
                return
            event = threading.Event()
            self._queue.put(event)
        if not event.wait(timeout=timeout):
            raise TimeoutError(f"JsonlWriter flush timed out after {timeout}s")
        if self._last_error is not None:
            raise self._last_error

    async def durable_barrier_async(self, path: Path) -> None:
        """Await a path durability barrier without blocking the event loop."""

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.durable_barrier, path)

    def close(self, timeout: float = 10.0) -> None:
        """Flush accepted writes, stop the worker, and join it exactly once."""

        with self._lifecycle_guard:
            if self._closed:
                return
            self._closed = True
            self._queue.put(_STOP)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError(f"JsonlWriter close timed out after {timeout}s")
        if self._last_error is not None:
            raise self._last_error

    def _run(self) -> None:
        buffer: list[tuple[Path, dict] | _AtomicAppendBatch] = []
        last_flush = time.monotonic()

        while True:
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                if (
                    buffer
                    and (time.monotonic() - last_flush) * 1000
                    >= self._FLUSH_INTERVAL_MS
                ):
                    try:
                        self._flush_buffer(buffer)
                    except Exception as e:
                        self._last_error = e
                    buffer = []
                    last_flush = time.monotonic()
                continue

            if item is _STOP:
                try:
                    if buffer:
                        self._flush_buffer(buffer)
                except Exception as e:
                    self._last_error = e
                return

            if isinstance(item, threading.Event):
                try:
                    if buffer:
                        self._flush_buffer(buffer)
                        buffer = []
                except Exception as e:
                    self._last_error = e
                item.set()
                last_flush = time.monotonic()
                continue

            buffer.append(item)
            if len(buffer) >= self._BATCH_SIZE:
                try:
                    self._flush_buffer(buffer)
                except Exception as e:
                    self._last_error = e
                buffer = []
                last_flush = time.monotonic()

    def _flush_buffer(
        self, buffer: list[tuple[Path, dict] | _AtomicAppendBatch]
    ) -> None:
        pending_by_path: dict[Path, list[dict]] = {}
        for item in buffer:
            if isinstance(item, _AtomicAppendBatch):
                pending = pending_by_path.pop(item.path, ())
                if pending:
                    self._append_entries(item.path, pending)
                self._atomic_append_entries(item.path, item.entries)
                continue
            path, entry = item
            pending_by_path.setdefault(path, []).append(entry)
        for path, entries in pending_by_path.items():
            self._append_entries(path, entries)

    @staticmethod
    def _append_entries(path: Path, entries: list[dict] | tuple[dict, ...]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload)

    @staticmethod
    def _atomic_append_entries(path: Path, entries: tuple[dict[str, Any], ...]) -> None:
        """Append linked records using a same-directory atomic replacement."""

        path.parent.mkdir(parents=True, exist_ok=True)
        replacement = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        payload = "".join(
            json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries
        )
        try:
            with replacement.open("wb") as target:
                if path.exists():
                    with path.open("rb") as source:
                        shutil.copyfileobj(source, target)
                target.write(payload.encode("utf-8"))
                target.flush()
                os.fsync(target.fileno())
            os.replace(replacement, path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                # The replacement is already committed. Some filesystems do not
                # support directory fsync, so never report a failed compaction
                # after making its complete batch visible.
                pass
        finally:
            try:
                replacement.unlink(missing_ok=True)
            except OSError:
                pass
