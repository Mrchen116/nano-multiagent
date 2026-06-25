"""RunController pending queue carries injection origin (bugfix-426 决策3).

The stranded-continuation path (RunsRegistry._run_worker_async) drains the
controller's pending queue when a run ends with messages that never reached a
round boundary, and re-submits them as a continuation run. For that continuation
to attribute the right origin (user steer → USER, not hardcoded BACKGROUND_TASK),
the pending queue must carry the origin alongside each message.
"""

from __future__ import annotations

from agent.core.agent.run_control import RunController
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin


def test_enqueue_drain_carries_origin_fifo() -> None:
    controller = RunController()
    controller.enqueue_message(
        LLMMessage(role="user", content="first"), origin=RunOrigin.USER
    )
    controller.enqueue_message(
        LLMMessage(role="user", content="second"),
        origin=RunOrigin.BACKGROUND_TASK,
    )

    drained = controller.drain_pending()

    assert [p.message.content for p in drained] == ["first", "second"]
    assert [p.origin for p in drained] == [
        RunOrigin.USER,
        RunOrigin.BACKGROUND_TASK,
    ]


def test_drain_empties_queue() -> None:
    controller = RunController()
    controller.enqueue_message(
        LLMMessage(role="user", content="x"), origin=RunOrigin.USER
    )
    assert len(controller.drain_pending()) == 1
    assert controller.drain_pending() == []
