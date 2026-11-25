# Design Review: feat-787-dsh-022-upgrade

## Round 1

### Metadata

- **Change Unit**: `feat-787-dsh-022-upgrade`
- **review_mode**: `full`
- **mode_reason**: 首轮 Gate 2 独立技术设计审查，完整核对现状断言、设计决定、用户拍板约束、架构红线、专项设计审查（Agent Context 与前端轨迹体验）、delta-spec 及 M1 实施与审查计划。
- **started_at**: `2026-11-25T13:35:21+09:00`
- **completed_at**: `2026-11-25T13:54:03+09:00`
- **duration**: `18m 42s`

### Verdict

**Issues Found**（`5 CRITICAL / 4 WARNING / 2 Recommendation`）

### Coverage & Evidence

本轮独立核对了变更目录（`spec.md`、`design.md`、3 份 delta-spec、`M1-dsh-022-upgrade/`）、目标 canonical specs（`docs/specs/gateway/{agent-capabilities,tool-approval,service-lifecycle,global-agent}.md`、`docs/specs/im/agent-work.md`）、本仓实现（`packages/dsh-integration/**`、`packages/trajectory-ui/**`、`packages/dsh-trajectory-viewer/**`、`apps/im-server/src/trajectory.ts`、`apps/node/src/capabilities.ts`、`scripts/build-windows-archives.py`、`tests/contract/test_runtime_dependency_contract.py`、`dsh-agent-context@0.3.0-rc.11`）以及上游 `@deepseek-ai/*@0.2.2-rc.5` 真实解包产物：

1. **现状断言与真实装配入口核查**：
   - 核实 `pnpm-workspace.yaml`、`packages/dsh-integration/{package.json,cordis.patch.yml}`、`packages/trajectory-ui/{package.json,upstream.json}`、`packages/dsh-trajectory-viewer/{package.json,build.mjs,src/boot.jsx,src/transport.ts}` 与 `scripts/build-windows-archives.py` 的版本锁与打包链路。
   - 对照上游 `0.2.2-rc.5` 的 `dsh-base/cordis.patch.yml`、`dsh-agent`、`dsh-agent-loop`、`dsh-system-prompt`、`dsh-tools`、`dsh-tool-fs`、`dsh-fs-patch`、`dsh-working-directory`、`dsh-subagent`、`dsh-web*`、`dsh-tool-web`、`dsh-cordis-host-runner`、`dsh-tool-cordis`、`dsh-client-ui-trajectory` 等包源码与 `.d.ts`：确认发现多处真实上游契约与 `design.md` 假设不符（详见 `R1-C1`～`R1-C5`）。
2. **用户拍板约束与非目标核查**：
   - 逐项核对 `spec.md` Q1～Q5 与非目标边界：Node 24 运行时兼容（上游 `0.2.2-rc.5` 各包 `engines` 均为 `>=22.19`）、JSONL 会话存储单事实源不变、不引入 IM 配置页与会话顶栏 UI 改动（归属 `feat-770`）、禁用模型侧 `working_directory` 切目录工具且 `dsh-base` 默认禁用 `fs-observation-policy`（读取工作区外文件不会自动加载外部 `AGENTS.md`）。
3. **架构红线与职责边界核查**：
   - 符合 `SPEC.md` 与 `tests/contract/test_runtime_dependency_contract.py`：服务端仅 `packages/dsh-integration` 访问公开声明的 `@deepseek-ai/*` exports，彻底移除原 `@deepseek-ai/dsh-subagent/internal` 导入方向正确；浏览器侧仅 `packages/trajectory-ui` 保持单包 UI 分叉。
   - 核查 `@deepseek-ai/dsh-tool-cordis@0.2.2-rc.5` (`lib/types/config.js:67-92`) 的 `Config.listConfigs` 实现：仅投影插件构造器上的静态 Schemastery JSON Schema 与包目录，不读取或暴露宿主运行态配置值/凭据，符合共享 DSH host 的跨会话机密边界。
4. **专项设计审查并入（`agent-context-review` 设计模式）**：
   - 盘点全部模型消费面：Global/PA 根会话、普通/fork 子会话、`dsh-agent-context` 滚窗引擎、后备 `NanoCompaction`、`Dreaming` 维护会话及 CC/Codex 自动审批审阅会话。
   - `<system-reminder>` 运行时快照与 `in-history` 系统提示词增量维持前缀稳定，`context-order.ts` 按 `source.kind === 'runtime-context'` 排序在 `0.2.2-rc.5` 仍匹配；实施后需按 `verify-context-cache-prefix` 实测首轮/续轮与子会话缓存前缀字节一致性。
   - 识别出 5 项模型可见上下文/归属缺陷并入本轮问题：`InterruptedWork` 注入伪造父 Agent 前缀与抬升审批信任级（`R1-C3`）、`dsh-agent-context` 漏算全部工具 Schema Token（`R1-C5`）、`installModelSelection` 误唤醒已撤回的回退步与子会话丢失动态路由继承（`R1-W1`）、`cordis_inspect_*` 经 `independentTool` 泄漏给无权限子会话（`R1-W2`）、手动 `systemPrompt.assemble` 漏传 `toolSet` 导致条件工具提示失真（`R1-W3`）。
5. **专项设计审查并入（`frontend-experience-review` 设计模式）**：
   - **原型边界判断**：本单元仅将上游 `dsh-client-ui-trajectory` 的增量能力（嵌套子调用折叠、工具详情“原始值 / 渲染结果”双态对照与冷态降级提示）同步至既有单包分叉 `packages/trajectory-ui`，不新建产品页面或跨页主流程，**无需补做 `prototype.html`**。
   - 识别出实时原始结果流全链路 RPC 方法名错配与 `boot.jsx` 漏挂 `remote.toolResults`（`R1-C4`），以及 `TrajectoryToolbar` 新增必填属性、`locate()` 范围跳转未展开嵌套子调用和 IM 右侧窄抽屉下工具栏拥挤度的设计/验收缺口（`R1-W4`）。
6. **Delta-spec 与 Milestone 拆分核查**：
   - DSH 多包共享单一 lockfile 与 Cordis 类型系统，按单里程碑 `M1-dsh-022-upgrade` 原子推进合理。
   - 3 份 delta-spec 均锚定了存在的 canonical target 并保留既有适用 Scenario，但 `specs/gateway/agent-capabilities.md` 未同步修订显式白名单不自动扩宽的既有条款（见 `R1-W2`）。

### Historical Issues Closure

无（首轮审查）。

### Issues

#### R1-C1 [CRITICAL] `NanoWeb` 与 `dsh-base` 默认 DeepSeek 搜索插件冲突、`available()` 恒真遮蔽及公共回退断裂

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「决策 5：`dsh-web` 官方 DeepSeek 搜索接入与公共回退优先级」（L125–129）
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「模块与文件设计」`packages/dsh-integration/cordis.patch.yml`（L152）、`src/client.ts`（L153）、`src/web.ts`（L185）
- **证据**：
  1. 上游 `@deepseek-ai/dsh-base@0.2.2-rc.5` (`cordis.patch.yml:490-509`) 默认启用 `web-search-deepseek`（注册搜索源 ID `'deepseek-official'`）与 `web-deepseek-api`（注册搜索源 ID `'deepseek-search-api'`）；`design.md` 未在 `packages/dsh-integration/cordis.patch.yml` 中禁用这两项。
  2. 核查上游源码：`@deepseek-ai/dsh-web-deepseek-api@0.2.2-rc.5` (`lib/index.js:16-18, 296-299, 649-660`) 的 `hasDeepSeekWebCredential` 因 `source.key` 为引用对象（`typeof source.key !== 'string'`）且含 `account` 源，导致 `'deepseek-search-api'.available()` **无条件恒返 `true`**；`@deepseek-ai/dsh-web-search-deepseek@0.2.2-rc.5` (`lib/index.js:113, 333`) 的 `'deepseek-official'.available()` 同样**无条件恒返 `true`**。仅异步 `ready(llmProvider)` 才会实际检查凭据是否存在。
  3. 在 `@deepseek-ai/dsh-web@0.2.2-rc.5` (`lib/index.js:231-239, 297-312`) 中，只要 `web.config.searchProvider` 未显式指定（`design.md:153` 在未配 `DSH_WEB_SEARCH_PROVIDER` / `SEARXNG_URL` / `BRAVE_API_KEY` 时留空），`selectSearchProvider('llm-pi-ai')` 必立即命中 `preferredId = 'deepseek-search-api'`。
- **不修后果**：
  - 若 `NanoWeb` 注册同 ID `'deepseek-search-api'`，启动即抛 `WebError('WEB_DUPLICATE_PROVIDER')`（`dsh-web/lib/index.js:163`）；若改用其他 ID，未固定 `searchProvider` 时仍被上游 `'deepseek-search-api'` 抢占，无法读取 Nano `llm-pi-ai` 配置的 DeepSeek profile（`apiKeyEnv` / 自定义 `baseUrl`）且不走 `proxyRouteFor` 代理路由。
  - 当环境无专用搜索源也无 DeepSeek 凭据时，`@deepseek-ai/dsh-tool-web@0.2.2-rc.5` (`lib/index.js:351`) 的步骤准入 `when: ({ modelSelection }) => ctx.web.searchReady(modelSelection.provider)` 会检查 `'deepseek-search-api'.ready('llm-pi-ai')` 得到 `false`，**导致模型侧 `web_search` 工具直接消失**，或执行时抛 `WEB_PROVIDER_CREDENTIAL_MISSING`，永远无法落入 `spec.md` 要求的 `'duckduckgo'` 公共搜索回退（且若仅禁用上游插件但保留多个 `available() === true` 的自定义源而不驱动 `searchProvider`，又会触发 `WEB_PROVIDER_AMBIGUOUS`）。设计需明确禁用上游冗余 DeepSeek 搜索插件并闭合 `searxng > brave > Nano DeepSeek > duckduckgo` 在 `available()`、`ready()` 与 `searchProvider` 选择器上的精确协同机制。

#### R1-C2 [CRITICAL] `apply_patch` 审批路径提取误用不存在的 `operation.movePath` 字段，且漏改 `NanoApproval` / `CcApproval` 的 `workingDirectory` 注入接线

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「模块与文件设计」`packages/dsh-integration/src/policy/file-approval.ts`（L176–177）
  - 关联实现：`packages/dsh-integration/src/policy/approval.ts`（L31, L149–153）、`packages/dsh-integration/src/policy/cc.ts`（L9, L13）
- **证据**：
  1. 在 `@deepseek-ai/dsh-fs-patch@0.2.2-rc.5` (`src/types.ts:30-37`, `src/parse.ts:97-98`) 中，`PatchOperation` 的 `update` 分支重命名目标字段定义为 `moveTo?: string`，**不存在** `design.md:177` 所写的 `operation.movePath`。
  2. `design.md:177` 将 `workspaceFileAllowed` 与 `codexFileAllowed` 签名改为接收 `{ workspaceRoot, effectiveCwd }`（通过 `ctx.workingDirectory.get(agent.session)` 获取），但修改文件清单遗漏了首道自动放行入口 `packages/dsh-integration/src/policy/approval.ts`（其 L31 `static inject` 未注入 `'workingDirectory'`，L150 在进入 `cc.ts`/`codex.ts` 前直接调用 `codexFileAllowed(cwd, ...)`），同时 `cc.ts:9` 的 `static inject = ['llm']` 也未声明 `'workingDirectory'`。
- **不修后果**：
  - 按 `operation.movePath` 实现会导致 TypeScript 编译失败；若以宽松字段读取返回 `undefined`，任何携带 `*** Move to: <path>` 的更新补丁都会漏检重命名目标路径，使移动到工作区外或覆盖受保护路径（如 `.git`、`AGENTS.md`）的操作在 CC Auto / Codex Auto 下直接免审放行。
  - 漏改 `approval.ts` 与 `cc.ts` 的 `workingDirectory` 依赖与调用入参会导致编译错误或运行时服务未注入异常。

#### R1-C3 [CRITICAL] 子 Agent 恢复契约断裂：`OwnedSessions.activateChild` 残留已移除的 `parentAgent` 且脱离 `SubagentManager`，`InterruptedWork` 改调 `ctx.subagents.sendMessage` 伪造父消息并抬升审批信任级

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「决策 4：移除 `@deepseek-ai/dsh-subagent/internal` 依赖」（L107–111）、`src/interrupted-work.ts`（L172）
  - 关联实现：`packages/dsh-integration/src/owned-sessions.ts`（L116–132）、`packages/dsh-integration/src/interrupted-work.ts`（L60–77）、`packages/dsh-integration/src/policy/sources.ts`（L202–214）
- **证据**：
  1. **冷恢复路径编译失败且脱离 `SubagentManager` 驻留表**：`owned-sessions.ts:122` 调用 `this.ctx.agents.resume({ resumeSessionId: child.header.id, parentAgent, ... })`，而 `@deepseek-ai/dsh-agent@0.2.2-rc.5` (`lib/types/index.d.ts:692-700`) 已删除 `ResumeAgentOptions.parentAgent`（`design.md` 未列出修改 `owned-sessions.ts`）。更关键的是，在 `@deepseek-ai/dsh-subagent@0.2.2-rc.5` (`src/manager.ts:509-522`) 中，子会话的归属与回传路由完全由 `SubagentManager.resident` 维护；经 `OwnedSessions.resolveManaged -> ctx.agents.resume` 直接恢复的子会话不在 `SubagentManager.resident` 中，该子会话调用 `send_message` / `subagent` / `list_agents` 时 `rootOf(caller)` 会直接抛 `SubagentError('agent has no active runtime owner', 'UNAUTHORIZED')`；且若一级子会话 `C1` 已借此进入 `ctx.agents`，`InterruptedWork.restore`（`interrupted-work.ts:70` 因 `ctx.agents.get(C1)` 存在而跳过 `C1`）随后恢复二级子会话 `C2` 调用 `ctx.subagents.sendMessage(C1, C2, ...)` 时，`rootOf(C1)` 同样抛 `UNAUTHORIZED` 中断整棵恢复树。
  2. **`ctx.subagents.sendMessage` 篡改系统恢复提示的发言人身份与审批来源**：旧版 `steerHostSubagentPrompt` 原样保留 `source: { kind: 'nano-system', channel: 'runtime-recovery', messageId }`。而 `0.2.2-rc.5` 的 `ctx.subagents.sendMessage(parent, childId, content, { signal })` 固定走 `createAgentMessage`（`dsh-subagent/src/continuation-messages.ts:64-76`）：(a) 在消息正文前强制拼接 `"Agent lead sent a message: "`（或父名称），向子模型伪造“父 Agent 发来新指令”；(b) 将 `source` 覆写为 `{ kind: 'agent-message', form: 'relay', senderSessionId: parent.id }` 并丢弃幂等 `messageId`；(c) 命中 `packages/dsh-integration/src/policy/sources.ts:202-214` 的 `parent` 分支（`source.kind === 'agent-message' && source.senderSessionId === agent.session.header.parentSession`），导致自动审批审阅器将该系统恢复提示误判为 `origin: { kind: 'direct-parent' }`（受信任父级指令）并漏挂 `system_source` 安全警告。
- **不修后果**：
  - `packages/dsh-integration` 类型检查直接失败；冷恢复的子会话无法回传父会话或导致多级断点恢复崩溃；子模型与自动审批审阅器把系统断点恢复提示当作父 Agent 新下达的授权指令，破坏 `spec.md` 与 `interrupted-work.ts` 的授权隔离承诺。

#### R1-C4 [CRITICAL] 原生轨迹实时原始结果流协议名全链路写错（应为 `'toolResults/watch'`）、`boot.jsx` 漏挂 `remote.toolResults` 契约且未剥离内联图片

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「现状与切入点」（L48）、§「决策 7」（L143）、§「模块与文件设计」`packages/dsh-integration/src/trajectory.ts`（L191）、`packages/dsh-trajectory-viewer/src/transport.ts`（L197）、`src/boot.jsx`（L198）、`apps/im-server/src/trajectory.ts`（L200）
- **证据**：
  1. 在 `@deepseek-ai/dsh-client-ui-trajectory@0.2.2-rc.5` 中，宿主服务 `SessionToolResults` 注册命名空间为 `{ namespace: "toolResults" }`（`lib/index.js:143`），客户端生成的远程流方法名为驼峰 **`'toolResults/watch'`**（`lib/typert.remote-client.js:27`），而非 `design.md` 在 `transport.ts`、`apps/im-server/src/trajectory.ts` 与 `packages/dsh-integration/src/trajectory.ts` 三处白名单写的 `'tool-results/watch'`。
  2. `0.2.2-rc.5` 轨迹客户端插件声明了 `export const inject = [..., 'remote', 'remote.toolResults']`（`src/client/index.ts:42`），并在 `watch-tool-result.ts:27` 调用 `ctx.remote.toolResults.watch(...)`；但 `packages/dsh-trajectory-viewer/src/boot.jsx`（L10–12, L111）仅挂载了 `[sessionRemote, commandsRemote, subagentRemote]`，`design.md:198` 只更新了 `init.version`，未导入并 `await ctx.remote.$mount(...)` 轨迹包的 `./remote` 契约。
  3. `packages/dsh-integration/src/trajectory.ts` 对 `session/follow` 与 `session/control` 输出帧均执行 `withoutInlineImages(...)`（L203, L226, L234, L243）以防绕过 IM `session/attachment` 鉴权直传内联图片字节；`design.md:191` 转发 `SessionToolResults.watch` 时未要求做相同脱敏。
- **不修后果**：
  - 轨迹查看器启动或点开任意工具调用时，因 `ctx.remote.toolResults` 未挂载直接抛 `TypeError`，或因 `'toolResults/watch'` 不在三层只读白名单中而被 `Read-only viewer denied toolResults/watch` 拦截，实时工具原始结果功能完全不可用；未经过 `withoutInlineImages` 过滤还会打开内联图片越权读取通道。

#### R1-C5 [CRITICAL] 默认上下文引擎 `dsh-agent-context@0.3.0-rc.11` 锁死 `0.2.1-alpha.1` peer 依赖，且受 `0.2.2` `system-prompt/assemble` 移除 `tools` 影响将工具 Schema Token 归零

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「决策 2」（L83）、§「模块与文件设计」`packages/dsh-integration/package.json`（L151）
  - 关联实现：`packages/dsh-integration/package.json`（`"dsh-agent-context": "0.3.0-rc.11"`）、`packages/dsh-integration/node_modules/dsh-agent-context/{package.json,lib/index.js,lib/budget.js}`
- **证据**：
  1. `dsh-agent-context@0.3.0-rc.11` 的 `peerDependencies`（`package.json:41-54`）精确锁定 `@deepseek-ai/*: "0.2.1-alpha.1"`、`@deepseek-ai/cordis: "4.0.5-alpha.1"` 与 `@deepseek-ai/schemastery: "~3.18.5-alpha.1"`，`design.md` 未包含 `dsh-agent-context` 的同步升级方案。
  2. `design.md:83` 已指出 `0.2.2` 的 `system-prompt/assemble` 瀑布流不再传入 `tools`（仅传 `PromptPresentation`，见 `dsh-system-prompt/lib/index.js:396-404`）并修复了后备 `NanoCompaction`（`compaction.ts`），但 Nano 会话默认启用的主滚窗引擎正是 `dsh-agent-context`（仅 `contextManagement === false` 时才走 `compaction.ts`）。核查 `dsh-agent-context/lib/index.js:59-65, 74-80, 192-207`：它在 `system-prompt/assemble` 中缓存不含 `.tools` 的返回值，并在 `agent/pre-step` 通过 `this.header(agent, assembly)` 生成 `{ ..., tools: undefined }` 传给 `budget.js:32, 38` 的 `meter.measure(session, header)` 与 `estimateToolsTokens(header)`。
- **不修后果**：
  - 包安装产生 peer dependency 失配；所有默认开启上下文管理的会话在步前预算测算时会将 `requestHeader().tools` 覆盖为 `undefined`，导致数千至上万的工具 Schema Token 被漏算为 `0`，固定预算上限保护、工具输出压力修剪、余量提醒注入与自动滚窗阈值全面失准。

---

#### R1-W1 [WARNING] `ModelPolicy` 迁至 `agent.model.select()` 存在撤回回退步被 `installModelSelection` 误唤醒及非冻结子会话丢失动态路由继承两处退化

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「决策 3：模型选择收敛到 `agent.model.select()`」（L96–100）、`src/model-policy.ts`（L160）
  - 关联实现：`packages/dsh-integration/src/model-policy.ts`（L41, L68–91, L151）
- **证据**：
  1. **`agent/pre-step` `{ prepend: true }` 顺序竞态**：在 Cordis 中后注册的 `{ prepend: true }` 监听器包裹先注册的监听器。`installModelSelection(agent.ctx)`（`dsh-agent/lib/index.js:232-243`）使用 `{ prepend: true }`，只要看到内层 `decision.messages.length > 0` 且路由较上次请求变更，就会追加 `[model changed: ...]` 消息。若 `ModelPolicy` 在其外层执行 `this.fallback.allowed(agent, decision.messages)` 过滤已撤回的回退消息（且已按 `design.md:160` 删去旧的 `model-selection` 过滤逻辑），撤回消息被滤除后数组仍残留 `[model changed: ...]`（`messages.length === 1`），`!messages.length` 拒绝分支失效。此外，冷恢复 `attach` 时若无条件调用 `agent.model.select()`，每次唤醒都会向持久日志重复追加 `model/selection` 事件推进 `seq`。
  2. **非冻结子会话动态继承断裂**：现有 `model-policy.ts:87-90` 在 `!config.modelRouteFrozen` 时让子会话每步动态读取父会话最新的 `sticky` 回退路由或 `/effort` 设置。`0.2.2-rc.5` 的 `ReactLoopAgent` 在 `agent/pre-step` 前即从子会话自身的 `childAgent.model.current()` 锁定当步路由（`dsh-agent-loop/lib/index.js:680`）；父会话发生 `ModelFallback` 粘性切换或 `/effort` 更新时，若不级联同步其存活的非冻结子会话，子会话不会感知父路由更新。
- **不修后果**：
  - 模型回退撤回轮次会被单条 `[model changed: ...]` 系统提示误唤醒发起空转模型请求；冷恢复产生冗余持久事件；父会话触发粘性模型回退后，其存活子 Agent 仍继续请求已故障的旧模型。

#### R1-W2 [WARNING] `cordis_inspect_*` 联动规则漏改 canonical spec 显式白名单条款，且在 `independentTool`、`CapabilityState` 与 `safeTools` 存在门控缺口

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/specs/gateway/agent-capabilities.md`（L1–28）
  - `docs/specs/gateway/agent-capabilities.md` § `Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖`（L829–853）
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「模块与文件设计」`src/capabilities.ts`（L181）
  - 关联实现：`packages/dsh-integration/src/capabilities.ts`（L17, L33–45, L81）、`src/capability-state.ts`（L30–31, L62–64）、`src/policy/approval.ts`（L25）
- **证据**：
  1. Canonical `docs/specs/gateway/agent-capabilities.md` L835 与 L851（`Scenario: 显式工具白名单不被默认集合自动扩宽`）明确限定显式非空 `tool_allowlist` 下“除四个上下文内部工具外，仅在启用 `plugin_manager` 时按已安装 workspace 工具集合增加独立工具名”。本次让 `plugin_manager` 额外联动开放 `cordis_inspect_list` / `cordis_inspect_query`，改变了该封闭集定义，但 delta-spec 未同步 `MODIFIED` 该 Requirement。
  2. 代码门控存在三处缺口：(a) 全局挂载的 `cordis_inspect_*` 会进入 `ToolSelection.captureDefaults()` 的 `nativeDefaults`，而 `userEntryTools`（`capabilities.ts:17`）未包含它们，导致禁用了 `plugin_manager` 的 Global 子会话仍会通过 `independentTool`（`capabilities.ts:36`）获得这两个工具；(b) `CapabilityState.prepare`（`capability-state.ts:62-64`）仅按公开目录 `catalog.tools` 计算撤回占用，关闭 `plugin_manager` 时不会自动锁住未出现在目录中的 `cordis_inspect_*` 在途/新发调用；(c) `approval.ts:25` 的 `safeTools` 未纳入这两个只读检查工具。
- **不修后果**：
  - 归并后 `docs/specs/gateway/agent-capabilities.md` 前后条款自相矛盾；内部子会话越权看到 `cordis_inspect_*`；在线关闭 `plugin_manager` 时无法原子排空在途 `cordis_inspect_*` 调用；每次只读运行时 Schema 查询在手动审批下弹窗阻塞或在 Auto 模式下额外消耗分类器 LLM 调用。

#### R1-W3 [WARNING] 手动调用 `ctx.systemPrompt.assemble` 未同步解析 `ctx.tools.resolve`（`toolSet`），导致条件工具在预压缩与能力预览中失真

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「模块与文件设计」`src/compaction.ts`（L162）
  - 关联实现：`packages/dsh-integration/src/index.ts`（L492, L526）、`packages/dsh-integration/src/knowledge/dreaming-agent.ts`（L121）
- **证据**：
  - 在 `@deepseek-ai/dsh-agent-loop@0.2.2-rc.5` (`lib/index.js:686-696`) 中，真实模型步先执行 `const toolSet = await ctx.tools.resolve({ agent, modelSelection, signal })`，再将 `{ ...assembleContextFor(agent, signal), modelSelection, toolSet }` 传入 `ctx.systemPrompt.assemble(...)`（结束后 `toolSet.dispose()`）。
  - 在 `@deepseek-ai/dsh-tools@0.2.2-rc.5` (`lib/index.js:418-420, 519-520, 579-581`) 与 `@deepseek-ai/dsh-tool-web@0.2.2-rc.5` (`lib/index.js:290, 351`) 中，若省略 `toolSet`，所有带 `when` 准入条件的工具（如无搜索源时的 `web_search`、无附件存储时的 `read_image`）均跳过 `when` 判定而被视为可见，同时混入 `assembly.tools` 与 `tool:web_search` 等系统提示词段落。`design.md:162` 仅传了 `modelSelection` 未传 `toolSet`，且未说明 `index.ts:492, 526` 与 `dreaming-agent.ts:121` 的同步口径。
- **不修后果**：
  - 小窗预压缩（`compaction.ts`）与上下文检查（`session.capabilities` / `preview`）组装出的工具列表和系统提示词与真实模型步不一致，既高估固定 Token 预算，也会干扰上下文前缀核查对真实请求载荷的判断。

#### R1-W4 [WARNING] `packages/trajectory-ui` 分叉合入未覆盖 `TrajectoryToolbar` 新增必填属性、`locate()` 嵌套折叠重置及窄抽屉工具栏密度验证

- **位置**：
  - `docs/changes/feat-787-dsh-022-upgrade/design.md` §「决策 7」（L141–145）、`packages/trajectory-ui/**`（L193）、§「里程碑 M1」（L227–230）
  - 关联实现：`packages/trajectory-ui/src/client/TrajectoryView.tsx`（L457–566）、`packages/trajectory-ui/src/client/TrajectoryToolbar.tsx`（L8–31）
- **证据**：
  1. 上游 `@deepseek-ai/dsh-client-ui-trajectory@0.2.2-rc.5` 在 `TrajectoryToolbarProps`（`TrajectoryToolbar.tsx:25-28`）新增了必填属性 `allSubCallsCollapsed` 与 `onToggleAllSubCalls`（渲染第 4 个折叠按钮 `subCalls`），并在 `TrajectoryView` 注入 `watchToolResult`。
  2. Nano 分叉在 `TrajectoryView.tsx:523-529` 定制了“定位起点 / 定位终点”跳转函数 `locate(end)`，当前仅清空 `collapsedTurns` 与 `collapsedAssistants`；合入 `collapsedSubCalls` 后若不在 `locate(end)` 中同步展开子调用折叠集，落在嵌套子调用内的范围边界记录将因处于折叠态而无法滚入可视区。
  3. Nano 原生轨迹运行在 IM Work 右侧分栏/抽屉的隔离 iframe 内，可用水平宽度明显窄于独立全屏页面；工具栏新增第 4 个按钮及工具详情新增“原始值 / 渲染结果”切换与冷态降级提示后，`design.md` 与 M1 验收未纳入 Work 抽屉常规窄视口下的工具栏排布与可读性核验。
- **不修后果**：
  - 合入上游组件时易遗漏 Nano 定制跳转与嵌套折叠状态的联动，导致执行范围定位失效，或在 IM 右侧 Work 抽屉窄宽度下出现工具栏按钮截断/搜索框挤压。

### Optional Recommendations

- **R1-R1 [Recommendation] 同步更新 `SPEC.md` 中的锁定版本号并显式纳入受管删除契约回归**：`SPEC.md:9` 仍写有“当前为 `0.2.1-alpha.1`”，且 `SPEC.md:51` 明确要求“DSH 升级需重新验证受管日志布局、租约与缓存清理契约”。建议在修改清单中补充更新 `SPEC.md:9` 的锁定版本说明，并在 M1 验证命令中显式列出 `agent-deletion` / JSONL 写租约与投影缓存清理相关单测。
- **R1-R2 [Recommendation] 微调 `ptc-runtime` 现状表述**：核查 `@deepseek-ai/dsh-ptc-runtime-node@0.2.2-rc.5` (`lib/index.js:69`) 可知 `executionMode` 默认值仍为 `'per-call'`（本次上游是新增了可选 `'persistent'` 模式而非改变默认值）。在 `cordis.patch.yml` 显式声明 `executionMode: per-call` 作为防漂移锁定完全合理，仅建议将 `design.md:36` 的表述修正为“新增可选进程复用模式，显式固定 `per-call`”。


### Author Resolutions

- **R1-C1** — `accepted`：核实 `@deepseek-ai/dsh-base@0.2.2-rc.5` 默认挂载的 `web-search-deepseek` 与 `web-deepseek-api` 均无条件返回 `available() === true`，未显式配置 `searchProvider` 时会抢占 `WebRuntime` 并在无 DeepSeek 凭据时令 `tool-web` 的 `when: ctx.web.searchReady(...)` 隐藏 `web_search` 阻断 `duckduckgo` 回退。已修订 `design.md`（关键决策 7、接口与数据流 §1/§3）：在 `cordis.patch.yml` 禁用 `web-search-deepseek` 与 `web-deepseek-api`，由 `NanoWeb` 单一注册 `'searxng'`、`'brave'`、`'deepseek-search-api'`（走 `proxyRouteFor` + `mapSearchResponse`，禁发 `ori_question`，仅接受原生 DeepSeek 凭据或 `hostname === 'api.deepseek.com'` 的 `llm-pi-ai` 密钥）与 `'duckduckgo'`，通过与 `NativeModelSetup` 同步的凭据快照实现互斥 `available()`/`ready()`，保证任一配置态下唯一目标源被选中且 `web_search` 在 `duckduckgo` 兜底态下始终可见。
- **R1-C2** — `accepted`：核实 `@deepseek-ai/dsh-fs-patch@0.2.2-rc.5` 的 `PatchOperation` 更新分支重命名目标字段确为 `operation.moveTo`（非 `movePath`），且 `NanoApproval`（`approval.ts`）、`CcApproval`（`cc.ts`）、`CodexApproval`（`codex.ts`）均需注入 `'workingDirectory'`。已修订 `design.md`（现状分析、关键决策 3/4、接口与数据流 §3），明确提取 `operation.path` 与 `operation.moveTo` 并补齐 `approval.ts`、`cc.ts`、`codex.ts` 与 `file-approval.ts` 的 `workingDirectory` 接线。
- **R1-C3** — `accepted`：核实 `@deepseek-ai/dsh-agent@0.2.2-rc.5` 已移除 `ResumeAgentOptions.parentAgent`、`SubagentManager.rootOf` 要求子会话驻留在 `SubagentManager.resident`，且 `ctx.subagents.sendMessage` 会拼接 `"Agent lead sent a message: "` 前缀并写入 `agent-message` 来源触发 `sources.ts` 误判为 `direct-parent`。进一步核查 `@deepseek-ai/dsh-typert-protocol` 与 `dsh-subagent` 确认公开方法 `ctx.subagents.prompt({ childSessionId, requestId, delivery: 'steer', content }, signal)` 在进程内直接调用时无装饰器拦截、在 `SubagentManager.resident` 内冷恢复目标子会话、原样投递正文且其 `{ kind: 'user', rpcId }` 在 `input-source.ts` 中 `isHumanSource === false`。已修订 `design.md`（关键决策 8、接口与数据流 §2/§4）：删除 `OwnedSessions.activateChild`；`InterruptedWork.restore`（及冷子会话 `schedule.deleted.notify`）改用 `ctx.subagents.prompt` 携带 `nano-runtime-*` 前缀 `requestId`，并在 `policy/sources.ts` 识别该 `rpcId` 归类为 `system_source`（`origin: { kind: 'nano-system' }`）。同时在核查子会话调度入口时一并补齐了 `@deepseek-ai/dsh-schedule@0.2.2-rc.5` v2 `ScheduleService` 与 `features/cron.ts` 主会话 6 工具桥接方案。
- **R1-C4** — `accepted`：已在 `design.md`（架构总览、关键决策 8、接口与数据流 §4 与时序图）统一固化驼峰方法名 `'toolResults/watch'`，明确在 `packages/dsh-trajectory-viewer/src/boot.jsx` 挂载 `@deepseek-ai/dsh-client-ui-trajectory/remote`（并登记 `test_runtime_dependency_contract.py`），以及在 `NativeTrajectory.open` 对每帧 `{ available: true, value }` 执行 `withoutInlineImages` 脱敏。
- **R1-C5** — `accepted`：已在 `design.md`（关键决策 1、接口与数据流 §2）明确同步升级发布 `dsh-agent-context@0.3.0-rc.12`（对齐 `0.2.2-rc.5` peer 依赖），在 `agent/pre-step` 先通过 `ctx.tools.resolve` 获取并释放 `toolSet`，再调 `ctx.systemPrompt.assemble` 读取完整 `assembly.tools` 计算真实工具 Schema Token 预算。
- **R1-W1** — `accepted`：已修订 `design.md`（关键决策 2、接口与数据流 §2）：在 `ModelPolicy.attach` 中先注册撤回过滤的 `agent/pre-step`（`{ prepend: true }`）再调用 `installModelSelection(agent.ctx)` 以阻断撤回轮次被 `[model changed: ...]` 误唤醒；`syncRoute` 仅在目标路由与 `agent.model.current()` 实际不等价时调用 `agent.model.select()` 避免冷恢复冗余事件；父路由变化时级联同步所有 `!childConfig.modelRouteFrozen` 的存活子会话（空闲立即同步、运行中 `whenIdle()` 同步）。
- **R1-W2** — `accepted`：已在 `specs/gateway/agent-capabilities.md` 新增 `MODIFIED Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖` 同步显式白名单封闭集条款，并在 `design.md`（关键决策 5、接口与数据流 §3）补齐 `capabilities.ts`（`userEntryTools`）、`capability-state.ts`（`prepare` 撤回目标集与 `begin` 占用拦截）及 `approval.ts`（`safeTools`）三处门控。
- **R1-W3** — `accepted`：已在 `design.md`（关键决策 6、接口与数据流 §2）统一规定 `dsh-agent-context@0.3.0-rc.12`、`packages/dsh-integration/src/index.ts`（`session.capabilities` 与 `preview`）及 `dreaming-agent.ts` 四处手动组装入口均先调用 `ctx.tools.resolve({ agent, modelSelection, signal })` 传入 `toolSet` 并在 `finally` 释放。
- **R1-W4** — `accepted`：已在 `design.md`（接口与数据流 §4、本次审查安排、Runbook 与 M1 退出标准）补齐 `TrajectoryToolbar` 新增必填属性 `allSubCallsCollapsed` / `onToggleAllSubCalls`、定制 `locate(end)` 清空 `collapsedSubCalls`，以及 IM Agent Work 右侧窄抽屉视口下的工具栏排布与可读性走查要求。
- **R1-R1** — `accepted`：已在 `design.md`（涉及范围、契约层增量、本次审查安排、Runbook 与 M1）显式纳入 `SPEC.md:9` 版本号更新与 `agent-deletion` 受管日志布局/写租约/缓存清理契约回归单测。
- **R1-R2** — `accepted`：已修正 `design.md` 关键决策 6 的表述，如实说明 `@deepseek-ai/dsh-ptc-runtime-node@0.2.2-rc.5` 新增可选 `'persistent-in-memory'` / `'vm-script'` 模式（默认仍为 `'per-call'`），在 `cordis.patch.yml` 显式声明 `executionMode: per-call` 作为防漂移锁定。


## Round 2

### Metadata

- **Change Unit**: `feat-787-dsh-022-upgrade`
- **review_mode**: `delta`
- **mode_reason**: Round 1 的 `5 CRITICAL / 4 WARNING / 2 Recommendation` 已全部修订回应，且本轮新增了公开 `ctx.subagents.prompt` 恢复与 `sources.ts` 系统来源归属、移除 `OwnedSessions.activateChild`、`dsh-schedule@0.2.2-rc.5` v2 `ScheduleService` 与主会话 6 工具桥接、`dsh-agent-context@0.3.0-rc.12` 适配要点及 `specs/gateway/agent-capabilities.md` 新增 `MODIFIED Requirement`；采用 `delta` 模式逐项核实历史问题闭环，并完整审查本轮新增设计与相邻模块接缝。
- **started_at**: `2026-11-25T14:12:10+09:00`
- **completed_at**: `2026-11-25T14:17:43+09:00`
- **duration**: `5m 33s`

### Verdict

**Approved**（`0 CRITICAL / 0 WARNING / 1 Recommendation`）

### Coverage & Evidence

本轮对照修订后的 `design.md`、`specs/gateway/agent-capabilities.md`、`design-review.md`（`### Author Resolutions`）、仓库受影响代码（`owned-sessions.ts`、`interrupted-work.ts`、`policy/sources.ts`、`input-source.ts`、`model-policy.ts`、`model-fallback.ts`、`cron-owners.ts`、`features/cron.ts`、`history.ts`、`agent-deletion.ts`、`agent-deletion-derived.ts`、`packages/product-contracts/src/runtime-rpc-schedule.ts`）以及 `@deepseek-ai/*@0.2.2-rc.5` 解包源码（新增核查 `dsh-subagent/src/{index,manager,control}.ts` 与 `dsh-schedule/lib/index.js`）：

1. **子会话恢复与来源隔离新方案核实**：
   - 核查 `@deepseek-ai/dsh-subagent@0.2.2-rc.5` (`src/index.ts:450-492`, `src/manager.ts:585-641`, `src/control.ts:15-23`)：`ctx.subagents.prompt({ childSessionId, requestId, delivery, content }, signal)` 为公开方法，进程内直接调用时 `principalOf(this.ctx.invocation)` 为 `undefined`，内部通过 `deliverPrompt -> resolveCreationAncestry -> deliverToMember` 在已激活的 `root` 下将冷子会话恢复进 `SubagentManager.resident` 并原样投递 `content`（不拼接 `"Agent lead sent a message: "` 前缀）。
   - 核查 `packages/dsh-integration/src/input-source.ts:25-28` 与 `policy/sources.ts:153-155, 202-215`：`subagents.prompt` 生成的 `source: { kind: 'user', rpcId }` 不含 `actorId/channel/messageId`，`isHumanSource(source)` 严格为 `false`；配合 `sources.ts` 将 `rpcId.startsWith('nano-runtime-')` 排除在 `initialId` 与 `parent` 之外并归入 `system_source`（`origin: { kind: 'nano-system' }`），以及删除 `OwnedSessions.activateChild`（检索全仓仅 `OwnedSessionController.resolveAgent` 与 `schedule.deleted.notify` 两处调用点，均已在设计中闭合），彻底消除了脱离 `SubagentManager` 的野生恢复与审批提权隐患。
2. **`dsh-schedule@0.2.2-rc.5` v2 桥接核实**：
   - 核查 `@deepseek-ai/dsh-schedule@0.2.2-rc.5` (`lib/index.js:1590-1677, 2117-2129, 2233-2535`)：`scheduleDomain` 升至 `version: 2` 且声明 `compatibleVersions: [1]`（读取时自动将旧 `sessionId` 归一为 `target: { kind: 'session', sessionId }`、将 `'inactive'` 归一为 `'ended'`）；`ScheduleService` 通过继承的 `sessionController`（即本仓挂载的 `OwnedSessionController`）激活目标根会话；`CronOwners.skipMissed`、`catalog`、`history` 与 `features/cron.ts` 自持主会话 6 工具的设计与 v2 存储和 `runtime-rpc-schedule.ts` 契约完全匹配。
3. **无 `parentSession` 普通分支与受管删除闭合核实**：
   - 核查 `history.ts:114-123`、`agent-deletion.ts:158-186` 与 `agent-deletion-derived.ts:44`：`OwnedSessions.fork` 移除 `header.parentSession` 后，`NativeHistory.configuration` 凭 `creating && isSeeded && origin !== 'subagent'` 写入 `historyDomain.forks`，而 `ownedLinks()` 原本即遍历 `historyDomain.table('forks')` 建立 `fork.source -> fork.sessionId` 归属边，永久删除范围不丢失新建普通分支。
4. **Delta-spec 与专项审查复核**：
   - 核查 `specs/gateway/agent-capabilities.md` 新增的 `MODIFIED Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖`（L51–91）：完整保留 canonical `docs/specs/gateway/agent-capabilities.md`（L829–870）全部正文与 6 个既有 Scenario，准确并入 `plugin_manager` 下的 `cordis_inspect_list` / `cordis_inspect_query` 受控增量并明确不自动扩宽未列出的 `apply_patch`。
   - Agent Context 与前端轨迹查看器专项设计问题（`dsh-agent-context@0.3.0-rc.12`、`tools.resolve` `toolSet`、`ModelPolicy` 包装顺序、驼峰 `toolResults/watch`、`boot.jsx` 挂载 `./remote`、`withoutInlineImages`、`locate()` 展开子调用及右侧窄抽屉走查）均已完整落入设计、Runbook 与 M1 退出标准。

### Historical Issues Closure

- **R1-C1** — `resolved`：`design.md`（关键决策 7、接口与数据流 §1/§3）已明确在 `cordis.patch.yml` 禁用 `web-search-deepseek` 与 `web-deepseek-api`，由 `NanoWeb` 单一注册互斥 `available()`/`ready()` 的四级搜索源并走 `proxyRouteFor` + `mapSearchResponse`（禁发 `ori_question`、限定官方 `api.deepseek.com` 域名），消除了注册冲突、`web_search` 消失与 `duckduckgo` 回退阻断。
- **R1-C2** — `resolved`：`design.md`（关键决策 3/4、接口与数据流 §3）已将 `apply_patch` 重命名目标字段修正为 `operation.moveTo`，并补齐 `NanoApproval`、`CcApproval`、`CodexApproval` 的 `'workingDirectory'` 注入与 `{ workspaceRoot, effectiveCwd }` 传参。
- **R1-C3** — `resolved`：`design.md`（关键决策 8、接口与数据流 §4）已删除 `OwnedSessions.activateChild`，统一改用公开 `ctx.subagents.prompt` 在 `SubagentManager.resident` 内恢复可接续子会话，并在 `policy/sources.ts` 将 `nano-runtime-*` `rpcId` 排除出 `initialId`/`parent` 归入 `system_source`。
- **R1-C4** — `resolved`：`design.md`（关键决策 8、接口与数据流 §4 及时序图）已统一修正为驼峰 `'toolResults/watch'`，补齐 `boot.jsx` 挂载 `@deepseek-ai/dsh-client-ui-trajectory/remote`（含契约测试白名单同步）及 `NativeTrajectory.open` 的 `withoutInlineImages` 脱敏。
- **R1-C5** — `resolved`：`design.md`（关键决策 1、接口与数据流 §2、风险与 M1）已明确同步发布接入 `dsh-agent-context@0.3.0-rc.12`，升级 `0.2.2-rc.5` peer 依赖、通过 `tools.resolve` + `systemPrompt.assemble` 计入真实 `assembly.tools` Token 预算，并去除了换窗后重复的裸文本 `runtime-context` 注入。
- **R1-W1** — `resolved`：`design.md`（关键决策 2、接口与数据流 §2）已明确先注册 `ModelPolicy` 撤回过滤 `{ prepend: true }` 监听器再调用 `installModelSelection(agent.ctx)`、`syncRoute` 按需判等调用 `agent.model.select()`，以及父路由变更向非冻结存活子会话级联同步。
- **R1-W2** — `resolved`：`specs/gateway/agent-capabilities.md` 已补充 `MODIFIED Requirement: Agent 工具集 SHALL 按工具选择兑现，Feature 保证完整依赖`；`design.md`（关键决策 5、接口与数据流 §3）已补齐 `userEntryTools`、`CapabilityState`（`prepare` 与 `begin`）及 `approval.ts` `safeTools` 门控。
- **R1-W3** — `resolved`：`design.md`（关键决策 6、接口与数据流 §2）已统一要求 `dsh-agent-context@0.3.0-rc.12`、`index.ts`（`session.capabilities` / `preview`）与 `dreaming-agent.ts` 先执行 `ctx.tools.resolve` 传入并在 `finally` 释放 `toolSet`。
- **R1-W4** — `resolved`：`design.md`（接口与数据流 §4、本次审查安排、Runbook 与 M1）已补齐 `TrajectoryToolbar` 新增必填折叠属性、`locate(end)` 清空 `collapsedSubCalls` 及 IM Work 右侧窄抽屉视口走查要求。
- **R1-R1 / R1-R2** — `resolved`：均已采纳落实（更新 `SPEC.md:9` 版本声明并纳入 `agent-deletion` 删除契约单测；修正 `ptc-runtime` 默认值现状表述）。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Optional Recommendations

- **R2-R1 [Recommendation] `scheduleHandlers.update` 兼容保留 `schedule_ended` 返回码**：核查 `@deepseek-ai/dsh-schedule@0.2.2-rc.5` (`lib/index.js:1940-1942`) 可知，对 `status === 'ended'` 的一次性任务若调用 `service.edit` 仅修改 `title`/`prompt` 而不提供新 `timing`，v2 会原样保留 `status: 'ended'` 并返回更新后条目，而本仓 `packages/product-contracts/src/runtime-rpc-schedule.ts:33` 契约定义了 `{ id, updated: false, code: 'schedule_ended' }`。建议实施 `scheduleHandlers.update`（及 `features/cron.ts` 的 `schedule_update`）桥接层时，对已处于 `'ended'` 且未传入新未来 `change` 的任务显式返回 `code: 'schedule_ended'`，保持既有 RPC 边界语义一致。


### Author Resolutions

- **R2-R1** — `accepted`：核实 `packages/product-contracts/src/runtime-rpc-schedule.ts:33` 既有返回码契约包含 `{ id, updated: false, code: 'schedule_ended' }`。这已包含在 `design.md` §「接口与数据流 §4」（`scheduleHandlers` / `features/cron.ts` 对接既有产品 RPC 契约）的实施职责内，实施时对 `status === 'ended'` 且未提供新未来 `change` 的更新请求显式返回 `code: 'schedule_ended'`；本轮受审设计文档与 delta-spec 无需再做实质改动。
