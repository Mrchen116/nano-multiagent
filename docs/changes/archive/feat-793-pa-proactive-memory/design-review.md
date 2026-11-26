# Design Review: feat-793-pa-proactive-memory

## Round 1

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, conversation `d85edea3-c3b3-433c-8aca-d852fe0a162f`)
- **target**: `feat-793-pa-proactive-memory` (`spec.md`, `design.md`, `specs/gateway/agent-capabilities.md`, `specs/gateway/personal-agent.md`, `specs/im/task-graphs.md`, `milestones/M1/.gitkeep`; branch `unit/feat-793-pa-proactive-memory @ 57acb80b0`)
- **review_mode**: `full`
- **mode_reason**: Round 1 首次独立设计审查，完整核查生产组装入口、需求覆盖、Q1–Q6 用户约束、Agent Context 消费与缓存生命周期、3 份 delta-spec 锚定与既有场景保留，以及 M1 范围与退出标准。
- **started_at**: `2026-11-26T18:14:00+09:00`
- **completed_at**: `2026-11-26T18:34:30+09:00`
- **duration**: `20m 30s`

### Verdict

- **Status**: **Issues Found**
- **Counts**: `2 CRITICAL / 3 WARNING / 2 Recommendations`

### Coverage 与证据

#### 1. 生产组装与现状断言核实

已从真实运行组装入口逐文件核实 `design.md` 的现状描述：

- **`apps/im-server/src/{task-notifications.ts,task-graphs.ts,messaging.ts,personal-agent.ts,task-context-access.ts}`**：确认现行 `taskNotices`（`task-notifications.ts:33-38`）仅在 `done`/`in_review` 时将 `n.created_by` 加入 `attention`，对 `proposed` 节点被人类改为 `closed`/`backlog`/`todo`/`doing`（当 `assignee` 为主人或未分配时）确实遗漏 `created_by`，且未输出 `previous_status`；同时核实出 `persistTaskNotice`（`messaging.ts:684-689`）会同步触发 WebSocket `enqueueRelays` 与 `task_context_index` 双写，进而暴露出 **R1-C1**（实时 `relay.message` 抢先写入 `review_state='pending'` 阻塞梦前预取）与 **R1-W1**（PA 自清理旧 `proposed` 卡产生伪负反馈）。
- **`apps/node/src/main.ts` & `packages/personal-assistant/src/{global-agent.ts,task-context.ts,inbox.ts,inbox-review.ts,proactive-coordinator.ts,tool-references.ts}`**：确认 `ToolReferences.result`（`tool-references.ts:542`）对 `memory.sources.refresh` 透传原值不破坏字段，但核实出 `apps/node/src/main.ts:528, 552` 中 `GlobalAgent` 与 `TaskContext` 分离构造且 `GlobalAgent` 并不持有共享 `TaskContext` 实例（**R1-C2**）。
- **`packages/dsh-integration/src/{index.ts,task-context.ts,personal-agent-defaults.ts,knowledge/*}`**：确认 `memory-source-view.ts:17` 与 `memory-sources.ts:106` 当前确实过滤了 `channel: 'task-context'`；确认 `index.ts:1422-1439` 已在 `proactive_nightly` 中通过 `updatedEntrySinceWindowStart` 注入尾部 `<updated-formal-memory>`，无需拼装第二份常驻文件；确认 `MemoryDocuments` 已引入 `mdast-util-from-markdown`（`memory-documents.ts:7`）且 `dreaming-agent.ts:141-172` 具备 3 次同会话修复与 `rollbackBatch` 闭环，同时核实出纯 `pendingTaskContext` 批次下的 `cutoff`/轨迹规则问题（**R1-W2**）与 `Dreaming` 观察池可见性/防串层/链接协议白名单漏口（**R1-W3**）。

#### 2. 用户约束与需求覆盖核对（`spec.md` Q1–Q6 及 5 项 Requirement）

| 约束 / 目标 | 设计响应与核查结论 |
| --- | --- |
| **Q1**：四处回流断点必改 + 三条归因护栏 | 覆盖方向完整，但漏点 B-1（白天纯点卡无后续聊天 → 凌晨拉取）在真实节点 `GlobalAgent.receive` + `apps/node/src/main.ts` 组装下存在阻塞性断路（**R1-C1**、**R1-C2**），且漏了排除 PA 自身夜间清理 `proposed` 卡（`actor.type === 'agent'`）的伪负反馈（**R1-W1**）。 |
| **Q2 / Q3**：`MEMORY.md` 固定四分栏常驻（无 `@路径` 展开）+ `knowledge/proactivity-signals.md` 物理隔离、满 `>= 2` 次晋升与显式直通 | 双层结构清晰合理；`## 主动性与介入偏好` 置于 `MEMORY.md` 顶部可天然受益于 `memoryEntryPreview` 顺序保留；但超期孤立样本自动清理缺少 `Dreaming` 首轮可见入口，且前台 PA 缺少 `DocumentMemory` 工具层读拦截与里程碑文件落点（**R1-W3**）。 |
| **Q4**：从 `unit/feat-785-pa-proactivity` 分叉并合回 | 已核实当前 worktree 分支自 `3499b08b6`（`unit/feat-785-pa-proactivity`）分叉，基线 `docs/specs/*` 已对齐 `feat-785`。 |
| **Q5**：不加白天主动性专属 `notes` 补丁、不阻塞主对话，跨硬换窗通用衔接归 `#557` | 严格遵守：未向 `notes` 增加主动性补丁，未引入阻塞式记忆更新。 |
| **Q6**：落盘后结构骨架、防串层、观察池容量/条数、相对死链与一级目录门禁 | 将 `consolidationIssues()` 与空闲轮询 `repositoryIssues()` 解耦的决策正确，避免存量旧 `MEMORY.md` 无增量空唤醒；需补齐列表格式约定与合法链接协议/URL 解码细节（**R1-W3**）。 |
| **原型与一次性部署迁移检查** | 本单元不新增或改动前端页面布局与交互流程，无需 `prototype.html`；无 SQLite/Git 底层格式变更，存量工作区随下次正常 `Dreaming` 整合原地补齐章节，无需 `deployment-prompt.md`。 |

#### 3. 架构判断（职责、依赖方向与能力复用）

- **跨包红线合规**：Markdown AST 解析（`mdast-util-from-markdown`）、`Dreaming` 提示词与记忆仓校验留在 `packages/dsh-integration`；任务通知归 `apps/im-server`；任务上下文同步归 `packages/personal-assistant`，符合 `AGENTS.md` 与 `SPEC.md` 依赖方向。
- **能力复用得当**：直接复用 `dreaming-agent.ts` 既有 3 次同会话修复 + `rollbackBatch` 以及 `proactive_nightly` 的 `<updated-formal-memory>` 注入，未引入多余的独立审查子 Agent、动态 `@路径` 模板引擎或第二套持久化存储。
- **待收口职责边界**：`TaskContext` 在节点进程中是拥有串行游标锁（`syncing`）的单例协调者，不能由 `GlobalAgent` 隐式分叉或留空；应在 `apps/node/src/main.ts` 明确单一实例接线（见 **R1-C2**）。

#### 4. Agent Context Review（设计模式专项）

- **Review Mode & Scope**：`design` 模式；范围涵盖 `unit/feat-793-pa-proactive-memory` 中受影响的 3 类模型消费者（PA 主会话及 fork 子执行、`Dreaming` Stage 1 提炼者、`Dreaming` Stage 2 整合者）。
- **Consumer 逐链判断**：
  1. **PA 主会话（日常对话 / 群观察唤醒 / `proactive_review` / `proactive_nightly`）**：
     - **缓存稳定性**：`MEMORY.md` 维持每上下文窗口首轮快照（`nano-document-memory-entry`），不在窗口中途改写 system prompt 或首轮快照前缀；当夜 `Dreaming` 更新后的最新四档偏好仅在 `proactive_nightly` 的尾部 user message `<updated-formal-memory>` 注入，KV Cache 前缀稳定。
     - **发现的问题（CONFIRMED 设计缺口）**：① `document-memory.ts`（持有 `nano_document_memory` 常驻指引与 `.nanoassistant/memory` 文件工具守卫）未列入 M1 修改范围，前台 PA 调用 `read("knowledge/proactivity-signals.md")` 未在工具钩子层拦截，且未提示忽略 `glob/grep` 中命中的 `proactivity-signals.md`（见 **R1-W3**）；② `specs/gateway/personal-agent.md` 将日常观察群正向主动提醒与 `<proactive-review-wake>` 静默记账混在同一 Scenario，易造成提示词指令冲突（见 **R1-W3**）。
  2. **`Dreaming` Stage 1（任务提炼者）**：
     - 升级 `extractionPrompt` 保留 PA 子任务中用户对主动跟进、候选提议与汇报时机的明确表态及原始适用范围，避免被通用编码历史规则过滤，方向合理。
  3. **`Dreaming` Stage 2（记忆整合者）**：
     - **发现的问题（CONFIRMED 设计缺口）**：① 当 `proactivity-signals.md` 已存在且含超 21 天孤立样本、而当晚仅有普通对话时，首轮输入既无文件目录也无 `proactivity-signals.md` 内容（且 `MEMORY.md` 严禁链接它），模型无从感知需执行超期清理，且未约束每条观察项必须使用顶层列表项以匹配 AST `<= 20` 条门禁（见 **R1-W3**）；② 未在通知与整合护栏中排除 `actor.type === 'agent'` 的 PA 自清理事件（见 **R1-W1**）。
- **Stage 4 实施后必查运行证据交接**：
  1. 读取隔离栈真实 LLM 请求日志中 PA 主会话的 `system` + 首轮快照（确认含四档常驻专区、不含 `proactivity-signals.md` 且换窗前前缀字节不变）及 `proactive_nightly` 请求中的 `<updated-formal-memory>`；
  2. 读取 `Dreaming` 整合会话首轮 user message 原文，核实纯点卡场景下的 `## Unconsumed task context updates`（含 `previous_status: "proposed"` 与真实 `actor`）、已入主会话后的 `[task context]` 标签及次夜 `integratedTaskContextIds` 去重跳过效果；
  3. 核实门禁故意违规单测/集成运行中 `dreaming-git-status` 自愈反馈正文与 3 次失败后的 Git `HEAD` 回滚结果。

#### 5. Delta-spec 与 Milestone 核查

- **Canonical Target 锚定与计数**：3 份 delta-spec 分别对应 `docs/specs/gateway/agent-capabilities.md`、`docs/specs/gateway/personal-agent.md`、`docs/specs/im/task-graphs.md`，均为 `MODIFIED Requirements`，不增减各包 `Canonical Areas` Requirement 数量，既有适用 Scenario 均已保留。
- **需修订的契约与范围偏差**：
  - `specs/gateway/agent-capabilities.md:78` 将无新增来源触发整合的条件收窄为「物理未提交或非 Markdown 问题」，误排除了既有的缺失/超长 `MEMORY.md` 触发（见 **R1-W2**）；
  - `specs/gateway/personal-agent.md:12-13` 在同一 Scenario 内混写观察群正向提醒与 `proactive_review` 静默限制（见 **R1-W3**）；
  - `specs/im/task-graphs.md:38-40` 要求删除 `proposed` 卡也在元数据保留原状态，但 `design.md:81` 未覆盖删除分支（见 **R1-W1**）；
  - `design.md` 的「涉及范围」与 M1 范围遗漏 `apps/node/src/main.ts`（**R1-C2**）与 `packages/dsh-integration/src/knowledge/document-memory.ts`（**R1-W3**）。
- **审查安排充分性**：`design.md`「本次审查安排」覆盖了 `change-code-review`、`agent-context-review`（设计+实施）与逻辑时钟隔离栈真实 LLM 跨天闭环验证，与本单元风险面匹配。

### 历史问题闭环

首次审查（Round 1），无历史遗留问题。

### Issues

#### `R1-C1` [CRITICAL] PA 实时 `relay.message` 将任务系统通知置入 `review_state='pending'`（`review_due_at=null`），导致白天纯点卡无聊天时凌晨 `peekPendingForDreaming` 恒返回空集

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L14（「涉及范围」）、L115-117（「2. 任务上下文进入 Dreaming 与跨夜精确一次去重」）
  - 关联实现：`apps/im-server/src/messaging.ts:684-689`、`apps/im-server/src/personal-agent.ts:145-163`、`packages/personal-assistant/src/global-agent.ts:179-182, 414-445`、`packages/personal-assistant/src/inbox.ts:305-318, 615-625`、`packages/personal-assistant/src/inbox-review.ts:32-35, 89-99`
- **证据**：
  1. 主人在任务面板对 PA 私人会话（或 PA 参与群）内的 `proposed` 卡点击「不采纳 / 先存着 / 批准开工」时，`persistTaskNotice`（`messaging.ts:684-689`）插入 `sender_type: "system"` 消息，同时执行 `enqueueRelays`（PA 在自身私人会话有写权限，属于 `relayAgents`）并写入 `task_context_index`。
  2. 节点实时收到 `relay.message` 进入 `globalProduct.receive`（`global-agent.ts:179-182`），以 `personal_unclassified: true` 写入 `inbox`，`reviews.initialize` 将该 `(agent_id, message_id)` 设为 `review_state = 'pending'`。
  3. 随后 `ingestAdmitted` 调用 `pa.source.admit` → `sourceFacts`（`personal-agent.ts:145, 161`）：因 `message.sender_type === 'system'` 而非 `'user'`，即使操作人是主人且位于主人专属私聊，`is_owner` 仍返回 `false`、`delivery` 返回 `'participant'`。
  4. `global-agent.ts:422-445` 进入非主人 `participant` 待审分支，因 `isTaskNotice === true` 计算 `dueAt = null`，调用 `inbox.stagePersonal(input, false, null)` 后直接 `return`；由于 `review_due_at IS NULL`，`armBackground()` 不会调度任何后台送审。
  5. 当天无后续聊天消息触发 `flushPendingReviews` 时，凌晨 `03:00` 按 `design.md:115` 执行 `peekPendingForDreaming`：`await this.sync(agentId)` 中的 `inbox.receive(item.input, false)` 因 `UNIQUE(agent_id, message_id)` 命中 `INSERT OR IGNORE`，`reviews.initialize` 因 `WHERE review_state IS NULL` 空转，行状态仍停留在 `review_state = 'pending'`；随后 `inbox.prepareSystemContext`（`inbox.ts:616, 624`）查询 `WHERE ... AND review_state = 'admitted'`，**恒返回 `[]`**。
- **未修后果**：
  在脱离 `GlobalAgent.receive` 的孤立 `TaskContext` 单测中看似通过，但在真实 IM + Node 运行栈中，`spec.md` Q1 漏点 B-1 及核心验收场景「纯点击不采纳且无后续聊天消息时夜间整理准确捕获负反馈」100% 漏采失效。设计须明确打通 `task_graph` 系统通知的准入状态（例如对主人专属私聊或服务端已鉴权主人触发的受控 `task_graph` 通知直接 `admitTrusted`，并在 `peekPendingForDreaming` / `TaskContext.prepare` 前确保共享参与群内待审任务通知完成准入结算或同步对账）。

#### `R1-C2` [CRITICAL] 生产组装入口 `apps/node/src/main.ts` 缺失，`GlobalAgent` 在真实节点中未接线共享 `TaskContext` 实例

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L14（「涉及范围」）、L116（「2.2 未入主会话的纯点击梦前预取」）、L206（「Milestones M1」）
  - 关联实现：`apps/node/src/main.ts:528, 552-567`、`packages/personal-assistant/src/global-agent.ts:17-30, 859-862`、`packages/personal-assistant/src/task-context.ts:13, 20-27`
- **证据**：
  1. `design.md:116` 规定 `GlobalAgent.execute` 在处理 `memory.sources.refresh` 时调用 `this.taskContext.peekPendingForDreaming(personalConfig.agentId)`，但「涉及范围」与 M1 文件范围均未包含 `apps/node/src/main.ts`。
  2. 在真实节点入口 `apps/node/src/main.ts` 中，`globalProduct = new GlobalAgent({... relay: external ...})`（L528）先于 `const taskContext = new TaskContext({... relay, refreshSources: agentId => globalProduct.prepareSystemContext(agentId) })`（L552）创建，两者存在反向回调依赖，`GlobalAgent` 现行 `Options` 中根本没有 `taskContext`。
  3. 若实现者将 `GlobalAgent` 的 `taskContext` 设为可选依赖以兼容现有数十处单测且不改 `apps/node/src/main.ts`，生产环境中预取将静默失效；若在 `GlobalAgent` 内部私自新建第二个 `TaskContext`，则会绕开 `main.ts` 主 `taskContext` 的 `syncing` 串行锁（`task-context.ts:13`）并混用 `external` relay，导致与主会话 `product.task_context.prepare` 并发竞争推进 `task_context_cursors`。
  4. 同时 `TaskContext.sync` 内部首行已调用 `refreshSources(agentId)`（即 `globalProduct.prepareSystemContext` → `refreshPersonalSources`，`task-context.ts:26`），而 `Dreaming.verifyCurrent`（`dreaming.ts:513`）在每批整合收尾时也会调用 `memory.sources.refresh`；若不加区分，每次整合会产生重复的 `pa.sources` 与无消费用途的收尾 `task.context.sync` 往返。
- **未修后果**：
  按当前设计范围实施会导致真实生产节点漏装 `peekPendingForDreaming` 或破坏 `TaskContext` 游标串行不变量。需将 `apps/node/src/main.ts` 纳入设计与 M1 范围，明确单一 `TaskContext` 实例的接线方式（如注入 `peekPendingTaskContext` 回调或在 `main.ts` 的 `product.call` 路由层组合），并区分首轮预取刷新与 `verifyCurrent` 资格复核（避免双重 `refreshPersonalSources`）。

#### `R1-W1` [WARNING] PA 夜间自清理旧 `proposed` 卡（`actor.type === 'agent'`）会被误标为「未采纳（已关闭）」回流污染观察池，且删除 `proposed` 卡遗漏 `metadata.previous_status`

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L77-83（「1. 任务面板反馈通知与原状态保留」）、L159（归因护栏 ③）
  - `docs/changes/feat-793-pa-proactive-memory/specs/im/task-graphs.md`：L37-40
  - 关联实现：`apps/im-server/src/task-notifications.ts:24-38, 62-66`、`apps/im-server/src/task-graphs.ts:758-762`、`apps/im-server/src/messaging.ts:684-689`、`packages/personal-assistant/src/proactive-coordinator.ts:109`
- **证据**：
  1. `proactive_nightly`（`proactive-coordinator.ts:109` 与 `nano-proactive-care/SKILL.md:27`）要求 PA 每晚先将已解决或过时的旧 `proposed` 卡置为 `closed`。此时 `task-graphs.ts:758-759` 以 `actor = { kind: 'agent', id: paAgentId }` 生成通知并通过 `persistTaskNotice`（`messaging.ts:687-688`）将 `attention_actor_ids` 写入 `task_context_index`。按 `design.md:79-82` 无条件规则，PA 自己的过期清理不仅会在用户聊天流展示误导性的「个人助手：[卡片]，未采纳（已关闭）」，还会写入 PA 自身的 `task_context_index` 并在次夜进入 `Dreaming`；而 `design.md:159` 护栏 ③ 仅凭 `previous_status: "proposed"` 识别负反馈，未要求核验 `actor.type === 'user'`（人类裁决）。
  2. `specs/im/task-graphs.md:38-40` 规定人类将 `proposed` 卡改状态**或直接删除**时均在元数据中保留原 `proposed` 状态，但 `design.md:81` 仅在「状态变化时」补充 `previous_status`，遗漏了 `!n` 删除分支。
- **未修后果**：
  PA 按规清理两张已过时/已解决的 `proposed` 卡就会自我制造 2 次“未采纳”负反馈，将本该正常跟进的长线事项误封入 `MEMORY.md` 免打扰禁区；删除 `proposed` 卡的元数据也会违反 `im/task-graphs` delta-spec。应在 `task-notifications.ts` / `task-graphs.ts` 区分人类裁决与 Agent 自身操作（Agent 自关旧提议不标为「未采纳」且无需向自身回灌提议裁决通知，同时删除节点时补齐 `previous_status: old.status`），并在 `dreaming-prompts.ts` 明确仅人类/主人（`actor.type === 'user'`）的操作计入主动性反馈。

#### `R1-W2` [WARNING] 纯 `pendingTaskContext` 批次的时间截点（`cutoff`）、`MemorySources` 历史轨迹过滤及 `agent-capabilities` 空源触发条款存在契约冲突

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L113、L117
  - `docs/changes/feat-793-pa-proactive-memory/specs/gateway/agent-capabilities.md`：L78、L89
  - 关联实现：`packages/dsh-integration/src/knowledge/dreaming.ts:355-373`、`packages/dsh-integration/src/knowledge/memory-sources.ts:66, 104-110, 158-161`、`packages/dsh-integration/src/knowledge/dreaming-history.ts:20-27, 120-129`、`packages/personal-assistant/src/global-agent.ts:924-926`
- **证据**：
  1. 当白天无新主会话步骤（`batch.units` 为空）、仅由 `pendingTaskContext` 启动整合时，`memory-sources.ts:159-160` 计算的 `batch.cutoffs[rootId]` 停留在旧根步骤时间（若启用后尚无根步骤则为 `0`）。`dreaming-history.ts:125-126` 将该 `cutoff` 传给 `memory.conversations`：若 `cutoff < owner.activationAt` 会在 `global-agent.ts:925`（`afterTime > cutoff`）直接抛错；即便存在旧步骤，`cutoff` 也早于当日点卡的 `event_time`，使 `Dreaming` 无法在获准窗口内用 `conversations` 核查点卡上下文。此外在 `dreaming.ts:360-364` 容量缩减循环中，若 `!current.batch.units.length` 会直接抛错退出，未考虑纯 `pendingTaskContext` 批次的预算度量与有界裁剪。
  2. `design.md:113` 要求 `MemorySources.freeze`「当遇到 `isTaskContext(source)` 且其会话仍在允许列表时」才选入，但 `MemorySources.freeze` 不持有会话 `allowed` 集合，且同批 `specs/gateway/agent-capabilities.md:89` 明确规定「已经记录的执行轨迹不按会话来源删改」（会话 `allowed` 过滤应仅作用于未消费的 `pendingTaskContext` 与实时 IM `conversations` 查询，保持与 `dreaming-history.ts:89` `qualifiedEvents` 一致）。
  3. `specs/gateway/agent-capabilities.md:78` 将 canonical L1082 的「正式仓的问题也能触发整合」改写收窄为「正式仓的物理未提交或非 Markdown 问题也能触发整合」，排除了 `repositoryIssues()` 现行覆盖且有测试保障的「已提交状态下的 `MEMORY.md` 缺失或超 8,000 码元」修复触发。
- **未修后果**：
  纯点卡批次调用 `conversations` 时报错或时间窗截断、`MemorySources` 与 `source_history` 轨迹视图不一致，且 delta-spec 误删既有 `MEMORY.md` 缺失/超长自动触发保证。

#### `R1-W3` [WARNING] `Dreaming` 首轮输入未呈现 `proactivity-signals.md` 现状导致「超期样本自动清理」不可达，且前台防串层、观察池格式与死链门禁存在漏口

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L142-147、L150-160、L206
  - `docs/changes/feat-793-pa-proactive-memory/spec.md`：L207-210、L240-244
  - `docs/changes/feat-793-pa-proactive-memory/specs/gateway/personal-agent.md`：L10-13
  - 关联实现：`packages/dsh-integration/src/knowledge/dreaming.ts:468-487`、`packages/dsh-integration/src/knowledge/document-memory.ts:75-82, 123-135`
- **证据**：
  1. **超期清理上下文不可见 & 20 条门禁计数绕过**：`Dreaming.renderInput`（`dreaming.ts:468-487`）仅内联 `MEMORY.md`，不展示记忆仓文件列表，而 `MEMORY.md` 又严禁引用 `knowledge/proactivity-signals.md`。当观察池中存在超 21 天的孤立单次样本、而当晚仅有普通业务对话（无新点卡信号且条数 `<= 20`）时，`Dreaming` 首轮上下文没有任何线索表明 `proactivity-signals.md` 存在待清理项，无法稳定兑现 `spec.md:207-210` 的超期自动清理场景（在 PA `Dreaming.renderInput` 中当 `knowledge/proactivity-signals.md` 存在时附带其当前内容或元数据即可确定性闭环，且计入首轮预算测量）。同时 `consolidationIssues()` 基于 AST 统计顶层列表项 `<= 20`（`design.md:144`），须在提示词与校验中同步约束每条待观察类别必须以单个顶层列表项表达（禁止用无列表的 `###` 段落堆叠绕过条数上限）。
  2. **前台 PA 物理隔离漏口与 `personal-agent` Scenario 混写**：`document-memory.ts`（负责向 PA 注入 `nano_document_memory` 指引及拦截 `.nanoassistant/memory` 文件工具）未列入 M1 范围（`design.md:206`），且 `document-memory.ts:123-135` 的 `tools/execute` 钩子未拒绝前台 PA 直接 `read("knowledge/proactivity-signals.md")`（也未在 `nano_document_memory` 中说明不在日常检索中读取/采信该观察池文件）。此外，`specs/gateway/personal-agent.md:12-13` 在 `<proactive-review-wake>` 轻量记账 Scenario 中混入了日常观察群的正向主动盯梢提醒，与下一句「非免打扰时段仅在发现约一小时内紧急冲突时可简短提醒一句，其余情况保持聊天静默」互相掣肘，应区分日常对话/观察轮的正向提醒与 `<proactive-review-wake>` 静默记账轮的职责。
  3. **相对链接校验白名单过窄与编码处理缺失（`design.md:146`）**：`consolidationIssues()` 仅跳过 `http:`/`https:`/`mailto:`、`#anchor` 与 `/tasks/...`，未豁免任务图已合法支持的受保护附件路径 `/im/v1/...`（见 `apps/im-server/src/task-graphs.ts:161`）及其他外部 URI scheme（通用 `/^[a-zA-Z][a-zA-Z0-9+.-]*:/`），且未对相对路径执行安全 `decodeURIComponent`（LLM 生成百分号编码中文 `.md` 链接时会误判为死链触发回滚）。
- **未修后果**：
  孤立单次反馈超期不退场或绕过 20 条上限；前台 PA 可通过 `read` 直接读取未收敛的 `seen=1` 样本破坏抗噪隔离；合法 `/im/v1/...` 附件引用或编码中文链接导致整批记忆被误判回滚。

### Recommendations

- **`R1-R1`**（可选）：`packages/dsh-integration/src/knowledge/dreaming-agent.ts:169-171` 的 3 次修复反馈文案目前仅围绕物理 Git 与恢复常规 `MEMORY.md` 措辞。接入 `consolidationIssues()` 后，建议将导语泛化为「物理、结构骨架与链接检查」，让模型在遇到非法子标题、观察池超限或相对死链时能直接聚焦 `{ path, reason }` 修复并重新提交。
- **`R1-R2`**（可选）：`packages/personal-assistant/src/proactive-coordinator.ts:232` 默认按 `22:00–08:00` 计算 `quietHours` 属性。建议在 `renderProactiveReviewWake` 与 `renderProactiveNightlyWake` 文本中点明：当 `MEMORY.md` 的「触达时机与汇总方式」记录了主人自定义的安静时段或早报窗口时，优先遵守 `MEMORY.md` 中的个性化时间边界。

### Author Resolutions

- **`R1-C1`**: `accepted` — 在 `apps/im-server/src/personal-agent.ts`（`sourceFacts`）中对服务端已鉴权确认由主人本人触发（`sender_type === 'system'`, 无外部 `sender_source_id`, `sender_user_id === owner_user_id`, `system_notice.kind === 'task_graph'`, `actor.type === 'user' && actor.id === owner_user_id`）的任务系统通知返回受信 `is_owner: true`（受 `!representedBy` 约束），使其经实时 `relay.message` 到达节点 `GlobalAgent` 时直接 `admitTrusted` 进入 `review_state = 'admitted'`；同时在 `TaskContext.peekPendingForDreaming` 中对共享参与群内待审任务通知先结算准入批次。已更新 `design.md`（§涉及范围、§关键决策 3、§接口与数据流 1.2 & 2、§Milestones M1）与 `specs/im/task-graphs.md`。
- **`R1-C2`**: `accepted` — 将 `apps/node/src/main.ts`（及 `packages/dsh-integration/src/evaluation.ts`）明确纳入 `design.md`「涉及范围」与 M1 文件范围，通过 `globalProduct.attachTaskContext(taskContext)` 共享全进程唯一 `TaskContext` 实例及其串行 `syncing` 锁；`peekPendingForDreaming` 直接复用 `TaskContext.sync` 内部的单次 `refreshSources`（避免重复 `pa.sources`），且 `Dreaming` 仅在批次首轮传 `includePendingTaskContext: true`、在 `verifyCurrent` 收尾复核传 `false`（避免无消费用途的收尾 `task.context.sync`）。已更新 `design.md`（§涉及范围、§可复用能力、§接口与数据流 2.1、§Milestones M1）。
- **`R1-W1`**: `accepted` — 在 `taskNotices`（`apps/im-server/src/task-notifications.ts` & `task-graphs.ts`）中全分支（含 `!n` 删除）输出 `previous_status`，并区分人类裁决与创建该提议卡的 Agent 自身操作（`actor.kind === 'agent' && actor.id === created_by.id` 时输出中性 `'过期提议已收起（已关闭）'` 且不向自身追加提议裁决回流）；同步在 `dreaming-prompts.ts` 护栏 ③ 写死仅采信 `actor.type === 'user'` 的人类反馈。已更新 `design.md`（§接口与数据流 1.1 & 4）与 `specs/im/task-graphs.md`、`specs/gateway/agent-capabilities.md`、`specs/gateway/personal-agent.md`。
- **`R1-W2`**: `accepted` — 1) 纯 `pendingTaskContext` 批次将 `batch.cutoffs[parent.id]` 推进至 `Math.max(既有 cutoff, owner.activationAt, ...selectedPending.timeMs)` 并支持首轮超容量按条分片；2) 修正 `design.md` 对 `MemorySources.freeze` 的描述，保持“已记录在主会话中的轨迹不按实时会话允许列表删改”（仅按 `excludeTaskContextIds` 跨夜去重，实时 `allowed` 过滤仅用于未消费预取与 `conversations` 实时查询）；3) 恢复 `specs/gateway/agent-capabilities.md` 中“正式仓的问题（含缺失或超长的 `MEMORY.md`）也能在无新增来源时触发整合”的完整保证。已更新 `design.md`（§接口与数据流 2.2）与 `specs/gateway/agent-capabilities.md`。
- **`R1-W3`**: `accepted` — 1) 在 PA `Dreaming.renderInput` 中当 `knowledge/proactivity-signals.md` 存在时直接内联其当前正文（计入首轮预算）以确保普通夜晚可清理超 21 天孤立样本，并在 `consolidationIssues()` 强制要求待观察信号使用顶层列表项（禁止子标题/散文块绕过 `<= 20` 条上限）；2) 将 `document-memory.ts` 纳入 M1 范围，在 `tools/execute` 钩子拒绝非维护会话 `read("knowledge/proactivity-signals.md")`；3) 在 `specs/gateway/personal-agent.md` 将日常对话/观察的正向主动校准提升至 Requirement 级，与 `proactive_review` 纯静默记账 Scenario 解耦；4) 在 `consolidationIssues()` 相对死链检查中放行通用外部协议 scheme、`/tasks/...` 与 `/im/v1/...` 路由并对相对路径执行安全 `decodeURIComponent`。已更新 `design.md`（§涉及范围、§关键决策 2、§接口与数据流 3 & 4、§Milestones M1）与 `specs/gateway/{agent-capabilities,personal-agent}.md`。
- **`R1-R1`**: `accepted` — 已纳入 `design.md` §接口与数据流 3.4，更新 `dreaming-agent.ts` 修复提示文案以覆盖物理、结构骨架、容量与链接检查。
- **`R1-R2`**: `accepted` — 已纳入 `design.md` §涉及范围与 §接口与数据流 4 及 `specs/gateway/personal-agent.md`，在主动唤醒提示中明确 `MEMORY.md` 个性化安静时段优先于默认 `22:00–08:00`。


## Round 2

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, conversation `d85edea3-c3b3-433c-8aca-d852fe0a162f`)
- **target**: `feat-793-pa-proactive-memory` (`spec.md`, `design.md`, `specs/gateway/agent-capabilities.md`, `specs/gateway/personal-agent.md`, `specs/im/task-graphs.md`, `milestones/M1/.gitkeep`; branch `unit/feat-793-pa-proactive-memory @ 57acb80b0`)
- **review_mode**: `delta`
- **retained_from**: `Round 1`
- **mode_reason**: `spec.md`、整体双层记忆架构、Q2/Q4/Q5 边界、主会话窗口级快照与 `<updated-formal-memory>` 缓存前缀机制均未改变（沿用 Round 1 结论）；Round 2 针对 `R1-C1..R1-W3` 与 `R1-R1..R1-R2` 修改了 `design.md`、3 份 delta-spec 与 M1 文件范围，需聚焦核查全部历史问题闭环及新增改动在 `apps/im-server/src/personal-agent.ts`、节点/评测组装与 `TaskContext` 边界上的波及影响。
- **started_at**: `2026-11-26T18:44:17+09:00`
- **completed_at**: `2026-11-26T18:51:30+09:00`
- **duration**: `7m 13s`

### Verdict

- **Status**: **Issues Found**
- **Counts**: `1 CRITICAL / 1 WARNING / 0 Recommendations`

### Coverage 与证据

#### 1. 增量变更与波及面核查（`retained_from: Round 1`）

沿用 Round 1 已核实的未变更部分（`spec.md` 5 项 Requirement 与 Q1–Q6 约束定义、`unit/feat-785-pa-proactivity` 分叉基线、无需 `prototype.html` 与 `deployment-prompt.md`、窗口级 `MEMORY.md` 快照 KV Cache 稳定性及既有未改动 Scenario），本轮重点顺着 Round 2 新增改动追查了真实代码波及面：

- **`apps/im-server/src/personal-agent.ts`（波及链核查）**：逐行核查 `sourceFacts`（L138-164）下游全部调用方——`admitSource`（L259-267）、`directOwnerMessage`（L171-175）、`ownerMessage`（L345-349）、`sources`（L86）、`handle('pa.agent.creation')`（L471）、`messageEvidence` / `compactMessageEvidence`（L184-215）、`authorization`（L366-380）与 `incident`（L409-412）。确认将 `sender_type === 'system'` 的任务通知直接标为 `sourceFacts().is_owner = true` 虽打通了 `admitTrusted`，但因 `directOwnerMessage` 未校验 `message.sender_type === 'user'` 而连带击穿了 `ownerMessage` 人类原话授权门禁及共享群非主人任务标题的输入审核边界（新增 **`R2-C1`**）。
- **`apps/im-server/src/{task-notifications.ts,task-graphs.ts}`**：确认全分支（含 `!n` 删除）输出 `previous_status`、区分人类裁决与创建者 Agent 自身过期收起（`actor?.kind === 'agent' && actor.id === (n ?? old).created_by?.id`），以及 `dreaming-prompts.ts` 仅采信 `actor.type === "user"` 的护栏闭环成立。
- **`apps/node/src/main.ts`、`evals/memory/nano-product.ts`、`packages/dsh-integration/src/evaluation.ts` 与 `packages/personal-assistant/src/{global-agent.ts,task-context.ts}`**：确认 `main.ts` 单例 `TaskContext` 共享接线与首轮/收尾 `includePendingTaskContext` 区分消除了双重 `pa.sources` 与并发游标竞争；但核实 `packages/dsh-integration/src/evaluation.ts`（L1-243）并不组装 `GlobalAgent`/`TaskContext`（真实评测产品组装位于 `evals/memory/nano-product.ts:46-51`，且 `dsh-integration` 受架构红线约束严禁依赖 `personal-assistant`），同时 `TaskContext` 自身不持有 `GlobalAgent.flushPendingReviews` 与 `allowed` 会话集合（新增 **`R2-W1`**）。
- **`packages/dsh-integration/src/knowledge/*` 与 3 份 delta-spec**：确认纯 `pendingTaskContext` 批次 `cutoff` 推进与按条分片、`MemorySources` 已记录轨迹不按实时会话允许列表删改、`repositoryIssues()` 恢复缺失/超长 `MEMORY.md` 触发、`Dreaming.renderInput` 内联 `proactivity-signals.md`、`DocumentMemory` 工具守卫拒读观察池、`consolidationIssues()` 顶层列表与 URI 解码/`/im/v1/` 白名单、以及 `personal-agent.md` 正向校准与静默记账解耦均已准确收敛。

#### 2. Agent Context Review（Round 2 增量核查）

- **已关闭的 Context 缺口**：
  1. `Dreaming` Stage 2 首轮在 `proactivity-signals.md` 存在时内联其全文（计入 `capacity.measure` 预算），普通对话夜晚可确定性识别并清理超 21 天孤立样本；
  2. `DocumentMemory` 在 `tools/execute` 层硬拒绝前台/子执行 `read("knowledge/proactivity-signals.md")` 并在 `nano_document_memory` 明示禁读，物理隔离成立；
  3. PA 自清理 `proposed` 卡在通知源头与 `Dreaming` 护栏双重排除，不再产生自激伪负反馈；
  4. `specs/gateway/personal-agent.md` 已将日常对话/观察正向提醒与 `<proactive-review-wake>` 静默记账拆清，并明示 `MEMORY.md` 个性化安静时段优先。
- **新引入的 Context 与安全边界回归（见 `R2-C1`）**：
  - 在共享参与群中，非主人成员创建的任务标题可包含任意不可信指令文本；当主人在面板点击关闭该任务时，`sourceFacts` 返回 `is_owner: true` 会使 `GlobalAgent` 跳过 `pa.review` 输入审核直接入库，且在 `messageEvidence` / `authorization` 会话上下文中将该系统消息标为 `sender.is_owner: true`，把非主人拟定的标题包装成受信主人上下文。

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核查证据与结论 | 状态 |
| --- | --- | --- | --- |
| `R1-C1` | `accepted`：在 `personal-agent.ts` `sourceFacts` 对主人触发的 `task_graph` 通知返回 `is_owner: true` 走 `admitTrusted`，并在 `peekPendingForDreaming` 结算共享群待审批次 | 原「白天纯点卡滞留 `review_state='pending'` 导致凌晨预取恒空」断路已打通（`design.md:84-85, 117`）；但直接在 `sourceFacts` 复用 `is_owner: true` 连带击穿了 `directOwnerMessage`/`ownerMessage` 人类原话鉴权与共享群不可信任务标题审核，已单列为新问题 **`R2-C1`** 追踪收口。 | `closed`（新引入副作用见 `R2-C1`） |
| `R1-C2` | `accepted`：将 `apps/node/src/main.ts` 纳入范围共享唯一 `TaskContext`，区分首轮 `includePendingTaskContext: true` 与 `verifyCurrent` `false` | 已核实 `design.md:14, 32, 115-120, 210`：真实节点共享同一 `TaskContext` `syncing` 锁，消除重复 `pa.sources` 与无消费用途的收尾 `task.context.sync`（评测组装路径误写与内部回调边界单列为 **`R2-W1`**）。 | `closed` |
| `R1-W1` | `accepted`：`taskNotices` 全分支（含删除）保留 `previous_status`，区分创建者 Agent 自关与人类裁决，`dreaming-prompts.ts` 限定 `actor.type === 'user'` | 已核实 `design.md:77-82, 163`、`specs/im/task-graphs.md:13, 15, 37-40`、`specs/gateway/agent-capabilities.md:32`：删除分支与 Agent 自清理回环均已闭环。 | `closed` |
| `R1-W2` | `accepted`：推进纯预取批次 `cutoff` 并支持超限分片；保持已记录轨迹不按实时 `allowed` 删改；恢复 `repositoryIssues()` 缺失/超长 `MEMORY.md` 触发 | 已核实 `design.md:122-128` 与 `specs/gateway/agent-capabilities.md:78, 92`：与 `dreaming-history.ts` / `global-agent.ts:925` 时间窗契约及 canonical 空源修复语义完全一致。 | `closed` |
| `R1-W3` | `accepted`：`Dreaming.renderInput` 内联现有观察池、强制顶层列表项；`DocumentMemory` 拒前台 `read`；解耦 `personal-agent` 正向提醒与静默记账；补齐链接协议/`/im/v1/`/URI 解码 | 已核实 `design.md:134-150, 210`、`specs/gateway/agent-capabilities.md:11, 64, 83`、`specs/gateway/personal-agent.md:7, 9-13`：四项子缺口全部闭环。 | `closed` |
| `R1-R1` | `accepted`：泛化 `dreaming-agent.ts` 修复提示文案 | 已纳入 `design.md:30, 139`。 | `closed` |
| `R1-R2` | `accepted`：主动唤醒明示 `MEMORY.md` 个性化安静时段优先 | 已纳入 `design.md:17, 160` 与 `specs/gateway/personal-agent.md:12`。 | `closed` |

### Issues

#### `R2-C1` [CRITICAL] 在 `sourceFacts` 中对 `sender_type === 'system'` 任务通知返回 `is_owner: true` 会击穿 `directOwnerMessage` / `ownerMessage` 人类原话授权门禁，并在共享群跳过对他人任务标题的输入审核

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L13、L68-69、L83-85
  - `docs/changes/feat-793-pa-proactive-memory/specs/im/task-graphs.md`：L40
  - 关联实现：`apps/im-server/src/personal-agent.ts:86, 145-146, 171-175, 187, 202, 345-349, 375, 411, 471`、`packages/personal-assistant/src/global-agent.ts:422-448`
- **证据**：
  1. **系统消息冒充真人原话通过高权限工具鉴权**：`PersonalAgentService.directOwnerMessage`（`apps/im-server/src/personal-agent.ts:171-175`）并未检查 `message.sender_type === 'user'`，仅判断 `!this.representedBy(message.id) && facts.is_owner && facts.delivery === 'participant' && (facts.conversation_type === 'direct' && this.ownerConversation(...) || facts.conversation_type === 'group' && facts.addressed_to_agent)`（因为现行 L145 保证 `is_owner === true` 必有 `sender_type === 'user'`，且 `authorizationGuard` L359 与 `authorization` L368 也均限定 `sender_type = 'user'`）。而 `ownerMessage(b, args.source_message_id)`（L345-349）以 `directOwnerMessage` 作为 `pa.sources`（修改会话排除/纳入策略，L86）与 `pa.agent.creation`（创建新 Agent，L471）的**唯一真人指令来源校验**。一旦按 `design.md:84` 对 `sender_type === 'system'` 返回 `is_owner: true`，主人在私聊（`ownerConversation === true`）或共享群中对提及 PA 的任务卡（`addressed_to_agent === true`）点击一次状态按钮，生成的被动系统通知 `message_id` 即可作为合法 `source_message_id` 通过 `ownerMessage` 校验，直接违反 `docs/specs/gateway/agent-capabilities.md:39-47`（「系统来源不成为真人同意」）与 `specs/im/task-graphs.md:16, 45`（「不借通知扩大任何主体访问权限」）。
  2. **共享参与群中非主人拟定的任务标题绕过 `pa.review` 且禁绝安全上报**：在多人共享参与群（`conversation_type === 'group'`）中，任何外部/群成员均可创建含提示词注入 `title` 的任务，而 `taskNotices` 会将该 `title` 拼入系统消息 `content`。当主人点击关闭该卡时（`actor.id === owner_user_id`），`sourceFacts` 返回 `is_owner: true` 会使：(a) `GlobalAgent.ingestAdmitted`（`global-agent.ts:422, 447`）跳过 `pa.review` 直接 `admitTrusted`；(b) `messageEvidence`（`personal-agent.ts:187, 202, 375`）在授权上下文中将其标为 `sender: { type: 'system', is_owner: true }`；(c) `incident()`（`personal-agent.ts:411`）因 `this.sourceFacts(b, source).is_owner === true` 直接返回 `404 incident_source_not_accessible`，连事后安全上报都被阻断。
- **未修后果**：
  被动任务状态系统通知可被用作 `pa.sources` / `pa.agent.creation` 的真人原话授权凭证，且共享群内他人构造的任务标题可借主人点击「关闭」绕过 PA 输入安全审核并伪装成 `is_owner: true` 消息。收敛方式非常直接：① 保持 `sourceFacts().is_owner` 仅对 `message.sender_type === 'user'` 为真（并在 `directOwnerMessage` 显式守卫 `message.sender_type === 'user'`），不污染 `ownerMessage`、`incident` 与 `sender.is_owner`；② 单独通过专用字段（如 `admitSource` 返回 `trusted_task_notice: true` → `GlobalAgent` `personal_trusted_task_notice`）仅对**主人专属私聊 `ownerConversation`**（或任务 `created_by` 亦为主人/PA 本身、无第三方文本注入）的主人点卡通知走 `admitTrusted`，而共享参与群涉及他人任务卡的通知继续保持待审并由 `peekPendingForDreaming` 第 1 步 `flushReviews` 正常过审结算；同步收紧 `specs/im/task-graphs.md:40` 括号表述避免要求系统消息直接等同 `is_owner` 真人原话事实。

#### `R2-W1` [WARNING] 评测宿主单例 `TaskContext` 接线文件路径误指 `packages/dsh-integration/src/evaluation.ts`（触碰跨包依赖边界），且 `TaskContext.peekPendingForDreaming` 缺少来自 `GlobalAgent` 的待审结算与 `allowed` 回调契约

- **位置**：
  - `docs/changes/feat-793-pa-proactive-memory/design.md`：L14、L115-119、L210
  - 关联实现：`packages/dsh-integration/src/evaluation.ts:1-60`、`evals/memory/nano-product.ts:46-52`、`packages/dsh-integration/tests/fixtures/evaluation.ts:66-70`、`packages/personal-assistant/src/task-context.ts:7-15`、`packages/personal-assistant/src/global-agent.ts:605-625, 859-862`
- **证据**：
  1. `design.md:14, 115, 210` 将评测侧 `globalProduct.attachTaskContext(taskContext)` 的改动落点写为 `packages/dsh-integration/src/evaluation.ts`。经核对源码，`packages/dsh-integration/src/evaluation.ts` 仅通过外部注入的 `NanoEvaluationOptions['createProduct']` 驱动评测，并不持有 `GlobalAgent` 或 `TaskContext`（且按 `AGENTS.md` 与 `test_runtime_dependency_contract.py`，`packages/dsh-integration` 严禁依赖 `@nano/personal-assistant`）；真实构造 `new GlobalAgent(...)` 与 `new TaskContext(...)` 的评测组装入口位于 `evals/memory/nano-product.ts:46-51`（此外 `packages/dsh-integration/tests/fixtures/evaluation.ts:68` 中 PA `Dreaming` 假模型写回 `# Personal memory` 时未含 `## 主动性与介入偏好`，接入 `consolidationIssues()` 后需同步更新该测试夹具）。
  2. `design.md:116-119` 将第 1 步「触发 `flushReviews` 完成共享群待审任务通知结算」与第 3 步「读取当前允许会话集合 `allowed`」均写在 `TaskContext.peekPendingForDreaming(agentId)` 内部，但 `TaskContext`（`packages/personal-assistant/src/task-context.ts:7-10`）当前仅持有 `{ store, inbox, runtime, relay, refreshSources: (agentId) => Promise<void> }`，既无 `GlobalAgent.flushPendingReviews` 也无 `PersonalAssistant` 允许会话列表（`global-agent.ts:615` `refreshPersonalSources` 当前返回 `void`）。
- **未修后果**：
  M1 实施者按里程碑范围文件表操作时无法在 `packages/dsh-integration/src/evaluation.ts` 完成 `attachTaskContext` 接线（强行引入还会破坏跨包依赖契约测试），且 `evals/memory/nano-product.ts` 会漏接单例 `TaskContext`；同时 `TaskContext` 与 `GlobalAgent` 之间的待审结算/`allowed` 集合传递若无明确接口约定易产生职责倒置。需将 `design.md` L14/L115/L210 中的评测组装文件更正为 `evals/memory/nano-product.ts`（及 `packages/dsh-integration/tests/fixtures/evaluation.ts` 测试夹具），并明确由 `GlobalAgent` 在调用 `taskContext.peekPendingForDreaming` 前（或通过扩展 `refreshSources` 返回值/注入回调）完成待审 `flushPendingReviews` 并传入当前 `allowed` 会话集合。

### Recommendations

无新增可选项。

### Author Resolutions

- **`R2-C1`**: `accepted` — 保持 `PersonalAgentService.sourceFacts().is_owner` 严格仅对 `message.sender_type === 'user'` 为真，并在 `directOwnerMessage` 显式校验 `message.sender_type === 'user'`，杜绝被动系统消息冒充 `ownerMessage`（`pa.sources` / `pa.agent.creation`）真人授权凭证或污染 `messageEvidence` / `incident`；新增独立字段 `trusted_owner_task_notice`（映射为 `personal_trusted_task_notice`），仅在**主人专属私聊 `ownerConversation`** 内由主人本人触发的受控 `task_graph` 通知上走 `admitTrusted`，而共享参与群中可能含第三方拟定标题的任务通知保持待审并由 `GlobalAgent.flushPendingReviews` 经 `pa.review` 正常过审结算。已更新 `design.md`（§涉及范围、§关键决策 3、§接口与数据流 1.2 & 2、§Milestones M1）与 `specs/im/task-graphs.md`。
- **`R2-W1`**: `accepted` — 将评测组装落点从 `packages/dsh-integration/src/evaluation.ts` 更正为真实组装 `GlobalAgent` 与 `TaskContext` 的 `evals/memory/nano-product.ts`（并补充 `packages/dsh-integration/tests/fixtures/evaluation.ts` 测试夹具更新，严守 `dsh-integration` 不依赖 `personal-assistant` 边界）；明确由 `GlobalAgent` 在 `memory.sources.refresh({ includePendingTaskContext: true })` 中先执行 `flushPendingReviews` 结算共享群待审项，再调用 `taskContext.peekPendingForDreaming` 并用 `refreshPersonalSources` 返回的 `allowed` 集合过滤结果。已更新 `design.md`（§涉及范围、§接口与数据流 2.1、§Milestones M1）。


## Round 3

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, conversation `d85edea3-c3b3-433c-8aca-d852fe0a162f`)
- **target**: `feat-793-pa-proactive-memory` (`spec.md`, `design.md`, `specs/gateway/agent-capabilities.md`, `specs/gateway/personal-agent.md`, `specs/im/task-graphs.md`, `milestones/M1/.gitkeep`; branch `unit/feat-793-pa-proactive-memory @ 57acb80b0`)
- **review_mode**: `closure`
- **retained_from**: `Round 1, Round 2`
- **mode_reason**: Round 3 仅针对 Round 2 剩余的 `R2-C1` 与 `R2-W1` 做局部授权边界收口与评测/组件接线消歧，未改变需求目标、双层记忆结构、KV Cache 窗口快照机制或其他 delta-spec（`agent-capabilities.md`、`personal-agent.md` 零改动），满足 `closure` 模式条件并核实了波及代码路径无新副作用。
- **started_at**: `2026-11-26T18:58:01+09:00`
- **completed_at**: `2026-11-26T19:00:15+09:00`
- **duration**: `2m 14s`

### Verdict

- **Status**: **Approved**
- **Counts**: `0 CRITICAL / 0 WARNING / 1 Recommendation`

### Coverage 与证据

围绕 `R2-C1` 与 `R2-W1` 的修订及受波及实现入口完成核实（其余未改动结论沿用 `Round 1` 与 `Round 2`）：

- **`apps/im-server/src/{personal-agent.ts,task-graphs.ts,messaging.ts}` 与 `packages/personal-assistant/src/{personal-assistant.ts,global-agent.ts}`**：
  - 核对 `task-graphs.ts:759` 与 `messaging.ts:685`：主人在 `/tasks` 面板操作时，`persistTaskNotice` 以已鉴权主人 `p.id`（即 `b.owner_user_id`）写入 `sender_user_id`、`sender_type = "system"` 及 `system_notice.actor = { type: 'user', id: actor.id }`，因此 `design.md:85` 对 `trusted_owner_task_notice: true` 的全部服务端判定条件与持久化事实完全吻合。
  - `sourceFacts().is_owner` 维持仅 `message.sender_type === 'user'` 可为真，且 `directOwnerMessage`（`personal-agent.ts:171`）显式校验 `message.sender_type === 'user'`，`ownerMessage`（`pa.sources` / `pa.agent.creation`）、`messageEvidence.sender.is_owner` 与共享群 `pa.incident`（`personal-agent.ts:411`）均不受系统消息污染。
  - 核对共享参与群路径：共享群任务通知不带 `trusted_owner_task_notice`，停留在 `review_state = 'pending'`；当 `GlobalAgent` 执行 `flushPendingReviews` → `PersonalAssistant.reviewBatchSlice`（`personal-assistant.ts:241-362`）时，`pa.input.context` + `pa.review` 正常对 `sender_type: 'system'` 消息中的第三方任务标题做安全裁决（放行则 `admitted`，注入则 `rejected` 并可正常上报 `pa.incident.report`）。
- **`apps/node/src/main.ts`、`evals/memory/nano-product.ts`、`packages/dsh-integration/tests/fixtures/evaluation.ts` 与 `TaskContext` 协作边界**：
  - M1 范围已移除 `packages/dsh-integration/src/evaluation.ts`，更正为真实组装 `GlobalAgent` + `TaskContext` 的 `evals/memory/nano-product.ts:46-51` 及测试夹具 `packages/dsh-integration/tests/fixtures/evaluation.ts:68`，严格满足 `AGENTS.md` 与 `test_runtime_dependency_contract.py` 跨包依赖边界。
  - `GlobalAgent` 先结算 `flushPendingReviews`、再调用 `taskContext.peekPendingForDreaming` 并用 `refreshPersonalSources` 返回的最新 `allowed` 集合过滤，职责顺向闭合、无重复 `pa.sources` 请求。
- **Agent Context Review 收口结论**：`R2-C1` 涉及的共享群第三方标题免审与 `sender.is_owner` 伪装风险已彻底消除；设计模式下的 Context 审查结论通过，Stage 4 实施后按 Round 1 §4 交接清单核验真实 LLM 请求日志与落盘证据即可。

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核查证据与结论 | 状态 |
| --- | --- | --- | --- |
| `R2-C1` | `accepted`：保持 `is_owner` 严格仅限 `sender_type === 'user'` 并在 `directOwnerMessage` 显式守卫；新增独立 `trusted_owner_task_notice`（`personal_trusted_task_notice`）仅对 `ownerConversation` 内的主人点卡通知走 `admitTrusted`，共享群保持 `pa.review` 审核；同步收紧 `specs/im/task-graphs.md` | 已核实 `design.md:13, 68-69, 83-86, 212`、`specs/im/task-graphs.md:40` 及关联源码 `personal-agent.ts:145, 171, 345, 411`、`task-graphs.ts:759`、`personal-assistant.ts:60-83, 241-362`、`global-agent.ts:422, 446`：人类原话授权门禁与共享群第三方标题输入审核均已严密闭环。 | `closed` |
| `R2-W1` | `accepted`：将评测组装入口更正为 `evals/memory/nano-product.ts`（并纳入 `packages/dsh-integration/tests/fixtures/evaluation.ts`），明确由 `GlobalAgent` 先执行 `flushPendingReviews` 并以 `refreshPersonalSources` 返回的 `allowed` 集合过滤 `peekPendingForDreaming` | 已核实 `design.md:14, 117-121, 212` 及 `evals/memory/nano-product.ts:46-51`、`task-context.ts:7-15`、`global-agent.ts:609-625`：文件路径、跨包依赖边界与方法职责完全对齐。 | `closed` |

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R3-R1`**（可选）：在 `packages/personal-assistant/src/personal-assistant.ts:105`（单条显式 `PersonalAssistant.admit` 分支）同步加上 `&& input.metadata.personal_trusted_task_notice !== true`，使其与 `GlobalAgent.ingestAdmitted`（`global-agent.ts:422`）及 `PersonalAssistant.source()`（`personal-assistant.ts:60`）对主人私聊任务通知的免审判定保持对称（例如节点在 `restorePersonalInputs` 重放未完成分类行时同样免走多余单条 `pa.review`）。

### Author Resolutions

- **`R3-R1`**: `accepted` — 在 M1 实现 `packages/personal-assistant/src/personal-assistant.ts`（`admit` L105）时同步加入 `&& input.metadata.personal_trusted_task_notice !== true`，保持与 `GlobalAgent.ingestAdmitted` 完全对称（无需实质改动设计文本）。

