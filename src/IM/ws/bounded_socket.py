"""Bound live transport memory and recheck persisted authority at delivery."""

import asyncio
import json
import time
from collections.abc import Callable

from fastapi import WebSocket, WebSocketDisconnect


class BoundedSocket:
    """Preserve WebSocket operations while bounding frames, waiters and slow sends."""

    def __init__(
        self,
        websocket: WebSocket,
        *,
        authorized: Callable[[], bool],
        frame_limit: int,
        frames_per_minute: int = 120,
    ):
        self._socket = websocket
        self._authorized = authorized
        self._frame_limit = frame_limit
        self._frames_per_minute = frames_per_minute
        self._window_start = time.monotonic()
        self._received = 0
        self._waiting = 0
        self._pending_bytes = 0
        self._send_lock = asyncio.Lock()

    def __getattr__(self, name):
        return getattr(self._socket, name)

    async def accept(self, *args, **kwargs):
        await self._socket.accept(*args, **kwargs)

    async def close(self, code: int = 1000, reason: str | None = None):
        try:
            await asyncio.wait_for(
                self._socket.close(code=code, reason=reason), timeout=2
            )
        except (RuntimeError, TimeoutError, WebSocketDisconnect):
            pass

    async def revoke(self, membership_status: str | None = None):
        """Deliver only a status control notice after authority has been revoked."""
        if membership_status:
            try:
                async with self._send_lock:
                    await asyncio.wait_for(
                        self._socket.send_json(
                            {
                                "op": "membership_changed",
                                "membership_status": membership_status,
                            }
                        ),
                        timeout=1,
                    )
            except (RuntimeError, TimeoutError, WebSocketDisconnect):
                pass
        await self.close(code=4003)

    async def receive_text(self) -> str:
        text = await self._socket.receive_text()
        if not self._authorized():
            await self.close(code=4003)
            raise WebSocketDisconnect(4003)
        now = time.monotonic()
        if now - self._window_start >= 60:
            self._window_start, self._received = now, 0
        self._received += 1
        if (
            len(text.encode()) > self._frame_limit
            or self._received > self._frames_per_minute
        ):
            await self.close(
                code=1009 if len(text.encode()) > self._frame_limit else 1013
            )
            raise WebSocketDisconnect(1009)
        return text

    async def send_text(self, text: str):
        size = len(text.encode())
        if not self._authorized():
            await self.close(code=4003)
            raise WebSocketDisconnect(4003)
        if self._waiting >= 256 or self._pending_bytes + size > 4 * 1024 * 1024:
            await self.close(code=1013)
            raise WebSocketDisconnect(1013)
        self._waiting += 1
        self._pending_bytes += size
        try:
            async with self._send_lock:
                if not self._authorized():
                    raise WebSocketDisconnect(4003)
                await asyncio.wait_for(self._socket.send_text(text), timeout=5)
        except TimeoutError:
            await self.close(code=1013)
            raise WebSocketDisconnect(1013) from None
        finally:
            self._waiting -= 1
            self._pending_bytes -= size

    async def send_json(self, data, mode: str = "text"):
        await self.send_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")))
