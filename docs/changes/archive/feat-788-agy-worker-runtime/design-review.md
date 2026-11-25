# feat-788: 本机 Global worker 支持 Antigravity CLI — Design Review

## Round 1

### Metadata

- **reviewer**: `change-design-reviewer`（独立审查子会话 `1302b5ca-e950-48e6-89fe-7a9d22d865b0`，并入 `agent-context-review` 设计模式）
- **target**: `docs/changes/feat-788-agy-worker-runtime/`（`spec.md`、`design.md`、`specs/gateway/global-agent.md`、`specs/gateway/tool-approval.md`、`specs/im/agent-work.md`、`M1-antigravity-worker/`，分支 `unit/feat-788-agy-worker-runtime`）
- **review_mode**: `full`
- **mode_reason**: Gate 2 首轮（Round 1）独立设计审查，全量核查现状断言、产品组装入口、关键决策、用户约束、delta-spec、milestone、跨包依赖边界及 Agent Context 链路。
- **started_at**: `2026-11-25T17:22:59+09:00`
- **completed_at**: `2026-11-25T17:45:15+09:00`
- **duration**: `22m16s`

### Verdict

**Issues Found** — `2 CRITICAL / 4 WARNING / 3 Recommendation`

---

### Coverage 与证据

#### 1. 现状断言与实际产品组装入口核查

沿真实产品启动与数据流逐跳核实了全部改动落点：

1. **节点配置与启动注入**：`apps/node/src/main.ts` → `apps/node/src/bootstrap.ts` → `apps/node/src/configuration.ts`（第 47–49、109 行）。`NodeConfiguration.read` 校验 `gateway.worker_runtime`（现硬编码 `['dsh', 'codex', 'claude']`），`NodeConfiguration.runtime` 注入 `AgentConfiguration.workerRuntime`（默认 `'dsh'`）。现状断言属实。
2. **主运行时与本机一级 worker 调度**：`packages/dsh-integration/src/index.ts` → `src/global-mode.ts`（第 20–36 行 `delegate_worker` 工具注册，读取当前根会话 `workerRuntime`）→ `src/local-workers/manager.ts`（第 18 行 `recordSchema.shape.runtime` 硬编码 `z.enum(['dsh', 'codex', 'claude'])`，第 250–303 行 `start`，第 329–382 行 `activate`，第 384–417 行 `control`）→ `src/local-workers/drivers.ts`（`openCliWorker` 分发 `cliDrivers`）与 `src/local-workers/report-bridge.ts`（本地临时目录 Unix socket + stdio MCP `nano-parent` `send_message`）。
   - **偏差 1（见 `R1-C1`）**：`design.md` 第 82、96 行声称 `TurnEvents.end` 提取 `total_tokens` 同步驱动 `LocalWorkers` 轮次累计并填入 `worker_state.turn_usage`。核查 `drivers.ts`（第 15、39–46 行）与 `manager.ts`（第 147–186、360–366 行）可见：`LocalWorkers.publishTurns`（生成 `worker_state.turn_usage`）**仅**用于无 `detail` 事件的 `runtime === 'dsh'` 原生子会话；外部 CLI worker 的 `TurnEvents.end` 从不向 `LocalWorkers` 传递 token，而是仅靠 `detail` 中的 `turn_end.payload.usage` 在 IM 侧累计。
   - **偏差 2（见 `R1-W2`、`R1-W3`）**：`cli-process.ts`（第 42–49、93–97 行）在 `onMessage` 前对全部 stdout 行强行 `JSON.parse` 且 `resolve()` 丢弃 JSON-RPC `error.code`，无法直接支持 `design.md` 第 101 行的非 JSON 未登录前缀识别与 `-32000` 结构化判断；`work-details.ts`（第 29–35、47–85 行）对 `tool_start` 按 `callId` 去重且 `toolEnd` 要求非空工具名，直接按第 108 行描述实现会丢失流式补全的工具参数或漏发 `tool_end`。
3. **PA 同步、会话删除与长期记忆隔离**：
   - `packages/personal-assistant/src/global-agent.ts`（第 1191–1204 行）：`projectRootPage` 将 `result.workerChanges` 映射为 `worker_state` 或 `detail` Work 事件。
   - `packages/personal-assistant/src/inbox.ts`（第 247 行）：`deletionSessionIds` 的 SQL 硬编码 `IN ('codex','claude')` 排除外部 CLI worker，防止 `packages/dsh-integration/src/agent-deletion.ts` 将 `worker-...` 误当作缺失的原生 DSH 会话报错；纳入 `antigravity`（收敛至 `cliWorkerRuntimes`）落点准确。
   - `packages/dsh-integration/src/descendants.ts`（第 131、246 行）、`src/trajectory.ts`（第 66、91 行）、`src/knowledge/memory-sources.ts`（第 179 行）：`LocalWorkers` 将 `antigravity` 写入 `nano_local_workers` 后，`isWorker(workerId)` 返回 `true`，自动阻断原生子轨迹暴露与 `source_history` 回查，且 Dreaming 仅遍历原生 `subagent/catalog` 事件，长期记忆解耦闭合成立。
4. **契约校验、IM Work 落库与双端展示**：
   - `packages/product-contracts/src/work-event-codec.ts`（第 50、76 行）与 `src/runtime-rpc-work.ts`（第 40–48 行）：`worker_state` 现硬编码 `['dsh', 'codex', 'claude']`；`turn_end.payload.usage` 已放行 `context_used`、`context_window`、`output`、`cache_read_tokens`、`cache_total_input_tokens`、`total_tokens`，但要求所有已出现键均为有限 `number`（不允许 `null`，见 `R1-W1`）。
   - `apps/im-server/src/work-records.ts`（第 285、407–436、470 行）与 `src/work-summaries.ts`（第 221–227 行）：第 285 行准入校验硬编码 `['codex', 'claude']`；`turn_end` 投影与 `updateWorkLifetimeUsage` 已原生支持上下文窗口、细分 token 落库与累计 token 汇总。
   - `src/IM/frontend/src/features/settings/agents/agent-work-api.ts`（第 11、15 行）、`agent-work-panel.tsx`（第 314、513、780–781 行）、`agent-work-presenters.tsx`（第 172–184 行 `WorkUsage`）以及 `src/IM/ios/NanoIM/Features/Agents/AgentWorkView.swift`（第 786–812 行）：Web 端更新 `workerRuntimeNames` 与 `externalWorker` 后即可在活动弹窗（`agent-activity-popover.tsx:100`）、派工关系（`agent-work-delegation.tsx:221`）与工作记录侧栏显示 `Antigravity` 并禁用原生轨迹切换；当 `turn_end.payload.usage` 同时提供数值型 `context_used` 与 `output` 时，Web `WorkUsage` 与 iOS `AgentWorkView` 均已原生展示上下文已用/窗口上限、百分比、本轮输出、缓存命中与总 token。

#### 2. 需求覆盖、用户约束与关键决策核查

- **用户澄清约束对齐**：Q1 用户明确选择“沿用 feat-778 按机器统一配置（在 `gateway.worker_runtime` 新增 `antigravity`，与 `dsh` / `codex` / `claude` 并列）”，`spec.md` 非目标排除了按次动态选框架、内置下载/OAuth 网页登录及二次子轨迹展开。`design.md` 严格遵守该边界，未引入越界配置或 UI。
- **本机 `agy` 与上游参考核实**：核对了宿主机 `agy 1.5.16`（`agy acp --help`）及参考仓 `t3code`（`AntigravityAcpSupport.ts`、`antigravityAuthSupport.ts`、`AntigravityProtocol.ts`、`AcpSessionRuntime.ts`）与 `raft-source`（`@botiverse/oar` `antigravity/session.js`）：
  - `agy acp --process-per-session`、`session/resume`、剔除 `SSH_CLIENT`/`SSH_CONNECTION`/`SSH_TTY`、`AGY_CLI_DISABLE_AUTO_UPDATE=true`、专属 `TMPDIR` 隔离与退出清理、185,000 UTF-8 字节输入上限（源自 OAR 对 `agy 1.5.6` 大输入截断实测）均有据可查。
  - 运行中二次 `session/prompt` steer 使前序挂起 `session/prompt` 提前结算、最终结果落在最后一个在途请求的机制与 `agy >= 1.5.0` 实测行为一致；但权限回退与协议细节存在 `R1-C2`，用量字段可选性与双写存在 `R1-C1`、`R1-W1`。

#### 3. 架构职责、依赖方向与复用判断

- **模块职责与复用判断**：将 ACP 协议适配收敛在 `packages/dsh-integration/src/local-workers/` 内，复用既有 `CliProcess`、`workerReportBridge`、`LocalWorkers` 持久状态机与 `IM Work` 账本，不引入 `@botiverse/oar` 或 `effect-acp` 等重型运行时依赖，职责边界清晰、维护与升级代价最低，符合 `AGENTS.md` 与 `SPEC.md`“仅 `dsh-integration` 管理本机一级 CLI worker、不新增第二套 Agent Loop 或内核 HTTP 服务”的红线。
- **跨包导入约束（见 `R1-W4`）**：`tests/contract/test_runtime_dependency_contract.py` 对前后端导入 `@nano/product-contracts` 实施非对称子路径白名单（后端仅允许根入口 `@nano/product-contracts`，Web 前端仅允许子路径 `@nano/product-contracts/worker-runtimes`），`design.md` 第 70 行的统一根入口表述需按包拆分写清，避免触发架构契约红测。

#### 4. 原型边界与一次性部署迁移检查

- **原型边界判断**：通过。按前端体验规范“原型的判断范围”，本 unit 仅在既有框架标签位新增字符串 `"Antigravity"`，并把外部 worker 的 `turn_end.payload.usage` 喂给已上线的 `WorkUsage` 组件（布局、字号、进度条与折叠交互完全不变），不存在待通过画面对齐的信息组织或交互取舍，不生成 `prototype.html` 合理。
- **一次性部署迁移判断**：通过。`gateway.worker_runtime` 默认保持 `dsh`，`nano_local_workers` 与 IM `agent_work_*` 表均以 JSON 文本承载负载而无旧枚举 SQL CHECK 约束，无需 `deployment-prompt.md`。

#### 5. 契约层增量（delta-spec）核查

- `specs/gateway/global-agent.md` → 锚定 `docs/specs/gateway/global-agent.md` 的 `Requirement: 主 Agent 将完整独立事项交给单一内部执行者负责`，完整保留全部 9 个既有 Scenario，仅在 `Scenario: 机器级派工与中断恢复` 纳入 `Antigravity CLI`，条款收窄恰当。
- `specs/im/agent-work.md` → 锚定 `docs/specs/im/agent-work.md` 的 `Requirement: Web Work 可以从派工关系进入同一工作记录`，完整保留既有 Scenario；新增的轮次上下文窗口与细分 token 描述以“当该轮报告上下文窗口与输出、缓存等细分统计时”为前提，不会将仅报告 `total_tokens` 的 `Codex`/`Claude Code` 或部分字段未报告轮次误判为回归。
- `specs/gateway/tool-approval.md` → 锚定 `docs/specs/gateway/tool-approval.md` 的 `Requirement: Auto默认采用Codex规则且可配置为CC或DSH规则`，完整保留全部 9 个 Scenario；但 `Scenario: 外部 worker 的 Auto 请求` 中“（目标会话未开放原生 Auto 时维持默认受控模式）”与后文“后续授权或补充作为同一会话的新输入重新判定”在 Nano 无宿主侧审批策略的前提下自相矛盾（见 `R1-C2`）。
- `no spec delta` 判断（`agent-capabilities`、`service-lifecycle`、`ios-client`）及 `docs/specs/im/response-metrics.md` 核对：均无需改动规范正文，但 `design.md` 的缓存统计映射须遵守 `response-metrics.md`“不把缺失缓存计数当成零命中”的既有条款（见 `R1-W1`）。

#### 6. 审查安排、Runbook 与 Milestone 核查

- **Milestone 划分**：单 milestone `M1-antigravity-worker` 覆盖契约枚举、ACP 驱动、IM 准入、前端标签及文档更新；改动紧密围绕同一跨包窄切片，无并行冲突，`[reviewer]` 与 `[worker]` 退出标准区分了用户可观察行为与窄测试/本机实测证据。
- **审查安排与 Runbook**：选用了 `change-code-review` + `agent-context-review`（无新增视觉/布局决策，不选 `frontend-experience-review` 合理，但 Web IM Work 展示仍须在实施与验收时按 `M1` `[reviewer]` 退出标准核验数据与组件呈现）。隔离栈启停命令遵循 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh` 与临时资源回收红线；本轮 Agent Context 审查识别出的**实现后必查观察点**已列于下节，应在实施取证与代码审查时逐项核验。

#### 7. Agent Context 专项审查（`agent-context-review` 设计模式）

- **审查范围与版本**：`feat-788-agy-worker-runtime` 设计稿（`spec.md` v1、`design.md`、`specs/gateway/tool-approval.md`），对照当前 worktree 代码与本机 `agy 1.5.16` ACP 契约。
- **Consumer 1 — Global / PA Root（主会话）**：
  - *装配与交付*：`delegate_worker` 工具定义与提示词不变；Antigravity 的 `nano-parent` `send_message` 主动提问、权限拒绝回执、原生 `interaction_` 提问拦截回执以及轮次终局汇报统一经 `LocalWorkers.deliver` 添加 `Worker ${label} (${workerId}): ` 前缀送入父会话，受既有 `inboxSourceInstructions`（非真人新授权）约束。
  - *风险判定*：**CONFIRMED（设计缺口，见 `R1-C2`、`R1-W2`）**——(1) ACP `session/request_permission` 允许仅凭 `toolCallId` 引用前序 `tool_call` 而省略 `title`/`rawInput`，若不合并已跟踪工具状态直接调用 `actionTarget`，父 Global 收到的被拒汇报将缺失命令/路径目标（变成空 `{}`），无法判断需要向用户澄清什么；(2) 未登录或缺失 `auto` 模式时若报出底层 JSON 解析错误或陷入 `default` 模式无限拒批，父 Global 无法获得可理解的失败原因。
- **Consumer 2 — Antigravity Worker（外部 CLI 会话）**：
  - *来源、生命周期与恢复*：每次 `session/new` 与冷恢复 `session/resume` 均通过 `_meta.antigravity.systemPrompt.append` 注入 `LocalWorkers` 固定角色说明 `instructions`，并重新挂载指向当次临时 Unix socket 的 `nano-parent` stdio MCP（注：`workerReportBridge` 通过命令行参数传 socket 路径、`env: {}` 不含长期凭据，因此即使 `agy` 将 `mcpServers` 记入自身会话库，每次 `session/resume` 也会被新 `mcpServers` 覆盖且不泄漏密钥）。
  - *工具、记忆与权限交互*：**REFUTED（记忆泄漏风险已排除）**——Nano 不传 `MEMORY.md` 或产品 IM 工具；`nanoWorkers.isWorker` 与 `MemorySources` 原生事件过滤确保双向隔离。**PLAUSIBLE（降级拼接污染，见 `R1-R3`）**——若极旧版本走“首条 `session/prompt` 前拼接角色说明”分支，须避免把系统说明一并写入 `WorkerTurnDetails` 的 `user` 消息或与用户原话无边界混排。
- **交回执行与实施后审查的必查观察点**：
  1. 捕获真实 `agy 1.5.16` 的 `initialize`、`session/new`、`session/resume`、`session/set_mode` 请求/响应帧，确认 `_meta.antigravity.systemPrompt.append` 被采纳、`mcpServers` 仅含 `nano-parent`、未覆写用户默认模型，且 `currentModeId` 实际切入 `auto`。
  2. 触发一次 `nano-parent` `send_message` 调用与一次越界/待批动作（及模拟 `interaction_` 提问），读取父 Global 实际收到的 `Worker <label> (<workerId>): ...` 文本，确认：(a) `send_message` 无需人工干预直达父级；(b) 被拒动作包含脱敏后的具体命令/目标路径与原因、不含文件正文；(c) `interaction_` 提问包含完整问题与选项文本。
  3. 验证 worker 轮次结束后 `isWorker(workerId) === true`，且 Dreaming 提炼输入不包含该 worker 会话内容。

---

### 历史问题闭环

无历史轮次（首次审查）。

---

### Issues

#### `R1-C1` [CRITICAL] `worker_state.turn_usage` 双写要求与外部 CLI worker 统计链路冲突，会导致重复计费或生成“仅有轮次统计”幽灵轮次

- **位置**：`design.md` `## 关键决策` 第 4 条（第 82 行）、`## 接口与数据流 > 契约与配置接口`（第 96 行）。
- **证据**：
  1. `packages/dsh-integration/src/local-workers/drivers.ts` 第 15、39–46 行中，`CliWorkerOptions.onEnd(id, state, text)` 不含 token 参数，`TurnEvents.end` 仅将用量交给 `WorkerTurnDetails.end` 发出 `detail`（`turn_end`）事件；`packages/dsh-integration/src/local-workers/manager.ts` 第 147–186 行的 `publishTurns`（产生 `worker_state.turn_usage`）专供不发 `detail` 明细的原生 `runtime === 'dsh'` 子会话（`nativeTurns` 第 164 行显式判断 `if (row?.runtime !== 'dsh') return;`）。
  2. `apps/im-server/src/work-records.ts` 第 407–436、470 行在处理外部 CLI worker 的 `turn_end` 事件时，`ended === true` 已将 `p.usage` 持久化到 `agent_work_turns`，并调用 `updateWorkLifetimeUsage(this.db, session, wasEnded, previousTokens, turn.usage?.total_tokens)` 更新派工关系图读取的 `agent_work_lifetime_usage`（`apps/im-server/src/work-summaries.ts` 第 221–227 行）。
- **未修后果**：若实施者按 `design.md` 第 82、96 行改动 `TurnEvents.end` 同步驱动 `LocalWorkers` 发出 `worker_state.turn_usage`：一旦 `TurnEvents.end(id, ...)` 的 `id` 与 `detail.turnId` 不同（例如现有 `claude` 驱动在 `drivers.ts:459` 传入 `message.uuid` 而 `detail.turnId` 为首条消息 `uuid`），`work-records.ts` 第 335、441–449、470 行会额外创建一条 `status: 'ended'` 的幽灵轮次（Web IM `agent-work-panel.tsx:755–756` 显示为 `"仅有轮次统计"`），并将 `ended_turns` 与 `total_tokens` 双倍计入派工图累计值（同时破坏 `claude` 既有统计）；即便 `turn_id` 相同，`worker_state` 先于 `turn_end` 到达时也会先把活跃轮次改写为 `status: 'ended'`。应移除外部 CLI 写入 `worker_state.turn_usage` 及 `TurnEvents.end` 驱动 `LocalWorkers` 累计的设计描述，保持外部 CLI 仅由 `turn_end.payload.usage` 单一路径驱动单轮展示与累计统计。

#### `R1-C2` [CRITICAL] 缺失 `auto` 模式时回退 `default` 无法兑现同会话续派重判契约，且 ACP `session/request_permission` 协议帧与工具识别规则不闭合

- **位置**：`design.md` `## 架构总览` 时序图（第 56–60 行）、`## 关键决策` 第 3 条（第 78 行）、`## 风险与回退` 风险 2（第 138 行），以及 `specs/gateway/tool-approval.md` `Scenario: 外部 worker 的 Auto 请求`（第 31 行）。
- **证据**：
  1. **`default` 模式死锁后续授权**：核查 T3 Code `apps/server/src/provider/acp/AntigravityAcpSupport.ts` 第 170–185、238–239 行，`agy` 的 `default` 模式对应 `approval-required`（无内置 Auto 分类器，每次写文件与执行命令均向宿主发送 `session/request_permission`）。T3 Code 能回退 `default` 是因为 T3 宿主自身持有实时审批策略与用户审批卡；而 Nano 的外部 CLI worker 宿主无状态拒绝除 `nano-parent` 外的全部审批请求，依赖 CLI 自身 Auto 模式在收到同会话后续授权 prompt 后自主放行（`codex` 固定传 `approvalsReviewer: 'auto_review'`，`claude` 在 `drivers.ts:468` 强制 `set_permission_mode('auto')`）。若 `agy` 会话不支持 `auto` 而静默留在 `default`，即便父 Global 向用户请示获批后通过原会话续派，下一轮任何编辑/命令仍会被宿主再次拒绝，直接违反 `specs/gateway/tool-approval.md` 第 31 行“后续授权或补充作为同一会话的新输入重新判定”。
  2. **ACP 权限响应结构与工具匹配**：按 ACP v1 契约及 `agy 1.5.16` 行为（见 T3 Code `AntigravityProtocol.ts:106–125, 184–188`、`AntigravityAcpSupport.ts:189–209`、`runtimeModel.ts:1270–1291`）：
     - `session/request_permission` 的 JSON-RPC `result` 必须为 `{ outcome: { outcome: 'selected', optionId } }`（从 `params.options` 查找 `kind === 'allow_once'` 或 `'reject_once'` 对应的 `optionId`）或 `{ outcome: { outcome: 'cancelled' } }`，而非 `design.md` 第 57、59、78 行写的 `selected: allow_once` / 返回 `'allow_once'`；
     - `params.toolCall` 无 `name` 字段，`agy` 直接调用 MCP 工具时在 `toolCall.title` 填入 `/^Run mcp_nano-parent_send_message\??$/`，代理调用时填入 `/^MCP Tool send_message\??$/` 且 `rawInput` 含 `ServerName === 'nano-parent' && ToolName === 'send_message'`（须同时排除 `kind === 'execute'` 及含 `CommandLine`/`command_line`/`commandLine`/`command` 字段的请求，防止命令行字符串伪造匹配）；
     - ACP 允许 `request_permission` 仅携带 `toolCallId` 而省略 `title`/`kind`/`rawInput`，必须先合并前序 `tool_call` 跟踪缓存再做白名单判定与 `actionTarget` 提取。
- **未修后果**：(a) 在不支持 `auto` 的 `agy` 版本或受限账号下，worker 静默退化为不可执行编辑/命令的死锁会话，与 `specs/gateway/tool-approval.md` 第 31 行规范冲突（应改为缺失 `auto` 或 `session/set_mode('auto')` 失败时直接报错交回父 Global 如实说明能力不足，并删去 `tool-approval.md` 第 31 行“维持默认受控模式”的冲突承诺）；(b) 按当前响应格式或未合并 `toolCallId` 实现会导致 ACP 协议报错、`nano-parent` 通信被误拒，或被拒请求向父 Global 上报空目标 `{}`。

#### `R1-W1` [WARNING] `turn_end.payload.usage` 未规定缺省字段省略与缓存未知口径，存在 Work RPC 校验失败及“缺失缓存显示为 0%”风险

- **位置**：`design.md` `## 关键决策` 第 4 条（第 81–82 行）、`## 接口与数据流 > 契约与配置接口`（第 96 行）。
- **证据**：
  1. `packages/product-contracts/src/work-event-codec.ts` 第 7、76 行对 `turn_end.payload.usage` 的所有已知字段（`context_used`、`output`、`context_window`、`total_tokens`、`cache_read_tokens`、`cache_total_input_tokens`）使用严格有限数值校验 `number`（**不接受 `null`**），且 `packages/product-contracts/src/runtime-rpc-work.ts` 第 40–41 行在 `session.work.root` 返回时对每条 `RuntimeWorkerDetail` 执行该校验。
  2. `docs/specs/im/response-metrics.md` 第 58、72–76 行与 `spec.md` 第 62 行规定“缺失值表示未知，不把缺失缓存计数当成零命中；未报告字段仍按既有规则如实显示未报告”；Web 前端 `WorkUsage`（`agent-work-presenters.tsx:177`）以 `cache_read_tokens != null && cache_total_input_tokens != null` 区分 `0 (0%)` 与 `未报告`（对比 `packages/personal-assistant/src/presentation.ts:18–20` 与 T3 Code `adapter.ts:404–417`）。
- **未修后果**：`design.md` 第 82 行要求将 6 个字段“一并写入 `turn_end.payload.usage`”并按 `cachedReadTokens ?? 0` 计算：若某轮未收到 `usage_update` 或因取消/失败缺少 `result.usage`，把缺失字段填为 `null` 会导致 `session.work.root` Zod 校验报错并阻断整个根会话的 Work 同步；把未报告的 `cachedReadTokens` 当作 `0` 写入 `cache_read_tokens` 则会让前端把“未报告”错误渲染为 `0 (0%)`。应明确：(1) `WorkUsage` 子字段仅在拿到合法非负整数时填入，未报告字段必须省略（`undefined`，严禁 `null`）；(2) 仅当本轮全部已结算 `session/prompt` 均实际返回 `cachedReadTokens` 时才写入 `cache_read_tokens` 与 `cache_total_input_tokens`；(3) steer 多请求合并时输入/输出/缓存累加，而 `context_used` / `context_window` 只取最新 `usage_update`。

#### `R1-W2` [WARNING] 未登录启动检测与 `CliProcess` 现行 stdout 解析 / 错误透传机制不兼容，且未约束宿主机浏览器拉起副作用

- **位置**：`design.md` `## 现状分析 > 可复用能力`（第 30 行）、`## 接口与数据流 > ACP 协议状态与事件映射`（第 101 行）。
- **证据**：
  1. `packages/dsh-integration/src/local-workers/cli-process.ts` 第 42–49 行对 stdout 每行直接调用 `JSON.parse(line)`，遇到非 JSON 文本立即以 `${runtime} protocol error: SyntaxError: ...` 失败退出，不会进入 `drivers.ts` 的 `onMessage`；第 93–97 行 `proc.resolve(id, result, error?: string)` 仅传入字符串消息，丢弃了 JSON-RPC `error.code`（如 `-32000`）。
  2. 对照 T3 Code `apps/server/src/provider/antigravityAuthSupport.ts`（第 27–31、55–82、167–177 行）与 `@botiverse/oar/dist/runtimes/antigravity/login-browser.js`（第 6–23 行）：`agy` 未登录时除 `session/new` / `session/resume` 返回 `-32000` 外，认证引导可能输出在 stdout 或 stderr，且一旦误调 `authenticate` 或继承宿主机 `BROWSER` 环境，可能在后台运行 Gateway 的机器桌面弹出浏览器并挂起等待交互。
- **未修后果**：若不扩展 `CliProcess`（如增加非 JSON 行前置检查/stderr 摘要识别，并在 `resolve` 保留 JSON-RPC `error.code`）且不显式禁止调用 `authenticate` / 清理 `BROWSER` 环境变量，登录失效时父 Global 只能收到不可理解的 `SyntaxError` 协议异常（违反 `spec.md` 第 44 行“收到明确失败原因并可向用户如实说明”），甚至在宿主机后台触发无人响应的浏览器授权流。

#### `R1-W3` [WARNING] ACP `tool_call` / `tool_call_update` 无标准 `name` 字段且参数流式补全被 `WorkerTurnDetails` 去重丢弃

- **位置**：`design.md` `## 接口与数据流 > ACP 协议状态与事件映射`（第 108 行）。
- **证据**：
  1. ACP v1 的 `tool_call` / `tool_call_update` 不含 `name` 字段，仅含 `toolCallId`、`title`（如 `"Run run_command"`、`"Running read_file"`）、`kind`、`rawInput`、`rawOutput` 与 `content`（见 `@botiverse/oar/dist/shared/acp/projection.js` 第 50–67 行、T3 Code `AntigravityProtocol.ts` 第 586–653 行）。
  2. `packages/dsh-integration/src/local-workers/work-details.ts` 第 29–35 行按 `[fact.type, item]` 对 `tool_start` 去重，第 70–71 行 `toolEnd` 在 `openTools.get(id) ?? name` 为空时直接早退不发 `tool_end`；`apps/im-server/src/work-records.ts` 第 510 行仅当 `tool_end` 携带 `arguments`（即 `toolEnd` 的 `options.args`）时才覆盖首帧空 `input`。同时 `agy` 原生工具参数使用 PascalCase（`CommandLine`、`Path`、`toolSummary`），而 `work-details.ts:49–50` 摘要提取仅读 `description` / `command` / `file_path`。
- **未修后果**：若仅按第 108 行“首个 `tool_callId` 触发 `toolStart`；参数随后补全时更新缓存；终态触发 `toolEnd`”实现而不从首帧 `title`/`kind` 派生非空 `tool_name`、不在 `toolEnd` 通过 `{ args: cachedArgs }` 回写补全后的参数（并适配 `agy` 摘要字段），IM Work 中工具记录会丢失真实调用参数（只剩 `{}`）甚至因缺 `name` 永久停留在 `running`，无法兑现 `spec.md` 第 58 行与 `specs/im/agent-work.md` 第 14 行要求。

#### `R1-W4` [WARNING] `@nano/product-contracts` 根入口统一导出描述与 `test_runtime_dependency_contract.py` 的前后端分包导入规则冲突

- **位置**：`design.md` `## 现状分析 > 可复用能力`（第 29 行）、`## 关键决策` 第 1 条（第 70 行）、`## 接口与数据流 > 契约与配置接口`（第 88 行）。
- **证据**：`packages/product-contracts/src/index.ts` 第 7 行已存在 `export * from './worker-runtimes.js';`。但 `tests/contract/test_runtime_dependency_contract.py` 第 13–60 行强制约束：`apps/node`、`packages/dsh-integration`、`packages/personal-assistant`、`apps/im-server` 的 `src/` **仅允许**导入根入口 `@nano/product-contracts`（禁止 `@nano/product-contracts/worker-runtimes`），而 `src/IM/frontend` 的 `src/`（含 `agent-work-api.ts`、`agent-work-panel.tsx`）**仅允许**导入子路径 `@nano/product-contracts/worker-runtimes`（禁止根入口 `@nano/product-contracts`），`packages/product-contracts` 内部（`work-event-codec.ts`）则只能用包内相对导入 `./worker-runtimes.js`。
- **未修后果**：按第 70 行“在 `@nano/product-contracts` 根入口重导出……消除 `apps/node`、`work-event-codec.ts`、……、`agent-work-panel.tsx` 的手写枚举分叉”直接编码，会让前端或后端违反 `ALLOWED` 白名单，导致里程碑必跑的 `test_runtime_dependency_contract.py` 失败。需在接口段明确各包的合法导入路径。

---

### Recommendations

- **`R1-R1`**：**显式处理 `session/prompt` 的 `stopReason === 'refusal'`**：在 `agy 1.5.x` 中，账号配额耗尽（`QUOTA_EXHAUSTED`）会以正常 JSON-RPC 结果返回 `stopReason: 'refusal'` 而非 RPC error（见 T3 Code `AntigravityTurnOutcome.ts:214–229`）。建议在 `drivers.ts` 中将 `stopReason === 'cancelled'` 映射为 `'interrupted'`、将 `stopReason === 'refusal'` 映射为 `'failed'`（而非默认归为 `'completed'`），防止父 Global 将配额耗尽误判为任务正常完成。
- **`R1-R2`**：**工具输出剔除内联 base64 图片并对超长文本做有界截断**：`agy` 的文件读取与终端工具在 `tool_call_update` 的 `content`/`rawOutput` 中可能附带 `data:image/...` / `{ type: 'image', data }` base64 块或超大输出（见 T3 Code `AntigravityProtocol.ts:250–299`）；建议写入 `WorkerTurnDetails` 前剥离内联二进制图片并对超长文本截断，避免撑爆 `workPageBytes`（`manager.ts:205`）单页上限。
- **`R1-R3`**：**旧版无 `systemPrompt.append` 降级分支隔离 Work 任务输入展示**：若保留 `design.md` 第 102 行针对不支持 `_meta.antigravity.systemPrompt.append` 旧版本的首轮提示词前缀兼容，建议仅在发往 `session/prompt` 的 wire 文本中用明确分隔符附带 `options.instructions`，而写入 `events.details.message(id, 'user', text)` 的记录仍只保留原始任务文本 `text`，避免内部角色说明混入 Web IM Work 的 `"任务输入"` 卡片。


---

### Author Resolutions

- **`R1-C1`**: `accepted` — 移除外部 CLI 写入 `worker_state.turn_usage` 及 `TurnEvents.end` 驱动 `LocalWorkers` 轮次累计的错误设计描述；在 `design.md`（`§现状分析 > 涉及范围`、`§现状分析 > 可复用能力`、`§关键决策 4`、`§接口与数据流 > 契约与配置接口`）明确外部 CLI worker 仅通过 `WorkerTurnDetails.end` 产出的 `turn_end.payload.usage` 单一路径上报统计，由 `apps/im-server/src/work-records.ts` 统一持久化单轮统计并更新 `agent_work_lifetime_usage`。
- **`R1-C2`**: `accepted` — (1) 移除缺失 `auto` 回退 `default` 的死锁分支：在 `design.md`（`§架构总览` 时序图、`§关键决策 3`、`§接口与数据流`、`§风险与回退`）明确 `session/new` 与 `session/resume` 后均须校验 `availableModes` 含 `'auto'` 且 `session/set_mode('auto')` 成功，否则关闭进程并报错交回父 Global，同时删去 `specs/gateway/tool-approval.md` `Scenario: 外部 worker 的 Auto 请求` 中冲突的括号说明；(2) 修正 `session/request_permission` 响应结构为标准 `{ outcome: { outcome: 'selected', optionId } }` / `{ outcome: { outcome: 'cancelled' } }`，并明确先合并 `toolCallId` 跟踪缓存再校验 `nano-parent` `send_message` 白名单（排除 `kind === 'execute'` 及命令行字段）与提取脱敏目标。
- **`R1-W1`**: `accepted` — 在 `design.md`（`§既有约束`、`§关键决策 4`、`§接口与数据流`）明确 `turn_end.payload.usage` 各子字段仅在取得合法非负整数时写入，未获字段一律省略（`undefined`，严禁 `null`）；`context_used` / `context_window` 仅取本轮最新有效 `usage_update`；`cache_read_tokens` 与 `cache_total_input_tokens` 仅在本轮全部已结算 `session/prompt` 均显式返回 `cachedReadTokens` 时写入，避免将未知缓存渲染为 `0 (0%)`。
- **`R1-W2`**: `accepted` — 在 `design.md`（`§可复用能力`、`§关键决策 2`、`§接口与数据流 > CliProcess 扩展`）明确为 `CliProcess` 增加 `onStdoutLine` 前置非 JSON 未登录引导识别、在 `resolve` 中保留 JSON-RPC `error.code`（识别 `-32000` 与无浏览器/未登录错误），同时清理 `BROWSER` 环境变量并禁止调用 ACP `authenticate`，防止无人值守节点弹出系统浏览器或报 `SyntaxError`。
- **`R1-W3`**: `accepted` — 在 `design.md`（`§可复用能力`、`§接口与数据流 > 流式通知、工具配对与停止`）明确按 `toolCallId` 缓存并从首帧规范化 `title` / `kind` 派生非空 `tool_name`，后续帧更新参数缓存并在 `toolEnd(..., { args: cached.args })` 回写完整参数；同时扩展 `WorkerTurnDetails.toolStart` 摘要提取兼容 `toolSummary`、`CommandLine`、`Path`。
- **`R1-W4`**: `accepted` — 核实 `packages/product-contracts/src/index.ts` 已导出 `./worker-runtimes.js`；在 `design.md`（`§既有约束`、`§关键决策 1`、`§接口与数据流 > 契约与配置接口`）按 `test_runtime_dependency_contract.py` 明确拆分包内相对导入 `./worker-runtimes.js`、后端根入口 `@nano/product-contracts` 与 Web 前端子路径 `@nano/product-contracts/worker-runtimes`。
- **`R1-R1`**: `accepted` — 在 `design.md`（`§关键决策 4`）明确将 `stopReason === 'cancelled'` 映射为 `'interrupted'`，将 `stopReason === 'refusal'` 或 `'error'` 映射为 `'failed'`。
- **`R1-R2`**: `accepted` — 在 `design.md`（`§接口与数据流 > 流式通知、工具配对与停止`）明确写入 `toolEnd` 前剥离内联 base64 图片并对超长文本做 16,000 字符有界截断。
- **`R1-R3`**: `accepted` — 在 `design.md`（`§接口与数据流 > 握手与会话建立`）明确旧版无 `systemPrompt.append` 降级拼接仅作用于首条发往 wire 的 `session/prompt` 文本，`events.details.message` 仍只记录纯净原始任务文本。


---

## Round 2

### Metadata

- **reviewer**: `change-design-reviewer`（独立审查子会话 `1302b5ca-e950-48e6-89fe-7a9d22d865b0`，并入 `agent-context-review` 设计模式）
- **target**: `docs/changes/feat-788-agy-worker-runtime/`（本轮修订 `design.md`、`specs/gateway/tool-approval.md` 及 `design-review.md` Round 1 `Author Resolutions`；`spec.md`、`specs/gateway/global-agent.md`、`specs/im/agent-work.md`、`M1-antigravity-worker/.gitkeep` 未变）
- **review_mode**: `delta`
- **mode_reason**: 本轮仅围绕 Round 1 提出的 6 项问题与 3 项建议对 `design.md` 内部接口/ACP 协议映射及 `specs/gateway/tool-approval.md` 单一条款做有界修订；需求范围（`spec.md`）、跨包职责边界、其余两个 delta-spec、无原型/无一次性迁移判断与单 milestone 结构均未改变，且由同一独立 reviewer 连续复审。
- **retained_from**: `Round 1`（`spec.md` 全部用户场景与非目标、`apps/node` 配置注入入口、PA 会话删除与长期记忆隔离链路、`specs/gateway/global-agent.md` 与 `specs/im/agent-work.md` 增量、原型边界与无部署迁移结论均未发生变动，沿用 Round 1 已核实证据）
- **started_at**: `2026-11-25T17:50:25+09:00`
- **completed_at**: `2026-11-25T17:52:55+09:00`
- **duration**: `2m30s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING / 0 Recommendation`

---

### Coverage 与证据（Delta 变化与波及范围）

1. **单路径轮次统计与既有 CLI 兼容性（波及 `work-details.ts`、`drivers.ts`、`work-event-codec.ts`、`work-records.ts`）**：
   - `design.md`（第 13、15、32、87–90、108–109 行）已彻底移除外部 CLI 写 `worker_state.turn_usage` 及改动 `LocalWorkers` 轮次累计的要求，明确外部 CLI 仅经 `WorkerTurnDetails.end` 输出 `turn_end.payload.usage`，由 `apps/im-server/src/work-records.ts`（第 407–436、470 行）落库单轮详情并驱动 `updateWorkLifetimeUsage`。
   - 核查波及影响：`TurnEvents.end` 保持 `onEnd(id, state, text)` 签名不变，`codex` / `claude` 继续传入 `number | null` 映射为 `{ total_tokens }` 或省略 `usage`，无回归风险；`antigravity` 传入 `WorkUsage` 时过滤 `undefined` 键且严禁 `null`，即使中途取消/失败仅收到 `usage_update`（缺 `output`/`total_tokens`）或仅收到 `result.usage`（缺 `context_used`），均能合法通过 `work-event-codec.ts:76` 有限数值校验并在前端 `WorkUsage`（`agent-work-presenters.tsx:174–177`）安全回退显示，缺失 `cachedReadTokens` 亦不会伪造为 `0 (0%)`。
2. **强制 `auto` 模式、ACP 权限帧与 `tool-approval` delta-spec 闭合（波及 `drivers.ts`、`specs/gateway/tool-approval.md`）**：
   - `design.md`（第 53、57–61、78–83、124、157 行）已要求 `session/new` 与 `session/resume` 后均校验 `availableModes` 含 `'auto'` 且 `session/set_mode({ sessionId, modeId: 'auto' })` 成功，否则关闭进程并报错交回父 Global；`specs/gateway/tool-approval.md`（第 31 行）同步移除了“（目标会话未开放原生 Auto 时维持默认受控模式）”的自相矛盾条款，与“后续授权或补充作为同一会话的新输入重新判定”及 `codex`/`claude` 行为完全一致。
   - `session/request_permission` 响应结构已修正为标准 `{ outcome: { outcome: 'selected', optionId } }`（按 `option.kind` 从 `params.options` 查找 `optionId`）与 `{ outcome: { outcome: 'cancelled' } }`，并规定先按 `toolCallId` 合并前序 `tool_call` / `tool_call_update` 缓存后再执行 `nano-parent` `send_message` 白名单校验（排除 `kind === 'execute'` 及命令行字段）与 PascalCase `actionTarget` 脱敏提取。
3. **`CliProcess` 扩展、工具流式配对与跨包导入边界（波及 `cli-process.ts`、`work-details.ts`、各包导入与 `M1` 退出标准）**：
   - `cli-process.ts`（`design.md` 第 31、75、113–120、156 行）新增 `env` 覆盖/删除、`JSON.parse` 前置 `onStdoutLine` 未登录引导拦截、`resolve` 结构化错误 `code` 保留及退出后 `onCleanup` 钩子，同时剔除 `BROWSER` 且绝不调用 `authenticate`，与初始化异常兜底清理形成闭环。
   - `tool_call` / `tool_call_update`（`design.md` 第 32、127 行）已规定首帧从 `name`/`toolName`/规范化 `title`/`kind` 派生非空 `tool_name`、后续帧刷新参数缓存、终态剥离内联 base64 图片并截断超长文本后通过 `toolEnd(..., { args: cached.args })` 回写完整参数，同时扩展 `WorkerTurnDetails.toolStart` 兼容 `toolSummary`、`CommandLine`、`Path`；`stopReason === 'refusal'` / `'error'` 显式映射为 `'failed'`（第 86 行）。
   - 跨包导入路径（`design.md` 第 21、71、102–105 行）逐项核对 `tests/contract/test_runtime_dependency_contract.py` 第 13–60 行 `ALLOWED` 表：`packages/product-contracts` 内部相对导入 `./worker-runtimes.js`、后端四包根入口 `@nano/product-contracts`、Web 前端子路径 `@nano/product-contracts/worker-runtimes` 全部命中允许集合。
4. **Agent Context 复核（`agent-context-review` 设计模式 delta）**：
   - Round 1 标记为 `CONFIRMED` 的两项设计缺口（缺 `toolCallId` 缓存合并导致父 Global 收到空被拒目标 `{}`、未登录或无 `auto` 时父 Global 收到不可理解错误/陷入 `default` 死锁）及 `PLAUSIBLE` 降级拼接污染（现已隔离 wire 拼接与 `events.details.message` 展示记录，`design.md` 第 121 行）均已在方案层消除。
   - Round 1 第 7 节列出的 3 项**实现后必查观察点**已纳入 `design.md` `§本次审查安排`（第 144 行）与 `M1-antigravity-worker` `[worker]` 退出标准（第 178 行），交由实施取证与代码审查阶段核验真实运行帧。

---

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|
| `R1-C1` | `accepted` — 移除外部 CLI 写 `worker_state.turn_usage` 与 `TurnEvents.end` 驱动 `LocalWorkers` 轮次累计，保持 `turn_end.payload.usage` 单路径统计 | `design.md` 第 13、15、32、87、108–109 行已改为仅经 `WorkerTurnDetails.end` 写 `turn_end.payload.usage`，`onEnd(id, state, text)` 不变 | `closed` |
| `R1-C2` | `accepted` — 强制校验并启用 `'auto'` 模式（失败报错终止），删去 `tool-approval.md` 冲突括号，修正 ACP `request_permission` `{ outcome }` 响应与 `toolCallId` 缓存合并 | `design.md` 第 53、57–61、78–83、124、157 行及 `specs/gateway/tool-approval.md` 第 31 行已全部对齐且无死锁分支 | `closed` |
| `R1-W1` | `accepted` — 明确 `WorkUsage` 子字段仅写合法非负整数、缺省一律 `undefined`（禁 `null`），`context_*` 取最新 `usage_update`，`cache_*` 仅在全部已结算请求均返回 `cachedReadTokens` 时写入 | `design.md` 第 24、87–90、108 行与 `work-event-codec.ts:76`、`response-metrics.md:58`、`agent-work-presenters.tsx:174–177` 完全闭合 | `closed` |
| `R1-W2` | `accepted` — 扩展 `CliProcess` 支持 `onStdoutLine`、保留 JSON-RPC `error.code`、剔除 `BROWSER` 且禁调 `authenticate` | `design.md` 第 31、75、113–120 行已覆盖非 JSON 未登录引导与 `-32000` 归一化，避免 `SyntaxError` 与桌面弹窗 | `closed` |
| `R1-W3` | `accepted` — 首帧规范化 `title`/`kind` 派生非空 `tool_name`，终态以 `toolEnd(..., { args: cached.args })` 回写完整参数并兼容 PascalCase 摘要字段 | `design.md` 第 32、127 行与 `work-details.ts:47–85`、`work-records.ts:510` 契约完全匹配 | `closed` |
| `R1-W4` | `accepted` — 按 `test_runtime_dependency_contract.py` 拆分包内相对导入、后端根入口与前端子路径导入 | `design.md` 第 21、71、102–105 行与 `test_runtime_dependency_contract.py:13–60` 白名单逐包一致 | `closed` |

（注：Round 1 可选建议 `R1-R1`、`R1-R2`、`R1-R3` 作者亦已采纳并落实于 `design.md` 第 86、121、127 行。）

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

无。
