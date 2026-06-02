# feat-394-M2: cron-subsystem

## 目标

为 personal_assistant 新增 cron 多任务定时调度子系统：agent 通过 cron 工具自管定时任务（at/every/cron 三种调度，不补跑），任务运行在隔离会话，结果投递 owner canonical 直聊，并以 System(untrusted) 注入直聊 kernel session 供用户追问承接。cron 工具与调度逻辑仅限 personal_assistant，coding_cli 不引入。

## 退出标准（来自 design.md Milestone 表 M2 行）

### Worker 验收
- `[worker]` cron 工具 schema/描述与 openclaw 逐字一致且注释标来源（单测）
- `[worker]` cron 不补跑 `computeNextRunAtMs` 语义单测
- `[worker]` awareness 以 `System(untrusted)` append 进直聊会话 JSONL、隔离 run 内部 turn 不进 的断言
- `[worker]` coding_cli 无 cron 工具/无 heartbeat·cron prompt 段 的隔离断言
- `[worker]` `pytest -m "not e2e"` 全绿（含 IM_service）+ 前端 vitest 绿

### Reviewer 验收（标记但不自行验收）
- `[reviewer]` 配置页开 cron 后 agent 自建定时任务（口述定时任务 agent 注册一条）
- `[reviewer]` 多任务并存独立触发
- `[reviewer]` 到点无上下文执行并投递直聊
- `[reviewer]` 配置页查看/删任务
- `[reviewer]` 重启不补跑刷屏 + 过期 at 不补
- `[reviewer]` cron 结果发后追问该结果时 agent 知道（awareness 承接）

## 测试策略

### 后端测试（TDD）
- R1: cron 调度不补跑语义单测（_AtSchedule/_IntervalSchedule/_CronSchedule，复用 M1 语义的断言写法）
- R2: CronJob 持久化 + CronScheduler 多任务调度（单元测试）
- R3: cron 工具 schema/描述 openclaw 逐字一致（单测）
- R4: cron_enabled 同步链路（IM→AgentWorkspaceConfig.cron_enabled 字段，单测）
- R5: cron 隔离执行 + System(untrusted) awareness 注入（单测）
- R6: coding_cli 隔离断言（无 cron 工具 + 无 cron/heartbeat prompt 段）

### 前端测试
- R7: IM 前端 cron 开关 UI（vitest + 浏览器验收）
  用户路径分类: `normal-ui`

### UI 状态矩阵

| 状态 | 覆盖方式 |
|---|---|
| default(disabled) | cron 开关初始关闭 |
| enabled | 开关打开后显示 cron 开启提示 |
| loading | N/A（继承页面级） |
| error | N/A（继承页面级） |
| disabled | N/A |
| mobile | 手动验收截图 |
| desktop | 手动验收截图 |

### 测试/验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| cron 不补跑语义 | 单元测试（Red→Green）| 是 |
| CronJob 持久化格式 | 单元测试 | 是 |
| cron 工具 openclaw 逐字 | 单元测试（字符串比较）| 是 |
| cron_enabled 同步链路 | 单元测试 | 是 |
| awareness System(untrusted) 注入 | 单元测试 + 断言直聊 JSONL | 是 |
| coding_cli 无 cron 泄漏 | 合约断言 | 是 |
| 前端 cron 开关 UI | vitest + 浏览器验收截图 | vitest 落库 |

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | cron 调度不补跑单测（at/every/cron 三种调度语义，复用 M1 _Schedule 类）| TODO |
| R2 | CronJob 持久化 + CronScheduler 多任务调度（jobs.json + per-job last_due）| TODO |
| R3 | cron 工具（照抄 openclaw schema/描述 + Provenance 注释）+ toolsets 门控 | TODO |
| R4 | cron_enabled 字段同步链路（IM domain → AgentWorkspaceConfig + sync_agent）| TODO |
| R5 | cron 隔离执行 + awareness System(untrusted) append 进直聊 JSONL + delete_after_run | TODO |
| R6 | coding_cli 隔离断言（无 cron 工具/无 heartbeat·cron prompt 段）| TODO |
| R7 | IM 前端 cron 开关 UI + vitest + API 字段 | TODO |
| R8 | prompt 段（cron 引导段 + 都开时路由段）+ SPEC §6 cron 部分 | TODO |
