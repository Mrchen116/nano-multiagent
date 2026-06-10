# bugfix-402-M3 progress

## R1 — RunsRegistry Task 登记 + DRAINING 状态机

**Status**: DONE

**Evidence**:
- `src/agent/core/runs/registry.py`: added `_RegistryState(StrEnum)` (OPEN/DRAINING/CLOSED),
  `RegistryClosedError`, `_owned_tasks: dict[str, asyncio.Task]`.
  `submit()` raises `RegistryClosedError` when state is DRAINING or CLOSED.
  `shutdown()` transitions OPEN→DRAINING, schedules `_drain_and_stop` via `call_soon_threadsafe`,
  waits on `concurrent.futures.Future`, joins thread, transitions to CLOSED.
  `_drain_and_stop()` gathers owned tasks with 30s timeout, cancels stragglers, stops loop.
  `_on_task_done()` done-callback removes completed tasks from `_owned_tasks`.
- Tests: `tests/unit/test_runs_registry.py` — `test_registry_submit_rejected_after_shutdown`,
  `test_registry_drains_active_task_before_loop_stops`.
- `pytest tests/unit/test_runs_registry.py` — all green.

## R2 — Kernel.aclose() + 幂等关闭

**Status**: DONE

**Evidence**:
- `src/agent/sdk/kernel.py`: added `aclose()` async method — checks `_closed` flag,
  schedules `_drain_and_stop` on Registry loop via `call_soon_threadsafe`, awaits
  `concurrent.futures.Future` via `asyncio.wrap_future()`. `close()` updated to check
  `_closed` flag first (idempotent, delegates to `shutdown()`).
- `src/coding_cli/commands.py`: `_async_main` finally block changed from `kernel.close()`
  to `await kernel.aclose()`.
- Tests: `tests/unit/test_cli_async_repl_sdk.py` — `test_coding_cli_async_main_uses_aclose_not_close`,
  `test_kernel_aclose_is_coroutine`, `test_kernel_close_is_still_callable`,
  `test_kernel_aclose_idempotent`, updated `test_run_cli_kernel_closed_on_exit`.
- `pytest tests/unit/test_cli_async_repl_sdk.py tests/unit/test_runs_registry.py` — all green.

## R3 — Gateway 生产者→消費者关闭顺序

**Status**: DONE

**Evidence**:
- `src/personal_assistant/main.py`:
  - `GatewayRuntime.__init__` gains `kernel: object | None = None` parameter; stored as `self._kernel`.
  - `_run_until_shutdown` finally block: inserted `await self._kernel.aclose()` after
    heartbeat/channels stop and before IM close.
  - `build_runtime`: removed `kernel.close` from `resource_closers`; added `kernel=kernel`
    to `GatewayRuntime(...)` call.
- Tests: `tests/unit/personal_assistant/test_gateway_shutdown_order.py` —
  `test_gateway_runtime_accepts_kernel_parameter`,
  `test_gateway_runtime_calls_kernel_aclose_before_im_close`,
  `test_gateway_runtime_kernel_aclose_called_exactly_once`,
  `test_build_runtime_does_not_add_kernel_close_to_resource_closers`.
- `pytest tests/unit/personal_assistant/test_gateway_shutdown_order.py` — all green.

## R4 — e2e-down.sh grace wait

**Status**: DONE

**Evidence**:
- `scripts/e2e-down.sh`: rewritten to send SIGTERM to Gateway first, wait up to
  `GATEWAY_GRACE_SECONDS=5` in a polling loop, force-kill on timeout, then stop IM and API.
  Previously all services were killed simultaneously at 0.5s.
- `bash -n scripts/e2e-down.sh` → exit 0 (syntax clean).

## Live E2E Shutdown Evidence (unit worktree)

**Date**: 2026-06-10

**Command sequence**:
```
./scripts/e2e-up.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-402
# → "e2e stack ready … IM 59734 … GW pid=33767"
# → "e2e config: node.user_id synced to ephemeral IM user 0553ef507aa54f5e915e4aa05a2f2619"

./scripts/e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-402
# → "e2e stack stopped (wt=…)" in 1s
```

**Shutdown timing**: Completed in 1s (well within 5s grace — no force-kill path triggered).

**Gateway process exit**: `kill -0 $GW_PID` → "gateway pid=33767 exited cleanly" (process gone before pid file cleanup).

**Error pattern scan**:
```
rg -n "different Context|Task was destroyed but it is pending|Traceback" .gateway.log
→ 0 matches
```

**Gateway log (full)**:
```
INFO node wt-unit-bugfix-402-33671 auto-bound to IM
  → NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for http://127.0.0.1:59734.
```
No cross-Context errors, no pending task destruction errors, no tracebacks.

**IM log (tail)**:
```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [33720]
```
IM shut down after Gateway exited, confirming correct shutdown order.
