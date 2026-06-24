"""RunController terminal-commit atomicity (bugfix-426-M4 决策5).

#140 root: a steer that lands in the window between the loop's last round-boundary
drain and its decision to break is stranded — the loop never drains it again, the
registry re-runs it as a *continuation run* with a NEW run_id, and the gateway relay
(anchored to the old run_id) drops every continuation event → 占位 120s 超时、黑屏。

决策5 closes the window by making "loop re-drains at terminal and commits" and
"registry injects" mutually exclusive: a single terminal lock guards both, so there
is no third state. Either the inject wins (loop sees it on re-drain and continues the
SAME run) or the commit wins (inject returns False; caller falls back to a new run).
"""

from __future__ import annotations

import threading

from agent.core.agent.run_control import RunController
from agent.core.llm.interfaces import LLMMessage
from agent.core.runs.origin import RunOrigin


def test_try_commit_terminal_returns_pending_when_nonempty_and_does_not_commit() -> (
    None
):
    controller = RunController()
    controller.enqueue_message(
        LLMMessage(role="user", content="steer"), origin=RunOrigin.USER
    )

    drained = controller.try_commit_terminal()

    # Non-empty: the loop must continue this run, so terminal is NOT committed.
    assert [p.message.content for p in drained] == ["steer"]
    assert controller.is_terminal_committed is False
    # A later inject still succeeds (run is still live, continuing).
    assert (
        controller.enqueue_message(
            LLMMessage(role="user", content="again"), origin=RunOrigin.USER
        )
        is True
    )


def test_try_commit_terminal_commits_when_empty() -> None:
    controller = RunController()

    drained = controller.try_commit_terminal()

    assert drained == []
    assert controller.is_terminal_committed is True


def test_enqueue_after_commit_is_rejected() -> None:
    controller = RunController()
    controller.try_commit_terminal()  # commits (empty)

    accepted = controller.enqueue_message(
        LLMMessage(role="user", content="late"), origin=RunOrigin.USER
    )

    assert accepted is False
    # Nothing was enqueued.
    assert controller.drain_pending() == []


def test_commit_terminal_is_hard_and_rejects_later_inject() -> None:
    """bugfix-426-M4 V1: the hard-stop commit (max_turns / tool_unavailable / abort
    exits) sets terminal unconditionally — no re-drain — so an inject racing AFTER it
    is rejected and routed to a fresh run, never stranded."""
    controller = RunController()

    controller.commit_terminal()

    assert controller.is_terminal_committed is True
    accepted = controller.enqueue_message(
        LLMMessage(role="user", content="steer at hard stop"), origin=RunOrigin.USER
    )
    assert accepted is False
    assert controller.drain_pending() == []


def test_commit_terminal_idempotent() -> None:
    controller = RunController()
    controller.commit_terminal()
    controller.commit_terminal()  # no raise, still committed
    assert controller.is_terminal_committed is True


def test_commit_and_enqueue_are_mutually_exclusive_under_contention() -> None:
    """Stress the lock: many threads race inject vs commit; the outcome is consistent.

    Invariant: a message is enqueued IFF commit has not happened. There is never a
    state where enqueue returned True yet the message was lost to a commit, nor where
    commit succeeded yet a message slipped into the queue afterwards.
    """
    for _ in range(200):
        controller = RunController()
        results: dict[str, object] = {}
        barrier = threading.Barrier(2)

        def _inject() -> None:
            barrier.wait()
            results["accepted"] = controller.enqueue_message(
                LLMMessage(role="user", content="x"), origin=RunOrigin.USER
            )

        def _commit() -> None:
            barrier.wait()
            results["drained"] = controller.try_commit_terminal()

        t1 = threading.Thread(target=_inject)
        t2 = threading.Thread(target=_commit)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        accepted = results["accepted"]
        drained = results["drained"]
        committed = controller.is_terminal_committed
        remaining = controller.drain_pending()

        if accepted:
            # Message went somewhere: either the commit drained it (returned it), or it
            # stayed in the queue for the next round. Never both, never neither.
            in_drained = any(p.message.content == "x" for p in drained)
            in_remaining = any(p.message.content == "x" for p in remaining)
            assert in_drained ^ in_remaining
            # If the inject won the race, terminal must NOT be committed.
            if in_remaining:
                assert committed is False
        else:
            # Inject rejected → commit won → terminal committed, nothing enqueued.
            assert committed is True
            assert drained == []
            assert remaining == []
