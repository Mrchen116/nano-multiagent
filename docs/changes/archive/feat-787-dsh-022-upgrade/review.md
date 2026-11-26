# feat-787: Review

## 范围与版本

- 本次问题与需求/设计位置：[`spec.md`](spec.md)、[`design.md`](design.md)、[`design-review.md`](design-review.md)、[`specs/gateway/agent-capabilities.md`](specs/gateway/agent-capabilities.md)、[`specs/gateway/tool-approval.md`](specs/gateway/tool-approval.md)、[`specs/im/agent-work.md`](specs/im/agent-work.md)、[`M1-dsh-022-upgrade/evidence/acceptance.md`](M1-dsh-022-upgrade/evidence/acceptance.md)
- 实际 `executed_base` / `validated_at`：`b9baa494ce4130b6b2e6bc24b8d9117c2bb8ed0e` (`origin/develop`) → Round 1 `5785f7341` → Round 2 `6443b1b1f99b3675842351792dd768d0e7cf8d87`
- 最终 `effective_base` / `effective_through` 与保留依据：`db7167c9d13a5e09fc23224359442a49582a8025` (`origin/develop`，新合入 `#548` `feat-788` 外部 `agy` worker 驱动) → `d3e9730adc2dbd2a650093fab0dcd8aa0e5446e3`（`6443b1b1f` 零冲突线性变基，与 DSH `0.2.2-rc.5` 运行时、上下文与原生轨迹改动正交，已复跑 `local-worker-*.test.ts` 4 文件 18 用例及全套本地 CI 门禁通过；后续收口提交仅含本 `review.md`、已核准契约归并、`docs/changes/archive/` 归档移动及 `anthropic_sse_collaboration_recording.py` 纯 `ruff format` 空白折行，无逻辑变更，独立审查结论完整保留）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| `@deepseek-ai/*@0.2.2-rc.5` 与 `dsh-agent-context@0.3.0-rc.12` 升级、`startActivation` 委派与恢复、`apply_patch` 审批/保护边界、`cordis_inspect_*` 权限联动、官方 DeepSeek 搜索脱敏复用、只读 `toolResults/watch` 透传、Windows 发布包图及最终契约一致性 | `change-code-review`，独立审查子代理（`d69705bb-7c41-4b04-a3fe-ddfb51164abe`），`full`（`b9baa494c..5785f7341`）+ `patch` / `closure` / `corrected-delta`（`5785f7341..6443b1b1f`） | `pass` | 独立逐行审查全部受影响包与测试，核实架构红线（`test_runtime_dependency_contract.py` 14/14、`pnpm peers check` 0 告警）、`R1-C1..C5`、`R1-W1..W4`、`R1-R1..R2`、`R2-R1` 全覆盖；Round 1 三项问题（`F1`–`F3`）在 `6443b1b1f` 全部关闭并补充定向单测；三份 delta-specs 与 canonical specs 及实现逐条核对为 `aligned`。 |
| 根会话与 `subagent_fork` / `spawn` 模型实际可见工具目录、描述、工作目录来源消息、正式记忆补丁保护、修剪/换窗衔接与 KV 缓存前缀不变量 | `agent-context-review`，独立审查子代理（`f3ffbc51-199f-49c5-9503-06ea81230f85`），实施模式（`5785f7341` 初审 + `6443b1b1f` 真模型出站 `wire-tee.jsonl` 复验） | `pass` | 独立审查者亲自核读脱敏出站 `/v1/messages` 请求原件（初轮 19 条 + 修复后 13 条，覆盖 `pa_a19e8ee354e6`、`daily-engineering` 主会话及 `subagent_fork` 子会话）与受控前缀重放测试：确认不含 `working_directory`、`subagent_oar`、`team_task_*`；PA 开启 `plugin_manager` 时准确下发并成功调用 `cordis_inspect_list`；`subagent_fork` 与父会话 `system`/`tools`/`messages[0..70]` 前缀 100% 一致；软链工作区下虚假 `working directory changed` 消息为 0。 |
| 原生轨迹查看器分叉升级后的多视口布局几何、子调用折叠交互可理解性、实时结构化原始结果与渲染结果双视图、冷态降级文案及失败错误可读性 | `frontend-experience-review`，独立审查子代理（`a9c51112-3914-4a78-bc20-298d2415831f`），实施模式（隔离真栈 `1440x900` / `960x800` / `640x800` 实测 + `6443b1b1f` 契约与截图复核） | `pass` | 在 `1440x900`（工具栏 `1062px`）、`960x800`（`814px`）与 `640x800` 实测 `scrollWidth === clientWidth`、零横向裁切且浏览器 `consoleErrors`/`pageErrors` 为空；核实存活会话 JsonTree `原始结果` + `渲染结果` 双栏/上下对照与冷态降级提示清晰无歧义；子调用批量折叠/点击摘要展开的表述偏差（`FE-1`）与两张采样截图偏差（`FE-2`）已收口。限制：桌面宿主窗口遮挡时 T3 预览未产出帧，按规则在同环境 Playwright Chromium 对同一隔离栈完成实测。 |
| 从真实 IM Web 入口验证存活会话 `toolResults/watch`、Gateway 冷重启不唤醒历史会话、工具报错原文保留、`subagent_fork` 子执行钻取范围定位与设置页能力开关边界 | `product-journey-review`，独立审查子代理（`a9c51112-3914-4a78-bc20-298d2415831f`），实施模式（基于同一隔离真栈与真实模型会话） | `pass` | 真实走通存活会话 `cordis_inspect_list` 结构化结果观察、Gateway 重启后查看 `51fbb433-...` 保持 `agentAvailable === false` 且完整回看 `渲染结果`、`read` 缺失文件红色错误详情、`subagent_fork` `← 返回发起点` 与 `定位起点`/`定位终点` 联动，以及能力配置页仅暴露 `apply_patch` 而不暴露 `cordis_inspect_*`/`working_directory`/`subagent_oar`。限制：未覆盖原生 iOS 客户端（原生轨迹双视图契约仅适用于 Web）。 |

## Findings 与关闭

- **F1 / ACR-1**（`packages/dsh-integration/src/capabilities.ts:21-25`）：`allowsCordisInspect` 旧判断排除 `config.personal` 且在 `isOrdinaryChild` 分支读取子级 `config.toolAllowlist`，导致启用 `plugin_manager` 的 PA 主会话无法获得 `cordis_inspect_*`，且未显式保存 `toolAllowlist` 的根会话调用 `subagent_fork` 时父子 `cordis_inspect_*` 工具集不一致破坏缓存前缀。
  - 严重度 / 证据状态：`HIGH` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：移除 `!config.personal` 限制；对 `isOrdinaryChild(agent) || globalWorkRole(agent, config)` 统一返回 `false`，而 `subagent_fork`（`!isOrdinaryChild`）沿用根配置 `config.toolAllowlist === undefined || config.toolAllowlist.includes('plugin_manager')` 与父级严格一致；新增 `cordis-inspect-and-web.test.ts` PA 用例、`fork-prefix-provider.test.ts` 与真模型 PA `wire-tee` 实测。
  - 独立关闭依据与版本：`change-code-review`（`d69705bb`）与 `agent-context-review`（`f3ffbc51`）在 `6443b1b1f` 核查代码、单测与 PA/Fork `wire-tee.jsonl`（PA 请求含 `cordis_inspect_list` 并真实调用成功，Fork 前缀 100% 匹配），判定 **`closed`**。
- **F2**（`packages/dsh-integration/src/workflow/engine.ts:205-214`，关联 `interrupted-work.ts:63-70`、`index.ts:327-332`、`global-mode.ts:119-121`）：DSH `0.2.2` 对 `startActivation({ delivery: 'caller' })` 的 Workflow step 会话同样持久化 `subagent.mode === 'continuable'`，导致节点重启中断恢复、超时回收提示与父级 `send_message({ agent })` 误将内部 Workflow step 当作普通可接续子会话。
  - 严重度 / 证据状态：`MEDIUM` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：新增 `NanoWorkflowEngine.isWorkChild(session)` 识别 `workflow_work_children` 记录，在 `InterruptedWork.restore`、`subagentRecovery.record` 与 `global-mode` `send_message({ agent })` 入口统一排除 Workflow step 会话；在 `subagent-recovery-and-model-cascade.test.ts` 新增回归测试。
  - 独立关闭依据与版本：`change-code-review`（`d69705bb`）在 `6443b1b1f` 核查三处守卫与新增回归测试通过，判定 **`closed`**。
- **F3**（`packages/dsh-integration/src/task-context.ts:62-75,147-160`）：`agent/turn-stopping` 钩子内过早执行 `stoppingSessions.delete(agent.id)`，若同轮后续 `ContextRolloverEngine` 注入自动 `new_context` 换窗续跑，续跑轮将漏挂 `stoppingSessions` 抑制标记并重注过期 `<task_context>`。
  - 严重度 / 证据状态：`MEDIUM` / `PLAUSIBLE`。
  - Resolution（`6443b1b1f`）：移除 `agent/turn-stopping` 内的提前删除，保持 `stoppingSessions` 跨越同轮自动 `new_context` 换窗，统一在 `turn/start`、`turn/end`、`agent/inbox/spliced`（`target === 'next-step' && removedCount > 0`）及实际重开步的 `agent/pre-step`（含 `prepareStep` 兜底）清理；新增 `task-child-context.test.ts` 回归测试。
  - 独立关闭依据与版本：`change-code-review`（`d69705bb`）在 `6443b1b1f` 核查事件时序与回归测试通过，判定 **`closed`**。
- **ACR-2**（`packages/dsh-integration/src/knowledge/document-memory.ts:170-219`）：正式记忆目录的 Dreaming 专属写保护此前仅拦截 `write`/`edit`，在 `dangerouslySkipPermissions`（免过 `ApprovalEngine`）场景下模型可通过 `apply_patch` 写入或 `Move to` 篡改正式记忆文件。
  - 严重度 / 证据状态：`HIGH` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：在 `DocumentMemory` 的 `tool/before-call` 守卫中接入 `@deepseek-ai/dsh-service-patch` 的 `parsePatch`，按会话有效 `workingDirectory` 与祖先软链真实路径校验全部 `op.path`、`op.moveTo`（解析失败在拥有正式记忆目录的会话上 fail-closed 拦截）；在 `memory-child-runtime.test.ts` 补充越权补丁与移动拦截测试。
  - 独立关闭依据与版本：`agent-context-review`（`f3ffbc51`）与 `change-code-review`（`d69705bb`）在 `6443b1b1f` 复核代码与单测通过，判定 **`closed`**。
- **ACR-3**（`packages/dsh-integration/src/child-role.ts:29-39`、`knowledge/runtime.ts:148`）：`attachChildRole` 非幂等覆盖及 `KnowledgeRuntime.isWorkWorker` 误判导致 Global 主会话调用 `subagent_fork` 时子会话被剥离 `memory_maintenance` 与记忆上下文，破坏父子缓存前缀一致。
  - 严重度 / 证据状态：`MEDIUM` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：`attachChildRole` 保持既有角色幂等，`KnowledgeRuntime.isWorkWorker` 收敛为 `isInternalExecution(agent)`，使根会话 `subagent_fork` 完整保留父级 `memory_maintenance` 工具声明；经 `fork-prefix-provider.test.ts` 与真模型 `wire-tee.jsonl` 确认父子 `tools` 与前缀完全一致。
  - 独立关闭依据与版本：`agent-context-review`（`f3ffbc51`）在 `6443b1b1f` 核对 `wire-tee.jsonl` 请求 `[07]`/`[08]` 前缀 100% 一致，判定 **`closed`**。
- **ACR-4**（`packages/dsh-integration/src/owned-sessions.ts:162-170`、`agent-config.ts:152-162`、`policy/sources.ts:218`、`global-mode.ts:102`）：macOS `/tmp` → `/private/tmp` 软链工作区下，`header.cwd` 与 `realpath` 字符串不等触发上游每轮注入无意义的 `<system-reminder>Working directory changed...</system-reminder>`，且 `sources.ts` 未显式归类 `working-directory` 来源、`send_message` 缺 `agent_id` 兼容参数说明。
  - 严重度 / 证据状态：`LOW` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：在不改动 `session.header.cwd === binding.cwd` 存储不变量的前提下，于 `setup` 初始同步归一化软链等价的 `workingDirectory`；在 `policy/sources.ts` 将 `source.kind === 'working-directory'` 归入 `system_source`；在 `global-mode.ts` 补充 `agent_id` 别名提示。
  - 独立关闭依据与版本：`agent-context-review`（`f3ffbc51`）在 `6443b1b1f` 核实 `/tmp/...` 隔离栈全 13 条真实出站请求中 `working directory changed` 消息为 0，判定 **`closed`**。
- **FE-1**（`docs/changes/feat-787-dsh-022-upgrade/spec.md:115-116`、`specs/im/agent-work.md:17`）：契约草案原写“逐行与批量折叠／展开”，而上游 `0.2.2-rc.5` 与本仓分叉实际提供工具栏批量子调用折叠/展开、点击已折叠摘要行独立展开（展开态不设逐行再次单独收起按钮）及搜索/定位命中自动展开。
  - 严重度 / 证据状态：`LOW` / `CONFIRMED`。
  - Resolution（`6443b1b1f`）：将 `spec.md` 与 `specs/im/agent-work.md` 精确收口为“工具栏嵌套子调用批量折叠／展开与点击已折叠摘要独立展开……搜索或定位命中被折叠的子调用时自动展开对应项”。
  - 独立关闭依据与版本：`change-code-review`（`d69705bb`）在 `6443b1b1f` 执行 `corrected-delta` 校对确认与 `TrajectoryTable.tsx`/`TrajectoryToolbar.tsx` 行为完全一致，判定 **`closed`**。
- **FE-2**（本地浏览器走查采样截图 `01`、`03`）：初轮自动截图脚本未先切换至「原生轨迹」标签即截取 `1440x900` 图，且 `subagent_fork` 子会话详情点中了助手行而非「返回发起点/定位起点」控件。
  - 严重度 / 证据状态：`LOW` / `CONFIRMED`（仅取证脚本定位偏差，非产品缺陷）。
  - Resolution（`6443b1b1f`）：修正采样定位后对同一隔离栈重新截取并目视核实 `1440x900` 原生轨迹工具栏与 `subagent_fork` 范围定位面包屑画面，验收结束后随临时目录一并清理不入库。
  - 独立关闭依据与版本：主 Agent 按 `frontend-experience-review` 指引重采核实画面与 DOM 测量一致，判定 **`closed`**。

最终状态：**无存活 findings（0 open）**。

## 流程收口

- 重要目标和关键设计覆盖：配套扩展 `Mrchen116/dsh-agent-context@0.3.0-rc.12` 已发布；[`spec.md`](spec.md) 与 [`design.md`](design.md) 的全部需求（`R1-C1`–`R1-C5`、`R1-W1`–`R1-W4`、`R1-R1`–`R1-R2`、`R2-R1`）及 `M1` 退出标准均已实现并通过四层验证漏斗与四项独立审查门禁。
- 开放问题 / pending / inconclusive：0 项。
- 最终 delta 校对：独立代码审查（`d69705bb-7c41-4b04-a3fe-ddfb51164abe`）在 `6443b1b1f` 完成 `corrected-delta` 核对，[`specs/gateway/agent-capabilities.md`](specs/gateway/agent-capabilities.md)、[`specs/gateway/tool-approval.md`](specs/gateway/tool-approval.md)、[`specs/im/agent-work.md`](specs/im/agent-work.md) 全部判定为 **`aligned`**（归并后 `gateway/agent-capabilities.md` Requirement 数由 `64` 增至 `67`，其余保持不变）。
- 版本变化后保留 / 补验的判断与依据：Round 1（`5785f7341`）→ Round 2（`6443b1b1f`）已完成独立代码补审、真模型 `wire-tee` Context 复验与 `corrected-delta` 校对；随后同步最新 `origin/develop`（`db7167c9d`，合入 `#548` `feat-788`）生成 `d3e9730ad` 无任何冲突且与本单元改动面正交，复跑 `local-worker-*.test.ts` 与全套本地 CI 门禁通过；最终归档提交仅含文档归并与目录移动，全部独立审查判断保持有效（`retained`）。
- 测试资源回收结果 / 例外保留项、owner 与回收触发：隔离真栈 `/tmp/nano-e2e-787.iPNxw8`、回环抓包进程 `wire-tee.py`、`tmux` 会话 `nano-e2e-787`、临时端口 `56168`/`60170`、浏览器截图缓存、`src/IM/frontend/dist` 及 `dsh-agent-context` 临时工作目录均已完整停止并清理核实；专属开发 worktree `/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-787-dsh-022-u-5c64eade305a14d8` 按仓库规则保留至 PR 合入 `develop` 后由执行合并或接手后续工作的 Agent 清理。
- 交付范围与剩余事项：完成三份 canonical specs 归并、归档 `docs/changes/archive/feat-787-dsh-022-upgrade`、跑通本地 CI 等价门禁，推送 `unit/feat-787-dsh-022-upgrade` 并创建目标为 `develop` 的 PR，等待远端检查与人工审阅合入（不自动 merge）。
