# feat-517 — 验收报告

> 对齐：`spec.md` 的验收标准与 `design.md` Runbook / 原型对齐契约

> Validation snapshot: `cd071e649d3fe4fe7a2f392643a49c8f87825898 → 7d77880234ccefdcfed03f3d630a1db450afb591`

> Round: 1（full revalidation，2026-08-10）

## Verdict

**fail**

**Highest Required Action：`fix-implementation`**

CLI 非交互与飞书可以完成最小 Workflow，但 coding CLI 默认交互主路径无法展示审批并被直接拒绝；Web IM 完成后不展示设计要求的后台原始返回；Web/飞书子 Agent 也没有继承用户指定的 Luna。这些都直接影响本 unit 的可交付性。

## User Journeys Exercised

1. **CLI Luna 最小生命周期与 provider A/B**：在 enabled 的默认交互终端明确要求一 Agent Workflow，观察审批、async launch 与 `/workflows`；再用非交互模式完成相同固定结果，查看 list/detail、保存 project、跨 CLI 尝试 resume；最后 disabled 后比较命令发现与 LLM Proxy request。
2. **隔离 Web IM enabled/disabled**：重建并启动 unit worktree 的 IM/Gateway/Vite，配置 Agent 为 Luna + Low；对照 desktop/mobile 原型走 permission pending、Allow once、async launch、completed、刷新、Deny；取消 Workflow 后验证 next-turn slash picker 与 provider request。
3. **原型全状态对照**：分别打开 `prototype.html` 的 waiting/running/launched/completed/failed/stopped/Agent background completed；waiting/running/launched/completed/failed 保存 desktop/mobile reference，stopped 与 Agent background completed 只保留有效 mobile reference，再与真实产品证据逐项比较。
4. **飞书专用测试 Bot**：验证私密 env、非 default profile 与 ingress probe；从真实飞书私聊发明确 opt-in，点击通用 Allow once 卡，查看一次完成投递与 `/workflows`；取消 Workflow 后验证下一轮不产生 Workflow 调用。

完整脱敏运行摘要与 provider request locators 见 [`acceptance-evidence/runtime-evidence.md`](acceptance-evidence/runtime-evidence.md)。本轮遵守成本限制，只运行一 Agent 固定字符串的最小 Workflow，没有做规模实验。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html`：等待确认 | 待决只显示既有 PermissionCard 与 raw input；deny 不经历 running，且无 duration | `reference-permission-pending-*`；`web-workflow-permission-pending-*`；`web-workflow-denied-*` | desktop + mobile / pending + deny | **match**：pending、Allow once 与 deny 交互均符合；无专属 Workflow 审批卡 |
| `prototype.html`：工具调用中 / 后台已启动 | allow 后才出现过程；input-first/result-second；pending 无结果，launch 后追加结果 | `reference-tool-running-*`、`reference-async-launched-*`；`web-workflow-async-launched-desktop.png`、`web-workflow-denied-expanded-desktop.png` | desktop + mobile reference；desktop actual | **deviation**：阶段顺序正确，但真实展开详情只有标题，脚本与 launch result 内容不可见；actual mobile launched 未取得完整对照 |
| `prototype.html`：Workflow completed / failed / stopped | 后续普通消息正文与一条可展开后台原始返回同在，刷新后保持 | completed/failed 的 `reference-*-desktop/mobile.png`、`reference-workflow-stopped-mobile.png`；`web-workflow-completed-missing-background-return-*`、`web-workflow-completed-after-reload-missing-background-return-desktop.png` | desktop + mobile / completed；reference-only failed；mobile reference-only stopped | **deviation**：completed 的后台返回在实时、刷新与移动端均缺失；真实 failed/stopped 未完成，stopped desktop reference 也未取得，`inconclusive` |
| `prototype.html`：Agent background completed | launch message 保留 async result；后续普通回复过程内含 Agent 原始返回 | `reference-agent-background-completed-mobile.png` | mobile / reference | **inconclusive**：真实 Agent background journey与 desktop reference 均未形成可对照证据 |

证据目录：[`acceptance-evidence/`](acceptance-evidence/)。

## Issues

### 1. 默认交互 CLI 的 Workflow 审批没有出现，主路径直接失败

- **Severity:** blocking
- **Regression Relation:** direct
- **Expected:** 明确 opt-in 后，终端先展示名称、阶段、用量提醒和允许/拒绝选择；允许后返回 task/run 并后台执行。
- **Actual:** 模型发起 Workflow 后立刻显示 `blocked_by_hook=True` 与 `The user doesn't want to proceed ... can_use_tool raised`；没有任何审批选项，也没有 run/task。
- **Reproduction:** 以 Runbook 的 Luna/low 环境启动交互式 `coding_cli`，明确要求只运行一个返回固定字符串的 Agent Workflow。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接阻断 spec 的 coding CLI 默认交互主路径；round 1 不具备 revise-design 条件。

### 2. Web IM 完成消息缺少 Workflow 后台原始返回

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** 主 Agent 综合正文与同一消息“过程”内的 Workflow background-return 同时可见；展开能看原始 result、run/task、usage、duration、diagnostics、resume hint，刷新后保持。
- **Actual:** Workflow 完成并返回 `WEB_WORKFLOW_LUNA_OK`，但后续普通消息没有 background-return；实时、刷新后、desktop/mobile 均复现。
- **Evidence:** `web-workflow-completed-missing-background-return-desktop.png`、`web-workflow-completed-after-reload-missing-background-return-desktop.png`、`web-workflow-completed-missing-background-return-mobile.png`。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反本 unit 新增的核心归因展示，用户无法区分后台原始结果与主 Agent 综合结论。

### 3. Web IM 的 Workflow 工具详情只显示空标题

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** 展开工具项后脚本输入在前，async launch result 在后；用户可核对两者实际内容。
- **Actual:** 展开后只显示 `WORKFLOW INPUT` 与 `LAUNCH RESULT` 标题，脚本和结果值均不可读。
- **Evidence:** `web-workflow-async-launched-desktop.png`、`web-workflow-denied-expanded-desktop.png`。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 用户面出现了结构但没有信息，不能满足可检查脚本和 input-first/result-second 契约。

### 4. Web/飞书 Workflow child 没有继承指定的 Luna

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** Runbook 同时指定 parent 与 child 为 `codexOAuth:gpt-5.6-luna`；未在脚本指定时 child 继承当前模型与 low effort，替换时告警。
- **Actual:** parent request 是 Luna，但 Web 与飞书的 Workflow child request 都路由到 `deepseek:deepseek-v4-flash`，用户未看到模型替换告警。CLI 的 child 路由正确为 Luna。
- **Evidence:** `acceptance-evidence/runtime-evidence.md` 中 Web 与飞书 provider locators。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反模型继承场景，也使用户的成本与模型选择失真。

### 5. CLI disabled 后仍在 `/help` 发现不可用的 Workflow 入口

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** Workflow 关闭时相关命令、保存和管理入口完全消失。
- **Actual:** disabled 的 provider request 已无 Workflow tool object，但交互式 `/help` 仍列出 `/workflows`、`/config`、`/effort`；执行 `/workflows` 又返回 unknown command。Web slash picker 的 disabled 行为正确。
- **Evidence:** `acceptance-evidence/runtime-evidence.md` 的 CLI disabled 段。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 同一个用户入口向用户宣告能力存在，实际却不能执行，直接违反 complete-off 契约。

### 6. 已完成运行从另一 CLI 恢复只返回笼统失败

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** 同会话、相同脚本与参数恢复已完成运行时复用最长相同调用前缀；不同会话应明确从头启动，不能给无诊断的失败。
- **Actual:** 在另一 CLI 选择原 session 后尝试 resume，用户只得到笼统失败，没有复用结果、重新执行或可操作诊断；对 completed run 的 pause 仍显示 completed。
- **Evidence:** `acceptance-evidence/runtime-evidence.md` 的 CLI lifecycle 摘要。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 恢复是本 unit 明确要求的用户能力，当前用户无法完成也无法判断下一步。

## Acceptance Criteria Coverage

### Requirement: Workflow 在所有 Agent 产品入口可用且由工具选择完整开关 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| coding CLI 启用 Workflow | spec + CLI Runbook | 交互 CLI 明确 opt-in | runtime evidence / Issue 1 | fail | 审批未出现，run 未启动 |
| 个人助手勾选 Workflow | spec + Web/飞书 Runbook | Web 配置后在 Web 与飞书下一轮启动 | enabled screenshots + Feishu screenshot/provider locator | pass | 两入口均暴露 Workflow 并进入通用审批 |
| 个人助手取消 Workflow | spec + Runbook A/B | Web 取消后再从 Web/飞书请求 | disabled screenshot/provider locator | pass | provider Workflow=0；Web 命令消失；飞书未产生 Workflow 调用 |
| 运行中修改工具选择 | spec | 需在同一运行跨轮修改 | 未执行 | inconclusive | 成本约束只跑单 Agent 短任务，未形成运行中窗口 |

### Requirement: 默认模式只响应明确 opt-in，ultracode 模式允许 Agent 自主编排 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 人类输入使用 ultracode 关键词 | spec | enabled/disabled Web 与飞书 keyword A/B | disabled screenshots/provider locator | inconclusive | disabled 侧确认 Workflow 不触发；enabled 侧未单独完成 ultracode 运行 |
| 人类用自然语言明确要求 Workflow | spec | CLI/Web/飞书明确自然语言要求 | runtime evidence | pass | enabled 入口均尝试/发起 Workflow |
| 普通任务不自动扩张 | spec | 需 ordinary no-opt-in turn | 未执行 | inconclusive | 本轮聚焦明确 opt-in lifecycle |
| 会话开启 ultracode 模式 | spec | 需开关模式并连续多轮 | 未执行 | inconclusive | 未建立会话模式旅程 |
| 非人工来源不因关键词自动激活 | spec | 非人工 origin | N/A | not-applicable | 疑似 origin/protocol 层 Scenario，应属 design.md |

### Requirement: Agent 生成和运行可检查、可编辑、可复用的 Python 编排脚本 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 从自然语言生成 Python Workflow | spec + prototype | CLI/Web/飞书要求生成一 Agent Python Workflow | runtime evidence + pending screenshots | pass | 真实请求生成 Python；审批前显示脚本，但 Web launch detail 内容为空见 Issue 3 |
| 查看并修改生成脚本后重跑 | spec | 修改 artifact 后重跑 | 未执行 | inconclusive | 只完成保存，未编辑重跑 |
| Python 脚本使用 Workflow primitives | spec | primitive 语义 | N/A | not-applicable | 疑似编排运行时语义，应属 design.md/implementation verification |
| 脚本试图直接取得系统能力 | spec | 受限脚本拒绝 | 未执行 | inconclusive | 属用户可见错误，但本轮未跑破坏性脚本 |
| 参数化运行 | spec | 保存并按名称带结构化参数运行 | 未执行 | inconclusive | 仅验证 project save |

### Requirement: Workflow 提供与 Claude Code 一致的确定性多 Agent 编排语义 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 并行汇合 | spec | 多 Agent parallel | 未执行 | inconclusive | 用户限制只跑一 Agent，不做规模实验 |
| 按 item 流水执行 | spec | 多 item pipeline | 未执行 | inconclusive | 同上 |
| 运行时分支和循环 | spec | 动态控制流 | 未执行 | inconclusive | 同上 |
| 单个 Agent 被停止或发生不可恢复错误 | spec | 子 Agent stop/error | 未执行 | inconclusive | 未制造失败型子 Agent |
| 整个 Workflow 的终态只由顶层执行结果决定 | spec | 顶层 return/exception/stop 语义 | N/A | not-applicable | 疑似运行时判定语义，应属 design.md/implementation verification |
| 中间结果不淹没主会话 | spec | Web/飞书最小运行观察消息数 | Feishu completion screenshot + runtime evidence | pass | 一次 launch/审批与一次终态，无 child transcript 泛滥 |

### Requirement: Workflow 后台运行且各入口均可查看和控制进度 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 启动后主会话保持可用 | spec + Runbook | Web/CLI noninteractive async launch | async screenshot + runtime evidence | pass | 返回 task/run 后后台执行；交互 CLI 例外另见 Issue 1 |
| 查看运行进度 | spec | CLI/飞书 `/workflows` list/detail | runtime evidence | pass | 可见 status、Agent、usage、duration、result、artifacts |
| 暂停与继续 | spec | CLI 对 run pause/resume | runtime evidence / Issue 6 | fail | completed pause 无变化，resume 给笼统失败；未验证 active pause |
| 停止 Agent 或整个 Workflow | spec | 飞书 completed run stop + active stop | runtime evidence | inconclusive | completed stop 只回 completed detail；未取得 active stopped 用户态 |
| Workflow 完成 | spec + prototype | Web/飞书等候完成通知 | screenshots + runtime evidence | fail | 飞书一次终态通过；Web 必需后台原始返回缺失，见 Issue 2 |

### Requirement: Web IM 对后台 Workflow 和后台 Agent 显示可归因的原始返回 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Workflow 返回与主 Agent 综合回复同时可见 | spec + prototype must-match | Web completed desktop/mobile | completed missing-return screenshots | fail | 主正文可见，过程内没有后台返回 |
| 后台 Agent 返回使用同一过程项 | spec + prototype must-match | 真实 Agent background | reference-only screenshots | inconclusive | 未形成真实产品证据 |
| 原始返回与综合结论清楚分层 | spec + prototype must-match | 展开 completed 普通回复 | completed missing-return screenshots | fail | 原始层完全缺失，无法分层阅读 |
| 主 Agent 正文为空时不丢后台返回 | spec + prototype | empty-text notification | 未执行 | inconclusive | Runbook 要求，但真实旅程未形成空正文 |
| 实时、历史和重放保持同一条返回 | spec + prototype must-match | 完成后刷新并查看移动端 | realtime/reload/mobile screenshots | fail | 三种视角都缺失同一 background-return |

### Requirement: 暂停或修改后的 Workflow 按最长相同 Agent 调用前缀恢复 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 恢复未完成的运行 | spec | active pause/stop 后 resume | 未执行 | inconclusive | 最小运行过短，未形成未完成窗口 |
| 修改后续 Agent 调用再恢复 | spec | 编辑后续调用再 resume | 未执行 | inconclusive | 未执行 |
| 完全相同的脚本与参数重跑 | spec | completed run resume | runtime evidence / Issue 6 | fail | 只得到笼统失败，无复用或结果 |
| 退出会话后重新启动 | spec | 新会话运行保存的同名 Workflow | 未执行 | inconclusive | 只在另一 CLI 选择原 session 尝试 resume |

### Requirement: Workflow 可保存、发现、分发并按名称运行 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 保存为项目 Workflow | spec | CLI save project | runtime evidence | pass | 生成 `.nanocode/workflows/acceptance-minimal.py`，清理前核对存在 |
| 保存为个人 Workflow | spec | save personal + 跨项目发现 | 未执行 | inconclusive | 未写用户级持久态 |
| 同名 Workflow 的发现优先级 | spec | project/personal 同名对比 | 未执行 | inconclusive | 未执行 |
| 运行内置或插件 Workflow | spec | named/plugin entry | 未执行 | inconclusive | 未执行 |
| Workflow 工具关闭时命名入口消失 | spec | CLI/Web disabled command discovery | disabled screenshots + runtime evidence | fail | Web pass；CLI `/help` 仍列出不可执行入口，见 Issue 5 |

### Requirement: Workflow 启动与子 Agent 工具调用遵循 Claude Code 权限语义 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 默认交互权限下审批计划 | spec + prototype | CLI/Web/飞书默认交互 | pending screenshots + Feishu screenshot + Issue 1 | fail | Web/飞书通用审批通过；CLI 没有审批 UI |
| ultracode 与非交互权限模式 | spec | CLI `--text` 非交互最小运行 | runtime evidence | pass | 非交互直接 async launch，无不可响应审批；ultracode 侧未单独确认 |
| 子 Agent 继承工具范围 | spec | provider child tool list观察 | runtime evidence | inconclusive | child 未使用工具；只能确认 Workflow tool 未向 child 递归暴露 |
| 子 Agent 使用未预先允许的能力 | spec | child 请求需审批能力 | 未执行 | inconclusive | 成本约束要求 child 不调用工具 |
| 运行中不接受普通阶段签字 | spec | 运行期间发送普通消息 | 未执行 | inconclusive | 最小运行窗口太短 |

### Requirement: Workflow 对规模、成本和模型路由提供与 Claude Code 一致的反馈与限制 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 查看实时成本 | spec | CLI/飞书运行详情 | runtime evidence | pass | 可见 Agent usage 与 duration；短运行未证明长任务实时刷新 |
| 大型 Workflow 警告 | spec | 大型运行 | 未执行 | inconclusive | 用户明确要求不做规模实验 |
| 调整规模 guideline | spec | UI/命令选择各 guideline | 未执行 | inconclusive | 本轮只确认 Agent 设置无额外 Workflow 配置；未走 `/config` |
| 达到运行时上限 | spec | 并发/总数硬上限 | N/A | not-applicable | 疑似运行时限制语义，应属 design.md/implementation verification；且用户禁止规模实验 |
| 模型与 effort 路由 | spec + Runbook | 固定 parent/child Luna + low，查 provider request | runtime evidence / Issue 4 | fail | Web/飞书 child 被替换为 DeepSeek 且无告警 |

### Requirement: Workflow 错误可定位且不破坏主会话 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Python 脚本不合法 | spec | invalid Python/metadata | 未执行 | inconclusive | 未制造 invalid artifact |
| 后台运行失败 | spec + prototype must-match | failed Workflow + 主会话继续 | reference-only failed screenshots | inconclusive | 真实 failed 用户态未形成 |
| 用户查看历史运行诊断 | spec | CLI/飞书 completed detail | runtime evidence | pass | 可定位持久化 script、run、Agent result、usage 与 diagnostics |

## Side Findings

- Feishu 取消 Workflow 后，明确要求 Workflow 的消息没有触发 Workflow，但模型改为申请 Bash 权限；用户期望的“不可用”说明没有出现。Workflow capability A/B 本身正确，作为相邻模型行为记录，不另立 issue。
- CLI `/effort low` 命令只接受 `ultracode|high`；本轮通过 Runbook 环境变量使用 low。是否应对用户暴露 low 不是本 unit 的明确验收项。
- Web 的 Workflow 工具行耗时包含等待人工审批的时间（本次约 36.1s），因此不等同于实际后台执行耗时；本轮只记录，不作为独立 issue。

## Upper-level Documentation Sync

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**；本 unit 没有改变既有跨包依赖方向或部署拓扑。
- [x] `docs/specs/<包>/`（长青行为契约层）：**需要更新**；最终实现稳定后，由 orchestrator 将本 unit 的 kernel/CLI/Gateway/IM 行为增量从 delta spec 归并到 canonical specs。当前 canonical 只描述既有 background task，尚未完整描述 Dynamic Workflows 与 background-return sidecar。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**；开发/运行约定未改变。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**；文档体系未改变。

## Recommended Next Step

`fix-implementation`。优先恢复 CLI 默认交互审批与 Web 后台原始返回，再修正 Workflow detail 内容、child Luna/effort 路由和 disabled CLI command discovery；下一轮应按上一轮所有 `fail` / `inconclusive` 继续复验，并补齐真实 failed/stopped、Agent background、empty-text 与 active pause/resume 状态。
