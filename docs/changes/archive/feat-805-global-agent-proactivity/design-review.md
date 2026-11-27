# feat-805: Global Agent 岗位主动性闭环与协作校准 — Design Review

## Round 1

### Metadata

- **reviewer**: `change-design-reviewer` + `agent-context-review` (independent subagent `67e71cea-d1d7-4ef2-bfa5-7a664c252db5`)
- **target**: `docs/changes/feat-805-global-agent-proactivity/{spec.md,design.md,specs/**,M1-global-agent-proactivity/.gitkeep}` @ branch `unit/feat-805-global-agent-proactivity`
- **review_mode**: `full`
- **mode_reason**: Gate 2 首轮独立设计审查（无前序 `design-review.md` 记录），同步合并 `agent-context-review` 设计态审查。
- **started_at**: `2026-11-27T22:07:19+09:00`
- **completed_at**: `2026-11-27T22:19:00+09:00`
- **duration**: `11m41s`

### Verdict

- **Conclusion**: **Changes Requested** (`Issues Found`)
- **Severity Counts**: `CRITICAL: 3` | `WARNING: 3` | `NIT: 2`

---

### Coverage 与证据

#### 1. 架构判断与跨包边界（`SPEC.md` / `AGENTS.md`）

整体架构方向合理且遵守仓库架构红线：
- **单主会话与单向依赖保持完好**：复用 `packages/personal-assistant` 的 `ProactiveCoordinator` 三水位状态机（`proactive-coordinator.ts#L114-L320`）与 `TaskContext.peekPendingForDreaming`（`task-context.ts#L106`），复用 `packages/dsh-integration` 的 `Dreaming` 单写者与 `MemoryDocuments.consolidationIssues()` AST 门禁（`memory-documents.ts#L315-L470`），并在 `apps/im-server/src/task-graphs.ts` 收敛 1v1 Agent 私聊焦点归属。未引入第二套 Agent Loop、未新增常驻子会话或内核 HTTP 端口、未越界调用 DSH 私有导出，符合 `SPEC.md` 与 `tests/contract/test_runtime_dependency_contract.py` 的单向依赖约束。
- **存量指纹零漂移策略正确**：不在 `canonicalAgentConfiguration`（`packages/product-contracts/src/configuration.ts`）中补写缺省 `features.proactive_planning`，并对显式关闭 `task_graph` 或工具白名单不含 `task_graph` 的存量配置将缺省 `proactive_planning` 解析为 `false`（`packages/product-contracts/src/capabilities.ts#L75-L84`），升级幂等性方向正确。

#### 2. 需求、澄清决策与非目标覆盖（对照 `spec.md`）

- **Q1（按所属 `conversation_id` 原路闭环 + 1v1 Agent 私聊入对端焦点台，`spec.md#L18-L23,#L99-L108`）**：设计在概念层完整映射了「群归群、私聊归私聊、纯职责新项归目标业务群（无群才落绑定管理者私聊）」与 `TaskGraphService` 的 `isDirectWithAgent` 扩展（`design.md#L69-L71,#L115-L123`）；**但落地链路存在 1 处阻断级断层（见 `R1-C1`）**——`ToolReferences` 未解析 `task_graph` 的投影用户短引用 `u_xxxxxx`，导致 Global Agent 在群聊设置 `proposed_for_user_id` 时会被 `im-server` 新增的成员校验直接以 `400 invalid_arguments` 拒绝。
- **Q2（`global` 默认开启、`single_thread` 不暴露不开启 + 团队低噪触达，`spec.md#L24-L29,#L113-L135,#L153-L159`）**：低噪触达规则（常规 `proposed` 静默挂板、已有周期汇报经 `notes` 合并、仅急需实质备料或时效风险建工作时段一次性 `schedule`、唤醒前未读核实）设计清晰；**但 `modes: ['global']` 在 `im-server` 能力投影、服务端校验/创建默认展开及 Web/iOS 新建与编辑组件多处漏改（见 `R1-C3`），且内置 `nano-proactive-care` Skill 正文与低噪策略冲突（见 `R1-W2`）**。
- **Q3（常驻首页岗位准则 + 单行带范围触发指针 vs 二级人物/项目详情页 + 多人作用域隔离，`spec.md#L30-L36,#L136-L152`）**：两层单源记忆分工与 `<bound_administrator>` 权限护栏设计合理；**但 `consolidationPrompt(false)` 未区分 `global` 与 `single_thread` 独立专家，会破坏 `single_thread` 的 `Dreaming`（见 `R1-C2`），且非 PA Global 的 `Dreaming.refreshSources` 会踩中 `sourcesPending` 死锁陷阱（见 `R1-W1`）**。
- **非目标守卫（`spec.md#L168-L171`）**：未向普通 Global Agent 开放 `pa.observations` / `pa.sources` / `send_user_message`，未改变正式记忆单写者边界；需修复 `R1-C2` 与 `R1-C3` 后才能真正兑现「不为 `single_thread` 开启或侵入」。

#### 3. Agent Context 与缓存前缀稳定性核查（`agent-context-review` 设计态）

- **前缀缓存稳定性（`NoSilentPrefixRewrite`）**：主会话窗口内新增的 `nano-global-mode` 与 `nano-document-memory` 说明均为窗口级静态文本；窗口首轮内联的 `MEMORY.md` 与 `.nanoassistant/ROLE.md` 快照不在窗口中途静默改写；`<proactive-review-wake>`、附带 `<updated-formal-memory>` 的 `<proactive-nightly-wake>` 及 `<schedule-observation-sync>` 均以尾部消息注入（`dsh-integration/src/index.ts#L348-L365,#L1506-L1515`），满足前缀稳定红线。
- **观察池物理隔离**：`DocumentMemory`（`document-memory.ts#L49-L55,#L205-L246`）对非 `Dreaming` 会话拦截 `read`/`bash` 读取 `proactivity-signals.md` 并脱敏 `grep`/`glob` 结果，将该守卫从 `personal` 扩展至 `proactiveCalibration` 后隔离机制完备。
- **上下文可操作性与一致性缺陷**：检出 4 项必须在实施前修正的 Context 链路问题——① 模型可见 `u_xxxxxx` 身份无法用于 `task_graph.proposed_for_user_id`（`R1-C1`）；② `consolidationPrompt(false)` 误注入 `single_thread` `Dreaming`（`R1-C2`）；③ 按需加载的 `nano-proactive-care/SKILL.md` 仍写死 PA 专属私聊投递、`09:00` 早报闹钟与 `[Pending Morning Brief]` 键名（`R1-W2`）；④ 无人值守主动轮次缺少前序人类指令时在 `NanoApproval` 下的工具放行边界未闭合（`R1-W3`）。

#### 4. `delta-spec`、审查安排、Runbook 与 Milestones 核查

- **`delta-spec` 范围与计数核实**：
  - `docs/specs/gateway/spec.md` 当前 `Global Agent` 共 `23` 条 `### Requirement:`，新增 1 条后为 `24`（与 `specs/gateway/spec.md#L9` 一致）；`Agent Capabilities` 当前 `69` 条，1 条 `RENAMED` + 2 条 `MODIFIED` 后仍为 `69`（与 `specs/gateway/spec.md#L10` 一致）；`Personal Agent` 2 条 `MODIFIED` 计数不变。
  - `docs/specs/im/spec.md` 当前 `Agents and Nodes`（`57`）、`Task Graphs`（`20`）、`Personal Agent`（`8`）均为 `MODIFIED`，计数不变（与 `specs/im/spec.md` 一致），未改动场景均完整保留原文。
- **审查安排、Runbook 与 Milestones**：
  - `M1-global-agent-proactivity/.gitkeep` 已就位；G1（`change-code-review`）+ G2（`agent-context-review` + `product-journey-review` 共享隔离真栈与 `llm_logs`）编组合理，Runbook 服务启停与健康检查可执行。
  - M1 范围列表存在错误文件路径 `src/IM/frontend/src/i18n/zh-CN.json`（实际为 `zh.json`）及多处漏列模块（见 `R1-C1`、`R1-C3`），且 E2E 方案漏覆盖 `spec.md` 场景二（见 `R1-W3`）。

---

### 历史问题闭环

首轮审查（Round 1），无历史遗留问题。

---

### Issues

#### `R1-C1` [CRITICAL] `ToolReferences` 未对 `task_graph` 解析/投影 `u_xxxxxx` 用户引用，导致 Global Agent 在群聊填写 `proposed_for_user_id` 必报 `400 invalid_arguments`

- **具体位置**：
  - `design.md#L10-L18`（涉及范围）、`design.md#L117-L119`（`proposed_for_user_id` 强校验）、`design.md#L146,#L186`（夜间唤醒指令要求传入 `proposed_for_user_id`）、`design.md#L242`（M1 范围）
  - 关联生产代码：`packages/personal-assistant/src/tool-references.ts#L88-L92,#L234-L270,#L410-L415,#L544`；`apps/im-server/src/identity.ts#L302`；`packages/dsh-integration/src/features/task-graph-schema.ts#L25-L28`
- **证据与机理**：
  1. IM 服务端真实用户主键 `users.id` 为 36 字符 UUID（`identity.ts#L302`）。`ToolReferences.userRef()` 将所有长度 `> 8` 的用户 ID 统一投影为 `u_xxxxxx`（`tool-references.ts#L88-L92`），因此 Global Agent 在 `inbox`、`conversations`、`read_messages`、`search_messages`、`ROLE.md` 的 `ownerRef`（`global-agent.ts#L162`）与 `<bound_administrator>`（`design.md#L169`）中可见的全部人类成员 ID 均为 `u_xxxxxx`，模型完全不可见底层 UUID。
  2. 但 `ToolReferences.arguments()` 的 `method === 'task_graph'` 分支（`tool-references.ts#L234-L270`）仅将 `target` 解析为 `conversation_id`，**从未调用 `resolveUser()` 解析顶层或 `operations[]`（`add_task`、`update_task.patch`、`set_assignee`）中的 `proposed_for_user_id`、`assignee`（`type === 'user'`）与 `wait.asked_user_id`**；同时 `ToolReferences.result()`（`tool-references.ts#L544`）也未将 `task_graph` 返回节点中的上述用户 ID 字段投影回 `u_xxxxxx`。
  3. 与此同时，`design.md#L118` 在 `TaskGraphService.executeTransaction` 新增硬性校验：若显式提供 `proposed_for_user_id`，必须属于 `doc.conversation_id` 的有效真人参与者 `users.id`，否则返回 `400 invalid_arguments`。此外，`packages/dsh-integration/src/features/task-graph-schema.ts#L25-L28` 的工具 schema 描述仍写着 `"omit in private PA chats"`，未说明普通 Global Agent 在 1 对 1 私聊中同样可省略并自动归属对端真人。
- **未修后果**：Global Agent 按 `<proactive-nightly-wake>` 指引在项目群为业务负责人（如 Alice `u_xxxxxx`）创建 `status="proposed"` 候选卡时，传入的 `"u_xxxxxx"` 不匹配 `conversation_participants.user_id`（UUID），会被 `im-server` 100% 拒绝并返回 `400 invalid_arguments`，导致 `spec.md` 场景一（`#L67`）与验收标准（`#L102`）的群聊原路提议闭环直接跑不通；且 `task_graph(get/list)` 返回裸 UUID 会造成模型上下文内同一真人出现两套 ID。
- **修改建议**：将 `packages/personal-assistant/src/tool-references.ts` 与 `packages/dsh-integration/src/features/task-graph-schema.ts` 纳入设计范围：在 `ToolReferences.arguments`（`method === 'task_graph'`）中递归解析顶层与 `operations[]` 内的 `proposed_for_user_id`、`assignee`（`type: 'user'`）及 `wait.asked_user_id`，在 `ToolReferences.result` 中将 `task_graph` 响应内的用户 ID 字段统一投影为 `u_xxxxxx`，并同步更新 `task-graph-schema.ts` 中 `proposed_for_user_id` 的 1v1 私聊参数说明。

#### `R1-C2` [CRITICAL] `consolidationPrompt(false)` 混同 `global` 与 `single_thread` 独立专家，导致单会话助手 `Dreaming` 触发 `consolidationIssues()` 门禁失败并回滚

- **具体位置**：
  - `design.md#L17,#L82,#L169-L170`
  - `specs/gateway/agent-capabilities.md#L18,#L83`
  - 关联生产代码：`packages/dsh-integration/src/knowledge/dreaming-agent.ts#L71`、`packages/dsh-integration/src/knowledge/dreaming-prompts.ts#L67`、`packages/dsh-integration/src/knowledge/dreaming.ts#L263,#L397-L402`、`packages/dsh-integration/src/knowledge/memory-documents.ts#L378-L382`、`packages/dsh-integration/src/knowledge/document-memory.ts#L136`
- **证据与机理**：
  1. `dreaming.ts#L263` 对所有开启 `dreaming` 的 Agent（包含 `config.mode === 'single_thread'` 的独立专家）均执行自动与显式 `Dreaming`；而 `dreaming-agent.ts#L71` 当前仅传入布尔值 `consolidationPrompt(!!config.personal)`。
  2. `design.md#L169` 规定在 `consolidationPrompt(false)` 中要求维护 `MEMORY.md` 唯一 `## 主动性与介入偏好` 四分栏及 `knowledge/proactivity-signals.md` 单次观察池；但 `design.md#L17,#L82` 同时规定 `MemoryDocuments` 仅对 `proactiveCalibration = Boolean(config.personal) || config.mode === 'global'` 开启主动性校准，对 `single_thread` 维持 `!proactiveCalibration` 拦截（`memory-documents.ts#L378-L382`：非主动校准记忆仓只要存在 `knowledge/proactivity-signals.md` 即报 `consolidationIssues` 错误）。
  3. 因此，当 `single_thread` Agent 运行 `Dreaming` 时，其 `!!config.personal` 同样为 `false`，模型将收到 `consolidationPrompt(false)` 的强制指令，向 `single_thread` 的 `MEMORY.md` 写入无意义的 `## 主动性与介入偏好` 章节，并在出现点卡/隐式信号时创建 `knowledge/proactivity-signals.md`——随即被 `consolidationIssues()` 判为非法文件，耗尽 3 次自愈重试后触发 `rollbackBatch` 回滚。
- **未修后果**：直接破坏所有 `single_thread` 模式助手的自动/手动 `Dreaming` 可用性，并违背 `spec.md#L169`（非目标：不为 `single_thread` 开启跨会话主动筹划）与 `specs/gateway/agent-capabilities.md#L83`（`single_thread` 记忆结构保持不变）。
- **修改建议**：将 `dreaming-agent.ts`、`dreaming-prompts.ts`、`dreaming.ts`（`<bound_administrator>` 注入）与 `document-memory.ts` 的角色分支从二元 `personal: boolean` 改为三态（`'personal' | 'global_expert' | 'single_thread_expert'`，或显式传入 `{ personal: boolean; proactiveCalibration: boolean }`），确保 `single_thread` 整合提示词、常驻记忆指引与 `<main_agent_background>` 完全不含主动性四分栏、`proactivity-signals.md` 或 `<bound_administrator>`。

#### `R1-C3` [CRITICAL] `proactive_planning` 的 `modes: ['global']` 在 `im-server` 能力投影、服务端校验/创建默认展开及 Web/iOS 新建与编辑页多处断链，且存在错误文件路径

- **具体位置**：
  - `design.md#L13-L14,#L18,#L105-L112,#L242`
  - 关联生产代码：
    - `apps/im-server/src/{agent-creation.ts#L75-L86,#L177,#L267-L271,control-routes.ts#L48,#L416,agent-settings.ts#L63-L75,control.ts#L219,task-graphs.ts#L31-L32,personal-agent-creation.ts#L46}`
    - `apps/node/src/{configuration.ts#L172,main.ts#L69,#L689}`、`packages/dsh-integration/src/{index.ts#L778,#L1490,capability-state.ts#L12,#L61-L62}`、`packages/product-contracts/src/node-rpc.ts#L22`
    - `src/IM/frontend/src/features/settings/agents/{capability-editor.tsx#L35,agent-create-page.tsx#L495,#L803-L816,#L1003,agent-detail-page.tsx#L1946,im-agent-config-api.ts#L27-L35}`、`src/IM/frontend/src/i18n/zh.json`
    - `src/IM/ios/NanoIM/Features/Agents/{AgentsView.swift#L419-L426,#L458,AgentModels.swift#L22-L29,#L168,CapabilitySelection.swift#L68-L72}`
- **证据与机理**：
  1. **`im-server` 协议层白名单剥离 `modes`**：`design.md#L14,#L112` 依赖 `GET /im/v1/nodes/{id}/capabilities` 返回带 `modes: ['global']` 的特性项供新建页按 `draft.work_mode` 收窄；但 `apps/im-server/src/agent-creation.ts#L75-L86` 的 `featureOptions()` 仅白名单映射 `{ key, label_i18n, help_i18n, default_on, available, requires }`，直接丢弃了 `modes`（`agent-settings.ts#L63-L71` 的 `configurationDisplay`、`node-rpc.ts#L22`、`im-agent-config-api.ts#L27-L35`、`AgentModels.swift#L22-L29` 同样无 `modes` 字段，且均未列入 `design.md` 改动范围）。
  2. **服务端 `definitionsForRole` 默认 `'global'` 误伤 `single_thread` 校验与创建**：`design.md#L108` 将 `definitionsForRole(isPersonal = false, definitions, workMode = 'global')` 默认值定为 `'global'`，却漏掉了 `apps/im-server/src/control.ts#L219`（`validateConfigurationCandidate` 未传 `candidate.work_mode`）、`apps/im-server/src/agent-creation.ts#L267-L271`（`b.features === undefined` 时用无参 `effectiveFeatures()` 为新建 `single_thread` Agent 展开 `proactive_planning: true`）、`apps/im-server/src/task-graphs.ts#L31-L32` 以及 `apps/node/src/configuration.ts#L172`（存量未写 `work_mode` 的本地记录在 `candidate.work_mode === undefined` 时若落入默认 `'global'`，将直接违反 `design.md#L14`“存量未写 `work_mode` 继续按 `single_thread` 解析”的兼容承诺）。
  3. **Web / iOS 新建页与共享编辑器漏改 + 错误 i18n 路径**：`design.md#L18,#L242` 仅列入 `agent-detail-page.tsx`、`i18n/{en,zh-CN}.json` 和 `AgentConfigView.swift`：① 仓库实际中文语言包路径为 `src/IM/frontend/src/i18n/zh.json`（**不存在 `zh-CN.json`**）；② 遗漏 `capability-editor.tsx#L35`（硬编码 `personal || feature.key !== "proactive_planning"`）、`agent-create-page.tsx#L495,#L803-L816,#L1003` 与 iOS 新建页 `AgentsView.swift#L419-L426,#L458` + `AgentModels.swift#L168`（新建默认 `global` 时已写入 `features.proactive_planning = true`，切换为 `single_thread` 时未隐藏或未剥离提交键）。
- **未修后果**：
  - 在 `single_thread` 助手详情页关闭 `task_graph` 或 `cron_scheduling` 时，`control.ts#L219` 会按默认 `'global'` 认定其隐式开启了 `proactive_planning`，抛出 `required_by_feature: ['proactive_planning']` 拒绝保存（而界面上 `single_thread` 根本不展示 `proactive_planning` 开关，用户陷入死锁），直接违反 `spec.md#L158` 与 `specs/gateway/agent-capabilities.md#L104`；
  - 新建页切换至 `single_thread` 或通过 API 创建 `single_thread` Agent 会向后端持久化非法的 `proactive_planning: true`；存量缺省 `work_mode` 节点记录在本地校验时发生语义翻转。
- **修改建议**：
  1. 补齐 `node-rpc.ts`、`im-server/src/{agent-creation,agent-settings,control,task-graphs,personal-agent-creation}.ts`、`apps/node/src/{capabilities,configuration,main}.ts`、`dsh-integration/src/{index,capability-state}.ts` 全链路 `modes` 透传与 `work_mode` 传参；特别注意 `apps/node/src/configuration.ts` 对存量缺省 `work_mode` 须显式按 `'single_thread'` 求值而非落入 `'global'` 默认值，且 `validateCapabilities` / `createAgent` 对 `single_thread` 拒绝或剥离 `proactive_planning`。
  2. 将 `capability-editor.tsx`、`agent-create-page.tsx`、`im-agent-config-api.ts`、`AgentsView.swift`、`AgentModels.swift`、`CapabilitySelection.swift` 纳入设计与 M1 范围，并将 `i18n/zh-CN.json` 修正为 `src/IM/frontend/src/i18n/zh.json`。

---

#### `R1-W1` [WARNING] 非 PA Global Agent 执行 `Dreaming.refreshSources` 会踩中 `documents.sourcesPending()` 未刷新陷阱，导致 `Dreaming` 抛错停摆

- **具体位置**：
  - `design.md#L16,#L33,#L82,#L142-L144`
  - 关联生产代码：`packages/dsh-integration/src/knowledge/dreaming.ts#L284-L299,#L318-L320,#L636`、`packages/dsh-integration/src/knowledge/memory-documents.ts#L221-L236,#L581`、`packages/personal-assistant/src/global-agent.ts#L931-L948`
- **证据与机理**：
  - `Dreaming.refreshSources(config)`（`dreaming.ts#L284-L299`）当前在调用 `memory.sources.refresh` 前无条件执行 `await this.documents.sourcesPending(config.agentId)`，将内存态 `sourcesPending` 标为 `true`；该标志只能由 `knowledge.sources.sync` 清零（`memory-documents.ts#L232`），而 `knowledge.sources.sync` 仅在 PA 的 `refreshPersonalSources`（读取 `pa.sources`）中被调用。
  - 若 `Dreaming` 进入 `#L320` 时 `eligibility.sourcesPending` 仍为 `true`，会立即抛出 `Error('Source eligibility has not been refreshed.')`（同时 `memory_maintenance(status)` `#L636` 卡死在 `source_eligibility_pending`）。普通 Global Agent 没有 `pa.sources` 资格表（`design.md#L23`），一旦 `refreshSources` 对其置位 `sourcesPending` 就会永久报错。
- **未修后果**：非 PA Global Agent 每晚 `03:00` `Dreaming` 均因 `Source eligibility has not been refreshed.` 失败，点卡预取与记忆校准无法落盘，还会拖慢等待 `Dreaming` 完成的 `proactive_nightly` 直至重试耗尽降级。
- **修改建议**：在 `design.md` 明确 `Dreaming.refreshSources` 与 `GlobalAgent.execute('memory.sources.refresh')` 的角色分支契约：仅 `config.personal` 调用 `documents.sourcesPending()` 与 `refreshPersonalSources()`；对 `!config.personal && config.mode === 'global'`，当 `includePendingTaskContext === true` 时仅调用 `taskContext.peekPendingForDreaming` 返回 `{ refreshed: true, pendingTaskContext }`，不置位 `sourcesPending`。

#### `R1-W2` [WARNING] 内置 `nano-proactive-care`（及 `nano-memory`）Skill 现行正文与普通 Global 的原会话闭环、低噪静默挂板及 `[Pending Proactive Handoff]` 协议冲突

- **具体位置**：
  - `design.md#L16-L17,#L74,#L160,#L186,#L216`
  - 关联生产代码：`packages/personal-assistant/assets/skills/nano-proactive-care/SKILL.md#L1-L62`、`packages/personal-assistant/assets/skills/nano-memory/SKILL.md#L12,#L16-L18,#L34-L40`
- **证据与机理**：
  - `design.md#L160` 规定普通 Global 主会话的常驻 `nano-global-mode` 提示模型“需要详细主动筹划方法时按需加载 `nano-proactive-care`”，并在 `#L74,#L160,#L186` 约定使用 `[Pending Proactive Handoff]` `notes` 块且常规 `proposed` 卡严禁创建 `09:00` 早报 `schedule`。
  - 但现行 `nano-proactive-care/SKILL.md` frontmatter 标注 `"Root PA only"`（`#L3`），正文写死：① 在 `"the owner's private PA conversation"` 创建 `proposed` 卡与发送早报（`#L38,#L50`）；② 无固定早间日程但产出了新 `proposed` 卡时**创建 `09:00` 一次性早报 `schedule_create`**（`#L43`）；③ `notes` 交接标题固定为 `[Pending Morning Brief]`（`#L42,#L49,#L55`）。同时 `nano-memory/SKILL.md#L12,#L16,#L38` 也写死“PA 的 `knowledge/proactivity-signals.md`”与“PA 的 `MEMORY.md`”。
  - `design.md` 虽将两份 `SKILL.md` 列入涉及范围表（`#L16`），但正文未说明如何拆分或组织 PA vs 普通 Global 数字员工的差异化章节与 `notes` 协议键名。
- **未修后果**：若普通 Global Agent 加载未彻底分清角色边界的 `nano-proactive-care`，模型会收到与 `<proactive-nightly-wake>` 正面矛盾的指导，导致把团队群事项塞进管理员私聊、为常规 `proposed` 卡创建 `09:00` 早报刷屏，或因 `[Pending Morning Brief]` vs `[Pending Proactive Handoff]` 键名不一致导致周期汇报漏消费。
- **修改建议**：在 `design.md` 第 4 节补充 `nano-proactive-care/SKILL.md` 与 `nano-memory/SKILL.md` 的改写契约：更新 frontmatter 适用范围，将共享原则（两阶段时机、四分栏禁区、发言前未读核实、`proactivity-signals.md` 前台禁读）与角色专属分支（**Bound PA**：主人私聊、`[Pending Morning Brief]`、有新卡可建早报；**Team/Private Global Agent**：原 `conversation_id` 归属、按会话索引的 `[Pending Proactive Handoff]`、常规卡静默挂板仅急需备料/时效风险建工作时段一次性 `schedule`、两层记忆与多人作用域护栏）显式分节写清。

#### `R1-W3` [WARNING] 普通 Global 无人值守主动轮次（尤其场景二无前序人类聊天交办）在 `NanoApproval` 下的工具审批放行边界未核实，且 E2E 漏覆盖场景二

- **具体位置**：
  - `design.md#L138-L148,#L191-L196,#L242`；对照 `spec.md#L73-L75,#L105-L108`
  - 关联生产代码：`packages/dsh-integration/src/policy/approval.ts#L86-L93,#L124-L126,#L159-L179`、`packages/dsh-integration/src/index.ts#L487`、`packages/dsh-integration/src/policy/sources.ts#L43,#L119`、`packages/product-contracts/src/approval.ts#L19-L23`
- **证据与机理**：
  1. 在 `NanoApproval.review()`（`approval.ts#L159-L166`）中，`task_graph` 仅 `list`/`get` 免审直通，`schedule_*` 仅 `schedule_list`/`schedule_history` 免审直通；`task_graph(create/apply)` 与 `schedule_create/update/delete` 必须经过自动审批分类器（默认 `rules: 'codex'` Guardian 或 `rules: 'nano'` CC 分类器）。
  2. `proactive_review` 与 `proactive_nightly` 在 `NanoApproval.route()`（`approval.ts#L90`）中属于 `'unattended'`，默认 `unattendedFallback: 'deny'`（`product-contracts/src/approval.ts#L21`），且 `index.ts#L487` 对 `config?.mode === 'global'` 无人工审批弹窗兜底。
  3. 尤其在 `spec.md` **场景二**（无前序聊天，纯依据 `.nanoassistant/ROLE.md` 长期职责在夜间自发向目标业务群创建 `proposed` 卡或工作时段风险提醒 `schedule_create`）中，会话历史里没有任何人类消息直接授权该动作，且 `.nanoassistant/ROLE.md` 属于 `runtime-context` 快照，在审批转录（`sources.ts#L43,#L119`）中被省略。`design.md` 未分析默认审批策略是否会拒绝此类无人值守 `task_graph` / `schedule_create` 调用，且 `verify_global_agent_proactivity_24h.py` 的三段式 E2E 设计（`design.md#L192-L195`）也未覆盖场景二（无前序对话纯职责归属目标业务群）。
- **未修后果**：默认开启 `approval` 的普通 Global Agent 在无人值守夜间筹划（特别是无前序聊天的纯职责巡检立卡或建工作时段提醒）时可能被 `NanoApprovalDenied` 拦截，导致场景二在真实环境失灵且被测试漏放。
- **修改建议**：核实并明确 `proactive_review` / `proactive_nightly` 下 `NanoApproval` 对 `task_graph`（至少 `status="proposed"` 候选卡创建/过期关闭与已有事项原位记账）及 `schedule_*` 的策略表现或宿主证据供给（例如是否需要将 `.nanoassistant/ROLE.md` 纳入审批证据或明确策略规则），并在 `verify_global_agent_proactivity_24h.py`（或集成测试）中补齐 `spec.md` 场景二的端到端验证。

---

### Recommendations (`NIT`)

- **`R1-R1` [NIT] 统一 `TaskGraphService` 写入侧与 `focus(scope='mine')` 读取侧的 `isDirectWithAgent` 参与者谓词**：
  `design.md#L119` 在自动补全 `proposed_for_user_id` 时限定「`type === 'direct'` 且参与者恰好为当前 Agent + 唯一有效真人成员 `U`」，而 `#L121` 在 `focus` 读取侧写为「`user` 为参与者且对端参与者为 `agent:*` 身份」。建议在实现时抽成同一个辅助函数（校验 `type === 'direct'` 且两名参与者恰好为 1 名有效真人 `U` + 1 名 `agent:*`），保证写入补全与历史存量读取口径完全一致。
- **`R1-R2` [NIT] 明确新建页 `global <-> single_thread` 往返切换时的默认开关恢复行为**：
  `design.md#L18` 指出在新建/编辑页切换为 `single_thread` 时隐藏并剥离 `proactive_planning`；建议针对新建页补充说明：若用户在提交前从 `global` 切到 `single_thread` 后又切回 `global`（且未手动关闭过 `proactive_planning`、`task_graph` 仍开启），应恢复 `global` 的默认开启态，避免一次模式试切导致新建出的 Global Agent 意外关闭主动筹划。


### Author Resolutions

- **`R1-C1` [CRITICAL] — `accepted`**：核实确认 `packages/personal-assistant/src/tool-references.ts` 的 `task_graph` 分支此前仅映射 `target`/`conversation_id` 与消息引用，未解析或投影 `u_xxxxxx` 短用户 ID。已将 `tool-references.ts` 与 `packages/dsh-integration/src/features/task-graph-schema.ts` 纳入 `design.md`（涉及范围、关键决策 2、接口与数据流 §2 及 M1 范围/退出标准），明确对顶层及 `operations[]` 中的 `proposed_for_user_id`、`assignee`（`type === 'user'`）、`assignee_id`（`assignee_type === 'user'`）与 `wait.asked_user_id` 执行 `u_xxxxxx <-> UUID` 双向映射，并更新 `task-graph-schema.ts` 的 1v1 私聊参数说明。
- **`R1-C2` [CRITICAL] — `accepted`**：核实确认 `dreaming.ts` 对 `single_thread` 同样运行 `Dreaming`，二分 `consolidationPrompt(personal: boolean)` 会污染 `single_thread` 并触发 `!proactiveCalibration` 的观察池门禁回滚。已在 `design.md`（涉及范围、关键决策 4、接口与数据流 §4 及 M1 范围/退出标准）将记忆整理提示词与门禁升级为 `'personal' | 'global_expert' | 'single_thread_expert'` 三态，确保 `single_thread_expert` 不注入 `<bound_administrator>`、不内联或允许 `proactivity-signals.md`、不要求 `## 主动性与介入偏好`。
- **`R1-C3` [CRITICAL] — `accepted`**：核实确认 `im-server` 白名单过滤、各端 `definitionsForRole` 调用点遗漏 `work_mode`、Web/iOS 新建与共享能力编辑器漏列及 `zh.json` 路径笔误。已在 `design.md`（涉及范围、关键决策 1、接口与数据流 §1、M1 范围/退出标准）与 `specs/im/agents-nodes.md` 补齐 `product-contracts/src/node-rpc.ts`、`im-server/src/{agent-creation,agent-settings,control,personal-agent-creation,task-graphs}.ts`、`apps/node/src/{capabilities,configuration,main}.ts`、`dsh-integration/src/{capability-state,index}.ts`、`IM/frontend`（含 `im-agent-config-api.ts`、`capability-editor.tsx`、`agent-create-page.tsx`、`i18n/zh.json`）及 `IM/ios`（含 `AgentModels.swift`、`CapabilitySelection.swift`、`AgentsView.swift`）的全链路 `modes` 透传与 `work_mode` 传参（存量缺省 `work_mode` 本地记录显式维持 `'single_thread'`，新建 `single_thread` 不展开 `proactive_planning`）。
- **`R1-W1` [WARNING] — `accepted`**：核实确认 `Dreaming.refreshSources` 若对非 PA Global 置位 `documents.sourcesPending` 会因无 `pa.sources` 同步卡死在 `Source eligibility has not been refreshed.`。已在 `design.md`（涉及范围、关键决策 5、接口与数据流 §3/§4 及 M1 退出标准）明确仅 `config.personal` 置位 `sourcesPending`，非 PA `mode === 'global'` 在 `includePendingTaskContext === true` 时无状态调用 `peekPendingForDreaming`。
- **`R1-W2` [WARNING] — `accepted`**：核实确认现行 `nano-proactive-care/SKILL.md` 与 `nano-memory/SKILL.md` 写死 PA 私聊投递、有卡即建 `09:00` 早报及 `[Pending Morning Brief]` 键名。已在 `design.md`（关键决策 3、接口与数据流 §4）与 `dsh-integration/src/capabilities.ts` 明确双角色分节改写契约（`Bound PA` 用 `[Pending Morning Brief]`，`Global Digital Employee` 用 `[Pending Proactive Handoff: <target>]` 且常规卡静默挂板，并对 worker 与 `single_thread` 屏蔽 `nano-proactive-care`）。
- **`R1-W3` [WARNING] — `accepted`**：核实确认 `NanoApproval` 的 `sources.ts` 此前省略 `runtime-context` 中的 `.nanoassistant/ROLE.md`，导致场景二（无前序聊天纯职责立卡/建提醒/发群预警）在尤其无本地 `read` 工具的 `CC` 分类器下缺少长期职责证据。已在 `design.md`（涉及范围、关键决策 5、接口与数据流 §3/§5、契约层增量、M1 范围/退出标准）及新增 `specs/gateway/tool-approval.md` 明确：不豁免写入/调度/外发审批门禁，由宿主将校验有效的 `.nanoassistant/ROLE.md` 纳入 `<agent_instructions>` 作为长期职责依据，并在 `verify_global_agent_proactivity_24h.py` 补齐场景二端到端验证。
- **`R1-R1` [NIT] — `accepted`**：已在 `design.md` 接口与数据流 §2 统一抽取 `directHumanPeerWithAgent(conversationId)` 辅助谓词供 `TaskGraphService` 写入补全与 `focus(scope='mine')` 读取共用。
- **`R1-R2` [NIT] — `accepted`**：已在 `design.md` 接口与数据流 §1 与 `specs/im/agents-nodes.md` 明确新建页 `global -> single_thread -> global` 往返切换时恢复默认开启态（除非用户在 `global` 下显式关过该项或关闭了 `task_graph`）。


---

## Round 2

### Metadata

- **reviewer**: `change-design-reviewer` + `agent-context-review` (independent subagent `67e71cea-d1d7-4ef2-bfa5-7a664c252db5`)
- **target**: `docs/changes/feat-805-global-agent-proactivity/{design.md,specs/gateway/tool-approval.md,specs/im/agents-nodes.md}` @ branch `unit/feat-805-global-agent-proactivity`
- **review_mode**: `delta`
- **mode_reason**: `retained_from: Round 1` — `spec.md`、`M1-global-agent-proactivity/.gitkeep` 及另外 7 份 `delta-spec`（`specs/gateway/{global-agent,agent-capabilities,personal-agent,spec}.md`、`specs/im/{task-graphs,personal-agent,spec}.md`）与跨包单向依赖、前缀缓存不静默重写底座未变，直接继承 Round 1 已核实结论；本轮聚焦核查 Round 1 全部 8 项问题的闭环质量，并对本轮修订的 `design.md`、`specs/im/agents-nodes.md` 及新增 `specs/gateway/tool-approval.md` 的代码波及面做独立深挖。
- **started_at**: `2026-11-27T22:32:32+09:00`
- **completed_at**: `2026-11-27T22:41:30+09:00`
- **duration**: `8m58s`

### Verdict

- **Conclusion**: **Changes Requested** (`Issues Found`)
- **Severity Counts**: `CRITICAL: 0` | `WARNING: 2` | `NIT: 0`

---

### Coverage 与证据

- **继承范围（`retained_from: Round 1`）**：跨包单向依赖红线（`SPEC.md`）、主会话 `NoSilentPrefixRewrite` 缓存前缀保护策略、存量配置 SHA-256 指纹不漂移机制，以及未发生变更的 7 份 `delta-spec`（含 `gateway/spec.md` 与 `im/spec.md` 的 Requirement 计数与场景完整性）保持有效。
- **本轮增量核查证据**：
  1. **新增 `specs/gateway/tool-approval.md` 与 `NanoApproval` 安全边界核实**：对照 `docs/specs/gateway/tool-approval.md`（共 11 条 Requirement，修改其中第 2 条 `#L46` 与第 6 条 `#L142`，计数保持 `11` 不变，无需再改 `specs/gateway/spec.md`），全部既有 Scenario 原文完整保留。回到生产代码核查自提权风险：`packages/dsh-integration/src/policy/file-approval.ts#L11` 已将 `.nanoassistant` 列为受保护目录，`workspaceFileAllowed`（CC）与 `codexFileAllowed`（Codex）均拒绝免审写入 `.nanoassistant/ROLE.md`；`DocumentMemory.readRole`（`document-memory.ts#L282-L287`）与 `role-document.ts#L13-L29` 校验真实工作区归属、拒绝符号链接、过滤默认未设定占位符与 `> 2,000` 码元超长文件；且在 `CodexApproval` 中，`{ agent_instructions: ... }` 进入 `evidence` 首部（`codex-context.ts#L48,#L60` 视为 `required` 历史项），一旦 `ROLE.md` 变更会导致 `ReviewSession`（`review-session.ts#L93,#L103`）`prefix(checkpoint.rows, serialized)` 失配并自动触发 `rebuild`，不会残留旧职责缓存。该设计安全闭合。
  2. **全链路 `modes: ['global']` 与 `specs/im/agents-nodes.md` 核实**：`design.md#L13-L15,#L18,#L88-L119,#L262` 已补齐 `node-rpc.ts`、`im-server` 五处模块、`apps/node` 三处模块、`dsh-integration` 两处模块、Web 四处组件与 `i18n/zh.json`、iOS 四处文件，并明确存量缺省 `work_mode` 本地记录维持 `'single_thread'` 及新建页往返切换恢复逻辑。
  3. **Agent Context 增量交叉核验（新检出 2 项 `WARNING`）**：顺着本轮新增的「`<= 8` 位短引用红线」（`design.md#L24`）与「`nano-proactive-care` 挂入普通 Global 主会话指引」（`design.md#L17,#L172,#L187`）回查真实代码链路，发现两处尚未闭合的实现断口：① `Dreaming` 预取的 `pendingTaskContext` 未经 `ToolReferences` 投影，携带 36 位原始用户 UUID 与 34 位原始会话 ID，无法与 `<bound_administrator>u_xxxxxx</bound_administrator>` 匹配（`R2-W1`）；② 通过 API 或 PA `agent_creation` 新建（以及存量 `explicit_allowlist`）的普通 Global Agent 因 `nano-proactive-care` 非 `default_on` 而被运行时白名单屏蔽，造成主会话悬空引用（`R2-W2`）。

---

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核查证据 | 状态 |
| --- | --- | --- | --- |
| `R1-C1` | `accepted` | `design.md#L16,#L71-L72,#L122-L125,#L262` 已纳入 `tool-references.ts` 与 `task-graph-schema.ts`，完整覆盖 `task_graph` 顶层及 `operations[]` 内 `proposed_for_user_id`、`assignee`（`type === 'user'`）、`assignee_id`（`assignee_type === 'user'`）、`wait.asked_user_id` 的 `u_xxxxxx <-> UUID` 双向解析与结果投影。 | `closed` |
| `R1-C2` | `accepted` | `design.md#L17,#L79-L81,#L173,#L179-L185,#L262` 已将文档记忆与 `Dreaming` 拆分为 `'personal' \| 'global_expert' \| 'single_thread_expert'` 三态，`single_thread_expert` 不注入 `<bound_administrator>`、不内联或允许 `proactivity-signals.md`、不要求 `## 主动性与介入偏好`。 | `closed` |
| `R1-C3` | `accepted` | `design.md#L13-L15,#L18,#L88-L119,#L262` 与 `specs/im/agents-nodes.md#L15-L18` 已补齐 `im-server`、`apps/node`、`dsh-integration`、Web IM（修正为 `i18n/zh.json`）与 iOS 全链路 `modes` 透传和 `work_mode` 传参，消除 `single_thread` 关闭 `task_graph` 死锁与默认脏键注入。 | `closed` |
| `R1-W1` | `accepted` | `design.md#L16-L17,#L84,#L149,#L180,#L262` 已明确仅 `config.personal` 调用 `documents.sourcesPending()`，非 PA `mode === 'global'` 无状态调用 `peekPendingForDreaming`，消除 `Source eligibility has not been refreshed.` 报错。 | `closed` |
| `R1-W2` | `accepted` | `design.md#L16-L17,#L75-L76,#L186-L188` 已明确拆分 `nano-proactive-care` 与 `nano-memory` 的 `Bound PA`（`[Pending Morning Brief]`）与 `Global Digital Employee`（`[Pending Proactive Handoff: <target>]` + 常规卡静默挂板）分节契约，消除了正文指令冲突（Skill 默认可见性遗漏单列为 `R2-W2`）。 | `closed` |
| `R1-W3` | `accepted` | `design.md#L17,#L84,#L163-L165,#L212,#L228,#L262` 与新增 `specs/gateway/tool-approval.md` 已明确将宿主校验有效的 `.nanoassistant/ROLE.md` 注入 `<agent_instructions>` 作为长期职责依据（不放宽审批门禁），并在 `verify_global_agent_proactivity_24h.py` 补入场景二验证。 | `closed` |
| `R1-R1` | `accepted` | `design.md#L15,#L72,#L126-L129` 已统一抽取 `directHumanPeerWithAgent(conversationId)` 供写入补全与 `focus(scope='mine')` 共用。 | `closed` |
| `R1-R2` | `accepted` | `design.md#L18,#L118` 与 `specs/im/agents-nodes.md#L17` 已明确新建页 `global -> single_thread -> global` 往返切换自动恢复默认开启态的条件。 | `closed` |

---

### Issues

#### `R2-W1` [WARNING] `pendingTaskContext`（及任务上下文通知）向 `Dreaming` 暴露原始 36 位用户 UUID 与 34 位会话 ID，无法与 `<bound_administrator>u_xxxxxx</bound_administrator>` 匹配且违背短引用红线

- **具体位置**：
  - `design.md#L16,#L24,#L149-L151,#L180,#L184`
  - 关联生产代码：`packages/personal-assistant/src/inbox.ts#L645-L658`（`systemContextEntry`）、`packages/personal-assistant/src/task-context.ts#L106-L136`（`peekPendingForDreaming`）、`packages/personal-assistant/src/global-agent.ts#L932-L949`（`memory.sources.refresh`）、`packages/dsh-integration/src/knowledge/dreaming.ts#L536-L544`（`Dreaming.renderInput`）、`apps/im-server/src/task-notifications.ts#L91-L100`
- **证据与机理**：
  1. 本轮 `design.md#L24` 明确规定：「所有由模型读写的产品用户/会话/消息标识保持 `<= 8` 位短引用（如 `u_xxxxxx`、`c_xxxxxx`），由宿主 `ToolReferences` 负责与中心 UUID 双向映射」；且 `design.md#L184` 为 `global_expert` `Dreaming` 注入的管理员身份为 `<bound_administrator>u_xxxxxx</bound_administrator>`（仅含 `ToolReferences.userRef` 投影短 ID）。
  2. 但核查 `TaskContext.peekPendingForDreaming`（`task-context.ts#L119-L135`）与 `inbox.systemContextEntry`（`inbox.ts#L652-L657`）可见：任务状态通知直接将原始 `input.conversation_id`（34 位 `c_<32hex>`）与 `input.message.sender` / `actor`（含 **36 位原始用户 UUID** `id` / `user_id`，以及正文 `<mention type="user" target_id="<UUID>"/>`）序列化进 `item.conversationId` 和 `item.text`，未经 `ToolReferences` 投影便由 `Dreaming.renderInput`（`dreaming.ts#L537-L543`）原样拼入 `## Unconsumed task context updates`（注：前台 `TaskContext.prepare` 注入主会话的 `[task context]` 同样含上述裸 UUID）。
  3. PA 在 `feat-793` 中未暴露该问题，是因为 PA 候选卡仅在主人单人私聊由唯一主人操作；而多协作者 Global Agent 在 `Dreaming` 中必须根据点卡事件判断「操作者是否为 `<bound_administrator>`」以及「该反馈作用于哪个协作者 `u_xxxxxx` / 哪个会话 `c_xxxxxx`」（`design.md#L80,#L184`）。
- **未修后果**：
  - 当绑定管理者或普通协作者在任务焦点台纯点击「批准 / 先存着 / 不采纳」（未发聊天消息）时，`Dreaming` 看到的 `actor.id` 是 36 位裸 UUID，与 `<bound_administrator>u_xxxxxx</bound_administrator>` 及历史聊天中的 `u_xxxxxx` / `c_xxxxxx` 完全对不上，导致管理员与协作者权限护栏失准；
  - `Dreaming` 会把 34/36 位原始内部 ID 写入 `proactivity-signals.md` 或 `MEMORY.md` 的单行作用域条件，破坏 `design.md#L24` 短引用契约并使主会话后续无法与 `inbox` 短 ID 关联。
- **修改建议**：在 `GlobalAgent.execute('memory.sources.refresh')` 返回 `pendingTaskContext` 前（置于 PA `allowed.has(item.conversationId)` 原始会话过滤之后，且保持 `item.messageId` 原始消息 ID 不变以维持 `dreaming.ts#L345` 的 `integratedTaskContextIds` / `batchTaskIds` 去重），用 `store.toolReferences` 将面向模型渲染的 `conversationId` 及 `item.text` 中的 `conversation_id`、`actor.id` / `actor.user_id` 与 `<mention target_id="..."/>` 投影为 `c_xxxxxx` / `u_xxxxxx`（并建议同步在 `inbox.systemContextEntry` 或 `TaskContext` 渲染文本层统一投影模型可见字段，同时保留内部鉴权所需的原始 `conversationId`）。

#### `R2-W2` [WARNING] 通过 REST API 或 PA `agent_creation` 创建的普通 Global Agent（及存量白名单 Global Agent）未启用 `nano-proactive-care` Skill，导致常驻指引出现悬空 Skill 引用

- **具体位置**：
  - `design.md#L14-L17,#L100-L105,#L172,#L187`
  - 关联生产代码：`apps/node/src/capabilities.ts#L75-L78`、`apps/im-server/src/agent-creation.ts#L240-L243,#L263-L266`、`apps/im-server/src/personal-agent-creation.ts#L54-L55`、`packages/product-contracts/src/configuration.ts#L19`、`packages/dsh-integration/src/capabilities.ts#L177-L183`
- **证据与机理**：
  1. `design.md#L172` 在普通 Global 主会话的常驻 `nano-global-mode` 中提示模型“需要详细方法时按需加载 `nano-proactive-care`”，并在 `#L17,#L187` 说明在 `dsh-integration/src/capabilities.ts` 对 `isWorkWorker || config.mode !== 'global'` 屏蔽该 Skill。
  2. 但核查 Skill 默认选中与运行时过滤链路发现：
     - `apps/node/src/capabilities.ts#L75-L78` 仅将内置 `nano-memory`、`nano-role-agreement`（及 PA 的 `tripai-skill`）标为 `default_on: true`，`nano-proactive-care` 的 `default_on` 为 `false`，且 `proactive_planning.requires.skills` 为 `[]`（`design.md#L104`）；
     - 虽然 Web/iOS 新建页默认使用 `skills_selection_mode: "explicit_denylist"`（`skills: []`），但通过 **`POST /im/v1/nodes/:id/agents` 省略 `skills` 创建**（`agent-creation.ts#L240-L242,#L263-L266` 仅收集 `s.default_on`，经 `configuration.ts#L19` 归一化为 `explicit_allowlist`——含 E2E 脚本常用创建方式）、通过 **PA 的 `agent_creation` 工具创建**（`personal-agent-creation.ts#L54-L55` 固定推荐 `explicit_allowlist` 且仅含 `default_on` + `requires.skills`），以及**存量已处于 `explicit_allowlist` 的 Global Agent**，其 `skillSelection.names` 均不包含 `nano-proactive-care`；
     - 运行时 `dsh-integration/src/capabilities.ts#L180-L182` 对 `explicit_allowlist` 严格拦截未列入 `names` 的内置 Skill（PA 之所以不受影响是因为 `personal-agent.ts#L587` 固定使用 `default_discovery`）。此外，当管理者关闭 Global Agent 的 `proactive_planning` 时，`dsh-integration/src/capabilities.ts` 与 `nano-global-mode` 也未联动隐藏 `nano-proactive-care` 指引。
- **未修后果**：通过主人对话委托 PA 创建（`agent_creation`）、API 创建（含 `verify_global_agent_proactivity_24h.py` 若调 REST 建号且未手写 `skills_selection_mode`）或存量白名单升级的普通 Global Agent，会在常驻系统提示词中看到“按需加载 `nano-proactive-care`”，但调用 `skill` 工具时该 Skill 不可见/被拒绝。
- **修改建议**：保持存量配置指纹不变的前提下补齐闭环：① 在 `apps/node/src/capabilities.ts#L75-L78` 对 `!agent || agent.mode === 'global'` 将内置 `nano-proactive-care` 设为 `default_on: true`（`im-server/src/agent-creation.ts` 在 `c.work_mode === 'single_thread'` 且省略 `skills` 时排除该项）；② 在 `dsh-integration/src/capabilities.ts` 与 `global-mode.ts` 按有效 `proactive_planning` 状态联动：仅当 `!isWorkWorker && config.mode === 'global' && effectiveProactivePlanning` 时暴露内置 `nano-proactive-care`（对未显式禁用它的存量 `explicit_allowlist` Global 主会话默认放行，或在 `proactive_planning` 关闭/Skill 被显式禁用时不注入该加载提示）。

---

### Recommendations (`NIT`)

无。


### Author Resolutions

- **`R2-W1` [WARNING] — `accepted`**：核实确认 `InboxStore.systemContextEntry` 与 `TaskContext.peekPendingForDreaming` 此前在任务变更事件 JSON 中原样输出 34 位会话 ID 与 36 位用户 UUID，会导致 `Dreaming` 无法将面板点卡的 `actor.id` 与 `<bound_administrator>u_xxxxxx</bound_administrator>` 或聊天中的 `u_xxxxxx`/`c_xxxxxx` 对齐。已将 `packages/personal-assistant/src/{inbox,task-context}.ts` 纳入 `design.md`（涉及范围、接口与数据流 §2、M1 范围与 `[worker]` 退出标准）及 `specs/gateway/agent-capabilities.md`：在构造模型可见任务事件文本时统一经 `ToolReferences` 将 `conversation_id`、`actor.id`/`actor.user_id`（含 `human_control.actor`）与正文 `<mention target_id="..."/>` 投影为 `c_xxxxxx` / `u_xxxxxx`（兼容在途旧摘要提交），同时保留外层内部 `messageId` 与 `conversationId` 供 `integratedTaskContextIds` 去重、PA `allowed` 过滤及 `Dreaming` `batch.conversations` 来源白名单校验，并在 `PendingTaskContextItem` 附带 `conversationRef` 供 `Dreaming.renderInput` 展示。
- **`R2-W2` [WARNING] — `accepted`**：核实确认 `apps/node/src/capabilities.ts` 未将 `nano-proactive-care` 设为全局模式 `default_on: true`，会导致 REST API 省略 `skills` 新建、PA `agent_creation` 推荐列表及存量 `explicit_allowlist` Global Agent 在运行时被白名单拦截而出现悬空提示。已在 `design.md`（涉及范围、接口与数据流 §4、M1 退出标准）与 `specs/gateway/global-agent.md` 补齐闭环：① `apps/node/src/capabilities.ts` 在 `!agent || agent.mode === 'global'` 下将 `nano-proactive-care` 设为 `default_on: true`（对 `single_thread` 隐藏，且 `im-server/src/agent-creation.ts` 在省略 `skills` 创建 `single_thread` 时剔除）；② `dsh-integration/src/capabilities.ts` 在 `isWorkWorker || config.mode !== 'global' || !effectiveProactivePlanning` 时一律隐藏该 Skill，并对未显式配置 `features.proactive_planning` 的存量 `explicit_allowlist` Global 主会话默认放行内置 `nano-proactive-care`（保留用户显式禁用优先，零配置指纹漂移）；③ `global-mode.ts` 仅在该 Skill 当前有效可用时静态注入加载提示，杜绝悬空引用。


---

## Round 3

### Metadata

- **reviewer**: `change-design-reviewer` + `agent-context-review` (independent subagent `67e71cea-d1d7-4ef2-bfa5-7a664c252db5`)
- **target**: `docs/changes/feat-805-global-agent-proactivity/{design.md,specs/gateway/agent-capabilities.md,specs/gateway/global-agent.md}` @ branch `unit/feat-805-global-agent-proactivity`
- **review_mode**: `delta`
- **mode_reason**: `retained_from: Round 2` — 需求基线 `spec.md`、跨包架构边界、其余 6 份未变动的 `delta-spec` 及 Round 1 已闭环的 8 项设计结论保持不变，直接继承前两轮核实结论；本轮聚焦核查 `R2-W1` 与 `R2-W2` 的闭环严密性，并对照真实源码复核本轮新增的 `InboxStore.commitSystemContext` 在途摘要兼容、`Dreaming` 会话目录、`nano-proactive-care` 全入口可见性与 `global-mode.ts` 前缀稳定性。
- **started_at**: `2026-11-27T22:48:58+09:00`
- **completed_at**: `2026-11-27T22:53:30+09:00`
- **duration**: `4m32s`

### Verdict

- **Conclusion**: **Approved**
- **Severity Counts**: `CRITICAL: 0` | `WARNING: 0` | `NIT: 1`

---

### Coverage 与证据

- **继承范围（`retained_from: Round 2`）**：`spec.md` 全部澄清决策（Q1–Q3）、4 大用户场景、4 项验收标准与非目标覆盖、`SPEC.md` 跨包单向依赖红线、`modes: ['global']` 全端透传、1v1 Agent 私聊 `directHumanPeerWithAgent` 读写统一、三态 `Dreaming` 隔离、`NanoApproval` `.nanoassistant/ROLE.md` 指令证据安全边界，以及全部 9 份 `delta-spec` 的 Requirement 计数与场景完整性均保持有效。
- **本轮增量核查证据**：
  1. **任务上下文短引用同源投影与在途升级兼容（`R2-W1` 波及面）**：对照 `packages/personal-assistant/src/inbox.ts#L645-L679`、`task-context.ts#L98-L160`、`store.ts#L30-L54` 与 `packages/dsh-integration/src/knowledge/dreaming.ts#L335-L355,#L536-L544` 核实：`design.md#L16,#L125` 与 `specs/gateway/agent-capabilities.md#L37` 将模型可见文本内的 `conversation_id`、`actor.id`/`actor.user_id`（含 `human_control.actor`）及 `<mention target_id="..."/>` 统一经 `ToolReferences` 投影为 `c_xxxxxx` / `u_xxxxxx`，同时保留外层 `inputId`（原始 `messageId`）与 `conversationId`（原始 34 位会话 ID），并在 `commitSystemContext` 兼容比对升级前已 `prepared` 条目的新旧投影摘要。该方案既让 `Dreaming` 看到的点卡操作者与 `<bound_administrator>u_xxxxxx</bound_administrator>` 及聊天记录完全同源，又确保 `integratedTaskContextIds` 去重、PA `allowed` 来源过滤与滚动升级消费回执零回归。
  2. **`nano-proactive-care` 全入口默认启用、状态联动与 `NoSilentPrefixRewrite`（`R2-W2` 波及面）**：对照 `apps/node/src/capabilities.ts#L75-L78`、`apps/im-server/src/{agent-creation.ts#L240-L271,personal-agent-creation.ts#L54-L55}`、`packages/dsh-integration/src/{capabilities.ts#L177-L183,global-mode.ts#L39-L84,agent-config.ts#L188-L191,#L230-L240}` 核实：`design.md#L14-L17,#L173,#L188` 与 `specs/gateway/global-agent.md#L9` 覆盖了节点共享/单 Agent 目录投影、`single_thread` 省略 `skills` 创建剔除、存量未显式配置 `features.proactive_planning` 的 `explicit_allowlist` Global 主会话兼容放行（用户显式禁用优先，不改写持久化 JSON 故配置 SHA-256 指纹零漂移），且 `GlobalMode.apply` 在会话挂载时一次性静态生成 `nano-global-mode` 段落文本（日常对话、夜间 `Dreaming` 与 `proactive_*` 唤醒期间零重写，严格满足 `NoSilentPrefixRewrite`）。

---

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核查证据 | 状态 |
| --- | --- | --- | --- |
| `R2-W1` | `accepted` | `design.md#L16,#L125,#L264` 与 `specs/gateway/agent-capabilities.md#L37` 已明确在 `InboxStore.systemContextEntry` / `TaskContext.peekPendingForDreaming` 中将面向模型的会话与人类操作者标识统一投影为 `c_xxxxxx` / `u_xxxxxx`（含 `PendingTaskContextItem.conversationRef` 与 `commitSystemContext` 在途旧摘要兼容），并保留内部原始 `messageId` 与 `conversationId` 供去重和来源过滤。 | `closed` |
| `R2-W2` | `accepted` | `design.md#L14-L17,#L173,#L188,#L264` 与 `specs/gateway/global-agent.md#L9` 已补齐 `apps/node`（`!agent \|\| agent.mode === 'global'` 下 `default_on: true`）、`im-server`（`single_thread` 省略 `skills` 剔除）、`dsh-integration/src/capabilities.ts`（按 `effectiveProactivePlanning` 门控并兼容存量白名单）与 `global-mode.ts`（仅有效可用时静态注入加载提示），彻底消除悬空 Skill 引用。 | `closed` |

---

### Issues

无。

---

### Recommendations (`NIT`)

- **`R3-R1` [NIT] 非 PA Global 的 `Dreaming` `batch.conversations` 同步推入 `conversationRef` 以对齐只读会话目录**：
  在 `packages/dsh-integration/src/knowledge/dreaming.ts#L354,#L588` 中，PA 依赖 `status.sources?.allowed`（原始会话 ID），而非 PA Global（`status.sources === undefined`）回退使用 `run.batch.conversations` 生成首轮提示中的 `IM source directory (data)`（`dreaming-agent.ts#L113`）及只读 `conversations(target=...)` 白名单（`dreaming-history.ts#L123`），且 `sourceConversations`（`memory-source-view.ts#L72-L74`）从主会话工具结果提取的已是 `c_xxxxxx`。实施时建议在 `dreaming.ts#L354` 对 `!config.personal` 推入 `item.conversationRef ?? item.conversationId`（PA 仍保持原始 `item.conversationId`），使非 PA Global 在纯点卡批次下的 `IM source directory (data)` 与 `Dreaming.renderInput` 同样保持纯 `c_xxxxxx` 短引用一致。


### Author Resolutions

- **`R3-R1` [NIT] — `accepted`**：核实确认非 PA Global（`!config.personal`）在 `dreaming.ts#L588` 回退使用 `run.batch.conversations` 作为 `IM source directory (data)` 与只读 `conversations(target=...)` 白名单，而 `PendingTaskContextItem.conversationRef` 已在 `design.md#L16,#L125` 纳入契约。M1 实施 `dreaming.ts#L354` 时对 `!config.personal` 推入 `item.conversationRef ?? item.conversationId`（PA 保持原始 `item.conversationId`）；已获批的 `spec.md`、`design.md`、`specs/**` 与 `M1-global-agent-proactivity/.gitkeep` 保持冻结无实质修改。
