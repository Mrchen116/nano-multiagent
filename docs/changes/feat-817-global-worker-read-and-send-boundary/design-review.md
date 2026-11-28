# Design Review: feat-817-global-worker-read-and-send-boundary

## Round 1

### Metadata

- **Reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, Antigravity subagent `e0375e1d-71ee-429e-9448-935be4231b7a`)
- **Review Target**: `docs/changes/feat-817-global-worker-read-and-send-boundary/` (`spec.md`, `design.md`, `specs/gateway/{spec,global-agent,agent-capabilities}.md`, `milestones/M1-worker-read-and-send-boundary/`)
- **review_mode**: `full`
- **mode_reason**: R1 首轮完整设计审查，同时加载 `agent-context-review` 设计模式审查模型可见工具面、提示词、Skill 与审批/授权来源边界。
- **started_at**: `2026-11-28T15:44:01+09:00`
- **completed_at**: `2026-11-28T15:52:00+09:00`
- **duration**: `7m59s`

### Verdict

**Issues Found** — **3 CRITICAL / 3 WARNING**（另附 **3 Recommendations**）

---

### Coverage 与证据

本轮沿实际生产装配链（`packages/dsh-integration/src/{index,agent-config,global-mode,capabilities,child-role,message-arguments}.ts`、`src/local-workers/{manager,work-details,drivers,report-bridge}.ts`、`src/policy/{approval,sources,retained-instructions,codex,cc,classifier}.ts`、`src/evaluation/runtime.ts`、`apps/node/src/capabilities.ts`、`packages/product-contracts/src/capabilities.ts`、`src/IM/ios/NanoIM/Features/Agents/CapabilitySelection.swift`、`src/IM/frontend/src/features/settings/agents/{agent-detail-page,agent-create}.tsx`、`packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md`）、锁定依赖包（`@deepseek-ai/dsh-tools`、`@deepseek-ai/dsh-tool-subagent-control`、`@deepseek-ai/dsh-subagent`、`@deepseek-ai/dsh-storage-domain`、`@deepseek-ai/dsh-storage-json`）以及现行长青契约（`docs/specs/gateway/{spec,global-agent,agent-capabilities,tool-approval}.md`）完成核验：

1. **现状断言核对**：
   - `LocalWorkers` 使用 `workerDomain`（`nano_local_workers`, `version: 1`, `layout: 'per-record'`），`confirmWork()` 仅清理 `row.pending`，`forget(roots)` 负责永久删除清理（`index.ts:1300`）。已核实 `@deepseek-ai/dsh-storage-json` `per-record` 布局的 `loadPerRecordState` 仅读取已声明表的目录、缺失目录视为空表且忽略未声明目录，故在 `version: 1` 下新增 `history` 表可无缝兼容存量数据与代码回滚，且 `workerId` 格式满足 `SAFE_KEY_RE`。
   - `GlobalMode.apply` 同时由 `single_thread`（`agent-config.ts:129` preset 级）与 Global root / 显式 root fork（`agent-config.ts:190` `agent.ctx` 局部级）复用——**发现关键遗漏（见 `R1-C1`）**。
   - `ToolSelection.refresh`（`capabilities.ts:113`）对 `agent.ctx.tools.restrict({ allow })` 必须排除所有 scope-local 工具（经核实 `@deepseek-ai/dsh-tools/lib/index.js:2906-2908` 会对未知全局工具名直接抛错）——**发现关键遗漏（见 `R1-C3`）**。
   - DSH 原生 `send_message`（`@deepseek-ai/dsh-tool-subagent-control/lib/index.js:23-36`）参数名为 `agent_id` 而非 `agent`，且 `@deepseek-ai/dsh-subagent/lib/index.js:603` 明确指导子会话传 `send_message({ agent_id, message })`——**发现关键错误（见 `R1-C2`）**。
   - 确认 `@deepseek-ai/dsh-tool-subagent-control` 仅注册 `send_message`、`interrupt_agent`、`list_agents`（不含 `wait_agent`），主 Agent 隐藏 `list_agents`/`interrupt_agent` 后不存在遗漏的原生查询/等待控制工具。
2. **设计决定与架构判断**：
   - 职责边界与依赖方向合规：全部运行时改动留在 `packages/dsh-integration`（通过公开 DSH exports：`ctx.sessions.get`、`ctx.sessionQuery.observeSession(..., { projectionMode: 'none' })`、`ctx.storageDomain`），不触碰 PA/Channels/IM 依赖红线，不修改 `apps/im-server` 或 Work 视图协议。
   - 复用与抽象判断合理：新增 `WorkerInspector` 封装双源投影/分页/预算/脱敏而非将查询塞进 `global-mode.ts` 或新建第二套注册表；DSH 直读原生事件日志避免双写；外部 CLI 新增独立 `history` 表避免破坏 `row.pending` 的 `hasPendingWork` / `confirmWork` 增量契约；在 `ToolSelection.refresh` 隐藏 `list_agents`/`interrupt_agent` 而不从 `catalog()` 硬删，避免存量 Global Agent 在 `agent-detail-page.tsx:1437` 触发 `missingTools` 阻断保存。
   - 但 `LocalWorkers` 内部 `onDetail`（`this.changes`）与 `deliver()`（`this.deliveries`）双队列并发写竞态、4 类 `deliver()` 来源去重区分及 DSH 元数据更新机制尚未闭合（见 `R1-W2`）；`NanoApproval.review` 在 `approval.ts:129` 的预处理与显式 root fork 边界尚未完全收口（见 `R1-W1`）。
3. **用户约束与 `agent-context-review`（设计模式）审查**：
   - 工具三段式梯度（`list` → `summary` → `read`，默认 `view="messages"`）、字符预算与四条克制读取纪律整体贴合用户核心诉求（防主 Agent 反复刷轨迹耗大量 Token），且 `read_worker` 排除在 `ApprovalSources.hostResults`（`policy/sources.ts:46`）与 `retainInstructions`（`policy/retained-instructions.ts:106`）之外，保证 Worker 输出保持 `untrusted-evidence` 不升级真人授权；`memory-trajectory.ts:91` 保留 8 KB 截断保护防止 Dreaming 膨胀。
   - 仍存在三处上下文/行为风险：① 若按 `R1-C1` 未同步删掉 Global 模式下 `send_message` 工具描述里的 `agent/message` 引导句，模型会看到 Schema 与描述冲突的指令；② 若按 `R1-C2` 漏投影 DSH `send_message({ agent_id })` 汇报并把 `agent-instructions`/`skill-invocation` 混入 `messages` 视图，会直接迫使主 Agent 升级展开 `activity` 或吞入大量无关 Token；③ 真实模型四场景验证缺少对“单轮重复 `summary` 变相轮询”与“模糊报错排查单次读取量/重刷上限”的定量判定口径（见 `R1-W3`）。
4. **Delta-spec 与文档检查**：
   - `./scripts/docs-check` 与 `scripts/check_platform_parity.py` 均通过；`docs/specs/gateway/global-agent.md` 现为 23 条 `### Requirement:`，`specs/gateway/spec.md` 更新为 24 条准确。
   - `specs/gateway/global-agent.md` 与 `specs/gateway/agent-capabilities.md` 均正确锚定 canonical 标题，MODIFIED 保留了既有适用 Scenario 且补充了 `download_attachment`/`send_user_message` 既有事实；`tool-approval.md` 标注 `no spec delta` 合理（`safeTools` 在 `policy.rules !== 'dsh'` 免审与既有 `download_attachment`/`inbox` 契约一致）。
   - 无视觉/交互新决策需要原型（跳过 prototype 合理）；无一次性部署迁移需求（不生成 `deployment-prompt.md` 合理）。
5. **五端对齐与 Milestone**：
   - 五端对齐矩阵与 `scripts/check_platform_parity.py` 规则一致（`Web`/`Desktop` 为 `shared`，`iOS` 与 `Node` 为 `native-sync`，M1 范围覆盖 `src/IM/ios/` 与 `apps/node/tests/`）。
   - 单 Milestone `M1-worker-read-and-send-boundary` 范围清晰，但退出标准需同步吸收本轮 CRITICAL/WARNING 修复点与定量 Token/调用次数验收口径。

---

### 历史问题闭环

R1 首轮审查，无历史遗留问题。

---

### Issues

#### `R1-C1` [CRITICAL] `GlobalMode.apply` 与 `single_thread` 共享挂载，方案未按 `config.mode === 'global'` 条件分支收口 `send_message` 与门控 `read_worker`

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 现状分析（L12）、关键决策 4（L89）、接口与数据流 1（L100）。
- **证据**：
  - 生产装配 `packages/dsh-integration/src/agent-config.ts:129` 对非 Global 模式（`single_thread`）在 preset 级挂载 `ctx.plugin(GlobalMode, { mode: config.mode, personal: !!config.personal })`；`agent-config.ts:190` 仅对 Global root 与显式 root fork 在 `agent.ctx` 级挂载同一 `GlobalMode.apply`。
  - `packages/dsh-integration/src/global-mode.ts:106-129` 当前为两种模式共用同一 `send_message` 定义与 `execute`；L114 仅过滤 `config.mode === 'global' || tool.name !== 'inbox'`。
  - `design.md:89, 100` 笼统写“删除 `agent`/`agent_id`/`message` 与 `nanoWorkers.control` 转发分支，Schema 收口为 `screenshotMessageParameters`”，未区分 `config.mode === 'global'` 与 `config.mode !== 'global'`，也未明确在 Global 模式下同步删去 `global-mode.ts:106` 工具描述末尾的 `"Use the native agent/message fields to continue a subagent in your subagent tree or report to your parent..."` 以及在 L114 过滤 `read_worker`。
- **未修后果**：直接按方案删除 `agent`/`agent_id`/`message` 分支会破坏 `single_thread` 模式根会话与子代理通信（违反 `spec.md:138` 零回归约束，且 `global-child-tools.test.ts` 的 `single_thread` 路径失败）；若未在 L114 过滤 `read_worker`，`single_thread` 及其子代理都会意外暴露 `read_worker`；若保留旧 `send_message` 描述尾句，会向 Global 主 Agent 交付与 Schema 矛盾的模型上下文。
- **修订要求**：明确 `GlobalMode.apply` 按 `config.mode === 'global'` 分支：① Global 模式注册 `read_worker`，并将 `send_message` 收口为纯对外 `screenshotMessageParameters`、移除描述中内部 `agent/message` 说明、移除 `nanoWorkers.control` 与内部转发分支；② 非 Global（`single_thread`）模式不注册 `read_worker`，完整保留原有 `send_message` Schema、描述与 `nativeSend`/`workflowEngine` 分支。

#### `R1-C2` [CRITICAL] DSH 原生汇报参数实为 `agent_id`（非 `agent`），且 DSH `user/message` 含系统注入大段上下文；按当前投影方案将丢失全部 DSH Worker 汇报并向主上下文灌入噪声

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 关键决策 3（L81-85）、接口与数据流 3（L146-148）。
- **证据**：
  - 在 Global 模式下，`agent-config.ts:129, 187` 不向 DSH 一级 Worker 挂载 `GlobalMode`，Worker 继承的是原生 `@deepseek-ai/dsh-tool-subagent-control` 注册的 `send_message`，其唯一目标参数是 `agent_id`（见 `@deepseek-ai/dsh-tool-subagent-control/lib/index.js:25-36`）；同时 DSH 的 `withContinuableReturnGuidance`（`@deepseek-ai/dsh-subagent/lib/index.js:603`）明确指示子会话调用 `send_message({ agent_id: <parentId>, message: "<self-contained result>" })`。而 `design.md:83` 写成 `send_message({ agent: 'lead' | rootId, message })`，漏掉了真实的 `agent_id` 字段。
  - DSH 会话事件中的 `user/message` 同时承载 `source.kind` 为 `agent-instructions`（完整 `AGENTS.md`）、`runtime-context`、`skill-invocation`（完整 `SKILL.md` 正文）与 `working-directory` 的内部注入（见 `packages/dsh-integration/src/policy/sources.ts:200-210`），且会话带 `inheritedEventCount` 边界。`design.md` 未规定 `projectDshSession` 对 `event.seq >= inheritedEventCount` 及 `user/message.source.kind` 的过滤规则，也未说明 DSH `tool/call` 的单行摘要生成（应复用 `extractToolSummary`）与冷会话不存在（`SESSION_QUERY_SESSION_NOT_FOUND`）时的处理。
- **未修后果**：真实运行中的 DSH Worker 正式回报将全部无法提升到 `messages` 视图和 `latest_report`（退化为 `"Done."`），而 `read_worker(action="read", view="messages")` 会把大段 `AGENTS.md`/`SKILL.md` 倾倒入主 Agent 上下文，直接放大 Token 消耗并迫使主 Agent 转而深读 `activity`。
- **修订要求**：在 `design.md` 中补全 `projectDshSession` 契约：① 仅扫描 `seq >= inheritedEventCount` 的自有事件，冷会话使用 `using` 释放 `observeSession(..., { projectionMode: 'none' })`，对 `SESSION_QUERY_SESSION_NOT_FOUND` 优雅返回空历史与已有元数据；② 识别父级汇报时检查 `(args.agent_id ?? args.agent)` 是否等于 `rootId` 或 `'lead'`（排除发给二级子代理的 `send_message`）；③ `user/message` 严格按 `source.kind` 过滤，排除 `agent-instructions`、`runtime-context`、`skill-invocation`、`working-directory` 等系统上下文注入，仅保留父级交办/追问与必要系统通知；④ `tool/call` 复用 `extractToolSummary` 填充 `recent_activity` 摘要，保证 DSH `summary` 足够清晰而不倒逼模型升读 `activity`。

#### `R1-C3` [CRITICAL] `capabilities.ts:113` 遗漏将 scope-local 的 `read_worker` 移出 `tools.restrict({ allow })`，运行期在 Global 主 Agent 与显式 root fork 上将直接抛错

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 现状分析（L13）、关键决策 4（L89）。
- **证据**：
  - `packages/dsh-integration/src/capabilities.ts:111-113` 在 `ToolSelection.refresh()` 中将 `fixedTools(...)` 并入 `agent.ctx.tools.restrict({ allow })`，并显式排除了 Global scope-local 工具集合 `['inbox', 'conversations', 'read_messages', 'search_messages', 'threads', 'download_attachment', 'delegate_worker']`。
  - 核实 `@deepseek-ai/dsh-tools/lib/index.js:2895-2909`：`restrict()` 会把 `allow` 中每个工具名与 `restrictableNames`（全局注册工具）比对，任何局部注册（`agent.ctx.tools.register`）的工具名都会立即抛出 `Error: tools.restrict() names unknown global tool "read_worker"`。
  - `design.md` 将 `read_worker` 加入 `fixedTools('global', ...)` 并在 `GlobalMode`（`agent.ctx`）局部注册，但仅提到在 `capabilities.ts` 隐藏 `list_agents`/`interrupt_agent`，遗漏更新 L113 的排除集合。
- **未修后果**：所有 Global / PA 主 Agent 及显式 root fork 在 `attachAgent` / `refresh` 时必然抛错，无法启动、恢复或生成 Prompt Preview。
- **修订要求**：在 `design.md` 明确将 `'read_worker'` 加入 `capabilities.ts:113` 的 Global scope-local 排除数组，并同步更新 `packages/dsh-integration/tests/capabilities.test.ts:25` 等断言。

#### `R1-W1` [WARNING] `NanoApproval.review` 漏改 `approval.ts:129` 预处理且按 `origin !== 'subagent'` 漏掉 Global 显式 root fork

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 关键决策 4（L89）、接口与数据流 5（L196）。
- **证据**：
  - `packages/dsh-integration/src/policy/approval.ts:129` 在获取 `agent`/`config`（L130）之前就以 `!isInternalSendArgs(exec.arguments)` 跳过 `normalizeMessageArguments`。若仅关闭 L166 的 `safe_tool` 分支而保留 L129，携带 `agent`/`agent_id` 的非法调用会绕过归一化，在开启 Auto 的 PA 上甚至会命中 L168 `allow('product_disclosure_gate')`。
  - `design.md:89` 以 `config.mode === 'global' && agent.session.header.origin !== 'subagent'` 判定，但 Global 显式 root fork（`subagent_fork`）的 `origin === 'subagent'` 且 `!isOrdinaryChild(agent)`（`child-role.ts:47-49`、`agent-config.ts:169, 190`），其挂载的也是 Global 纯对外 `send_message`。
- **未修后果**：Global 主 Agent 预处理路径与显式 root fork 仍残留 `isInternalSendArgs` 旁路，与方案声明的“任何调用均须走 `normalizeMessageArguments` 并彻底闭合旁路”不一致。
- **修订要求**：在 `approval.ts:129` 之前读取 `agent`/`config`，统一采用与 `agent-config.ts:169` 一致的判定（`config?.mode === 'global' && !isOrdinaryChild(agent) && !globalWorkRole(agent, config)`），同时收口 L129 的归一化与 L166 的 `safe_tool` 免审分支。

#### `R1-W2` [WARNING] `LocalWorkers` 历史持久化与元数据更新存在并发队列竞态、4 类 `deliver()` 来源混写与 DSH 元数据更新盲区

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 关键决策 2（L75-79）、接口与数据流 2-3（L124-127, L139-145）。
- **证据**：
  - **并发竞态**：`manager.ts:403` 的 `onDetail` 串行在 `this.changes[workerId]`，而 `manager.ts:322` 的 `deliver()` 串行在 `this.deliveries[reportKey(workerId, eventId)]`。若两条路径并发读写同一 `workerId` 的 `history` 或 `workers` 记录，会造成 read-modify-write 丢写。
  - **4 类 `deliver()` 来源混写**：`deliver()` 同时处理 ① `nano-parent` MCP `send_message` 汇报（未通过 `onDetail` 记为 `message`）、② `TurnEvents.report` 权限/提问系统通知（已在 `drivers.ts:51` 通过 `onDetail` 记为 `system`）、③ `onEnd` 终局回报（已在 `onDetail` 记过最终 `assistant` 文本，且 `manager.ts:417-419` 拼接了固定前缀 `"This turn ended. The worker will do no further work unless you send it more.\n"`）、④ `recover()` 中断通知。`design.md:145` 未区分这 4 类来源的写入、去重与 `latestReport`/`latestError` 更新规则。
  - **DSH 元数据与存量回退缺口**：DSH Worker 不经过 `onDetail`/`deliver()`，且 `manager.ts:145` 在 `state`/`sessionId` 未变时提前返回；方案未规定 DSH Worker 在 `start()`、`control('send')`、`nativeState()`、`nativeTurns()` 中更新 `createdAt`/`updatedAt`/`turnCount`（及 `summary` 对 DSH 的权威来源），也未明确升级前存量 `storedWorker` 缺少上述可选字段时 `list` 的返回/排序回退与无对应历史条目时（如 `start()` 启动前即失败）省略 `latest_error_item_id` 的规则。
- **未修后果**：外部 CLI 并发回调可能丢失历史条目，或 `messages` 视图出现重复文本、权限系统通知误覆写 `latest_report`、`latest_report` 带固定结束语噪声；DSH Worker 在 `list` 中排序和轮次失真，存量旧记录读取可能产生 `undefined` 排序异常。
- **修订要求**：① 统一将同一 `workerId` 的 `workers`/`history` 写入串行在 `this.changes[workerId]`；② 明确 4 类 `deliver()` 来源的分流与去重策略（剥离 `onEnd` 固定前缀、仅真实汇报/成功终局正文更新 `latestReport`、权限/中断/失败归入 `system` 或 `latestError`）；③ 明确 DSH Worker 元数据更新点（`start`/`control`/`nativeState`/`nativeTurns`，`summary` 以 DSH 实时投影补齐 `turn_count`/`latest_report`/`latest_error`），并定义存量缺省字段回退及无匹配条目时省略 `*_item_id`。

#### `R1-W3` [WARNING] 真实模型“克制读取、不反复刷轨迹耗大量 Token”验证缺少定量通过门槛与同轮重复 `summary` 观测约束

- **位置**：`docs/changes/feat-817-global-worker-read-and-send-boundary/design.md` 接口与数据流 5 Validation（L199）、本次审查安排 `G2-context-and-behavior`（L216）、Milestones `M1` 退出标准（L255）。
- **证据**：
  - 用户在 `spec.md` 原始需求及 Q5 明确强调：“ok，要实际注意最后测试主agent不会反反复复读worker的具体轨迹，花大量token去读”。
  - 当前 `design.md:199` 与 `M1` 退出标准对场景 1（派发后 `read_worker = 0`）与场景 3（清晰终局回报后 `read = 0`）有硬指标，但：① 场景 2（运行中进度询问）未约束单轮 `summary` 调用上限（无法防模型看到 `state="running"` 后同轮连调多次 `summary` 变相轮询）；② 场景 4（模糊报错排查）与 `G2` 证据记录未规定必须采集并校验每次 `read_worker` 的 `action`/`view`/返回字符数与总 Token 消耗，也没有给出“禁止重复同参/同页 `read`”及最大调用次数的明确通过阈值。
- **未修后果**：实施期和审查期难以客观判定“是否消耗大量 Token 反复读取”，容易只凭最终回复正确就放行隐性多次深读或轮询行为。
- **修订要求**：在 `design.md:199`、`G2-context-and-behavior` 与 `M1` 退出标准中补充四场景定量验收线（例如：场景 1 `read_worker == 0`；场景 2 `summary <= 1`、`read == 0` 且回复后结束轮次不轮询；场景 3 `read == 0`；场景 4 无重复同参/同页 `read`、针对单一模糊报错 `read` 调用受界且在证据中记录各场景 `read_worker` 调用明细与返回总字符/Token 量），明确超线即在 M1 内迭代工具描述与提示词直至达标。

---

### Recommendations

- **`R1-R1`**：更新 `src/IM/frontend/src/i18n/{en,zh}.json`（L990/L998）中 Global 模式固定工具说明文案加入 `read_worker` 时，建议一并补上已在 `fixedTools` 中的 `download_attachment`，使设置页说明与 `packages/product-contracts/src/capabilities.ts` 及 `specs/gateway/agent-capabilities.md` 完全一致。
- **`R1-R2`**：`packages/personal-assistant/assets/skills/nano-ongoing-work/SKILL.md` 的受众同时包含 Global/PA 主 Agent 与其内部 Worker，更新时建议显式标明 `delegate_worker`/`read_worker` 仅限主 Agent，内部 Worker 仍沿用原生 `subagent`/`send_message` 与父级/子代理通信，防止 Worker 加载该 Skill 后产生工具误解。
- **`R1-R3`**：`summary` 在 `latest_report_truncated: true` 或 `latest_error_truncated: true` 时可考虑附带 `latest_report_total_chars` / `latest_error_total_chars`（或保留现有轻量字段），让模型在决定是否定向续读前知晓全文规模，进一步抑制非必要续读。


### Author Resolutions (Round 1)

- **`R1-C1` (`accepted`)**：核实 `agent-config.ts:129, 190` 与 `global-mode.ts:106-129` 属实。已在 `design.md` 现状分析、关键决策 4、接口与数据流 1 及 `M1` 明确 `GlobalMode.apply` 严格按 `config.mode === 'global'` 分支：仅 Global 模式注册 `read_worker` 并将 `send_message`（Schema、描述与 `execute`）收口为纯对外；`single_thread` 完整保留原有 `send_message` 且不暴露 `read_worker`。
- **`R1-C2` (`accepted`)**：核实 DSH 原生 `send_message` 参数为 `agent_id` 且 `user/message` 含系统注入事件属实。已在 `design.md` 关键决策 3、接口与数据流 3 及 `M1` 补全 `projectDshSession` 契约：仅扫 `seq >= inheritedEventCount` 自有事件、跳过替换事件、按 `source.kind` 排除 `agent-instructions`/`runtime-context`/`skill-invocation`/`working-directory`/`compact-checkpoint`、按 `(args.agent_id ?? args.agent)` 匹配 `rootId | 'lead'` 提升父级汇报、复用 `extractToolSummary` 填充 `recent_activity`、并对 `SESSION_QUERY_SESSION_NOT_FOUND` 优雅降级。
- **`R1-C3` (`accepted`)**：核实 `capabilities.ts:113` 必须排除所有 Global scope-local 局部注册工具属实。已在 `design.md` 现状分析、关键决策 4 及 `M1` 明确将 `'read_worker'` 加入 `capabilities.ts:113` 排除数组与 L107 子 Agent 禁用列表，并同步更新 `capabilities.test.ts`。
- **`R1-W1` (`accepted`)**：核实 `approval.ts:129` 预处理时机与 Global 显式 root fork 边界属实。已在 `design.md` 现状分析、关键决策 4、接口与数据流 5 及 `M1` 明确在 `approval.ts:129` 前解析 `agent`/`config`，统一使用 `config?.mode === 'global' && !isOrdinaryChild(agent) && !globalWorkRole(agent, config)` 同时收口 L129 与 L166。
- **`R1-W2` (`accepted`)**：核实 `LocalWorkers` 双队列竞态、4 类 `deliver()` 来源与 DSH 元数据缺口属实。已在 `design.md` 关键决策 2、接口与数据流 2-3 及 `M1` 明确：同一 `workerId` 的 `workers`/`history` 写入统一串行在 `this.changes[workerId]`；4 类 `deliver()` 来源显式分流去重并剥离 `onEnd` 固定前缀；补齐 DSH `start`/`control`/`nativeState`/`nativeTurns` 元数据更新与 `summary` 实时投影优先；定义存量缺省字段回退及无对应条目时省略 `*_item_id`。
- **`R1-W3` (`accepted`)**：已在 `design.md` 接口与数据流 5 Validation、`G2-context-and-behavior` 与 `M1` 退出标准补齐四场景定量硬门槛（场景 1 `read_worker == 0`；场景 2 `summary <= 1`、`read == 0` 且回复后结束；场景 3 `read == 0`；场景 4 无重复同参/同页 `read`、`read <= 2`、累计返回 `<= 16,000` 字符）及逐次调用明细/字符数/Token 证据留存要求。
- **`R1-R1` / `R1-R2` / `R1-R3` (`accepted`)**：均已一并吸收进 `design.md`（i18n 顺手补齐 `download_attachment`；`nano-ongoing-work/SKILL.md` 明确区分主 Agent 与内部 Worker 工具边界；`summary` 截断时附带 `*_total_chars`）。


---

## Round 2

### Metadata

- **Reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `agent-context-review` design mode, Antigravity subagent `e0375e1d-71ee-429e-9448-935be4231b7a`)
- **Review Target**: `docs/changes/feat-817-global-worker-read-and-send-boundary/design.md`（及 `design-review.md` 的 `Author Resolutions (Round 1)`）
- **review_mode**: `delta`
- **mode_reason**: `spec.md`、3 份 Gateway delta-spec 与 Milestone 切分均未变化；本轮修订均为针对 R1 全部 6 项问题及 3 项建议的有界技术设计闭环，按 `delta` 模式逐项核验修订内容及其对生产装配、审批边界、模型上下文与验证口径的波及范围。
- **started_at**: `2026-11-28T15:56:21+09:00`
- **completed_at**: `2026-11-28T15:58:00+09:00`
- **duration**: `1m39s`

### Verdict

**Approved** — **0 CRITICAL / 0 WARNING**（0 Recommendations）

---

### Coverage 与证据

- **本轮变化与波及范围核查**：
  1. `GlobalMode.apply` 条件分支与 `single_thread` 隔离（`design.md` L12、L90、L103-107、L205、L275）：确认 Global 模式独占 `read_worker` 与纯对外 `send_message`（Schema、描述尾部清理与 `execute` 同步收口），非 Global 模式完整保留组合 `send_message` 且不挂载 `read_worker`，无跨模式回归风险。
  2. `WorkerInspector` / `projectDshSession` 契约（`design.md` L31、L81-85、L158-162、L235、L275）：确认已对齐 DSH 原生 `send_message` 的 `agent_id` 参数（兼容 `agent`），严格按 `seq >= inheritedEventCount` 过滤替换事件及 `agent-instructions`/`runtime-context`/`skill-invocation`/`working-directory`/`compact-checkpoint` 系统注入，复用 `extractToolSummary` 补齐 `recent_activity`，并对 `SESSION_QUERY_SESSION_NOT_FOUND` 做降级处理。
  3. `capabilities.ts` 与 `approval.ts` 边界闭合（`design.md` L13-14、L91-92、L212、L235、L275）：确认 `capabilities.ts:113` 排除 `'read_worker'` 避免 `tools.restrict()` 报错，同时 `approval.ts` L129 与 L166 均在解析 `agent`/`config` 后统一以 `config?.mode === 'global' && !isOrdinaryChild(agent) && !globalWorkRole(agent, config)` 判定，经逐类角色核对（Global/PA root、Global 显式 root fork、DSH L1/L2 子代理、`worker-fork`、`single_thread`、Workflow 子执行者）均无遗漏或误伤。
  4. `LocalWorkers` 单队列串行化、`deliver()` 四源分流与 DSH/存量元数据（`design.md` L32、L60、L77、L128-131、L148-155、L162、L275）：确认 `workers`/`history` 写操作统一串行在 `this.changes[workerId]`，4 类 `deliver()` 来源（`nano-parent`、`TurnEvents.report`、`onEnd` 剥离前缀、`recover()`）分流与去重明确，DSH 元数据更新点与存量缺省字段回退（`created_at?`/`updated_at?`、缺历史条目省略 `*_item_id`）自洽。
  5. 模型上下文与克制读取定量验证（`agent-context-review` 设计模式，`design.md` L201-219、L236、L248、L267、L275）：四场景硬门槛与逐次调用明细/字符数/Token 留存要求已落入 Validation、`G2-context-and-behavior` 与 `M1` 退出标准，`nano-ongoing-work/SKILL.md` 亦明确区隔主 Agent 与内部 Worker 工具边界。
  6. 自动化文档检查：`./scripts/docs-check`（242 maintained Markdown sources, 74 required routes）与 `scripts/check_platform_parity.py` 均通过。
- **未受影响项引用（`retained_from: Round 1`）**：
  - `spec.md`、`specs/gateway/{spec,global-agent,agent-capabilities}.md` 锚点与 Scenario 覆盖、`tool-approval.md` `no spec delta` 裁决、DSH `per-record` 存储兼容性与回滚安全性、五端对齐矩阵（`Web`/`Desktop` `shared`，`iOS`/`Node` `native-sync`）、跳过原型与一次性部署迁移判断均未发生实质变化，沿用 Round 1 核查证据。

---

### 历史问题闭环

| 原 Issue ID | Author Resolution | 本轮核查证据 | 状态 |
|---|---|---|---|
| `R1-C1` | `accepted`：按 `config.mode === 'global'` 条件分支收口 `GlobalMode.apply` | `design.md` L12、L90、L103-107、L205、L275 已明确仅 Global 注册 `read_worker` 并收口 `send_message`（含描述尾部清理），`single_thread` 原样保留且不暴露 `read_worker` | `closed` |
| `R1-C2` | `accepted`：补全 `projectDshSession` 的 `agent_id` 识别、系统注入过滤、摘要复用与缺失降级 | `design.md` L31、L81-85、L158-162、L235、L275 已完整覆盖 `(args.agent_id ?? args.agent)`、`seq >= inheritedEventCount`、`source.kind` 排除列表、`extractToolSummary` 与 `SESSION_QUERY_SESSION_NOT_FOUND` 降级 | `closed` |
| `R1-C3` | `accepted`：将 `'read_worker'` 加入 `capabilities.ts:113` scope-local 排除数组 | `design.md` L13、L91、L235、L275 已明确同步更新 `capabilities.ts` L104-105、L107、L113 及 `capabilities.test.ts` | `closed` |
| `R1-W1` | `accepted`：在 `approval.ts:129` 前解析并统一判定 Global root 与显式 root fork | `design.md` L14、L92、L104、L212、L235、L275 已明确在 L129 前解析 `agent`/`config` 并以 `!isOrdinaryChild(agent) && !globalWorkRole(agent, config)` 同时收口 L129 与 L166 | `closed` |
| `R1-W2` | `accepted`：统一 `this.changes[workerId]` 串行、4 类 `deliver()` 分流与 DSH/存量元数据规则 | `design.md` L32、L60、L77、L128-131、L148-155、L162、L275 已完整闭合并发串行、4 类 `deliver()` 去重分流、DSH 更新点/实时投影与存量字段/`*_item_id` 回退 | `closed` |
| `R1-W3` | `accepted`：补齐真实模型四场景定量门槛与调用明细/字符/Token 证据要求 | `design.md` L208、L215-219、L236、L248、L267、L275 已固化四场景硬指标（含场景 2 `summary <= 1` 与场景 4 `read <= 2` / 0 重复 / `<= 16,000` 字符）与证据留存口径 | `closed` |

（另确认 `R1-R1`、`R1-R2`、`R1-R3` 亦已分别在 `design.md` L17/L225、L18/L201/L208、L73/L130 采纳落地。）

---

### Issues

无。

---

### Recommendations

无。
