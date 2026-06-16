# bugfix-417-M1 — Progress

## 开工记录

- 上下文已读全（design.md / incident.md / specs/{kernel,gateway,im}/spec.md / 现有 registry.py / kernel.py / runtime.py / broker.py / test_run_cancel.py）。
- 范围确认：仅 `src/agent/core/runs/registry.py` + `src/agent/sdk/kernel.py`。runtime CancelledError 恢复路径（runtime.py:577-582）已就绪，本 M1 不改。liveness 事件（delta-spec ADDED）归 M3，本 M1 不做。
- test_command = `python -m pytest`（从 CLAUDE.md / pyproject 推断；C2 前跑最窄相关单测 + 必要广度）。基线绿。

## R1 — registry.cancel 强制取消承载 Task，释放 session 锁

- Context: 现状 `registry.cancel`（registry.py:464）只 `controller.cancel()` 翻协作标志 + `_set_status(CANCELLED)`，**不碰承载 Task**。run 若 parked 在一个永不返回的 await（工具执行 / LLM 等待 / 权限决策），`_run_locked` 的 `async with lock`（runtime.py:279）永不退出 → per-session 锁永久泄漏 → 该 session 后续 run 全部卡死（#110 P0）。`_owned_tasks` + `_async_loop` 强制取消能力此前只在 shutdown 用，未接进 per-run cancel。
- Decision: `cancel` 翻状态后调新增的 `_force_cancel_owned_task(run_id)`——若 `_owned_tasks` 有该 run 未完成 Task，经 `self._async_loop.call_soon_threadsafe(task.cancel)` 强制取消。让 `async with lock` 经 CancelledError 退出释放锁；runtime 的 CancelledError 恢复路径（runtime.py:577-582，本 M1 不改）在 finally 用 shield 恢复孤儿 tool_call。
- Rationale: 复用现成零件（`_owned_tasks`/`_async_loop`/runtime 恢复路径），最小改动闭合 P0 不变量「没有任何单条 run 能让一把 session 锁永久不可释放」（design 决策 1）。Task.cancel 必须在拥有该 Task 的 loop 上调用，故走 `call_soon_threadsafe`。幂等：已终态在前面 `_TERMINAL_STATUSES` 分支已 return（不进取消）；无 live Task 时 `_owned_tasks.get` 为 None / task.done() → no-op。
- Evidence:
  - Tests: `tests/unit/test_run_cancel.py` 7 passed（含新增 2 个）；广度回归 test_runs_registry + transport_lifecycle + permission_requester_cancel + agent_runtime 38 passed。
  - Entry: 进程内 registry 直跑（真 per-session asyncio.Lock，与生产同机制）。`test_cancel_force_releases_session_lock_so_next_run_proceeds`：run1 持锁 parked → run2 排队卡锁外 → `cancel(run1)` → run2 跑到 COMPLETED。修前该断言 3s 超时（锁不释放，整测 33s 因 shutdown drain 强杀），修后 0.16s 通过（锁立即释放）——即 P0 不变量真实投影。
  - Frontend State Matrix: N/A（后端内核）
  - Browser QA: N/A（后端内核）
  - E2E/Regression: `tests/unit/test_run_cancel.py::test_cancel_force_releases_session_lock_so_next_run_proceeds`（锁释放回归）+ `::test_cancel_already_terminal_run_is_idempotent_noop`（幂等回归）。命令 `PYTHONPATH=src python -m pytest tests/unit/test_run_cancel.py`，结果 7 passed。
  - Visual/Interaction: N/A
- Rollback: 回退到 C1（2f4c2460）即恢复纯合作式 cancel（现状，不更坏）。
- Commits: C1=2f4c2460, C2=b4913f93, C3=<本提交>
- Next: R2 — kernel.cancel 连带取消 permission broker pending。

## R2 — kernel.cancel 连带取消 permission broker pending

- ...
