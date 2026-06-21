# bugfix-417-M7 — Progress

## R1 — ForegroundExecutionRegistry（core，新建）

- Context: 决策 12 要求前台 bash 退出 BackgroundTaskRegistry，但前台子进程在 to_thread 内层、async cancel 够不到，必须保留一个 killpg 旁路句柄。故需一个「恰好只持那一项」的窄 registry。
- Decision: 新建 `core/background_tasks/foreground_registry.py::ForegroundExecutionRegistry`，持 `{session_id: [stopper]}`，提供 `register` / `unregister(session_id, stopper=None)` / `stop_for_session(session_id)->bool`。stopper 复用 core `interfaces.BackgroundTaskStopper` Protocol（注入端口，core 不依赖 platform）。
- Rationale: `stop_for_session` 刻意对齐 M5 `stop_foreground_for_session` 的 `(session_id)->bool` 签名，使 kernel 注入改向只需改一行、`runs/registry.py` 零改动。支持同 session 多前台句柄（list），unregister 可按句柄精确移除（auto-bg 移交 / 完成）或整 session 清空。unknown session 安全 no-op（完成/移交可能与已清条目的 /stop 竞态）。
- Evidence:
  - Tests: `tests/unit/agent/background_tasks/test_foreground_registry.py` 7 passed（命中/scope/未命中 False/unregister 后 no-op/多句柄全停/精确移除/unknown 安全）
  - Entry: N/A（纯 core 数据结构，入口验证在 R2/R4 经 bash + build_kernel）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 端到端硬闸在 R4
  - Visual/Interaction: N/A
- Rollback: revert R1 三 commit（plan 之后第一组）
- Commits: C1=test 红, C2=feat 实现, C3=docs（本段）

## R2 — bash.py 前台改登记 fg registry + auto-bg 显式移交

- Context: 前台 bash 原 `register_bash`+`mark_running`+`set_stop_handle(foreground=True)` 进后台 registry，靠 `notified=is_foreground` + `result_holder["backgrounded"]` 推断「我其实是前台」。`on_fail` 漏补 `notified=True` → 前台超时/失败仍走 `notified=False` → `_NotifyingStore` 投 `<task-notification>` → 双通道（本 bug 直接触发点）。
- Decision: `_run_foreground` 改登记 `wiring.foreground_registry`（只持 killpg 句柄）。引入 `handoff_lock` + `handoff_state{owner, terminal}`：on_complete/on_fail 以「当前 owner」为唯一判据投递——foreground 期只 set completed_event + result_holder（**不碰后台 registry**），hand-off 后才 `registry.complete/fail`（`notified` 默认 False，通知正确）。auto-bg 移交在 `handoff_lock` 内原子完成：若 `terminal` 已置（命令在最后一轮 poll 与取锁之间恰好完成）则放弃移交、按完成走；否则 `register_bash`→`mark_running`→`set_stop_handle(stopper)`→翻 `owner`→`foreground_registry.unregister`。wiring 装配 `ForegroundExecutionRegistry`，加入 `BackgroundTaskWiring`。
- Rationale: 双通道在结构上不可能再发生——`<task-notification>` 只由 `BackgroundTaskRegistry._NotifyingStore` 投，而前台命令物理上不进它。移交/回调竞态用单锁 + 单一 owner 判据消解：完成回调与移交互斥，恰好命中边界时只有一方生效，结果不丢、不双投、不双终态。`_ForegroundStopper.stop()` 仍唤醒 waiter（M5 行为保留），但句柄现在挂在 fg registry。
- Evidence:
  - Tests: `tests/unit/agent/tools/test_bash_tool.py` + `test_foreground_registry.py` 22 passed（含：前台完成/失败后台 registry 零记录、interrupt 经 fg.stop_for_session 5s 内返回无线程泄漏、auto-bg 移交进后台 registry + fg 已注销 + notified False、移交/回调竞态不丢不双投）；`test_background_tasks.py` 32 passed（R3 删补丁前仍绿）
  - Entry: 经 build_kernel 的端到端入口验证在 R4
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 端到端 DONE 硬闸在 R4
  - Visual/Interaction: N/A
- Rollback: revert R2 三 commit
- Commits: C1=test 红, C2=feat 实现, C3=docs（本段）

<!-- 每个 roadpoint 完成后实时追加。 -->
