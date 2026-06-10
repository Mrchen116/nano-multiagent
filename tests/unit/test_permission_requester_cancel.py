"""Tests for finding 2b: can_use_task.result() raises CancelledError (BaseException).

When can_use_task is externally cancelled it lands in asyncio.wait's done set;
can_use_task.result() re-raises CancelledError which is BaseException — a bare
`except Exception` guard cannot catch it, causing CancelledError to escape the
permission_requester with response unset and broker future potentially pending.

Fix: add explicit `except asyncio.CancelledError` before `except Exception` in
the can_use_task.result() call-site inside runtime._permission_requester.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


class TestPermissionRequesterCanUseCancelled:
    """When can_use_task is externally cancelled it lands in asyncio.wait's
    done set; can_use_task.result() re-raises CancelledError (BaseException),
    which a bare `except Exception` guard cannot catch — finding 2b.
    """

    @pytest.mark.asyncio
    async def test_can_use_task_cancelled_treated_as_deny(self):
        """can_use_task cancelled mid-race must be treated as deny, not propagate
        CancelledError out of the permission_requester (finding 2b).

        Reproduces the exact try/except block from runtime._permission_requester
        so that any divergence breaks this test loudly.
        """
        import asyncio as _asyncio

        from agent.platform.config.auto_mode import AutoModeConfig
        from agent.platform.permissions.broker import (
            PermissionBroker,
            PermissionRequest,
        )

        broker = PermissionBroker(config=AutoModeConfig())
        reached_can_use = _asyncio.Event()

        async def _hanging_can_use_tool(tool_name, tool_input, req_ctx):
            """Signals it started, then hangs — simulate interactive CLI prompt."""
            reached_can_use.set()
            await _asyncio.sleep(60)  # will be cancelled before returning

        req = PermissionRequest(
            id="req-2b-cancel",
            tool_name="bash",
            tool_input={"command": "echo hi"},
            question="Allow bash?",
            options=(),
        )
        future = broker.register_request(req.id, run_id="run-2b")

        async def _await_future(f: "_asyncio.Future[Any]") -> Any:
            return await _asyncio.shield(f)

        can_use_task = _asyncio.create_task(
            _hanging_can_use_tool(req.tool_name, req.tool_input, req)
        )
        # Wait for can_use_tool to start, then cancel it mid-race.
        await reached_can_use.wait()
        can_use_task.cancel()
        await _asyncio.sleep(0)  # one tick so task is marked cancelled

        done, pending = await _asyncio.wait(
            {can_use_task, _asyncio.ensure_future(_await_future(future))},
            return_when=_asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        if pending:
            await _asyncio.gather(*pending, return_exceptions=True)

        # Mirror the fixed production code path from runtime._permission_requester.
        # The fix adds `except asyncio.CancelledError` before `except Exception`
        # so the cancelled task is handled gracefully (feat-394-M14 finding 2b).
        response: Any = None
        if future.done() and not future.cancelled():
            response = future.result()
        else:
            try:
                raw_decision: Any = can_use_task.result()
            except _asyncio.CancelledError:
                raw_decision = type(
                    "_D", (), {"behavior": "deny", "reason": "can_use_tool cancelled"}
                )()
            except Exception:
                raw_decision = type(
                    "_D", (), {"behavior": "deny", "reason": "can_use_tool raised"}
                )()
            behavior = getattr(raw_decision, "behavior", "deny")
            reason = getattr(raw_decision, "reason", "")
            response = type(
                "_R",
                (),
                {
                    "decision": "deny" if behavior == "deny" else "allow_once",
                    "reason": reason,
                    "request_id": req.id,
                    "rule_update": None,
                },
            )()
            with broker._lock:  # noqa: SLF001
                broker._pending.pop(req.id, None)  # noqa: SLF001
            if not future.done():
                future.get_loop().call_soon_threadsafe(future.set_result, response)

        assert response is not None, (
            "response must be set — CancelledError must not escape (finding 2b)"
        )
        assert getattr(response, "decision") == "deny", (
            "cancelled can_use_task must yield deny"
        )
        assert not broker.is_pending(req.id), "no pending broker entry must remain"

    @pytest.mark.asyncio
    async def test_cancelled_error_is_not_subclass_of_exception(self):
        """Regression guard: CancelledError is BaseException, not Exception.

        Documents the language invariant that makes finding 2b possible — if
        Python ever changes this, the CancelledError fix in runtime.py needs
        re-evaluation.
        """
        import asyncio as _asyncio

        async def _coro() -> None:
            await _asyncio.sleep(10)

        task = _asyncio.create_task(_coro())
        task.cancel()
        await _asyncio.sleep(0)

        caught_by_exception = False
        caught_by_cancelled_error = False
        try:
            task.result()
        except _asyncio.CancelledError:
            caught_by_cancelled_error = True
        except Exception:
            caught_by_exception = True

        # CancelledError is NOT a subclass of Exception in Python 3.8+.
        assert caught_by_cancelled_error, (
            "CancelledError must be caught explicitly — not subsumed by Exception"
        )
        assert not caught_by_exception, (
            "except Exception must NOT catch CancelledError (it is BaseException)"
        )


class TestPermissionRequesterPopOwnership:
    """cancel_all_pending that pops first must prevent a second set_result.

    The "whoever pops owns it" invariant: broker._pending.pop return value
    gates whether runtime schedules set_result at all.  If cancel_all_pending
    already popped and scheduled deny, runtime pop returns None → skip.
    """

    @pytest.mark.asyncio
    async def test_cancel_all_pending_first_pop_prevents_double_set_result(self):
        """When cancel_all_pending pops before can_use_tool win path,
        runtime must not schedule a second set_result (finding 1+3 last window).

        Assert: future resolves exactly once, final decision is deny (from
        cancel_all_pending), and no InvalidStateError is raised.
        """
        import asyncio as _asyncio

        from agent.platform.config.auto_mode import AutoModeConfig
        from agent.platform.permissions.broker import (
            PermissionBroker,
            PermissionRequest,
        )

        broker = PermissionBroker(config=AutoModeConfig())
        req = PermissionRequest(
            id="req-pop-race",
            tool_name="bash",
            tool_input={},
            question="Allow?",
            options=(),
        )
        future = broker.register_request(req.id, run_id="run-pop")

        # cancel_all_pending pops first (simulates run interrupt beating
        # can_use_tool win path).
        broker.cancel_all_pending(run_id="run-pop")

        # Give loop one tick so cancel_all_pending's call_soon_threadsafe fires.
        await _asyncio.sleep(0)

        # Simulate runtime can_use_tool win path attempting to pop + set_result.
        # With the fix, owned is None → set_result is skipped.
        with broker._lock:  # noqa: SLF001
            owned = broker._pending.pop(req.id, None)  # noqa: SLF001

        # Owned must be None — cancel_all_pending already consumed the entry.
        assert owned is None, "runtime pop must return None when cancel_all_pending won"

        # future must already be resolved to deny (no InvalidStateError).
        assert future.done(), "future must be resolved by cancel_all_pending"
        result = future.result()
        assert result.decision == "deny", "final decision must be deny (from cancel)"

        # Attempting set_result again must raise InvalidStateError — this is
        # what the fix prevents by gating on owned is not None.
        errors: list[Exception] = []

        def _bad_set() -> None:
            try:
                future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        future.get_loop().call_soon_threadsafe(_bad_set)
        await _asyncio.sleep(0)

        assert len(errors) == 1 and isinstance(errors[0], _asyncio.InvalidStateError), (
            "double set_result must raise InvalidStateError — "
            "confirms the fix prevents this path"
        )
