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

<!-- 每个 roadpoint 完成后实时追加。 -->
