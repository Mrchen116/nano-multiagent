"""浏览器用户维度的 WebSocket 实时流（每用户一条连接，多标签页可多连接）。"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sqlite3
from fastapi import WebSocket, WebSocketDisconnect

from IM.application.event_service import EventService
from IM.domain.models import ConversationEvent

# 与迁移计划对齐；可用环境变量覆盖（后续可加）
REPLAY_MAX_BATCH = 500
REPLAY_MAX_GAP = 2000
REPLAY_WINDOW_MINUTES = 15


def resolve_recipient_user_ids(connection: sqlite3.Connection, conversation_id: str) -> list[str]:
    """返回应接收该会话事件的 user_id 列表（与 conversation_participants 一致）。"""
    rows = connection.execute(
        "SELECT user_id FROM conversation_participants WHERE conversation_id = ? ORDER BY rowid",
        (conversation_id,),
    ).fetchall()
    return [str(row["user_id"]) for row in rows]


def conversation_event_to_wire_data(event: ConversationEvent) -> dict[str, object]:
    """与 HTTP SSE 的 data 字段语义对齐，供前端沿用既有解析逻辑。"""
    try:
        raw_payload = json.loads(event.payload_json)
        if not isinstance(raw_payload, dict):
            raw_payload = {}
    except json.JSONDecodeError:
        raw_payload = {}
    return {
        **raw_payload,
        "event_id": event.event_id,
        "conversation_id": event.conversation_id,
        "message_id": event.message_id,
        "delivery_status": event.delivery_status,
        "created_at": event.created_at,
    }


def encode_user_stream_event_frame(event: ConversationEvent) -> str:
    """编码为下发给浏览器的一条 JSON 文本帧。"""
    body = {
        "op": "event",
        "event_type": event.event_type,
        "event_id": event.event_id,
        "conversation_id": event.conversation_id,
        "data": conversation_event_to_wire_data(event),
    }
    return json.dumps(body, ensure_ascii=True, separators=(",", ":"))


def replay_cutoff_iso() -> str:
    """回放时间窗下限（UTC ISO）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=REPLAY_WINDOW_MINUTES)
    return cutoff.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """resume 回放结果。"""

    events: list[ConversationEvent]
    resync_required: bool
    reason: str | None


def list_events_for_user_resume(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    after_event_id: int,
) -> ReplayOutcome:
    """按用户可见会话与游标列出待回放事件；必要时要求客户端走 /sync。"""
    row = connection.execute("SELECT MAX(event_id) AS m FROM conversation_events").fetchone()
    max_id = int(row["m"] or 0) if row is not None else 0
    if after_event_id > 0 and max_id - after_event_id > REPLAY_MAX_GAP:
        return ReplayOutcome(events=[], resync_required=True, reason="event_gap_exceeded")

    cutoff = replay_cutoff_iso()
    rows = connection.execute(
        """
        SELECT event_id, conversation_id, message_id, event_type, delivery_status, payload_json, created_at
        FROM conversation_events
        WHERE event_id > ?
          AND created_at >= ?
          AND conversation_id IN (
            SELECT conversation_id FROM conversation_participants WHERE user_id = ?
          )
        ORDER BY event_id
        LIMIT ?
        """,
        (after_event_id, cutoff, user_id, REPLAY_MAX_BATCH),
    ).fetchall()

    # 若游标过旧导致时间窗内没有记录但库里有更新，要求全量对齐
    if after_event_id > 0 and not rows and max_id > after_event_id:
        return ReplayOutcome(events=[], resync_required=True, reason="cursor_stale_or_outside_replay_window")

    events = [
        ConversationEvent(
            event_id=int(r["event_id"]),
            conversation_id=str(r["conversation_id"]),
            message_id=str(r["message_id"]) if r["message_id"] is not None else None,
            event_type=str(r["event_type"]),
            delivery_status=str(r["delivery_status"]),
            payload_json=str(r["payload_json"]),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
    return ReplayOutcome(events=events, resync_required=False, reason=None)


def global_max_event_id(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(event_id) AS m FROM conversation_events").fetchone()
    if row is None or row["m"] is None:
        return 0
    return int(row["m"])


class UserStreamRegistry:
    """进程内维护 user_id → 若干 WebSocket 连接。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_user: dict[str, set[WebSocket]] = defaultdict(set)

    async def add(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._by_user[user_id].add(websocket)

    async def remove(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._by_user.get(user_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                del self._by_user[user_id]

    async def broadcast_to_user(self, user_id: str, text: str) -> None:
        """Send one text frame to all connections owned by ``user_id``.

        Convenience wrapper around ``broadcast_to_users`` for the single-owner case
        used by node/agent status events (feat-340-M10 决策 11). Reusing the
        multi-user path keeps dead-connection pruning and fan-out semantics consistent.
        """
        await self.broadcast_to_users((user_id,), text)

    async def broadcast_to_users(self, user_ids: Iterable[str], text: str) -> None:
        """向给定用户下的所有连接发送同一文本帧（忽略已断开）。"""
        id_set = frozenset(user_ids)
        if not id_set:
            return
        async with self._lock:
            targets: list[tuple[str, WebSocket]] = []
            for uid in id_set:
                for ws in list(self._by_user.get(uid, ())):
                    targets.append((uid, ws))
        dead: list[tuple[str, WebSocket]] = []
        for uid, ws in targets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append((uid, ws))
        if dead:
            async with self._lock:
                for uid, ws in dead:
                    bucket = self._by_user.get(uid)
                    if bucket is not None:
                        bucket.discard(ws)
                        if not bucket:
                            del self._by_user[uid]


def build_notify_enqueue(
    *,
    connection: sqlite3.Connection,
    outbound_queue: asyncio.Queue[tuple[frozenset[str], str]],
    loop: asyncio.AbstractEventLoop,
    event_service: EventService | None = None,
) -> Callable[[ConversationEvent], None]:
    """构建同步上下文中可调用的通知函数，将帧投递到异步泵队列。"""

    def notify(event: ConversationEvent) -> None:
        out = event
        if event_service is not None:
            rows = event_service.list_events(
                conversation_id=event.conversation_id,
                after_event_id=max(0, event.event_id - 1),
                limit=1,
            )
            if rows:
                out = rows[-1]
        users = frozenset(resolve_recipient_user_ids(connection, out.conversation_id))
        if not users:
            return
        text = encode_user_stream_event_frame(out)
        loop.call_soon_threadsafe(outbound_queue.put_nowait, (users, text))

    return notify


async def pump_user_stream_outbound(
    *,
    registry: UserStreamRegistry,
    outbound_queue: asyncio.Queue[tuple[frozenset[str], str]],
) -> None:
    """后台任务：从队列取出并广播到用户连接。"""
    while True:
        user_ids, text = await outbound_queue.get()
        await registry.broadcast_to_users(user_ids, text)


async def serve_user_websocket(
    *,
    websocket: WebSocket,
    connection: sqlite3.Connection,
    registry: UserStreamRegistry,
    user_id: str,
) -> None:
    """接受浏览器用户 WebSocket：握手后处理 resume 与心跳。"""
    await websocket.accept()
    await registry.add(user_id, websocket)
    after_event_id = 0
    try:
        try:
            first = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            payload = json.loads(first)
            if isinstance(payload, dict) and payload.get("op") == "resume":
                raw_after = payload.get("after_event_id", 0)
                if isinstance(raw_after, int) and raw_after >= 0:
                    after_event_id = raw_after
        except TimeoutError:
            after_event_id = 0
        except json.JSONDecodeError:
            after_event_id = 0

        outcome = list_events_for_user_resume(connection, user_id=user_id, after_event_id=after_event_id)
        if outcome.resync_required:
            await websocket.send_text(
                json.dumps(
                    {"op": "resync_required", "reason": outcome.reason},
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
        for event in outcome.events:
            await websocket.send_text(encode_user_stream_event_frame(event))

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            op = msg.get("op")
            if op == "ping":
                await websocket.send_text(json.dumps({"op": "pong"}, ensure_ascii=True, separators=(",", ":")))
            elif op == "resume":
                raw_after = msg.get("after_event_id", 0)
                next_after = int(raw_after) if isinstance(raw_after, int) and raw_after >= 0 else 0
                again = list_events_for_user_resume(connection, user_id=user_id, after_event_id=next_after)
                if again.resync_required:
                    await websocket.send_text(
                        json.dumps(
                            {"op": "resync_required", "reason": again.reason},
                            ensure_ascii=True,
                            separators=(",", ":"),
                        )
                    )
                for event in again.events:
                    await websocket.send_text(encode_user_stream_event_frame(event))
    except WebSocketDisconnect:
        pass
    finally:
        await registry.remove(user_id, websocket)
