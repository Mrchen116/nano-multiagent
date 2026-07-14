"""Append-only JSONL writer with background batching."""

import asyncio
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any


_STOP = object()


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
        buffer: list[tuple[Path, dict]] = []
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

    def _flush_buffer(self, buffer: list[tuple[Path, dict]]) -> None:
        by_path: dict[Path, list[dict]] = {}
        for path, entry in buffer:
            by_path.setdefault(path, []).append(entry)
        for path, entries in by_path.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
