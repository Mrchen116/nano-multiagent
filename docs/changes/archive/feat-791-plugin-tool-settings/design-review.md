# Design Review: feat-791-plugin-tool-settings

## Round 1

### Metadata

- **Change Unit**: `feat-791-plugin-tool-settings` (`Full`)
- **Round**: `Round 1`
- **review_mode**: `full`（首次 Gate 2 独立设计审查；完整核对 [spec.md](spec.md)、[design.md](design.md)、两份 delta-specs、受影响长青契约、生产代码真实装配链、Agent Context 设计影响与前端/iOS 体验及验收路径）
- **started_at**: `2026-11-26T10:43:30+09:00`
- **completed_at**: `2026-11-26T11:01:30+09:00`
- **duration**: `18m 00s`

### Verdict

**Issues Found**（`1 CRITICAL / 3 WARNING / 3 Recommendations`）

整体方案方向清晰：通过 `@nano/product-contracts` 增补默认开启的 `plugin_management` 运行特性解耦 `cordis_inspect_list` / `cordis_inspect_query`、将 `contextTools` 从静态 `fixedTools()` 剥离并按工作区插件动态归属 `source_label`、统一 Web/iOS 全量工具折叠视图与跨 Tab 缓存失效，架构边界符合 `SPEC.md` 与 `AGENTS.md` 红线。但在存量配置无状态推导闭环（D2）、Node 目录投影与运行时挂起状态解耦（D1）、非 Global 模式 `send_message` 保留与脏状态基线归一化（D5）、以及忙碌/异步卸载期间的插件目录缓存竞态（D6）上存在 4 处阻塞性设计缺口，需在进入实施前收口。

---

### Coverage 与证据

#### 1. 现状断言核实（Current-State Assertions vs Production Wiring）

| `design.md` 现状断言 | 生产代码核对位置 | 核实结论 |
|---|---|---|
| `featureDependencies` 当前无 `plugin_management`；`fixedTools()` 默认拼入 `contextTools` | `packages/product-contracts/src/capabilities.ts:27-33, 55-64` | 属实。但 `fixedTools` 中 `send_message` 仅在 `mode === 'global'` 时属于固定工具（第 58 行），D5「剔除所有模式 `fixed_tools`」措辞与非 Global 模式冲突（见 `R1-W2`）。 |
| `dsh-integration` 将 `cordis_inspect_list` / `cordis_inspect_query` 隐藏并绑定 `plugin_manager` 隐式注入 | `packages/dsh-integration/src/capabilities.ts:16-25, 48-54, 65, 85` | 部分属实：实际符号为 `cordisInspectSet` + `allowsCordisInspect()`（非 `hiddenTools`），且 **`apps/node/src/capabilities.ts:50` 另有第二道硬编码过滤**，`design.md` 遗漏了后者（见 `R1-W1`）。 |
| `WorkspaceExtensions` 仅输出 `{name, description, source_group: 'workspace', enabled}`，无插件包来源标签 | `packages/dsh-integration/src/workspace-tools.ts:110-112, 214, 228-235`；`packages/dsh-integration/src/capabilities.ts:68-69` | 属实。`WorkspaceOwner.entries()` 已持有 `bundle.meta?.title ?? bundle.name` 与 `rows[].rowId`（第 232-234 行）。 |
| Web `CapabilityEditor` 将静态工具与插件工具拆成两块 `PillSelector`；`AgentPluginsPanel` 操作后未失效 `['agent-settings', id]` | `src/IM/frontend/src/features/settings/agents/capability-editor.tsx:16-49`；`agent-detail-page.tsx:1367`；`agent-plugins-panel.tsx:66-76` | 属实。同时核对发现 `workspace-tools.ts:311-315` 与 `apps/node/src/main.ts:374` 在插件实际完成卸载前过早广播变更，会污染 IM 5 分钟 `CatalogReads` 缓存（见 `R1-W3`）。 |
| iOS `AgentConfigView` 将静态工具与插件工具分列两块 `FlowLayout`，且硬编码了 `fixedTools` 副本 | `src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift:326-352`；`CapabilitySelection.swift:154-156`；`AgentModels.swift:76-78` | 属实，且 iOS 现有本地 `fixedTools` 漏掉了 `download_attachment`、`personal_sources`、`send_user_message`（见 `R1-W2`）。 |
| `scripts/e2e_catalog.py` 将 `fixed_tools` 拼入持久化 `tool_allowlist` | `scripts/e2e_catalog.py:42` | 属实（`allow = list(dict.fromkeys([*selected_tools, *fixed_tools]))`）。 |

#### 2. 用户拍板约束（Q1–Q4）与技术决策（D1–D6）覆盖核对

- **Q1（新增「插件开发与管理」默认开启 Feature，关联 `plugin_manager`、`cordis_inspect_list`、`cordis_inspect_query`、`nano-plugin-development`；关闭后可独立勾选工具/Skill）**：D1/D2 覆盖正向模型，但存量未迁移 Profile 的局部编辑、UI 展示、预览与 `explicit_allowlist` 边界未闭环（`R1-C1`），Node 目录投影遗漏过滤移除（`R1-W1`）。
- **Q2（不把 Goal、Workflow 抽成新 Feature）**：D1、两份 delta-specs 均保持 Goal/Workflow 原状，未引入范围蔓延。
- **Q3（配置页合并展示全量现役工具、默认折叠显示启用数、点击插件工具弹 2s 轻提示引导去「插件」页）**：D4/D5 覆盖 Web 与 iOS 双端交互模型。
- **Q4（关闭插件后工具立即消失、切回配置页无需手动刷新、历史混入的上下文工具名保存不报 400）**：D3/D5/D6 给出了方向，但存在忙碌/卸载异步阶段的目录缓存竞态（`R1-W3`）与存量污染列表打开即 `dirty` 的基线不对称问题（`R1-W2`）。

#### 3. Delta-Specs 锚点、Scenario 保留与契约文体核对

- **[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md)**：3 个 `MODIFIED` Requirement 标题与 `docs/specs/gateway/agent-capabilities.md`（第 566、835、876 行）逐字精确匹配；原 8 + 6 + 3 = 17 个既有 Scenario 全部保留并增补了独立检查工具与存量平滑承接 Scenario。
- **[specs/im/agents-nodes.md](specs/im/agents-nodes.md)**：3 个 `MODIFIED` Requirement 标题与 `docs/specs/im/agents-nodes.md`（第 659、971、1005 行）逐字精确匹配；原 2 + 5 + 4 = 11 个既有 Scenario 全部保留并增补折叠全量展示与插件联动刷新 Scenario。第 62 行存在一处变更日志口吻“本次”（见 `R1-R2`）。

#### 4. 架构红线与 Milestones 可验证性核对

- **架构边界**：所有改动均位于公开导出与既有跨包边界内（`packages/product-contracts` → `packages/dsh-integration` / `apps/node` / `apps/im-server` / `src/IM/*`），未引入运行时私有导入或跨包相对路径绕过，符合 `SPEC.md` 与 `tests/contract/test_runtime_dependency_contract.py`。
- **Milestones**：M1（契约与 DSH/Node 运行时）→ M2（IM Server 与 Web）→ M3（iOS 与 E2E 脚本）切分合理，验证命令覆盖 Vitest、Node test、Web build、Xcode test 与 pytest。

#### 5. Agent Context 设计审查（`agent-context-review` Design Mode）

- **工具可见性与角色隔离**：根会话与显式 `subagent_fork` 按有效工具选择获得 `cordis_inspect_list` / `cordis_inspect_query`；普通 `subagent` 与 Global `worker` / `worker-fork` 仍由 `userEntryTools` 与 `ToolSelection.refresh()`（`packages/dsh-integration/src/capabilities.ts:19, 90`）拦截，不会越权暴露。
- **审批策略一致性**：`packages/dsh-integration/src/policy/approval.ts:27` 已将 `cordisInspectTools` 列入只读 `safeTools`，而 `plugin_manager` 仍走审批/分类器；独立开启 `cordis_inspect_*` 不会连带放宽写操作权限。
- **上下文自洽性缺口**：
  1. `packages/dsh-integration/src/plugin-development.ts:9` 在 `plugin_manager(action: "describe_api", topic: "service")` 返回给模型的上下文中写死 `"When plugin_manager is enabled, use cordis_inspect_list and cordis_inspect_query..."`。解耦后当用户关闭 `plugin_management` 且仅单独开启 `plugin_manager`（未勾选 `cordis_inspect_*`）时，工具返回正文会直接诱导模型调用未授权工具并触发拒绝错误（已并入 `R1-W1`）。
  2. 系统提示词预览（`configuration.preview`）在存量未迁移草稿上传入物化 `features` 与原始 `tool_allowlist` 会触发依赖校验异常（已并入 `R1-C1`）。

#### 6. 前端体验、原型边界与 Runbook 设计审查（`frontend-experience-review` Design Mode）

- **信息组织与心智模型**：默认折叠 + 已启用工具计数降低了长列表首屏压迫感；展开后合并展示全量现役工具并用既有 2 秒非挤压浮层 `CapabilityToast` 区分「受运行特性锁定」「模式固定基础工具」「插件提供（去插件页关闭 / 需开启 `plugin_manager`）」，消除了“插件已关但配置页仍显示勾选/保存报错”的割裂感。
- **原型边界判断**：本变更完全复用既有 `PillSelector`、`CapabilityToast`、`BehaviorCard` 特性行与 `AgentPluginsPanel`，不涉及新视觉体系或复杂空间编排，**无需补画 `prototype.html`**；建议在 `design.md` 简述免原型理由，并明确折叠头部的无嵌套按钮结构与创建页隐藏「管理插件 →」细节（见 `R1-R3`）。
- **Runbook 完整性**：已采用受控 `./scripts/e2e-up.sh --profile daily --wt "$WT_ROOT"` 与 `trap` 回收契约，但缺少双端改动所需的 iOS 模拟器/组件验收步骤说明（见 `R1-R3`）。

---

### Issues

#### `R1-C1` [CRITICAL] — D2 存量无状态推导在局部编辑、配置展示、提示词预览及 `explicit_allowlist`/无工作区边界上未闭环，会阻断存量 Agent 编辑与节点启动

- **位置**：
  - [design.md](design.md) D2（第 88–95 行）
  - `packages/product-contracts/src/capabilities.ts:47-53, 81-142`
  - `src/IM/ios/NanoIM/Features/Agents/CapabilitySelection.swift:41-133`、`AgentConfigView.swift:381`、`AgentModels.swift:102-106`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:100-110, 193-199`
  - `apps/im-server/src/agent-settings.ts:73`、`personal-agent-creation.ts:53`、`agent-creation.ts:160-173`
  - `packages/dsh-integration/src/index.ts:541, 671`、`workspace-tools.ts:66`；`apps/node/src/main.ts:66`
- **问题机制与后果**：
  1. **`changeCapability` 局部编辑陷阱**：D2 规定仅当 `features?.plugin_management === undefined` 时隐式伴随 `cordis_inspect_list` / `cordis_inspect_query`；一旦 `features.plugin_management` 物化为显式布尔值，校验与运行时均只认显式 `tool_allowlist`。但在 `changeCapability()`（`packages/product-contracts/src/capabilities.ts:113-116` 及 iOS `CapabilitySelection.swift:67-69`）中，`features = effectiveCapabilityFeatures(draft, definitions)` 会立即将 `next.features.plugin_management` 物化为 `true`，而 `let tools = [...draft.tool_allowlist]` 仍拷贝自升级前不含 `cordis_inspect_*` 的原始列表。结果用户在存量 Agent 上点击**任何无关能力**（如开启 `web_search`、切换任意 Skill、关闭 `intelligent_ui`），第 141 行 `validateCapabilities(next, catalog)` 都会因 `next.features.plugin_management === true` 且缺少 `cordis_inspect_*` 判定失败，阻断无关编辑并误弹“需先关闭插件开发与管理”提示。
  2. **受限存量 Agent 的 UI 开关与离线展示误亮**：Web `resolveEffectiveFeatures`（`agent-detail-page.tsx:100-110`）、iOS 开关绑定（`AgentConfigView.swift:381`：`draft.features[feature.key] ?? feature.default_on`）与 IM 离线快照 `configurationDisplay`（`apps/im-server/src/agent-settings.ts:73`）在 `plugin_management === undefined` 时均直接回退 `default_on`（`true`），未走 `effectiveCapabilityFeatures(draft)`。升级前已移除 `plugin_manager` 的受限存量 Agent（如 `tool_allowlist: ['read']`, `features: {}`）在 Web/iOS 配置页会被错误显示为「插件开发与管理：开启」，违反 [spec.md](spec.md) `Scenario: 存量助手平滑承接既有插件管理权限`，且用户修改其他字段保存时会直接触发 `400` 校验错误。
  3. **提示词预览报错**：Web `BehaviorCard.fetchPreview`（`agent-detail-page.tsx:193-199`）与 iOS `AgentDraft.previewPayload`（`AgentModels.swift:102-106`）向 `prompt-preview` 发送物化后的 `features`（`plugin_management: true`）但传原始 `draft.tool_allowlist`（缺 `cordis_inspect_*`），导致 `NanoRuntime` `configuration.preview`（`packages/dsh-integration/src/index.ts:541`）因 `validateCapabilities` 失败抛错。
  4. **`explicit_allowlist` 技能模式与无工作区目录崩溃**：D2 将推导条件写为“未显式禁用 `nano-plugin-development` Skill”，但存量配置或创建链路（`personal-agent-creation.ts:53`、`agent-creation.ts:160-173`）可能处于 `skills_selection_mode: 'explicit_allowlist'` 且未包含 `nano-plugin-development`；同时无 `workspace` 的配置（`workspace-tools.ts:66`）在运行时目录中不注册 `plugin_manager`。若 `effectiveCapabilityFeatures(draft, definitions, catalog)` 不检查 `selected(draft, {kind: 'skill', name: 'nano-plugin-development'}, catalog)` 及可选 `catalog` 中依赖项的实际存在性，`apps/node/src/main.ts:66` 启动加载或 `configuration.prepare`（`index.ts:671`）会直接校验失败阻塞启动。
- **收口要求**：
  - 在 `effectiveCapabilityFeatures(draft, definitions, catalog?)` 中同时核验 `plugin_manager` 已选中、`nano-plugin-development` 在当前 `skills_selection_mode`（含 `explicit_allowlist` 与 `explicit_denylist`）下处于有效选中、以及传入 `catalog` 时所需工具/Skill 在目录中可用；
  - 在 `changeCapability`（`product-contracts` 与 iOS `CapabilitySelection.swift`）将 `draft.features?.plugin_management === undefined` 物化为显式布尔草稿时，使用 `effectiveSelectedTools(draft)` 初始化 `tools`，使伴随的 `cordis_inspect_*` 同步落入草稿 `tool_allowlist`；
  - Web `resolveEffectiveFeatures`、iOS `AgentConfigView` 特性开关、`apps/im-server/src/agent-settings.ts` `configurationDisplay`、以及 Web/iOS `prompt-preview` 请求负载统一使用 `effectiveCapabilityFeatures(draft)` 与 `effectiveSelectedTools(draft)`。

---

#### `R1-W1` [WARNING] — Node 能力投影仍硬编码过滤 `cordis_inspect_*`，且 DSH `CapabilityState` 与 `describe_api` 上下文提示残留旧 `plugin_manager` 耦合

- **位置**：
  - [design.md](design.md) D1（第 81–86 行）与文件改动表（第 131–136 行）
  - `apps/node/src/capabilities.ts:50`
  - `packages/dsh-integration/src/capabilities.ts:17, 21-25, 48-54, 65, 85`
  - `packages/dsh-integration/src/capability-state.ts:32, 62`
  - `packages/dsh-integration/src/plugin-development.ts:9`
- **问题机制与后果**：
  1. **Node 二次过滤遗漏**：`apps/node/src/capabilities.ts:50` 硬编码了 `catalog.tools.filter(tool => !['memory', 'cordis_inspect_list', 'cordis_inspect_query'].includes(tool.name))`。`design.md` D1 仅要求修改 `packages/dsh-integration/src/capabilities.ts`（注：实际符号为 `cordisInspectSet` / `allowsCordisInspect` 而非 `hiddenTools`），文件改动表对 `apps/node/src/capabilities.ts` 也仅列出 `source_label` 与 `fixed_tools`。若保留第 50 行过滤，Node 上报给 IM、Web 与 iOS 的 `capabilities.tools` 仍不含 `cordis_inspect_list` 与 `cordis_inspect_query`，主需求在全链路无法生效。
  2. **`CapabilityState` 撤回挂起耦合与旧默认判定**：`packages/dsh-integration/src/capability-state.ts:32` 的 `pluginManagerHeld` 只要检测到 `plugin_manager` 处于撤回挂起，就会连带阻断 `cordis_inspect_list` / `cordis_inspect_query`。解耦后若用户关闭 `plugin_management`、同时独立勾选 `plugin_manager` 与 `cordis_inspect_list`，随后仅撤回 `plugin_manager` 保留 `cordis_inspect_list`，第 32 行会错误阻断合法的 `cordis_inspect_list` 调用；同时第 62 行仍调用旧 `effectiveFeatures(previous.features)` 而非 `effectiveCapabilityFeatures(capabilityDraft(...))`，对存量受限 Agent 会误判 `plugin_management` 状态变化。
  3. **Agent Context 工具说明矛盾**：`packages/dsh-integration/src/plugin-development.ts:9` 在 `plugin_manager(action: "describe_api", topic: "service")` 输出中写死 `"When plugin_manager is enabled, use cordis_inspect_list and cordis_inspect_query..."`。当用户关闭 `plugin_management` 并仅独立开启 `plugin_manager` 时，该返回内容会诱导模型调用未启用的 `cordis_inspect_*` 并收到执行层拒绝。
- **收口要求**：
  - 在 `design.md` D1 及文件改动表中明确从 `apps/node/src/capabilities.ts:50` 移除 `'cordis_inspect_list'`、`'cordis_inspect_query'` 过滤（仅保留 `'memory'` 过滤），并对齐 `packages/dsh-integration/src/capabilities.ts` 的真实符号（`cordisInspectSet` / `allowsCordisInspect`）；
  - 明确移除 `capability-state.ts:32` 的 `pluginManagerHeld` 耦合（直接由第 67 行对实际被撤回工具名的挂起保护覆盖），并将第 62 行切换为 `effectiveCapabilityFeatures(capabilityDraft(...))`；
  - 更新 `plugin-development.ts:9` 的 `service` 主题指引，改为仅在 `cordis_inspect_list` / `cordis_inspect_query` 已启用时使用，避免误导模型。

---

#### `R1-W2` [WARNING] — D5「剔除所有模式 `fixed_tools`」会误删普通模式的 `send_message`，且未对齐存量脏状态基线与双端离线 `fixedTools` 兜底

- **位置**：
  - [design.md](design.md) D5/D6（第 115、122 行）
  - `packages/product-contracts/src/capabilities.ts:27, 29, 55-60`
  - `src/IM/frontend/src/features/settings/agents/capability-editor.tsx:8-10`、`agent-detail-page.tsx:1344-1380, 1590`
  - `src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift:36-40, 349`、`CapabilitySelection.swift:154-156`、`AgentModels.swift:76-78`
- **问题机制与后果**：
  1. **`send_message` 跨模式耦合破坏普通 Agent 校验与消息能力**：在 `packages/product-contracts/src/capabilities.ts:55-60` 中，`send_message` 仅在 `mode === 'global'` 时属于 `fixedTools`，而在普通模式（`chat` / `single_thread`）下属于用户可选静态工具，且是 `intelligent_ui`（`requires.tools: ['send_message', 'skill']`）与 `heartbeat`（`requires.tools: ['send_message']`）的必需依赖。若按 D5 字面要求在编辑态与提交时“剔除**所有模式** `fixed_tools`”，普通模式 Agent 的 `send_message` 会被从 `tool_allowlist` 强行剔除，导致开启 `intelligent_ui` 或 `heartbeat` 的普通 Agent 全部无法通过 `validateCapabilities` 保存；反之若按“当前模式 `fixedTools(mode, agentKind)`”剔除，则用户在编辑页将 `global` 切换为普通模式时若未补齐已开启 Feature 所需的 `send_message` 也会触发校验失败。
  2. **存量污染列表导致打开页面即误报“未保存”（`dirty`）**：历史 E2E 与旧客户端已将 `notes`、`history`、`inbox` 等写入持久化 `tool_allowlist`。若编辑态草稿在加载或插件刷新时净化了 `draft.tool_allowlist`，而 Web `sameEditableConfig(current, baseConfig.current)`（`agent-detail-page.tsx:1344`）或 iOS `dirty`（`AgentConfigView.swift:36-40`：`draft != baseline`）仍拿未净化的原始 `config.tool_allowlist` 对比，用户刚打开存量 Agent 配置页（或从插件页返回）未做任何编辑就会立即触发未保存横幅与离开确认弹窗；且 iOS 第 349 行还会把历史残留名称渲染成“已保存，目录未报告”。
  3. **Web/iOS 本地 `fixedTools` 兜底不完整**：Web `capabilityCatalog`（`capability-editor.tsx:9`）写死 `fixedTools(mode, "root", false)`，漏掉 Personal Agent 的 `'personal'` 固定工具（`personal_sources`、`send_user_message`）；iOS `CapabilitySelection.swift:155` 与 `AgentModels.swift:77` 硬编码数组漏掉了 `download_attachment`、`personal_sources`、`send_user_message`。
- **收口要求**：
  - 将 D5 净化集合精确限定为「当前 Agent 生效的 `fixedTools(mode, agentKind)` + `contextTools` + 当前目录中 `source_group === 'workspace'` 的工具」（绝不在非 `global` 模式下剔除 `send_message`），并规定当用户在编辑态从 `global` 切回非 `global` 模式时，自动补齐当前已开启 Feature（如 `intelligent_ui`、`heartbeat`）所需的 `send_message`；
  - 明确 Web `sameEditableConfig` 基线、iOS `AgentConfigView` 的 `dirty` 对比基线及未知工具告警列表同步套用同一静态工具归一化函数，保证存量污染配置静默无感打开、不在未编辑时变脏，并在下次实际保存配置时落盘净化；
  - 对齐 Web（传入 `agentKind`）与 iOS `CapabilitySelection.swift` / `AgentModels.swift` 的 `fixedTools(mode, agentKind)` 映射。

---

#### `R1-W3` [WARNING] — D6 插件启停跨页同步与 `WorkspaceOwner.execute()` 变更广播存在时序竞态，忙碌等待或异步卸载期间易将旧工具目录写入 IM 5 分钟缓存

- **位置**：
  - [design.md](design.md) D6（第 118–124 行）
  - `packages/dsh-integration/src/workspace-tools.ts:214-215, 249-255, 311-315`
  - `apps/node/src/main.ts:372-375, 607`
  - `apps/im-server/src/control-routes.ts:396`、`catalog-reads.ts:45-98`
  - `src/IM/frontend/src/features/settings/agents/agent-plugins-panel.tsx:66-76`
- **问题机制与后果**：
  1. **`mount.tools` 更新前提前广播 `catalogChanged = true`**：在 `packages/dsh-integration/src/workspace-tools.ts:311-315` 中，`WorkspaceOwner.execute()` 先对所有 `mount` 调用 `this.changed(mount.config.agentId, true)`（触发 `configuration.catalog.changed` → Node `publishCatalogChange()` → IM `catalogs.invalidateNode`），**随后**才在第 315 行执行 `await this.host.hmr.runExclusive(() => this.refresh())` 卸载插件纤维并在第 214 行更新内存中的 `mount.tools`，而 `this.refresh()` 结束时第 215 行调用的是 `this.changed(..., false)`（不再通知 Node）。由于 `configuration.catalog` 直接读取内存中的 `mount.tools`，前端收到首次 WS/mutation 信号立即重拉 `/settings` 或 `/capabilities` 时，若 `this.refresh()` 仍在异步卸载纤维，IM Server 的 `CatalogReads`（`catalog-reads.ts:98`，TTL 5 分钟）会把**卸载前的旧工具列表**重新缓存 5 分钟，且后续不再收到失效通知。
  2. **Agent 忙碌挂起（`pending.phase === 'waiting'`）过早失效**：当工作区 Agent 忙碌时，`plugins.manage` 会立即返回 `{ view: { pending: { phase: 'waiting' } } }`（`workspace-tools.ts:249-255`）。此时插件尚未停用，但 `apps/node/src/main.ts:374` 与 `control-routes.ts:396` 已执行首次失效；若 Web `AgentPluginsPanel` 仅在 `manageMutation.onSuccess` 时 `invalidateQueries` 而不监听轮询中 `pending` 从非空变为结算完成的转换，忙碌结算后前端配置页仍会停留在旧目录。
- **收口要求**：
  - 在 `WorkspaceOwner.execute()`（`workspace-tools.ts:311-315`）中将 `for (const mount of this.mounts) this.changed(mount.config.agentId, true)` 移至 `await this.host.hmr.runExclusive(() => this.refresh())` 完成 `mount.tools` 更新**之后**（对提前返回的 `restart-required` 分支按需单独保留）；
  - 在 Web `AgentPluginsPanel`（及 iOS `AgentPluginsView`）中，除即时完成（返回值无 `pending`）时失效 `['agent-settings', agentId]` / `['agent-capabilities', agentId]` 外，当轮询观察到 `pending` 结算消失时也必须再次触发上述查询失效，确保忙碌等待场景切回「配置」页同样满足 Q4。

---

### Recommendations

#### `R1-R1` — 多自装插件 `source_label` 归属优先读取已挂载 Entry Fiber Scope，避免增量 `root.update` 破坏跨插件 `inject`

- **位置**：[design.md](design.md) D4（第 104–106 行）、`packages/dsh-integration/src/workspace-tools.ts:185-214`
- **建议**：`mount.tree.root.update(structuredClone(mountedRows))` 在单次调用中完成整个工作区插件树装配；若为统计工具增量而改为逐个 bundle 循环调用 `root.update`，当两个插件在 `cordis.patch.yml` 中存在服务 `inject` 依赖时会触发中间态 `Missing service` 审计失败（第 204 行）并增加重复热重载开销。建议保持单次原子 `root.update`，随后遍历激活的 `mount.tree.entries()`，通过 `entry.options.id` 匹配 `listBundles()` 的 `rows[].rowId`，用 `mount.ctx.tools.schemas(scopeOf(entry.fiber.ctx))` 减去 `mount.baseline` 确定归属（无法精确命中时再回退包名兜底）。

#### `R1-R2` — 移除 `specs/im/agents-nodes.md` 中的变更日志措辞「本次」

- **位置**：[specs/im/agents-nodes.md](specs/im/agents-nodes.md) 第 62 行
- **建议**：将 `本次除 plugin_management 外不新增 Goal 或 Workflow 等其他 Feature` 改为长青契约表述（如 `Goal 与 Workflow 等独立工具不设额外 Feature 开关`），避免归并至 `docs/specs/im/agents-nodes.md` 后残留单次变更时间口吻。

#### `R1-R3` — 补充免 `prototype.html` 说明、折叠头部无障碍结构约束与 iOS 验收步骤

- **位置**：[design.md](design.md) D5（第 110–113 行）与 `Runbook for Reviewer`（第 163–171 行）
- **建议**：
  1. 在 `design.md` 简述免产出 `prototype.html` 的理由（完全复用既有 `PillSelector`、`CapabilityToast` 与 `BehaviorCard` 定型组件，无新视觉层级）；
  2. 明确 `CapabilityEditor` 仅在传入 `onManagePlugins` 回调时渲染「管理插件 →」（`AgentCreatePage` 不渲染死链），且折叠切换 `<button aria-expanded>` 与「管理插件 →」`<button>` 在头部互为兄弟节点而非按钮嵌套，确保 `390px` 窄屏换行与键盘焦点合法；
  3. 在 `Runbook for Reviewer` 补入 iOS 端（`xcodebuild ... test` 或模拟器打开 `AgentConfigView` → `AgentPluginsView`）的对应核验步骤与隔离栈测试账号（`nano` / `nano1234`）提示。


### Author Resolutions

- **`R1-C1`**: `accepted` — 已在 [design.md](design.md) `D2`、`接口与数据流 §1` 及 `Milestones` 完整收口存量无状态推导闭环：① `effectiveCapabilityFeatures(draft, definitions, catalog?)` 同时核验 `plugin_manager` 选中、`nano-plugin-development` 在 `default_discovery` / `explicit_denylist` / `explicit_allowlist` 三种模式下有效选中、以及传入 `catalog` 时全部依赖在目录中真实存在（保证无 `workspace` 配置推导为 `false` 而不触发启动或 `prepare` 崩溃）；② `changeCapability`（`product-contracts` 与 iOS `CapabilitySelection.swift`）在物化 `next.features` 的同时用 `effectiveSelectedTools(draft, catalog)` 初始化 `next.tool_allowlist`，消除存量配置局部编辑任意无关能力时的依赖缺失误报；③ Web `resolveEffectiveFeatures`、iOS `AgentConfigView` 开关绑定、IM `configurationDisplay` 与双端 `prompt-preview` 负载统一改用 `effectiveCapabilityFeatures` 与 `effectiveSelectedTools`。
- **`R1-W1`**: `accepted` — 已在 [design.md](design.md) `D1` 与 `Milestones` 明确补齐 [apps/node/src/capabilities.ts](../../../apps/node/src/capabilities.ts) 第 50 行移除 `'cordis_inspect_list'` / `'cordis_inspect_query'` 过滤，对齐 `packages/dsh-integration/src/capabilities.ts` 真实符号（`cordisInspectSet` / `allowsCordisInspect`），移除 `capability-state.ts:32` 的 `pluginManagerHeld` 耦合与第 61 行的旧 `effectiveFeatures` 调用，并更新 `plugin-development.ts:9` 的 `describe_api(topic: 'service')` 说明文案。
- **`R1-W2`**: `accepted` — 已在 [design.md](design.md) `D5`、`接口与数据流 §1` 与 `Milestones` 将静态白名单净化精确限定为按当前 Agent 自身 `workMode` 与 `role` 计算的 `fixedTools(workMode, role, false)` + 四项 `contextTools` + 当前目录 `source_group === 'workspace'` 工具（完整保留 `single_thread` 普通模式下的 `send_message`，并在新建页从 `global` 切为 `single_thread` 时重跑已开启 Feature 闭包补齐 `send_message`）；同时对 Web `sameEditableConfig` / `baseConfig` 与 iOS `dirty` 基线及未知工具过滤列表对称套用同一净化函数，消除存量污染配置打开即变脏的问题，并补齐 Web/iOS 对 `download_attachment` 与 `personal` 角色固定工具的一比一映射。
- **`R1-W3`**: `accepted` — 已在 [design.md](design.md) `D6`、核心时序图与 `Milestones` 明确将 [workspace-tools.ts](../../../packages/dsh-integration/src/workspace-tools.ts) `WorkspaceOwner.execute()` 中的 `this.changed(mount.config.agentId, true)` 移至 `await this.host.hmr.runExclusive(() => this.refresh())` 更新完 `mount.tools` **之后**（`restart-required` 提前返回分支单独保留），`apps/node/src/main.ts` 仅在返回无 `pending` 时立即发布目录变更，且双端插件页同时在即时完成与轮询观察到 `pending -> undefined` 时失效主设置与能力缓存。
- **`R1-R1`**: `accepted` — 已在 [design.md](design.md) `D4` 采纳保持单次原子 `mount.tree.root.update(structuredClone(mountedRows))` 的建议以避免跨插件 `inject` 中间态审计失败；同时经核查 `@deepseek-ai/dsh-scope/lib/types/index.d.ts:80-84`，`EntryTree` 子节点继承同一 preset `ScopeKey`（`scopeOf(entry.fiber.ctx) === scopeOf(mount.ctx)`），故多自装插件归属采用单次原子挂载前后的工具差集持久化至 `.nanoassistant/dsh-plugins/nano-tool-owners.json`（辅以单自装插件直接映射与未知手改场景的通用文案优雅降级），兼顾原子挂载与重启后归属准确。
- **`R1-R2`**: `accepted` — 已在 [specs/im/agents-nodes.md](specs/im/agents-nodes.md) 移除变更日志口吻“本次”，改为长青契约表述“Goal 与 Workflow 等独立工具保持各自工具选择，不设额外 Feature 开关”。
- **`R1-R3`**: `accepted` — 已在 [design.md](design.md) `§3 双端界面与交互细节` 明确折叠 `<button aria-expanded>` 与详情页「管理插件 →」`<button>` 互为兄弟节点（严禁按钮嵌套）且新建页不传 `labelAction`，并在 `Runbook for Reviewer` 补充隔离栈凭据定位与 iOS Simulator `xcodebuild` 验收命令。


---

## Round 2

### Metadata

- **Reviewer Target**: `feat-791-plugin-tool-settings`（[design.md](design.md)、[specs/im/agents-nodes.md](specs/im/agents-nodes.md)、[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md) 及 Round 1 问题闭环）
- **Round**: `Round 2`
- **review_mode**: `delta`
- **mode_reason**: 本轮基于 Round 1 反馈对 [design.md](design.md) `D1`–`D6`、`接口与数据流 §1–§4`、`Runbook for Reviewer`、`Milestones` 及 [specs/im/agents-nodes.md](specs/im/agents-nodes.md) 进行了有界技术修订（包含新增纯辅助函数签名、`plugin_bundle` / `plugin_title` 目录字段、`nano-tool-owners.json` 多插件归属侧车索引及 `main.ts` 忙碌通知门禁），未改变 [spec.md](spec.md) 用户需求边界与跨包依赖拓扑，适合采用 `delta` 模式核验全部历史问题闭环及本轮新增机制的波及面。
- **retained_from**: `Round 1`（[spec.md](spec.md) Q1–Q4 目标边界、[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md) 全部 Requirement/Scenario 锚点、跨包公开导出架构边界、只读审批 `safeTools` 与子会话角色隔离结论未发生变更，沿用 Round 1 已核实证据）
- **started_at**: `2026-11-26T11:08:52+09:00`
- **completed_at**: `2026-11-26T11:12:06+09:00`
- **duration**: `3m 14s`

### Verdict

**Approved**（`0 CRITICAL / 0 WARNING / 1 Recommendation`）

Round 1 提出的 `1 CRITICAL` 与 `3 WARNING`（及 `3 Recommendations`）已全部在 [design.md](design.md) 与 [specs/im/agents-nodes.md](specs/im/agents-nodes.md) 中实质闭环；本轮修订引入的共享纯函数契约、多插件侧车归属索引与缓存失效时序同生产代码真实落点逐项核对一致，无新增阻塞缺陷，准予通过 Gate 2 进入实施。

---

### Coverage 与证据（Delta 变更与波及范围）

1. **共享纯函数与目录增量闭合性（`D2`、`D5`、`接口与数据流 §1`）**：
   - `effectiveCapabilityFeatures(draft, definitions, catalog?)` 与 `effectiveSelectedTools(draft, catalog?)` 已完整覆盖 `default_discovery` / `explicit_denylist` / `explicit_allowlist` 三类技能模式及在线 `catalog` 存在性守卫（无 `workspace` 时自动落为 `false`），并贯穿 `validateCapabilities`、`changeCapability`（初始化 `next.features` 与 `next.tool_allowlist`）、IM `configurationDisplay`、Web/iOS 开关渲染与 `prompt-preview` 净荷。
   - 复核 `packages/product-contracts/src/capabilities.ts:57-62` 确认 `fixedTools('single_thread', 'root', false)` 确为空数组 `[]`，而 `fixedTools('global', role, false)` 返回 `global`（及 `personal`）固定工具；因此 `sanitizeStaticToolAllowlist(tools, workMode, role, workspaceToolNames)` 在普通模式下完整保留 `send_message`，并在 `AgentCreatePage` 从 `global` 切回 `single_thread` 时重跑已开启 Feature 闭包补齐 `send_message`。
   - 目录工具元数据字段收敛为具名 `plugin_bundle?: string | null` 与 `plugin_title?: string | Record<string, string> | null`（匹配 `PluginView` 中 `PluginText` 的多语言标题结构），`CapabilityBlock.code` 新增 `'provided_by_plugin'` 与 `'plugin_requires_manager'` 且优先级高于 `'fixed_capability'`，确保 `dsh-agent-context` 的 `notes` 等工具提示前往「插件」页关闭而非误报不可关闭的基础能力。
2. **多插件工具归属侧车机制安全性（`D4`）**：
   - 核对 `packages/dsh-integration/src/workspace-tools.ts:140` 确认 `WorkspaceOwner` 仅监听 `package.json` 与 `cordis.patch.yml`；将多自装插件激活前后的工具差集持久化至 `.nanoassistant/dsh-plugins/nano-tool-owners.json` 既避免了拆分 `mount.tree.root.update` 破坏跨插件 `inject` 依赖，又不会触发 HMR 自激循环或干扰 `loadProfileDirectory`，且手改未命中场景有通用轻提示文案兜底。
3. **跨模块缓存失效与 React Query Key 核实（`D6`、`§2`）**：
   - `WorkspaceOwner.execute()` 调整为 `this.refresh()` 更新完 `mount.tools` 后再广播 `configuration.catalog.changed`，`apps/node/src/main.ts` 在 `node.plugins.request` 返回存在 `pending` 时抑制提前广播；
   - 核对 `src/IM/frontend/src/features/settings/agents/use-agent-settings-state.ts:15-16` 确认详情页状态查询键前缀正是 `['settings', 'agents', agentId]`，因此 `D6` 在无 `pending` 完成及轮询 `pending -> undefined` 时失效 `['settings', 'agents']`、`['agent-capabilities']` 与 `['chat', 'slash-candidates']` 可精确刷新当前及同工作区兄弟 Agent 的配置与能力视图。
4. **Milestone、契约文体与文档完整性校验**：
   - `M1-plugin-tool-settings` 范围已补齐 `apps/node/src/main.ts`，`[reviewer]` 与 `[worker]` 退出标准可测性清晰；
   - 对全仓及本单元全部文档运行 `scripts/docs_check.py` 校验通过（`0` 项问题）。

---

### 历史问题闭环

| ID | 原严重度 | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|---|
| `R1-C1` | CRITICAL | `accepted` | [design.md](design.md) `D2`（第 90–100 行）与 `§1`（第 170 行）已定义 `effectiveCapabilityFeatures(draft, definitions, catalog?)` 三重前置核验（含 `explicit_allowlist` 技能判定与 `catalog` 可用性守卫）、`changeCapability` 用 `effectiveSelectedTools(draft, catalog)` 同步物化草稿 `tool_allowlist`、以及双端展示/`configurationDisplay`/`prompt-preview` 同源调用，并在 `Milestones` 锁定四类存量样本单测。 | `closed` |
| `R1-W1` | WARNING | `accepted` | [design.md](design.md) `D1`（第 83–86 行）、`§1.2`（第 185 行）与 `§4`（第 249 行）已明确移除 `apps/node/src/capabilities.ts:50` 对 `cordis_inspect_*` 的过滤、对齐 `cordisInspectSet` / `allowsCordisInspect` 真实符号、移除 `capability-state.ts:32` 的 `pluginManagerHeld` 并切换 `effectiveCapabilityFeatures`、更新 `plugin-development.ts:9` 的 `describe_api('service')` 文案。 | `closed` |
| `R1-W2` | WARNING | `accepted` | [design.md](design.md) `D5`（第 117–124 行）已改为按当前 Agent `fixedTools(workMode, role, false)` 精准剥离（`single_thread` 保留 `send_message`，新建页 `global -> single_thread` 重跑闭包补齐 `send_message`），对 Web `sameEditableConfig` 基线与 iOS `dirty` 基线/未知工具列表对称归一化，并补齐双端 `download_attachment` 与 `personal` 角色固定工具映射。 | `closed` |
| `R1-W3` | WARNING | `accepted` | [design.md](design.md) `D6`（第 126–133 行）与 `§2` 时序图（第 208–212 行）已明确在 `WorkspaceOwner.refresh()` 更新 `mount.tools` 后再触发 `this.changed(..., true)`，`apps/node/src/main.ts` 仅在无 `pending` 时立即发布变更，双端插件页同时在即时完成与轮询 `pending -> undefined` 时失效主缓存。 | `closed` |
| `R1-R1` | Recommendation | `accepted` | [design.md](design.md) `D4`（第 110–115 行）保持单次原子 `mount.tree.root.update` 并采用 `nano-tool-owners.json` 侧车差集索引与通用文案降级。 | `closed` |
| `R1-R2` | Recommendation | `accepted` | [specs/im/agents-nodes.md](specs/im/agents-nodes.md) 第 62 行已改为长青契约表述，无“本次”变更日志口吻。 | `closed` |
| `R1-R3` | Recommendation | `accepted` | [design.md](design.md) `§3`（第 229、234 行）与 `Runbook for Reviewer`（第 285–288 行）已补充免原型说明、折叠按钮与「管理插件 →」兄弟节点无嵌套约束、创建页不传 `labelAction` 及 iOS Simulator `xcodebuild` 验收命令。 | `closed` |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

#### `R2-R1` — Runbook 环境变量文件名与网关存活检查可与 `e2e-up.sh` 实际输出对齐

- **位置**：[design.md](design.md) `Runbook for Reviewer`（第 283、286 行）
- **建议**：`./scripts/e2e-up.sh` 实际在 worktree 下写出 `.e2e-ports.env`（暴露 `IM_URL`、`UI_URL` 等），且 Gateway/DSH 仅通过 stdio 通信不监听独立健康检查 HTTP 端口（无 `NANO_GATEWAY_HEALTH_PORT`）；实施或验收时直接按 `docs/development/worktree-runtime.md` 使用 `source "$WT_ROOT/.e2e-ports.env"`、`curl -fsS "$IM_URL/openapi.json"`、`pnpm pa status --config "$WT_ROOT/.gateway-config.yaml"` 与默认测试账号 `nano` / `nano1234` 即可，不影响方案实施。


### Author Resolutions

- **`R2-R1`**: `accepted` — 已同步修正 [design.md](design.md) `Runbook for Reviewer` 中的健康检查与环境变量定位，对齐 `scripts/e2e-up.sh` 真实产物 `./.e2e-ports.env`、`curl -fsS "$IM_URL/openapi.json"`、`pnpm pa status --config ./.gateway-config.yaml` 及默认测试账号 `nano` / `nano1234`。


---

## Round 3

### Metadata

- **Reviewer Target**: `feat-791-plugin-tool-settings`（[design.md](design.md) `Runbook for Reviewer` 第 283–286 行及 `R2-R1` 闭环）
- **Round**: `Round 3`
- **review_mode**: `closure`
- **mode_reason**: 本轮仅针对 Round 2 非阻塞建议 `R2-R1` 更新了 [design.md](design.md) 第 283–286 行 `Runbook for Reviewer` 的环境变量文件路径、可执行健康检查命令与默认测试凭据说明，未涉及任何需求、技术决策、接口、delta-specs 或 Milestones 变更，采用 `closure` 模式核实闭环。
- **started_at**: `2026-11-26T11:14:57+09:00`
- **completed_at**: `2026-11-26T11:15:31+09:00`
- **duration**: `34s`

### Verdict

**Approved**（`0 CRITICAL / 0 WARNING / 0 Recommendations`）

---

### Coverage 与证据（Closure）

- 仅局部消歧修订：核对 [design.md](design.md) 第 283–286 行与 `docs/development/worktree-runtime.md`（第 174–189 行）及 `scripts/e2e-up.sh`（第 24–28、50 行）完全一致；其余章节与两份 delta-specs 保持 Round 2 已通过状态不变。

---

### 历史问题闭环

| ID | 原类别 | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|---|
| `R2-R1` | Recommendation | `accepted` | [design.md](design.md) 第 283 行健康检查已更新为 `source ./.e2e-ports.env && curl -fsS "$IM_URL/openapi.json" >/dev/null && pnpm pa status --config ./.gateway-config.yaml`，第 286 行已明确 `source ./.e2e-ports.env` 获取 `$IM_URL` 与默认测试账号 `nano` / `nano1234`。 | `closed` |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

无（`0 Recommendations`）。
