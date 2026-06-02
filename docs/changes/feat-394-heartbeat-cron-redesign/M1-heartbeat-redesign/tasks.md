# feat-394-M1: heartbeat-redesign

## 目标

重新设计 heartbeat 子系统，使其跑在 owner canonical 直聊 kernel session（带历史），并实现：
- HEARTBEAT_OK token 静默
- 空文件跳过
- 忙会话跳过
- activeHours 活跃时段
- HEARTBEAT.md tasks: 多子节律 + per-task last_due 状态
- _IntervalSchedule 不补跑（openclaw computeNextRunAtMs 语义）
- prompt 段照抄 openclaw + enabled_when 门控
- IM 配置页 heartbeat 开关 + every/activeHours 字段
- AgentWorkspaceConfig heartbeat 字段 → ConfigSyncNotifier 同步

## 退出标准（来自 design.md Milestone 表 M1 行）

- `[worker]` heartbeat prompt/系统段与 openclaw 逐字一致且注释标来源（单测）
- `[worker]` 静默轮询后该会话 LLM 上下文无噪声堆积 + 忙会话跳过 的断言
- `[worker]` `_IntervalSchedule` 不补跑（重启只排下一时隙）单测
- `[worker]` 配置页开关→gateway 调度器对该 agent 跑 的端到端断言
- `[worker]` `pytest -m "not e2e"` 全绿（含 IM_service）+ 前端 vitest 绿
- `[reviewer]` 配置页开 heartbeat 后带上下文主动汇报、记得上下文
- `[reviewer]` 无事静默；不同关注项不同频率；activeHours 外不打扰
- `[reviewer]` 开关 per-agent 启用/停用；首次无直聊自动新建

## 测试策略

### 后端测试（TDD）
- R1: _IntervalSchedule 不补跑语义（单元测试，Red→Green）
- R2: HeartbeatScheduler 按 heartbeat 开关过滤 agents（单元测试）
- R3: HEARTBEAT_OK token 静默检测（单元测试）
- R5: AgentWorkspaceConfig + ConfigSyncNotifier heartbeat 字段同步（单元/集成）

### 前端测试
- R4: agent-create/detail-page heartbeat 开关（vitest + 浏览器验收）
- 用户路径分类: `normal-ui`（开关配置属于普通 UI 改动，非核心业务路径的原子操作）

### UI 状态矩阵

| 状态 | 覆盖方式 |
|---|---|
| default(disabled) | 开关初始状态 |
| enabled | 开关打开后字段显示 |
| loading | N/A（不单独显示 loading）|
| error | N/A（继承页面级 error）|
| disabled | N/A |
| mobile | 手动验收截图 |
| desktop | 手动验收截图 |

### 测试/验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| _IntervalSchedule 不补跑 | 单元测试（Red→Green）| 是 |
| heartbeat 开关过滤 agents | 单元测试 | 是 |
| HEARTBEAT_OK 静默 | 单元测试 + prompt 逐字比较 | 是 |
| heartbeat 字段同步链路 | 集成测试 | 是 |
| 前端开关 UI | vitest + 浏览器手动验收截图 | vitest 落库 |

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | _IntervalSchedule 不补跑 + _CronSchedule 不补跑 单测 | TODO |
| R2 | AgentWorkspaceConfig heartbeat 字段 + 调度器 per-agent 开关过滤 | TODO |
| R3 | HEARTBEAT_OK 静默 + 空文件跳过 + prompt 段照抄 openclaw | TODO |
| R4 | IM frontend heartbeat 开关 UI + API 字段 + vitest | TODO |
| R5 | ConfigSyncNotifier / config_service.py heartbeat 字段同步 | TODO |
| R6 | HeartbeatScheduler 跑 canonical 直聊 session（改决策3） + tasks: 多子节律 | TODO |
| R7 | activeHours + 忙会话跳过 + transcript 修剪 + NodeGateway-SPEC §6 更新 | TODO |
