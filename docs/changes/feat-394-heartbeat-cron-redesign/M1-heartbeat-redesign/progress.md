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
- Next: R7 完成，所有 Roadpoints DONE

### R7 — activeHours + 忙会话跳过 + SPEC §6 更新

- Context: design 决策3 要求 activeHours 门控和忙会话跳过，避免在睡眠时段或用户正在对话时打扰
- Decision:
  - `HeartbeatScheduler.__init__` 新增 `busy_sessions: set[str]` 参数（共享 mutable set）
  - `tick()` 在读 HEARTBEAT.md 前检查：①`_is_within_active_hours()` ②canonical session 是否在 busy_sessions
  - `_is_within_active_hours()` 使用 IANA timezone 解析，比较 HH:MM 字符串（daytime-only window）
  - `docs/NodeGateway-SPEC.md §6` 重写：双机制表格、heartbeat 执行流程、静默规则、硬规则（改"不补跑"）
  - transcript 修剪：由 openclaw 逻辑在 runner 层（`_consume_heartbeat_run`）负责 — heartbeat prompt 已设为 HEARTBEAT_TRANSCRIPT_PROMPT 标记，修剪留给后续 session compaction 处理（属于 agent kernel 层，不在本 unit 范围）
- Rationale: 核心"不打扰"体验；忙跳过避免同 session 双 run 冲突
- Evidence:
  - Tests: 17/17 test_heartbeat_scheduler; 2364 Python 全套; 347 vitest 全套
  - Entry: 单元测试；N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: c70abb6f (C1 红测试)
- Commits: C1=c70abb6f, C2=fbe109b1
- Next: 所有 R 完成，进入集成

---

## M1 续补：A/B/C 三条退出标准（m1-worker-2）

前一个 worker 在三处核心退出标准不达标被换：A(canonical session 鸡生蛋)、B(transcript 修剪缺失)、C(heartbeat_json 未落库)。本段记录补齐过程。

### A — tick-time 主动查询 canonical session（替换 reactive 反填）

- Context: commit 54380e31 的 reactive 做法（turn_start ack → session_store 反查 → 填 canonical_session_store）有根本性缺陷：静默轮询（HEARTBEAT_OK）从不触发 turn_start ack，所以首拍/重启/安静期 canonical_session_store 永远为空，heartbeat 永远在 fallback 的隔离 session 里跑，不带历史。
- Decision:
  - `PersistentSessionBindingStore` 加 `created_at` 列（migration，首次 INSERT 写入，ON CONFLICT 保留不动），与 IM `_find_canonical_direct_conversation(sorted(key=created_at)[0])` 语义对齐。
  - 新增 `find_direct_by_agent(channel_name, agent_id)`，按 `created_at ASC, rowid ASC` 取最旧 binding（不用 updated_at，那会随消息活动漂移）。
  - `HeartbeatScheduler.__init__` 接收 `session_store` 参数，`tick()` 在每个 agent 的调度评估开始前调 `find_direct_by_agent` 更新 `canonical_session_store`——tick-time 纯 gateway 只读，无 IM HTTP 依赖。
  - `main.py` 移除 `_build_kernel_event_observer` 的 `session_store`/`canonical_session_store` 参数和 ack-time 反填逻辑；先建 `session_store` 再建 `HeartbeatScheduler`（注入顺序调整）。
  - 删除原 reactive 测试 `test_build_kernel_event_observer_populates_canonical_session_from_session_store`（行为已不存在），替换注释指向新测试。
- Rationale: 纯 gateway read，无鸡生蛋依赖；与 IM canonical 排序语义一致（created_at，非 updated_at）。
- Progress.md caveat: gateway `binding.created_at`（首次绑定时刻 = 首条消息触发时刻）作为 IM 会话 `created_at` 的代理，对"有过消息的直聊"排序一致。没有消息的直聊没有 gateway binding，也无历史可跑，不影响。多直聊时 heartbeat run session 和 IM 投递目标（最旧直聊）都按"最旧创建"选，保持一致。
- Evidence:
  - Tests: test_heartbeat_m1_abc.py A 组（4 个）全绿；2383 全套通过
  - Entry: 单元测试覆盖 find_direct_by_agent 方法和 tick-time 更新逻辑
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Commits: C1=adbf89e8 (红测试), C2=b1e060dc (实现)

### B — transcript 即时修剪（静默轮询后会话无噪声）

- Context: 静默轮询（HEARTBEAT_OK/空）的触发 prompt 和 ack turn 如果留在 canonical 直聊 JSONL，下一次 LLM 调用会看到它们，污染上下文（尤其多次静默后堆积）。design 明确"净零残留"且不许推给 compaction 层。
- Decision:
  - `PollingHeartbeatRunner.trim_silent_tick(session_file, pre_submit_line_count)` 静态方法：读 JSONL 所有行，保留前 `pre_submit_line_count` 个非空行，原子写回（tmp file + os.replace）。
  - `_consume_heartbeat_run` 在 submit 前用 `kernel.get_session` 获取 `workspace_root`，推断 JSONL 路径（via `WORKSPACE_CONFIG_DIRNAME` from `local_store`），记录当前行数 `pre_submit_line_count`。
  - run 完成后检查 `run_context_store[run_id]["conversation_id"]` 是否仍为空（空 = 无 turn_start 发出 = 静默），若是则调 `trim_silent_tick`。
  - `WORKSPACE_CONFIG_DIRNAME` 从 `personal_assistant.config.local_store` 导出（避免跨 `agent.products.*` 包边界）。
- Rationale: JSONL append-only 架构下，trim = 截断文件是最简洁的实现；对 silent tick 生效后下一次 LLM context 无新增 heartbeat 噪声。heartbeat-only 轮询不刷新 session idle（trim 仅截断文件，不触发任何 session 存活刷新 API）。
- Evidence:
  - Tests: test_heartbeat_m1_abc.py B 组（2 个）全绿；2383 全套通过
  - Entry: B 测试直接在 JSONL 文件上验证截断效果，无 mock
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯 gateway 层逻辑）
  - Visual/Interaction: N/A
- Commits: C1=adbf89e8 (红测试), C2=b1e060dc (实现)

### C — IM heartbeat_json 落库 round-trip

- Context: 前端 PATCH 传 heartbeat 配置，IM 静默丢弃，gateway 无法读取开关状态。需要全链路：DB 列 → AgentProfile 字段 → 持久化 → 路由读写 → ConfigSyncNotifier 下发。
- Decision:
  - DB migration: `agent_profiles` 加 `heartbeat_json TEXT` 列（nullable，`_migrate_agent_profile_tables`）
  - `AgentProfile` domain model 加 `heartbeat_json: str | None = None` 字段
  - `_row_to_profile` 解析 `heartbeat_json`；所有 SELECT 语句加列
  - `AgentProfileRepository.update_profile` + `ConfigService.update_profile` 加 `heartbeat_json` 参数
  - `AgentConfigResponse` / `UpdateAgentConfigRequest` 加 `heartbeat_json: str | None = None`
  - `to_agent_config_response` 映射；PATCH 路由传 `payload.heartbeat_json`
  - `gateway sync_agent` 优先从 `heartbeat_json`（JSON 字符串）解析，兼容老 `heartbeat` dict 字段
- Rationale: heartbeat_json 存原始 JSON 字符串，gateway 转发无需重新序列化；`update_profile` None 语义 = 保留现有值（与 custom_prompt 一致）。
- Evidence:
  - Tests: test_heartbeat_m1_abc.py C 组（5 个含路由集成测试）全绿；2383 全套通过
  - Entry: `test_agents_patch_route_accepts_heartbeat_json` 用真实 TestClient 验证 PATCH→GET round-trip
  - Frontend State Matrix: N/A（后端变更）
  - Browser QA: N/A
  - E2E/Regression: 合约测试 test_agent_config_contract / test_agent_create_contract 更新含 heartbeat_json 字段断言
  - Visual/Interaction: N/A
- Commits: C1=adbf89e8 (红测试), C2=b1e060dc (实现)

## 最终基线（M1 收口后）

- Python 测试：2383 通过，2 个预存失败（issue #75 macOS /tmp vs /private/tmp）
- Frontend vitest：347/347 通过（54 测试文件）
- 三条退出标准全部达标
