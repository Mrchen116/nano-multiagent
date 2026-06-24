"""共享有界轮询 helper —— 关键路径 e2e 里「等待直到某条件成立」的唯一实现。

真 LLM + 真进程时序下，几乎每条旅程都要「轮询某个 REST/状态直到 predicate 命中，超时则
带上下文 raise」。此前这套逻辑散在 ``IMClient.wait_for_*`` 和各测试文件的 ``_wait_*`` /
内联 ``while time.monotonic()`` 里（多处同构副本）。集中成一个 ``poll_until``，调用点只写
「探一次返回什么」+「命中判据」+「超时描述」。
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def poll_until(
    probe: Callable[[], T],
    predicate: Callable[[T], bool],
    *,
    timeout: float,
    interval: float = 0.5,
    desc: str = "condition",
) -> T:
    """周期性调 ``probe()`` 直到 ``predicate(result)`` 为真，返回该 result；超时 raise。

    Args:
        probe: 每轮探一次的取值函数（如 ``self.list_nodes``）。
        predicate: 对 probe 结果判命中。
        timeout: 总超时秒数。
        interval: 两轮之间的 sleep 秒数。
        desc: 超时报错里的人类可读描述（如 ``"online node"``）。

    Raises:
        AssertionError: ``timeout`` 秒内 predicate 始终未命中；报错带最后一次 probe 结果。
    """
    deadline = time.monotonic() + timeout
    last: T | None = None
    while time.monotonic() < deadline:
        last = probe()
        if predicate(last):
            return last
        time.sleep(interval)
    raise AssertionError(
        f"timed out after {timeout}s waiting for {desc}; last probe: {last!r}"
    )


def assert_absent_within(
    probe: Callable[[], object],
    predicate: Callable[[object], bool],
    *,
    window: float,
    interval: float = 2.0,
    desc: str = "signal",
) -> None:
    """否定式断言：``window`` 秒内 ``predicate`` 对任一 probe 结果都不命中，否则 raise。

    决策 4：否定断言（B 不抢话 / deny 后工具不执行）天生偏脆，靠「足够宽窗口 + 只断协议
    信号缺席」缓解。命中即 fail（说明本不该出现的信号出现了）。
    """
    deadline = time.monotonic() + window
    while time.monotonic() < deadline:
        if predicate(probe()):
            raise AssertionError(f"unexpected {desc} appeared within {window}s window")
        time.sleep(interval)
