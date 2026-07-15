# refactor-463-M2 — Progress

## 启动基线

- Context: M1 已合入并推送 `unit/refactor-463`；milestone worktree 从 `origin/unit/refactor-463` 的 `45f4cda271883ae270d47b7cacc27da055b6d634` 创建。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3347 passed, 1 skipped`（38.40s）。
- Leader alignment: M2 必须覆盖 typed image、subscriber/queue/dispatcher/delivery owner、one 80% deadline 与完整 shutdown graph，并留下真端到端图片/后台/stop/offline 证据。
- Scope rationale: M2 范围列漏列 `scheduler/cron_service_registry.py` 与 `scheduler/cron_execution_service.py`，但 D6/退出标准已明确要求 cron O(1) seal / same-deadline drain。orchestrator 确认两文件是落实既定 decision 的必要真实 owner，不需改 design；变更只限 admission seal、具名 current task drain/timeout isolation 与公开接线，不改变 cron 调度、持久化或投递语义。

## R1 — 迁出 typed models 与图片解析策略

- Context: 进行中。
