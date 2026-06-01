"""Append-only JSONL writer with background batching."""

import asyncio
import json
import queue
import threading
import time
from pathlib import Path


class JsonlWriter:
    """Append-only JSONL writer with background batching.

    - enqueue: 入内存 buffer，立即返回，不阻塞 caller
    - _run:    后台线程，每 100ms 或 buffer 满 50 条时批量 flush
    - flush:   强制刷盘，asyncio-safe（内部用 run_in_executor）

    > NOTE: JSONL 文件只追加不删，长期运行会无限增长。清理由 product 层决定。
    > NOTE: _session_histories 内存无上限，product 层需控制并发 session 数。
    """

    _BATCH_SIZE = 50
    _FLUSH_INTERVAL_MS = 100

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[Path, dict] | threading.Event] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._last_error: Exception | None = None

    def enqueue(self, path: Path, entry: dict) -> None:
        self._queue.put((path, entry))

    def flush(self, timeout: float = 10.0) -> None:
        """Block until all queued writes are done. Raise on timeout or background error."""
        if self._last_error is not None:
            raise self._last_error
        event = threading.Event()
        self._queue.put(event)
        if not event.wait(timeout=timeout):
            raise TimeoutError(f"JsonlWriter flush timed out after {timeout}s")
        if self._last_error is not None:
            raise self._last_error

    async def flush_async(self) -> None:
        """Async-safe flush — never blocks the asyncio event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.flush)

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
