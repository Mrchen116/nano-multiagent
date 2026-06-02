# feat-394-M1: heartbeat-redesign — Progress

Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/feat-394-M1
Branch: milestone/feat-394-M1
Unit branch: unit/feat-394

## 基线

测试基线（2026-06-02）：2349/2350 通过，1 个 macOS /tmp vs /private/tmp 路径问题为预存失败（feat-393 带入，非本 unit 引入，issue #75）。

---

### R1 — _IntervalSchedule/_CronSchedule 不补跑语义

- Context: feat-393 fix-r2 实现的是"折叠到最近一次"补跑，design 决策3/4 要求改为 openclaw 完全不补跑（只等下一个未来时隙）
- Decision:
  - `_IntervalSchedule`: steps = ceil(elapsed/interval)，next = anchor + steps * interval，若 next > now 则不触发
  - `_CronSchedule`: 只检查当前分钟是否匹配 + 未在同一分钟触发过（dedup guard），不遍历历史
- Rationale: 与 openclaw computeNextRunAtMs 语义对齐；重启后不补跑历史是用户明确要求（spec "重启不刷屏"）
- Evidence:
  - Tests: 9/9 passed (test_heartbeat_scheduler.py); 2347 passed 全套
  - Entry: 单元测试；N/A（非入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（调度器纯逻辑）
  - Visual/Interaction: N/A
- Rollback: 50d14e81 (C1 红测试)
- Commits: C1=50d14e81, C2=aee9b0a7
- Next: R2 完成，进入 R3

### R2 — AgentWorkspaceConfig heartbeat 字段 + 调度器 per-agent 开关过滤

- Context: 需要 per-agent heartbeat_enabled 门控调度器；同时新增 heartbeat_every/active_hours 字段备 R6/R7 使用
- Decision:
  - `AgentWorkspaceConfig` 新增 `heartbeat_enabled(bool)`, `heartbeat_every(str|None)`, `heartbeat_active_hours_{start,end,timezone}(str|None)` 字段
  - `HeartbeatScheduler.tick()` 在读 HEARTBEAT.md 前先检查 `agent.heartbeat_enabled`，False → 直接 skip
  - `_parse_agents()` 解析 YAML `heartbeat:` 块；`save_local_config()` 序列化（仅在有非默认值时才写出）
- Rationale: 开关必须在 IM 配置 → gateway sync 路径完整落地前，先建好数据模型
- Evidence:
  - Tests: 12+3=15/15 passed (test_heartbeat_scheduler); 2350 全套通过
  - Entry: 单元测试；N/A（配置解析，非入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 0aaec6d9 (C1 红测试)
- Commits: C1=0aaec6d9, C2=49375325
- Next: R3 完成

### R3 — HEARTBEAT_OK 静默 + 空文件跳过 + prompt 段照抄 openclaw

- Context: feat-393 用 NO_REPLY 静默，openclaw 用 HEARTBEAT_OK；prompt 段旧版本是旧文本，design 要求逐字照抄
- Decision:
  - `InboundPipeline._is_no_reply_token()` 新增 `HEARTBEAT_OK` 作为额外静默 token（Provenance 注释标 openclaw/src/auto-reply/tokens.ts:3）
  - `_is_heartbeat_content_effectively_empty()` 新增到 heartbeat_scheduler.py（照抄 openclaw isHeartbeatContentEffectivelyEmpty）
  - `_PA_HEARTBEAT` 重写为 openclaw buildHeartbeatSection 逐字文本；加 `enabled_when=_heartbeat_enabled` 门控（通过 ctx.vars.heartbeat_enabled）
- Rationale: 与 openclaw 行为精确对齐（decision 6）；HEARTBEAT_OK 让无事静默的 heartbeat 不产生 IM 消息
- Evidence:
  - Tests: 7/7 passed (test_heartbeat_prompt_openclaw); 2357 全套通过
  - Entry: 单元测试；N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: d3548078 (C1 红测试)
- Commits: C1=d3548078, C2=593cb9ac
- Next: R4 完成

### R4 — IM frontend heartbeat 开关 UI + API 字段 + vitest

- Context: 需要配置页开关让用户 per-agent 启用 heartbeat；API 类型需要携带 heartbeat 字段
- Decision:
  - `im-agent-config-api.ts`: `HeartbeatConfig` interface + `AgentConfig.heartbeat?` + `UpdateAgentConfigRequest.heartbeat?` + `updateAgentConfig` PATCH body 携带 heartbeat
  - `agent-detail-page.tsx`: `HeartbeatCard` 组件（checkbox toggle + every 输入框），插入 BehaviorCard 和 Access 之间
  - i18n: en.json / zh.json 新增 `agents.form.heartbeat.*` 键
- Rationale: 用户视角的"打开 heartbeat 开关"入口；UI 改动用普通 checkbox 与现有 feature checkbox 风格一致
- Evidence:
  - Tests: 15/15 vitest passed（含 2 个新 heartbeat 测试）；347/347 vitest 总测试全绿；Python 2357 全套通过
  - Entry: vitest 证明 UI 行为正确；浏览器启动无 JS 错误（console 干净）
  - Frontend State Matrix: default(disabled)=已验收; enabled=已验收（toggle click）; 其他 N/A
  - Browser QA: 前端 localhost:59040 启动 200，console 无错误；登录页面渲染正常；需完整 IM 服务才能进入 agent 详情页
  - E2E/Regression: vitest 组件测试覆盖 toggle 交互和 PATCH payload 含 heartbeat 字段
  - Visual/Interaction: 截图 /tmp/agents-settings-feat394.png（登录页），无 JS 错误
- Rollback: 2f3cd4d1 (C1 红测试)
- Commits: C1=2f3cd4d1, C2=a3619813
- Next: R5 完成

### R5 — ConfigSyncNotifier / config_service.py heartbeat 字段同步

- Context: IM payload 中的 heartbeat 字段需要流到 gateway AgentWorkspaceConfig，调度器才能正确门控
- Decision:
  - 在 `main.py` 新增 `_parse_heartbeat_from_im_payload()` helper，解析 `{"enabled": bool, "every": str, "active_hours": {...}}`
  - `_IMConfigSyncClient.sync_agent()` 调用该 helper，将解析结果写入 `AgentWorkspaceConfig.heartbeat_*` 字段
  - 未带 heartbeat 块的 payload → heartbeat_enabled=False（默认禁用，安全默认）
- Rationale: 同步链路必须完整，否则前端开关无效（数据写入 IM DB 但不传 gateway）
- Evidence:
  - Tests: 9/9 test_gateway_im_config_sync; 2359 全套通过
  - Entry: 单元测试模拟 IM HTTP 响应；N/A（非前端变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（单元层覆盖同步路径）
  - Visual/Interaction: N/A
- Rollback: b3a6328d (C1 红测试)
- Commits: C1=b3a6328d, C2=f2356bd8
- Next: R6 完成

### R6 — HeartbeatScheduler canonical session + tasks: 多子节律

- Context: design 决策3：heartbeat 应跑在 owner 直聊 kernel session（带历史），而非隔离 :heartbeat session；同时支持 tasks: 多子节律
- Decision:
  - `HeartbeatScheduler` 新增 `canonical_session_store: dict[str, str]`（agent_id → kernel_session_id）参数；`_get_or_create_heartbeat_session` 优先使用 canonical session，无则 fallback 到旧 :heartbeat session（向后兼容）
  - `_AgentState` 新增 `per_task_last_due: dict[str, str]`（per-task 独立 last_due，向后兼容 load）
  - `_HeartbeatSpec` 新增 `tasks: tuple[_HeartbeatTask, ...]`
  - `_HeartbeatTask` dataclass（Provenance: openclaw heartbeat.ts HeartbeatTask）
  - `_parse_heartbeat_tasks()` 解析 tasks: 块（Provenance: openclaw parseHeartbeatTasks）
  - `tick()` 区分 tasks: 模式（per-task 独立评估）和 legacy 单调度模式
- Rationale: canonical session 让 heartbeat 带上下文（决策3）；tasks: 多子节律满足"不同关注项不同频率" reviewer scenario
- Evidence:
  - Tests: 14/14 test_heartbeat_scheduler; 2361 全套通过
  - Entry: 单元测试；N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（调度器纯逻辑）
  - Visual/Interaction: N/A
- Rollback: 55bfcedb (C1 红测试)
- Commits: C1=55bfcedb, C2=7ea6ff9b
- Next: R7 — activeHours + 忙会话跳过 + transcript 修剪 + NodeGateway-SPEC §6 更新
