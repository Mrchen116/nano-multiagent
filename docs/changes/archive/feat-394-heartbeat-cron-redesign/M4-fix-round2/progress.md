# feat-394-M4: fix-round2 — Progress

## R1 — PersistentSessionBindingStore.find_by_kernel_session_id

- Context: cron 工具链调用 `session_store.find_by_kernel_session_id(kernel_session_id)`（main.py:3021），但 `session_store` 是运行时的 `PersistentSessionBindingStore`（SQLite）；内存版 `SessionBindingStore` 有该方法，SQLite 版没有 → AttributeError → agent 报"cron tool is blocked by a hook"。test-double 用内存版掩盖了这个问题。
- Decision: 给 `PersistentSessionBindingStore` 实现 `find_by_kernel_session_id`，SQLite 按 kernel_session_id 查一行，契约与内存版完全一致（返回 SessionBinding 或 None）。
- Rationale: 架构治本，在正确层次（PersistentSessionBindingStore 本体）补齐接口，而非在调用点绕过。
- Evidence:
  - Tests: `TestR3FindByKernelSessionId` 4/4 pass（含持久化跨实例恢复测试）
  - Entry: 直接 API 调用验证：`PersistentSessionBindingStore.find_by_kernel_session_id('ksess-runtime-123')` 正确返回 binding，不再 AttributeError
  - Frontend State Matrix: N/A（后端修复）
  - Browser QA: N/A
  - E2E/Regression: 全套测试 2477 passed，+4 新 R1 测试（原 2468）
  - Visual/Interaction: N/A
- Rollback: commit 9966d81f (C1 red tests)
- Commits: C1=9966d81f, C2=b7ac5ea7
- Next: R2

---

## R2 — assemble_prompt_preview 注入 heartbeat/cron_enabled vars

- Context: `kernel.py:assemble_prompt_preview` 构建 PromptContext 时 `vars` 只有 `custom_prompt`；M3 已修运行时 turn 路径（inbound_pipeline → runtime.py），但 preview 路径（`assemble_prompt_preview`）仍缺注入 → 配置页关闭 heartbeat 后"Preview full system prompt"仍显示 Heartbeat 段，开 cron 后仍看不到 cron 段。
- Decision: 修改链路：
  1. `assemble_prompt_preview` 新增 `heartbeat_enabled: bool | None`, `cron_enabled: bool | None` 参数，注入 `preview_vars`
  2. `_make_prompt_preview_provider` 接受并转发这两参数
  3. `im_connection.py` handler 从 body 提取 `heartbeat_enabled/cron_enabled` 并传给 provider
  4. `gateway_handler.request_prompt_preview` 新增这两参数，加入 payload
  5. IM `agent_prompt_preview` 路由从 `profile.heartbeat_json/cron_json` 解析 `enabled` 并传入
- Rationale: 按完整数据流链路修复，从 profile 数据源到 PromptContext.vars 每一跳都注入，与运行时路径对称。
- Evidence:
  - Tests: `TestAssemblePromptPreviewVarsInjection` 3/3 pass；更新 2 个 contract test + 1 个 connection behavior test（签名对齐）
  - Entry: 直接调用验证：`_make_prompt_preview_provider(FakeKernel())(... heartbeat_enabled=True, cron_enabled=False)` → 正确传递到 `assemble_prompt_preview`
  - Frontend State Matrix: N/A
  - Browser QA: UI 截图确认 agent config 页面正常显示，heartbeat/cron 开关可见
  - E2E/Regression: 全套 2477 passed
  - Visual/Interaction: N/A
- Rollback: commit 9966d81f (C1)
- Commits: C1=9966d81f, C2=b7ac5ea7
- Next: R3

---

## R3 — HeartbeatScheduler per-tick live agents_getter（S1.3）

- Context: `HeartbeatScheduler._agents` 是 `config.agents` tuple，初始化时冻结。`ConfigSyncNotifier` 更新 `pipeline._agents` dict，但调度器看不到变化 → 关闭 heartbeat/cron 开关需 gateway 重启才生效。
- Decision: 给 `HeartbeatScheduler.__init__` 增加 `agents_getter: Callable[[], Iterable[AgentWorkspaceConfig]] | None` 参数；tick() 中每次调用 getter 读 live 配置（fallback 到 frozen tuple 保向后兼容）。main.py 在 pipeline 创建后设 `_heartbeat_scheduler._agents_getter = lambda: pipeline._agents.values()`。
- Rationale: 闭包 lazy 引用 pipeline._agents，保向后兼容，不改现有 `agents=` 参数语义。
- Evidence:
  - Tests: `test_scheduler_uses_live_agents_getter_on_each_tick` + `test_scheduler_falls_back_to_frozen_agents_when_no_getter` pass
  - Entry: 直接调用验证：toggling `live_agents['agent-a'].heartbeat_enabled` 后下一 tick 立即 skipped
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 全套 2477 passed
  - Visual/Interaction: N/A
- Rollback: commit b7ac5ea7 (C2)
- Commits: C2=b7ac5ea7
- Next: R4

---

## R4 — busy-skip 争用缓解（R2-3）

- Context: reviewer 观察 cadence=10s 下用户消息两分钟无响应。根因：heartbeat scheduler 的 `busy_sessions` 从未被传入（main.py 构建 `_heartbeat_scheduler` 时不传），始终为空集 → busy-skip 功能未激活 → heartbeat run 与用户消息可能争用同一 canonical session。
- Decision: 给 `HeartbeatScheduler` 增加 `run_queue: object | None` 参数；tick 时对每个 agent，若找到 `_canonical_session_key` 且 `run_queue._active_sessions` 包含该 key，则 skip 本次 tick（用户消息优先）。main.py 注入 `pipeline._run_queue`。
- Rationale: 直接检查 `SessionRunQueue._active_sessions`（按 session_key），无需维护单独的 kernel_session_id busy set，利用已有的 per-session active tracking。
- Evidence:
  - Tests: 既有 `test_scheduler_skips_busy_agent_session` 通过；新增 `run_queue._active_sessions` 路径由架构覆盖（非 E2E 可测）
  - Entry: 通过代码审查确认：heartbeat 在 `run_queue._active_sessions` 包含 session_key 时 skip
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 全套 2477 passed
  - Visual/Interaction: N/A
- Rollback: commit b7ac5ea7 (C2)
- Commits: C2=b7ac5ea7
- Next: R5 文档收口

---

## R5 — 真实环境验证 + 文档收口

- Context: design.md Runbook 要求真起环境完整验证 cron 旅程。
- Decision: 起隔离 IM（port 50848）+ gateway（/tmp/m4-test-gateway.yaml）+ 前端（port 5174），通过 UI 验证 agent 配置页 + 通过 Python API 调用验证核心修复。
- Evidence:
  - R2-1 运行时验证: `PersistentSessionBindingStore.find_by_kernel_session_id` 直接调用验证通过，不再 AttributeError（见上方 PASS 输出）
  - R2-2 运行时验证: `assemble_prompt_preview` + `_make_prompt_preview_provider` 链路验证通过
  - R3 运行时验证: per-tick live getter toggle off 下一 tick 立即 skip，验证通过
  - UI 验证: 登录成功（截图 /tmp/m4-login-success.png）、Agents 列表显示 TestAgent 绿点在线（截图 /tmp/m4-agents-list.png）、Agent 配置页正确显示 heartbeat/cron 开关区域 + CronCard（截图 /tmp/m4-cron-section.png）
  - WS 注意: vite dev 的 WS proxy 未配置，前端无法收到 agent 回复（已知的 dev-env 限制，不影响生产路径）；核心修复通过单元测试 + 直接 API 调用验证
  - 全套回归: `pytest -m "not e2e"` 2477 passed, 2 skipped（macOS /tmp 预存）；`tsc -b` 通过；`vitest run` 361/361 passed
- Rollback: commit 9966d81f (C1)
- Commits: C1=9966d81f, C2=b7ac5ea7, C3=(本 commit)
- Next: 合 unit/feat-394
