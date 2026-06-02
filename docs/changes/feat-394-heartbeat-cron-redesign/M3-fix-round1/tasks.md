# M3 Fix Round-1 — Tasks

## 目标

修复 round-1 验收（verifier + reviewer）中发现的 3 关键 + 3 warning + 2 minor 问题，使 heartbeat/cron 两个核心链路真正在运行时生效。

## 退出标准

- cron 接入 polling runner，到点真触发执行（CRITICAL-1）
- heartbeat_enabled/cron_enabled 正确注入 PromptContext.vars，门控生效（CRITICAL-2）
- _IMConfigSyncClient 传 token_getter，auto-bind 后不 401（acceptance Issue 1）
- cron_enabled 驱动 cron 工具自动进 agent 工具表（WARNING-1）
- _build_heartbeat_message 逐字照抄 openclaw HEARTBEAT_PROMPT（WARNING-2/决策6）
- CronCard 补任务清单 + 删除 UI（WARNING-3/spec Scenario 配置页查看并手动删除任务）
- 前端 tsc -b 类型断言修复（minor Issue 3）
- Cadence 输入框 select-all（minor Issue 4）
- 全套回归绿：pytest -m "not e2e" + 前端 tsc -b + vitest
- Runbook 真跑验证 heartbeat 唤醒 + cron 触发各一次，证据进 progress.md

## 测试策略

| Fix | 测试类型 | 落库? |
|---|---|---|
| CRITICAL-1 cron 接入运行循环 | 集成测试：gateway tick → due cron job 真触发执行 | 是 |
| CRITICAL-2 vars 注入 | 单测：开关状态真驱动两段 enabled | 是 |
| token_getter 修复 | 单测：token 刷新后 config sync 不 401 | 是 |
| cron 工具自动门控 | 单测：cron_enabled=True → 工具进 allowlist | 是（已有测试扩展） |
| HEARTBEAT_PROMPT 逐字 | 单测：_build_heartbeat_message 逐字比较 | 是 |
| CronCard 任务清单 | 前端组件/集成测试 + 浏览器验收 | 是 |
| tsc 类型修复 | tsc -b 无错 | 是 |
| Cadence select-all | 浏览器验收 | 截图证据 |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | token_getter 修复 + vars 注入（后端链路修复）| TODO |
| R2 | cron 接入 polling runner（最大关键修复）| TODO |
| R3 | cron 工具自动门控 + HEARTBEAT_PROMPT 逐字（决策补全）| TODO |
| R4 | CronCard 任务清单 UI（spec Scenario 补全）| TODO |
| R5 | 前端类型修复 + Cadence select-all（minor）| TODO |
| R6 | Runbook 运行时验证 | TODO |

## UI 状态矩阵

CronCard 任务清单（新增组件）：

| 状态 | 覆盖 |
|---|---|
| default（有任务） | 是 |
| empty（无任务） | 是 |
| loading | N/A（同步 API） |
| error | 是（API fail graceful） |
| delete confirm | 是 |
| mobile viewport | N/A（配置页桌面场景） |
| desktop viewport | 是 |
