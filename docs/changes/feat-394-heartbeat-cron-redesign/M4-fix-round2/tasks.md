# feat-394-M4: fix-round2 — Tasks

## 目标

关闭 round-2 reviewer 所有 blocking/major/minor issues，并通过真实环境 cron 全链路验证。

## 退出标准（来自 design.md M4 行）

- [reviewer] cron 自建/列出/删除任务全链路真跑通（S3.1~S3.5），CronCard 显示任务并能删
- [reviewer] 到点真触发执行投递 + awareness 追问
- [reviewer] 关闭 heartbeat/cron 开关后免重启即停用（S1.3）
- [reviewer] prompt preview 受开关控制（R2-2）
- [worker] find_by_kernel_session_id 在 PersistentSessionBindingStore 的单测 + cron 工具链用生产持久版跑通的集成测试
- [worker] assemble_prompt_preview 注入 vars 的测试
- [worker] 调度器 per-tick live 读、toggle off 下一 tick 不跑 的测试
- [worker] pytest -m "not e2e" + tsc -b + vitest 全绿

## 测试策略

所有修复均为后端逻辑/架构修复，测试策略：
- R1: PersistentSessionBindingStore 单测（已有测试文件 + 新 TestR3 class）
- R2: 现有 test_heartbeat_cron_vars_injection.py 扩展 TestAssemblePromptPreviewVarsInjection
- R3: test_heartbeat_scheduler.py 扩展 2 个 live getter 测试
- R4: 通过 test_heartbeat_scheduler.py run_queue skip 测试（已有架构覆盖）
- 真实环境验证：按 design.md Runbook 跑完整 cron 旅程

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | PersistentSessionBindingStore.find_by_kernel_session_id | DONE |
| R2 | assemble_prompt_preview 注入 heartbeat/cron_enabled vars | DONE |
| R3 | HeartbeatScheduler per-tick live agents_getter（S1.3） | DONE |
| R4 | busy-skip 争用缓解（run_queue 集成） | DONE |
| R5 | 真实环境 cron 全链路验证 + 文档收口 | DONE |
