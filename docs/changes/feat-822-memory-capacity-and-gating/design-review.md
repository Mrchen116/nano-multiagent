# Design Review: feat-822-memory-capacity-and-gating

## Round 1

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, session `a5759120-e907-4923-9619-a45d5f2e7a48`)
- **target**: `docs/changes/feat-822-memory-capacity-and-gating/{spec.md,design.md,M1-memory-capacity-and-gating/.gitkeep,specs/gateway/{agent-capabilities.md,personal-agent.md,global-agent.md}}` @ `37eb7b21653a0c2e571573ebe00f2072aa1d6bd2` (base `890d74f70`)
- **review_mode**: `full`
- **mode_reason**: Round 1 full Gate 2 review covering `spec.md`, `design.md`, all three `gateway` delta-specs, milestone `M1`, and `agent-context-review` (design mode) across affected foreground, proactive-wake, and `Dreaming` model-visible surfaces.
- **started_at**: `2026-11-28T16:16:45+09:00`
- **completed_at**: `2026-11-28T16:28:30+09:00`
- **duration**: `11m45s`

### Verdict

**Issues Found** — `0 CRITICAL / 3 WARNING` (`2 Recommendations`)

### Coverage 与证据

1. **架构边界、模块职责与既有能力复用（`AGENTS.md` / `SPEC.md`）**：
   - 核实 `packages/product-contracts/src/{knowledge.ts,configuration.ts}`、`apps/node/src/configuration.ts`、`packages/dsh-integration/src/{index.ts,agent-config.ts}` 与 `packages/personal-assistant/src/proactive-coordinator.ts`：
     - `KnowledgeConfiguration['dreaming']` 与 `DEFAULT_DREAMING_SCHEDULE` 归属 `@nano/product-contracts` 纯数据契约；`canonicalAgentConfiguration`（`packages/product-contracts/src/configuration.ts:37-49`）不纳入 `knowledge` 字段，且 `normalizeKnowledge`（`packages/product-contracts/src/knowledge.ts:33-45`）在未配置 `knowledge.dreaming` 时保持 `dreaming: undefined`，存量 Agent 配置指纹确为零漂移（实现 `normalizeKnowledge` 时须同步放行 `minSourceTokens === 0` 并校验 `maxDeferDays` 为 `>= 1` 整数，因现行第 35 行默认拒绝除 `quietMs`/`nightlyHour` 外的 `0` 值）。
     - 记忆结构护栏、文件工具守卫、尾部注入与 `Dreaming` 增量调度全部落在 `packages/dsh-integration`（唯一公开 `@deepseek-ai/*` 消费方）；`packages/personal-assistant` 仅更新唤醒提示语与随包 `SKILL.md`，无跨包反向依赖。
     - 直接复用 `MemoryDocuments.consolidationIssues` + `runDreamingAgent` 三次同会话修复与 `rollbackBatch`（`packages/dsh-integration/src/knowledge/dreaming-agent.ts:144-175`）承载主动专区 `2,000` 码元、`proactivity-policy.md` `6,000` 码元与本批触及页 `16,000` / `32,000` 码元护栏，职责单一且不引入第二套修复或写者机制。
     - 正式记忆单写者边界（前台 `write`/`edit`/`apply_patch` 经 `touchesFormalMemory` 拦截）与 `knowledge/proactivity-signals.md` 前台禁读/检索擦除守卫（`packages/dsh-integration/src/knowledge/document-memory.ts:214-261`）保持完整，而 `knowledge/proactivity-policy.md` 作为普通 `knowledge/*.md` 对前台可读、仅 `Dreaming` 可写，且仅对 `personal` 与 `global_expert` 合法（`single_thread_expert` 严格隔离）。
   - 核实 `scripts/check_platform_parity.py:165-213` 与 `scripts/docs_check.py`：本单元为纯后端运行时与提示词改动，无需 UI 原型（`prototype.html`）或一次性部署迁移（`deployment-prompt.md`）；《五端对齐矩阵》声明四客户端 `platform-exempt`、`Node` `shared` 与 `packages/product-contracts/src/knowledge.ts` 触发规则完全匹配，`./scripts/docs-check` 当前通过。

2. **需求覆盖与关键设计决定核对（`spec.md` 4 项 Requirement）**：
   - **Req 1（首页主动专区配额与主动细则分层）**：`MEMORY.md` `## 主动性与介入偏好` `<= 2,000` UTF-16 码元 + `knowledge/proactivity-policy.md` `<= 6,000` 码元 + 被动业务 SOP 归回 `Topics`/`knowledge/`/`entities/` 覆盖需求，但主动唤醒尾部注入在同窗多次 `proactive_review` 下存在未去重的上下文累积缺陷（见 `R1-W1`）。
   - **Req 2（二级主题页容量护栏与当前态维护）**：`topicPageLimit = 16000`（`entities/`、`knowledge/` 除两份专用小文件外、`workstreams/`、`projects/`）与 `historyPageLimit = 32000`（`timeline/`、`work-history/`）仅在 `consolidationIssues(beforeVersions)` 对变更页生效（无参调用全检），`repositoryIssues()`（`memory-documents.ts:275-301`）不检查二级页长度，确保存量超长旧档空闲夜零空转、无关批次零阻塞。
   - **Req 3（去防御性无权限免责套话）**：同时覆盖 `dreaming-prompts.ts` Stage 1 提炼（`buildExtractionPrompt`）与 Stage 2 整合（`consolidationPrompt`，含移除第 102/122 行“禁止裁剪主动专区”及重写第 155 行易被模型抄入正文的免责句式）以及 `nano-memory/SKILL.md`，同时保留 `document-memory.ts:141` 前台固定系统提示与 `NanoApproval` 实际权限检查不降级。
   - **Req 4（自动夜间巩固最小有效增量门禁与最长延后兜底）**：拆分 `lastCompletedCycle` 与 `lastConsolidatedCycle` 以兼顾游标保留、`Dreaming.tick` 止转及 `nightlyStatus.completed === true` 放行 `proactive_nightly` 的方向合理，但 `task-context` 人类信号判定、空闲多日后 `lastConsolidatedCycle` 推进、Global 模式 `send_message` 实质回复计量以及评测运行时对 `deferred_below_min_volume` 的兼容存在未闭合缺口（见 `R1-W2`、`R1-W3`）。

3. **Agent Context Review（设计模式 — 受影响模型输入面与观察交接）**：
   - **Consumer 1 & 2（前台主会话日常轮 + `proactive_review` / `proactive_nightly` 唤醒轮）**：
     - 前缀稳定性：不改写 `systemPrompt`、`nano-document-memory`、`nano-document-memory-entry`、`nano-role-agreement` 或工具 schema，满足 `NoSilentPrefixRewrite`。
     - 窗口内生命周期缺陷：由于 `packages/dsh-integration/src/index.ts:1515-1534` 通过 `agent.followup(message)` 将主动唤醒写入持久主会话事件流，该消息会一直留在当前上下文窗口的 `agent.session.deriveMessages()` 中，直至发生换窗压缩；若每次 `proactive_review`（每静默 12 分钟可触发一次）都无条件重复注入 `<proactive-policy>` 与相对窗口首轮变化的 `<updated-formal-memory>`，同一窗口内的日常对话与后续唤醒都会背负多份完全相同的全文副本（见 `R1-W1`）。
     - 权限与安全语义：`proactive_review` / `proactive_nightly` 的 `source.kind === 'nano-system'` 在 `NanoApproval` 与 `pa.review` 中均不具备真人授权资格（`isHumanSource === false`），内联 `<proactive-policy>` 不会扩大外发或工具审批权限。
   - **Consumer 3 & 4（`Dreaming` 整合与子任务提炼会话）**：
     - 首轮组装：在 `dreaming.ts:571-583` 除 `MEMORY.md` 与 `proactivity-signals.md` 外同步内联已存在的 `knowledge/proactivity-policy.md`，并纳入 `dreaming.ts:431-456` 的 70% 首轮测量裁剪闭环，避免模型未读先覆写既有主动细则；修复回路需在 `dreaming-agent.ts:113,173` 同步透出新配额说明以保证 3 次自愈提示与校验一致。
   - **实施阶段需交回 Stage 4 审查观察的运行输入与行为**：
     1) 主会话同一上下文窗口内连续触发多次 `proactive_review` + 穿插普通对话 + 跨夜 `proactive_nightly` 的实际 `llm/stream` `messages` 原件，核实 `system` 与首轮 `runtime-context` 前缀字节级不变，且未发生变化的 `<updated-formal-memory>` / `<proactive-policy>` 不在同一窗口重复追加；
     2) `Dreaming` 触发主动专区超 `2,000` 码元或主题页超 `16,000` 码元时的真实修复轮次输入与最终提交文件；
     3) DolphinBench Morgan 前缀真实模型运行产出的 `MEMORY.md`、`knowledge/proactivity-policy.md`、二级主题页体积分布、正文是否消除“不代表发送/预订/付款授权”类套话，以及低增量日 `deferred_below_min_volume` 与跨天合并的实际轨迹。

4. **契约层增量（delta-spec）与 Milestone 核对**：
   - `specs/gateway/agent-capabilities.md` 锚定 `docs/specs/gateway/agent-capabilities.md` 的 3 条既有 Requirement，完整保留其下全部既有 Scenario（3 + 3 + 11 个 Scenario 无遗漏），并更新了原第 1076 行与 `2,000` 码元上限冲突的旧表述；第 30 行关于 `maxDeferDays` 触发条件需随 `R1-W2` 收紧为“存在待整理合格增量且达到最长延后天数上限”。
   - `specs/gateway/personal-agent.md` 与 `specs/gateway/global-agent.md` 均准确锚定各自唯一目标 Requirement 并保留全部 4 个既有 Scenario，尾部按需附带规则需随 `R1-W1` 同步明确“仅附带当前上下文窗口尚未见过的更新版本”。
   - Milestone `M1` 为单里程碑串行范围，需补充评测适配落点与 `feat-806` 基线前置说明（见 `R1-W3`）。

### 历史问题闭环

首轮审查，无历史问题。

### Issues

- **`R1-W1` [WARNING] — 同一上下文窗口内多次 `proactive_review` 会向持久主会话重复追加相同的 `<proactive-policy>` 与 `<updated-formal-memory>`，污染后续日常对话上下文**
  - **位置**：
    - `docs/changes/feat-822-memory-capacity-and-gating/design.md`（第 15、21、70–71、91–92 行）
    - `docs/changes/feat-822-memory-capacity-and-gating/specs/gateway/personal-agent.md`（第 14、21 行）
    - `docs/changes/feat-822-memory-capacity-and-gating/specs/gateway/global-agent.md`（第 14、20 行）
  - **证据**：
    - `packages/dsh-integration/src/index.ts:1515-1534` 将主动唤醒构造为 `UserMessage` 并通过 `agent.followup(message)` 持久写入主会话；该消息在当前上下文窗口内会一直保留在 `agent.session.deriveMessages()` 中，被后续**所有日常用户对话轮次**与后续主动唤醒轮次共同携带，直至换窗压缩（`compact-checkpoint`）。
    - 与每晚最多一次的 `proactive_nightly` 不同，`proactive_review` 在每次对话或观察活动静默 12 分钟后即可触发（`packages/personal-assistant/src/proactive-coordinator.ts:13,253-260`），单个跨天大窗口内可触发十余次。
    - 当前 `DocumentMemory.updatedEntrySinceWindowStart`（`packages/dsh-integration/src/knowledge/document-memory.ts:344-354`）仅对比窗口首轮 `savedEntry(agent)` 快照，且 `design.md` 规定“当窗口启动后 `MEMORY.md` 有更新时附带 `<updated-formal-memory>`、当存在 `knowledge/proactivity-policy.md` 时附带 `<proactive-policy>`”。一旦某晚 `Dreaming` 更新了 `MEMORY.md`（最高 `8,000` 码元）且存在 `proactivity-policy.md`（最高 `6,000` 码元），次日同一窗口内的每一次 `proactive_review` 都会把完全相同的最高 `14,000` 码元全文再次追加进会话历史。
  - **未修后果**：
    - 违背 `spec.md` Scenario 1（“日常普通对话不额外膨胀”）及 `docs/specs/gateway/agent-capabilities.md:1153`（“普通输入和内部对象重建不重复追加无变化信息”），在高频分段对话日向主会话窗口堆积数万至十余万字符的重复策略/记忆副本，挤占有效上下文窗口、稀释近期对话注意力并提前触发压缩换窗。
  - **修订方向**：
    - 在 `DocumentMemory` 中沿用 `savedEntry(agent)`（`document-memory.ts:65-70`）以最近一次 `compact-checkpoint` 为窗口边界扫描当前窗口历史：`<updated-formal-memory>` 仅在当前 `MEMORY.md` 同时异于窗口首轮 `nano-document-memory-entry` 快照**且**异于当前窗口内最近一次已注入的 `<updated-formal-memory>` 时注入；`<proactive-policy>` 仅在有效 `knowledge/proactivity-policy.md` 非空**且**异于当前窗口内最近一次已注入的 `<proactive-policy>` 时注入（同窗未变时可仅保留单行引用提示或不重复内联，换窗后自动在新窗口首次主动唤醒恢复内联），并同步更新 `design.md` 与 `personal-agent.md` / `global-agent.md` delta-spec 表述。

- **`R1-W2` [WARNING] — `Dreaming` 最小增量与延后门禁存在三处状态机与信号判定缺口（Agent 自产 `task-context` 误旁路、空闲日后 `lastConsolidatedCycle` 陈旧失灵、Global 回复 token 漏计）**
  - **位置**：
    - `docs/changes/feat-822-memory-capacity-and-gating/design.md`（第 15、78–80、110–114 行）
    - `docs/changes/feat-822-memory-capacity-and-gating/specs/gateway/agent-capabilities.md`（第 30 行）
  - **证据**：
    1. **Agent 自身 `task_graph` 记账产生的 `task-context` 会误触发“人类拍板信号”直通**：`design.md` 第 15 行将“无人类任务面板拍板事件”定义为“`selectedPending` 与批次内 `task-context` 均为空”。但核查 `apps/im-server/src/task-graphs.ts:786-792`、`apps/im-server/src/task-notifications.ts:14,26` 与 `packages/personal-assistant/src/inbox.ts:653,689` 可见，除收起/删除自身旧 `proposed` 卡外，PA 或 Global 数字员工在 `03:20` `proactive_nightly` 新建自领 `proposed` 卡或在白天 `proactive_review` 原位更新自身负责的任务节点时，`im-server` 均会生成 `actor.type === "agent"` 且 `attention_actor_ids` 含该 Agent 的 `task_graph` 通知并进入 `selectedPending` / 批次 `task-context`。若仅判空而不区分人类操作者（`actor.type === "user"` 或 `humanTaskControl`），开启 `proactive_planning` 后日常 1–2 句对话经 `proactive_review` 记账（或前夜 `03:20` 立卡）即会在次日 `03:00` 旁路 `minSourceTokens` 门禁。此外，在 `dreaming.ts:347-497` 的单周期多批 `while (true)` 循环中，门禁须限定在首批（`completed.length === 0` 且无未完结 `continuation`）评估，且延后分支须同步清零 `owner.failures` 与 `owner.retryAt`。
    2. **多日完全无消息后 `lastConsolidatedCycle` 停留在旧日期，导致回归首条短寒暄立即触发巩固**：`design.md` 第 111 行规定 `lastConsolidatedCycle` 仅在“实际执行模型整合并完成或确认**初始空库**无增量时”同步更新。当助手已完成过建档后经历 `>= 3` 天完全无新消息（每晚走 `dreaming.ts:385` `no_eligible_increment`，此时全流游标已追平、待整理积压为 `0`），`lastConsolidatedCycle` 不会推进；用户在第 4 天仅发一句 `"早"`（`< 600` tokens），当夜即因 `slotDiff >= maxDeferDays (3)` 立即跑完整 `Dreaming`，使低频用户在静默数日后的首日攒批完全失效。同时 `MemoryDocuments.open`（`memory-documents.ts:124-130`）初始化即写入并提交非空 seed `MEMORY.md`（含 `No topics saved yet.`），`design.md` 需明确“首次空白记忆建档”按角色 seed 模板且无二级页面判定，避免误按空字符串或一次性布尔位实现。
    3. **Global / PA 模式实质回复主要经 `send_message` 工具参数发出而非 `assistant/message` 文本**：`design.md` 第 113 行 `substantiveSourceTokens(units)` 仅列出“主 Agent 文本回复”，但在 Global/PA 模式（`packages/dsh-integration/src/global-mode.ts:76,80` 及 `packages/dsh-integration/src/evaluation/history.ts:96-97`）中，`assistant/message` 仅为一句话私有结语，真正的长篇分析与正式回复位于 `send_message` / `send_user_message` `tool/call` 的 `arguments.text`（及 `interactive`），且入站消息亦可能经 `read_messages`（`global-agent.md:456`）或超长分段 `source_text_continuation`（`memory-sources.ts:134`）承载。
  - **未修后果**：
    - 开启 `proactive_planning` 时低增量日仍每晚触发 `Dreaming`；低频用户隔 3 天发一句寒暄无法延后攒批；Global/PA 长回复对话被严重低估 token 量，或单周期第 2 批尾包返回 `deferred_below_min_volume` 覆盖第 1 批已完成状态。
  - **修订方向**：
    - ① 任务信号直通条件收窄为批次 `task-context` 或 `selectedPending` 中存在人类触发记录（`actor.type === "user"` 或携带 `humanTaskControl`），且增量门禁仅在自动自然日周期首批（`completed.length === 0` 且无 `continuation`）执行并重置 `failures`/`retryAt`；② 在任意 `no_eligible_increment`（无未消费积压）周期同步推进 `lastConsolidatedCycle`（或改为记录最早未消化积压槽位 `unconsolidatedSinceCycle`），并在 `specs/gateway/agent-capabilities.md:30` 明确“存在待整理合格增量且距上次无积压/完成巩固周期已满 `maxDeferDays`”，同时明确初始建档判据为记忆仓仍处于角色初始 seed 态；③ `substantiveSourceTokens` 纳入 `send_message`/`send_user_message` 文本载荷、`read_messages` 消息正文与 `source_text_continuation` 文本块。

- **`R1-W3` [WARNING] — 评测运行时与 DolphinBench 验收链路未兼容 `deferred_below_min_volume`，且 `feat-806` 基线尚未合入当前分支范围**
  - **位置**：
    - `docs/changes/feat-822-memory-capacity-and-gating/design.md`（第 15、37、47、119、147–155 行）
  - **证据**：
    1. 本仓现有 `packages/dsh-integration/src/evaluation/runtime.ts:96` 仅将 `run?.state === 'completed' || run?.reason === 'no_eligible_increment'` 视为合法自动周期结果，其余结果一律判为 `{ status: 'failed', reason: ... }`；一旦通过 `NanoMemoryCandidate` 显式传入 `minSourceTokens > 0` 验证增量延后，首个低增量夜返回 `reason: 'deferred_below_min_volume'` 即会导致准备阶段直接报错失败，且 `Milestones` M1 范围（`packages/dsh-integration/src/{index.ts,evaluation.ts,knowledge/*}`）遗漏了 `evaluation/*` 子目录。
    2. `design.md` 将“完成 DolphinBench Morgan 前缀实跑对比验证”列为 `M1` 退出标准、审查编组证据与 `Runbook for Reviewer` 驱动方式，但当前 worktree 基线 `890d74f70` 尚未包含仍在开放 PR #583（`unit/feat-806-dolphinbench-eval`）中的 `evals/dolphinbench/` 与 `packages/dsh-integration/src/evaluation/dolphinbench*.ts`；且核查 `feat-806` 的 `dolphinbench-runtime.ts:291-300` 与 `dolphinbench.ts:248`，第 298 行同样在 `run.reason === 'deferred_below_min_volume'` 时直接抛出 `Error: Dreaming failed at ...: deferred_below_min_volume`，第 291 行在延后未整理时仍错误推进 `lastConsolidationAt`，且封板 `freezeIngestion(..., finalNightMs)`（`force: true`）仍调用自动 `dreaming.tick()` 而非手动强制整理，遇到末尾不足 `600` tokens 的对话会漏刷封板记忆。
  - **未修后果**：
    - 下游实施 worker 按当前 M1 文件范围与分支基线无法执行必需的 DolphinBench Morgan 前缀对比验证，且合入 `feat-806` 后运行默认 `minSourceTokens: 600` 会在首个低增量自然日直接抛错中断。
  - **修订方向**：
    - 在 `design.md` 明确与 `feat-806`（PR #583）的基线先后/合入关系，将 `packages/dsh-integration/src/evaluation/*` 纳入 `M1` 范围：在 `evaluation/runtime.ts`（以及 `feat-806` 合入后的 `dolphinbench-runtime.ts`）中将 `reason === 'deferred_below_min_volume'` 识别为正常延后而非失败，在 `dolphinbench-runtime.ts` 中仅当实际发生巩固时更新 `lastConsolidationAt`，并让 `freezeIngestion` 的 `force: true` 收尾步走手动/无视最小增量门禁的整理以确保封板快照完整。

### Recommendations

- **`R1-R1`**：在 `DocumentMemory.proactivePolicySnapshot` 与 `Dreaming.renderInput` 读取 `knowledge/proactivity-policy.md` 时，建议比照 `MEMORY.md` / `ROLE.md` 校验真实路径归属（非符号链接）与 `<= proactivityPolicyLimit`（`6,000` 码元）上限：若磁盘文件因外部异常编辑超出上限，主动唤醒不内联超限正文，而 `Dreaming.renderInput` 仅给出路径修复提示而非内联全文，防止超限脏文件撑爆首轮 70% 输入预算。
- **`R1-R2`**：`MemoryDocuments.consolidationIssues(beforeVersions)` 判定“本批新增或修改页面”时，除对比 `manifest.versions` 外，建议将批次起始时已处于 Git 未提交状态（`start` / 初始 `gitChanges()`）的页面一并视为本批触及页，防止前序异常中断遗留的未提交超 `16,000` 码元草稿在恢复批次中未经精简即被直接 `git commit`。


### Author Resolutions

- **`R1-W1`: `accepted`** — 已修订 `design.md`（涉及范围、Context Engineering 主会话主动唤醒段与 Milestones 退出标准）及 `specs/gateway/{personal-agent,global-agent}.md`：`DocumentMemory` 提供以最近一次 `compact-checkpoint` 为当前上下文窗口边界的 `updatedEntryForWindowWake` 与 `proactivePolicyForWindowWake`，`<updated-formal-memory>` 仅在异于窗口首轮快照且异于当前窗口最近一次已内联版本时附带，`<proactive-policy>` 仅在合规非空且异于当前窗口最近一次已内联版本时附带，彻底消除高频 `proactive_review` 在同一窗口内的重复全文堆积。
- **`R1-W2`: `accepted`** — 已修订 `design.md`（涉及范围、核心数据结构与门禁计算、Milestones）与 `specs/gateway/agent-capabilities.md`：① 任务面板信号直通收窄为 `actor.type === "user"` 或携带 `human_control` 的人类操作记录，忽略 `actor.type === "agent"` 的自动记账/立卡通知，且门禁限定于自动自然日周期首批（`completed.length === 0` 且无 `continuation`）并清零 `failures`/`retryAt`；② 在任意 `no_eligible_increment`（零积压）周期同步推进 `lastConsolidatedCycle`，收紧 `maxDeferDays` 为“存在待整理合格增量且满最长延后天数”，并明确首次建档按“无二级页面且 `MEMORY.md` 含 `No topics saved yet.`”判定；③ `substantiveSourceTokens` 显式纳入 `send_message`/`send_user_message` 文本载荷、`read_messages` 消息正文与 `source_text_continuation` 块。
- **`R1-W3`: `accepted`** — 已将分支 `unit/feat-822-memory-capacity-and-gating` 直接 rebase 至 `unit/feat-806-dolphinbench-eval`（`222591463`），在 `spec.md` 声明 `Depends on: feat-806`，并将 `packages/dsh-integration/src/evaluation/*`（含 `runtime.ts` 与 `dolphinbench-runtime.ts`）纳入 `design.md` 涉及范围与 `M1` 范围：两者均把 `deferred_below_min_volume` 识别为正常延后，`dolphinbench-runtime.ts` 仅在实际完成巩固时推进 `lastConsolidationAt`，且 `freezeIngestion` 的 `force: true` 走 `dreaming.start(parent, false)` 强制排空末尾残留增量。
- **`R1-R1`: `accepted`** — 已纳入 `design.md` 与 `specs/gateway/agent-capabilities.md`：`proactivePolicyForWindowWake` 与 `Dreaming.renderInput` 均校验 `knowledge/proactivity-policy.md` 为库内非符号链接常规文件且 `<= 6,000` 码元，超限异常文件在主动唤醒中不内联、在 `Dreaming` 首轮仅输出路径修复提示。
- **`R1-R2`: `accepted`** — 已纳入 `design.md`：`consolidationIssues(beforeVersions, initialDirtyPaths)` 同时将批次起始已处于 Git 未提交状态的页面纳入本批触及页上限检查。
