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
- Commits: C1=2f4c2460, C2=b4913f93, C3=c4994f92
- Next: R2 — kernel.cancel 连带取消 permission broker pending。

## R2 — kernel.cancel 连带取消 permission broker pending

- Context: R1 让 `registry.cancel` 强制取消承载 Task、释放 session 锁，但若该 run parked 在权限决策上，broker 里仍残留一个 pending future（`PermissionBroker._pending`）——Task 被 cancel 后没人再 resolve 它，future 泄漏，等它的 hook 协程也悬着。`kernel.cancel`（kernel.py:970 附近）原本只把 `runs_registry.cancel` 的结果转 `RunInfo`，不碰 broker。
- Decision: `Kernel.cancel` 在 `runs_registry.cancel` 返回非 None（即确有该 run 被取消）后，调 `self._c.permission_broker.cancel_all_pending(run_id=run_id)`，把该 run scope 内所有 pending future resolve 为 deny 并从 `_pending` 移除。`record is None`（未知 / 已清理的 run）时直接 return None，不触碰 broker——天然幂等。
- Rationale: 复用 broker 既有的 run-scoped `cancel_all_pending`（broker.py:194，原为 interrupt / timeout cleanup 而建），不新造取消通道；放在 registry.cancel 之后是因为只有确认 run 真被取消才该清它的待决权限，避免对未知 run 误触 broker。broker future 必须在其所属 loop 上 resolve，`cancel_all_pending` 内部已用 `future.get_loop().call_soon_threadsafe`，故 kernel 层同步调用即可。
- Evidence:
  - Tests: `tests/unit/test_kernel_cancel_permission.py` 2 passed；与 R1 合跑 `test_run_cancel.py` + `test_kernel_cancel_permission.py` 共 9 passed。
  - Entry: 进程内 kernel（`agent.sdk.Kernel`）真实 cancel 路径——`test_kernel_cancel_denies_pending_permission_for_run`：真 SessionManager + 真 RunsRegistry + 真 PermissionBroker，submit 一条 run 跑到 RUNNING、在 registry loop 上 `broker.register_request` 造一个该 run 的 pending future，`kernel.cancel(run_id)` 后断言 (a) 返回 RunInfo.status == "cancelled"，(b) 该 pending future resolve 为 `decision == "deny"`，(c) `broker.is_pending` 转 False。非 mock 入口，是 #110 "parked-on-permission 取消后 broker 不泄漏" 的真实投影。
  - Frontend State Matrix: N/A（后端内核）
  - Browser QA: N/A（后端内核）
  - E2E/Regression: `tests/unit/test_kernel_cancel_permission.py::test_kernel_cancel_denies_pending_permission_for_run`（broker 不泄漏回归）+ `::test_kernel_cancel_unknown_run_returns_none_and_no_broker_error`（未知 run 幂等、不误触 broker）。命令 `PYTHONPATH=src python -m pytest tests/unit/test_kernel_cancel_permission.py`，结果 2 passed。
  - Visual/Interaction: N/A
- Rollback: 回退到 C1（0cd6fb11）即恢复 kernel.cancel 不碰 broker（R1 的锁释放仍在，仅 broker pending 会重新泄漏，不更坏于 R1 前）。
- Commits: C1=0cd6fb11, C2=2f5a0331, C3=<本提交>
- Next: 本 milestone 全部 roadpoint DONE，进入集成。
