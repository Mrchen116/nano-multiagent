# bugfix-402 — 回归验证

> 对齐: incident.md v1
> Round 1 — 2026-06-11

## Verdict

**fail**

**Highest Required Action**: fix-implementation

**Issues**: blocking: 1, major: 0, minor: 0

---

## 验收标准覆盖

### Requirement: 手动运行复用 cron 原有任务语义

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 立即运行已有任务 | 向 default-agent 发消息请求运行 `test-echo-job`，观察 agent 回复 | Agent 回复 "cron execution service is currently unavailable"（旅程 1） | **fail** | blocking issue #1 |
| 手动任务完成 | 依赖上条通过，无法验证 | 未验证（前置 fail） | **inconclusive** | 依赖前条 |
| 手动运行未知任务 | 依赖 cron service 可用 | 未验证（前置 fail） | **inconclusive** | 依赖前条 |

**Requirement 结论**: fail（blocking issue 阻断全部 Scenario）

---

### Requirement: 异常终结不会永久损坏会话

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 等待权限时中断 | 单元测试 `TestInterruptCancelRecovery`（3 tests covering interrupt/cancelled/shutdown reason）；回归测试 `TestOrphanedToolCallRecovery` | `pytest tests/unit/test_session_manager.py::TestInterruptCancelRecovery tests/unit/test_session_persistence_fidelity.py::TestOrphanedToolCallRecovery` — 11 passed | **pass** | 单测覆盖 interrupt/cancel/shutdown 三种 reason 的完整链路（append → flush → load → build_chat_messages 合法） |
| 加载已有受损会话 | 单元测试 `TestPrepareTranscript`（5 cases）；integration test `test_prepare_transcript_idempotent_across_process_restart` | `pytest tests/unit/test_session_manager.py::TestPrepareTranscript tests/integration/test_session_store_persistence_integration.py` — 15 passed | **pass** | 跨进程重启场景（不同 store 实例 prepare 各一次，load 后只有 1 条 recovery entry） |
| 异常恢复保持幂等 | `TestPrepareTranscript::test_prepare_transcript_idempotent`；integration 跨实例测试 | 同上 — idempotency_key 机制在同一 store 和不同 store 实例下均只产生一套 recovery | **pass** | - |

**Requirement 结论**: pass（单元+集成测试覆盖完整，代码链路：`prepare_transcript_for_run` → `append_tool_call_recovery` → `load()` 物化为合成 tool result）

---

### Requirement: 模型错误按可恢复语义重试并保留真实原因

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 可能恢复的模型故障 | 单元测试 `test_llm_error_classifier.py`（含 billing/quota/timeout/429/5xx 场景）；`test_retrying_llm_client.py` | `pytest tests/unit/test_llm_error_classifier.py tests/unit/test_retrying_llm_client.py` — 30 passed | **pass** | 分类器按语义：billing/quota/429/5xx 均为可重试；顺序保证 403 "overdue" 类响应在状态码检查前先匹配 billing 文本 → 仍为可重试 |
| 明确的永久请求错误 | `test_llm_error_classifier.py` 涵盖明确参数错误、无效凭证、权限不足场景；`test_loop_retry.py` | 30 passed；`test_loop_retry.py` — 见 M2 suite 59 passed | **pass** | 参数错误、鉴权失败、not-found 均标为 `retryable=False` |
| 重试后仍失败 | `test_retrying_llm_client.py` 含 exhaustion 场景；integration `test_provider_error_user_visible.py` | 59 passed | **pass** | 耗尽后保留 `exc.message` + code/type/status/raw body，只追加 retry_exhausted 诊断字段；不用 "exceeded N retries" 包装文案替换 |

**Requirement 结论**: pass

---

### Requirement: Gateway 有序关闭

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 有运行中任务时停止 Gateway | `./scripts/e2e-down.sh` + 扫 `.gateway.log` | `e2e stack stopped` 在 1 秒内完成；`grep "different Context\|Task was destroyed" .gateway.log` 无输出 | **pass** | 无 cross-Context 二次异常；单元测试 `test_runs_registry.py` + `test_gateway_shutdown_order.py` 12 passed |
| 因真实故障退出 | `pytest tests/unit/test_runs_registry.py` — DRAINING 状态机保留首因错误；关闭阶段次要错误只 log 不覆盖 | 12 passed；e2e log 无 Traceback | **pass** | - |

**Requirement 结论**: pass

---

### Requirement: Web IM 不再依赖全局真人用户目录

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 打开和使用现有聊天 | 浏览器：登录 → /chat → 浏览会话列表 → 进入 default-agent 对话 | 全程网络请求无 `/im/v1/users`，无 404；截图 `/tmp/m5-02-after-login.png`, `/tmp/m5-08-open-chat.png` | **pass** | 网络日志全程只见 `/agents`, `/conversations`, `/nodes`, `/auth/login` |
| 创建 Agent 直聊或 Agent 群聊 | 浏览器：Agents 页面 → default-agent → "Open chat ↗"；`+Group` modal → 选择 agent 创建群 | 创建直聊：POST `/im/v1/conversations` 201，无 `/users`；Group modal 只展示 AGENTS 区域无真人目录；截图 `/tmp/m5-09-group-modal.png` | **pass** | 候选列表来自 `GET /im/v1/agents`，无全局用户目录 |
| 真人用户发现 | 浏览器：Chat 页面 + Group modal 全面检查 | 整个 UI 无真人用户搜索或发现入口；`+Group` modal 仅显示 AGENTS；console 无 `/im/v1/users` 404 | **pass** | 旧 `listUsersRaw`/`createUserRaw`/`loadUserMap` 已删除；contract test 确保 `/im/v1/users` 字符串不再出现 |

**Requirement 结论**: pass

---

## User Journeys Exercised

**旅程 1 — 手动 cron 运行（M4 主路径）**：登录 IM → 创建与 default-agent 对话 → 发送 "Run cron job test-echo-job now" → 等待 agent 响应。期望：立即收到"已入队"确认。实际：收到 "cron execution service is currently unavailable"。覆盖 Scenario: 立即运行已有任务。

**旅程 2 — Web IM 无 /users（M5 全路径）**：打开 Vite dev（Vite 57800, IM 62454）→ 登录 → /chat → Agent 标签 → Agents 页面 → 打开 default-agent 直聊 → +Group modal。全程监控 network。覆盖 Scenario: 打开和使用现有聊天、创建 Agent 直聊或群聊、真人用户发现。

**旅程 3 — 单测验证 M1/M2/M3**：运行全测试树（unit 2165 + contract/integration/im_service 492 = 2657 passed）。覆盖会话恢复、模型错误语义、关闭链路。

**旅程 4 — Gateway 关闭（M3 实机）**：`./scripts/e2e-down.sh` → 扫 `.gateway.log` cross-context 错误。

---

## Issues

### Issue 1: 手动 cron 运行时 cron execution service 不可用

- **Severity**: blocking
- **Regression Relation**: direct（直接违反 Requirement: 手动运行复用 cron 原有任务语义 → Scenario: 立即运行已有任务）
- **Recommended Action**: fix-implementation
- **Action Rationale**: 用户面现象明确：agent 回复 "cron execution service is currently unavailable"（即 `error_code: cron_unavailable`，`accepted=False`），说明 `GatewayCronDispatcher._resolve_service(workspace_root)` 无法找到 default-agent 对应的 `CronExecutionService`。Config 中 `features.cron_scheduling=true`，`test-echo-job` 存在且 enabled。Gateway 日志也持续输出 "cron tick: no CronExecutionService for agent=default-agent ws=..."，表明 scheduled tick 路径也同样受影响。这是 M4 实现中 CronExecutionService 注册或 workspace_root 路径解析存在问题，需要 fix-implementation 修复。

**复现步骤**:
1. 启动 e2e 栈（e2e-up.sh）
2. 向 default-agent 发消息："Run cron job test-echo-job now"
3. Agent 回复包含 "cron execution service is currently unavailable"
4. `.gateway.log` 中有 "cron tick: no CronExecutionService for agent=default-agent" 重复出现

**期望**: Agent 立即回复"已入队"确认；`.gateway.log` 中无 "no CronExecutionService" 警告

---

## Side Findings

- Web IM Vite dev 模式下 console 有 WebSocket 警告（`ws://127.0.0.1:57800/im/ws/user?token=...` failed）。这是 Vite HMR proxy 未配置的预有问题（M5 progress.md 已记录），不是本次引入，不影响功能。minor，不立 issue。

---

## 自动化测试增量

本 unit 新增测试共覆盖：

- M1: `TestPrepareTranscript`（5 cases）, `TestInterruptCancelRecovery`（3 cases）, `TestOrphanedToolCallRecovery`, `test_prepare_transcript_idempotent_across_process_restart`；覆盖 orphaned/partial/idempotent/readonly/closed/跨进程重启场景
- M2: `test_llm_error_classifier.py`（billing/quota/auth/param/5xx/429 分类），`test_retrying_llm_client.py`（yielded_content 不重试、exhaustion 保留原始错误），`test_provider_error_user_visible.py`；覆盖 Kimi/火山代表性 4xx fixtures
- M3: `test_runs_registry.py`（DRAINING 状态机、Task 登记清理），`test_gateway_shutdown_order.py`（aclose 顺序、resource_closers 不含 kernel.close）
- M4: `test_cron_tool_openclaw.py`（TestCronToolRunHostCapability 5 cases），`test_cron_delivery_chain.py`, `test_cron_runner_awareness.py`, `test_cron_scheduler_tick.py`, `test_cron_coding_cli_isolation.py`；覆盖 accepted→running→terminal 三阶段、失败与重启遗留、一次性 job
- M5: `v2/legacy-isolation.test.ts`（contract test 扫 im-chat-api.ts 不含 `/im/v1/users`）；npm test 372 passed

全测试树（非 e2e）：unit 2165 + contract/integration/im_service 492 = **2657 passed，0 failed**

---

## 复现验证

本 unit 是 bugfix，验证修复是否生效：

- **#85（会话毒化 + 不可重试 4xx 盲重试）**：单测 TestPrepareTranscript/TestOrphanedToolCallRecovery + M2 error classifier 测试均通过，机制已实现。用户面：工具调用闭合 + 可恢复错误语义改善。**已修复**（单测）。
- **#86（Gateway 退出 cross-Context ValueError）**：`e2e-down.sh` 验证关闭时 `.gateway.log` 无 "different Context" 输出。**已修复**（实机验证）。
- **#87（Web IM `/im/v1/users` 404）**：浏览器全程无 `/users` 调用，contract test 阻止字符串重现。**已修复**（浏览器+测试验证）。
- **手动 cron 旁路**：`gateway_cron_url` 路径已移除，改用 `personal_assistant.cron.enqueue` capability。但 **cron execution service 在 e2e 环境中不可用**（Issue 1），用户面功能仍失败。**未完全修复**。

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 不改变四包顶层职责划分）
- [x] `docs/specs/kernel/spec.md`：需要更新（design.md delta-spec 列明了 transcript 闭合不变量和 `prepare_transcript_for_run` 契约增量，应由 orchestrator §7.0 收尾归并写入）
- [x] `docs/specs/gateway/spec.md`：需要更新（cron 手动入队尚未进入契约，有序关闭协议改动；同上由 orchestrator 收尾归并）
- [x] `docs/specs/im/spec.md`：无需更新（M5 只修复前端迁移遗漏，Actor 长期契约已存在）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新（本 unit 未改文档体系）

---

# Round 2 — 2026-06-11

## Verdict

**fail**

**Highest Required Action**: fix-implementation

**Issues**: blocking: 1, major: 0, minor: 0

## Fast-lane 说明

复用上轮上下文做轻量复验。重点验证 Round 1 blocking Issue 1（M4 手动 cron）对应的三个 Scenario；其余上轮 pass 的 Requirement 轻量抽验。

## 验收标准覆盖（Round 2 更新）

### Requirement: 手动运行复用 cron 原有任务语义

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 立即运行已有任务 | 重启 e2e 栈（HEAD=0aee0928），向 default-agent 发消息 "Run cron job test-echo-job now" | Agent 回复 "cron execution service is currently unavailable"；`.gateway.log` 仍有 "cron tick: no CronExecutionService for agent=default-agent ws=..." | **fail** | M6 Fix 1 在 e2e 实机仍未生效，见 Issue 1（Round 2） |
| 手动任务完成 | 依赖前条通过 | 未验证（前置 fail） | **inconclusive** | — |
| 手动运行未知任务 | 依赖 cron service 可用 | 未验证（前置 fail） | **inconclusive** | — |

**Requirement 结论**: fail（同 Round 1，blocking issue 未解除）

### 其余 Requirement（轻量抽验）

- **异常终结不会永久损坏会话（M1）**：全树测试 2667 passed（M6 progress 记录），较 Round 1 新增 Fix 3 修复 `load()` 静默丢弃 recovery 的 bug 并新增测试，**维持 pass**。
- **模型错误按可恢复语义重试（M2）**：Fix 4 修正了 billing text 优先级（结构化永久类型/code 优先于 billing 文本），避免 `invalid_request_error` + body 含 "credit" 被误判为可重试；新增 4 个测试。**维持 pass**。
- **Gateway 有序关闭（M3）**：Fix 2 修正 `aclose()` 绕过状态机问题；Fix 5 修正 `e2e-down.sh` grace 计时（`elapsed+=1` → `elapsed_ticks` 正确计数）；Fix 6 新增 `CronExecutionService.drain()`。**维持 pass**。
- **Web IM 不再依赖全局用户目录（M5）**：上轮 pass，本轮无相关修改，**维持 pass**。

## Issues（Round 2）

### Issue 1: 手动 cron 运行时 cron execution service 仍不可用（M6 Fix 1 未生效）

- **Severity**: blocking
- **Regression Relation**: direct（同 Round 1 Issue 1，Requirement: 手动运行复用 cron 原有任务语义）
- **Recommended Action**: fix-implementation
- **Action Rationale**: M6 Fix 1 的 worker 验证是直接调用 `GatewayCronDispatcher.invoke()` 绕过完整 Gateway 启动流程，没有覆盖 `build_runtime()` 循环注册路径在真实 e2e 场景下的表现。实机验证：重启 e2e 栈后 Gateway log 仍输出 "cron tick: no CronExecutionService for agent=default-agent ws=/Users/czj/nano-assistant/workspace/default-agent"，agent 对 cron run 请求的回复仍为 "cron execution service is currently unavailable"。

**复现**：启动 e2e 栈 → 向 default-agent 发 cron run 请求 → 收到 cron_unavailable 回复；`.gateway.log` 有 no-CronExecutionService 警告。

**定位方向（供 fix worker 参考）**：M6 Fix 1 增加了 `on_agent_created` callback 路径，解决了动态注册的 agent；但静态注册路径（`build_runtime()` 启动循环遍历 `config.agents`）仍可能存在路径不匹配。e2e config 中 default-agent 的 `workspace_root` = `/Users/czj/nano-assistant/workspace/default-agent`；注册调用 `Path(ws).expanduser().resolve()` 后得到的 key 应与 dispatcher 调用时 `context.workspace_root` 的值一致——需要确认 `HostCapabilityContext.workspace_root` 在 cron tool 调用时传入的是什么路径，与注册时用的 key 是否完全相同。

---

# Round 3 — 2026-06-11

## Verdict

**pass**

**Highest Required Action**: pass

**Issues**: blocking: 0, major: 0, minor: 0

## Fast-lane 说明

复用上轮上下文做轻量复验。重点验证 Round 1/2 blocking Issue 1（M4 手动 cron）全部三个 Scenario；其余 Requirement 轻量抽验。HEAD=fd8836d7，根因修复：改用 `agent_id` 作为 `GatewayCronDispatcher` 路由 key，消除 `workspace_root` 两数据源不一致问题。

## 验收标准覆盖（Round 3 更新）

### Requirement: 手动运行复用 cron 原有任务语义

| Scenario | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|
| 立即运行已有任务 | 重启 e2e 栈（HEAD=fd8836d7），向 default-agent 发 "Run cron job test-echo-job now"；观察 agent 回复 | Agent 立即回复 "The cron job `test-echo-job` has been triggered and is running now."；`.gateway.log` 无 "no CronExecutionService" 警告 | **pass** | |
| 手动任务完成 | 等待 agent 发出 cron 执行结果；检查 runs.jsonl 历史和目标会话消息 | 对话中出现 `[agent]: CRON_RUN_OK - e2e validation complete.`；runs.jsonl 记录 `trigger=manual status=completed result_summary=CRON_RUN_OK - e2e validation complete.` | **pass** | 三阶段历史 accepted→running→completed 完整；结果出现在触发用的同一对话 |
| 手动运行未知任务 | 向同一对话发 "Run cron job nonexistent-job now"；观察 agent 回复 | Agent 回复 "That cron job doesn't exist. There's no job named `nonexistent-job` on the system."；无任务被创建或执行 | **pass** | 明确反馈任务不存在，不执行其他任务 |

**Requirement 结论**: pass（三个 Scenario 全部通过）

### 其余 Requirement（轻量抽验）

- **异常终结不会永久损坏会话（M1）**：全树测试在 M6 已达 2667 passed；Round 3 无新修改，**维持 pass**。
- **模型错误按可恢复语义重试（M2）**：Round 3 无新修改，**维持 pass**。
- **Gateway 有序关闭（M3）**：`e2e-down.sh` 验证关闭无 "different Context\|Task was destroyed" 输出，**维持 pass**。
- **Web IM 不再依赖全局用户目录（M5）**：无相关修改，**维持 pass**。

## Side Findings

- Gateway 日志中有 `cron: awareness inject failed: agent=default-agent job=test-echo-job session=sess_4fd0d3a302ca37ad`。这是 cron 执行完成后向 canonical session 写回 awareness 记录时失败，但用户在对话中已收到结果（CRON_RUN_OK），runs.jsonl 历史完整。awareness inject 属于辅助行为，不是 incident.md Scenario 2 THEN 的直接用户可观察项（"结果出现在目标会话和运行历史中"已满足）。minor，不立 issue，记录供后续关注。

