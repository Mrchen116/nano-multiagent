"""IM 用户流 WebSocket 客户端 —— 事件帧封装 + 有界轮询的事件等待 / 否定断言。

从 ``_im_client`` 拆出（行为聚类 + 单文件 ≤400 行）：HTTP 黑盒客户端在 ``_im_client``，
WS 事件流这一面集中在此。``websockets`` 依赖在模块顶层 ``pytest.importorskip``：缺失则
整组 e2e 干净 skip 而非 ImportError 崩溃（design.md 决策 2 风险项）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import pytest

# 决策 2 风险缓解:WS 客户端依赖可选化。缺失 → 整组 skip,不崩。
websockets = pytest.importorskip(
    "websockets",
    reason="websockets is required for IM WebSocket critical-path e2e",
)
from websockets.sync.client import connect as ws_connect  # noqa: E402,F401

# WS 事件流断连时 ``recv`` 抛的异常族:Gateway 重启 / IM 断连场景下优雅收口为「无新帧」。
_WS_CLOSED_EXCEPTIONS = (
    websockets.exceptions.ConnectionClosedOK,
    websockets.exceptions.ConnectionClosedError,
    websockets.exceptions.ConnectionClosed,
)


# 真 LLM + 真进程时序下事件到达偏慢;窗口集中成常量便于按需放宽(决策 4)。
DEFAULT_EVENT_TIMEOUT = 90.0
# 否定式断言(B 不抢话 / deny 后工具不执行)的「足够宽等待窗」(决策 4)。
NEGATIVE_ASSERT_WINDOW = 25.0


def mention_tag(agent_id: str) -> str:
    """拼一个 IM wire 层唯一认得的 agent mention 标签。

    relay_service.py 只认 ``<mention type="agent" target_id="X"/>``,不认 ``@文本``。
    """
    return f'<mention type="agent" target_id="{agent_id}"/>'


@dataclass
class EventFrame:
    """一帧用户流 WebSocket 事件(``{op:"event", ...}``)的轻封装。"""

    event_type: str
    event_id: int
    conversation_id: str | None
    data: dict[str, Any]

    @classmethod
    def from_wire(cls, raw: dict[str, Any]) -> "EventFrame":
        return cls(
            event_type=raw.get("event_type", ""),
            event_id=int(raw.get("event_id", 0)),
            conversation_id=raw.get("conversation_id"),
            data=raw.get("data") or {},
        )


class IMUserWebSocket:
    """一条已完成 ``resume`` 握手的用户流 WebSocket，带有界轮询的事件等待。"""

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        # resume 回放或乱序到达的事件先缓冲,wait_for_event 先扫缓冲再读新帧。
        self._buffer: list[EventFrame] = []

    def _drain_one(self, timeout: float) -> EventFrame | None:
        """读一帧;非 ``event`` 帧(如 ``resync_required``)跳过。超时/断连返回 None。

        Gateway 重启 / IM 断连时 ``recv`` 抛 ConnectionClosed* —— 优雅返回 None(视作
        「这一刻没有新帧」),让上层有界轮询窗口自然走完,而非冒泡成测试 ERROR。
        """
        try:
            raw_text = self._ws.recv(timeout=timeout)
        except TimeoutError:
            return None
        except _WS_CLOSED_EXCEPTIONS:
            return None
        try:
            raw = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(raw, dict) or raw.get("op") != "event":
            return None
        return EventFrame.from_wire(raw)

    def wait_for_event(
        self,
        event_type: str,
        predicate: Callable[[EventFrame], bool] | None = None,
        *,
        timeout: float = DEFAULT_EVENT_TIMEOUT,
    ) -> EventFrame:
        """等待第一帧 ``event_type`` 且满足 ``predicate`` 的事件;超时 raise AssertionError。

        先扫已缓冲帧,再有界轮询新帧;不匹配的事件回收进缓冲供后续 wait 复用。
        """
        deadline = time.monotonic() + timeout

        # 1) 先扫缓冲。
        for i, frame in enumerate(self._buffer):
            if frame.event_type == event_type and (
                predicate is None or predicate(frame)
            ):
                del self._buffer[i]
                return frame

        # 2) 有界轮询新帧。
        while time.monotonic() < deadline:
            frame = self._drain_one(timeout=max(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            if frame.event_type == event_type and (
                predicate is None or predicate(frame)
            ):
                return frame
            # 不匹配但可能后面要用 → 缓冲。
            self._buffer.append(frame)

        raise AssertionError(
            f"timed out after {timeout}s waiting for event_type={event_type!r}; "
            f"buffered events so far: "
            f"{[(f.event_type, f.event_id) for f in self._buffer]}"
        )

    def assert_no_event(
        self,
        predicate: Callable[[EventFrame], bool],
        *,
        window: float = NEGATIVE_ASSERT_WINDOW,
    ) -> None:
        """否定式断言:在 ``window`` 秒内没有任何满足 ``predicate`` 的事件出现。

        决策 4:否定断言天生偏脆,靠「足够宽窗口 + 只断协议事件缺席」缓解。
        """
        deadline = time.monotonic() + window
        # 先查已缓冲帧。
        for frame in self._buffer:
            if predicate(frame):
                raise AssertionError(
                    f"unexpected event already buffered: "
                    f"type={frame.event_type} data_keys={list(frame.data)}"
                )
        while time.monotonic() < deadline:
            frame = self._drain_one(timeout=max(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            self._buffer.append(frame)
            if predicate(frame):
                raise AssertionError(
                    f"unexpected event within {window}s window: "
                    f"type={frame.event_type} data_keys={list(frame.data)}"
                )

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass
