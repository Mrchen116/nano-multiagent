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

---

# Round 2 — 2026-08-10

> Targeted Fast-lane re-review

> Validation snapshot: `517b3bd585fb06fd5b319b12cdc69f77f8578dac → ce4f2aab1bc12df76c4aa5e4d18ad981cddc5e9d`

## Verdict

**fail**

**Highest Required Action：`fix-implementation`**

Round 1 的 CLI 默认审批、Web background return、Workflow detail、disabled CLI discovery 已关闭；PA child model 也已改为 Luna。但同 session 在进程重启后仍无法 resume，且 PA child request 没有继承 low effort，第二次 Workflow 的 terminal continuation 又回落到 DeepSeek。其余未列入本次 targeted 范围的 Round 1 `fail` / `inconclusive` 继续继承，因此本 unit 仍不能判 pass。

## Targeted User Journeys Exercised

1. **CLI default approval + disabled discovery + restart resume**：Luna/low、单无工具 Agent；真实 TTY Allow once、completed、退出后 `--resume`、TTY control、显式 resume、跨 session resume；disabled `/help` 与 `/workflows` 对照。
2. **隔离 Web realtime/reload/mobile**：独立 IM/Gateway/Vite + Playwright Chromium；Workflow permission、launch detail、completed background return、展开 raw result、reload、390×844 mobile。
3. **PA child routing + child tool smoke**：同一 Luna/Low profile 下，再运行一个只调用一次安全 Bash 的单 child Workflow；对照 child/continuation provider requests，并观察用户入口是否卡死。

真实 Chrome 与真实飞书均未打开、未控制、未发送任何消息。完整 locator 与脱敏输出见 [`acceptance-evidence/round2-runtime-evidence.md`](acceptance-evidence/round2-runtime-evidence.md)。

## Reference Artifacts Re-reviewed

| Reference contract | Actual Round 2 evidence | Viewport / state | Conclusion |
|---|---|---|---|
| Workflow input-first / result-second | `round2-web-workflow-completed-expanded-desktop.png` | desktop / async launched | **match**：完整 inline Python 在前，`async_launched`、run/task 与 artifact locator 在后 |
| Workflow completed background return | `round2-web-background-return-details-desktop.png` | desktop / realtime completed | **match**：正文与独立 background-return process item 同时存在；展开含 raw result、identity、usage、duration、diagnostics、resume hint |
| history / replay / mobile same return | `round2-web-background-return-after-reload-desktop.png`、`round2-web-background-return-after-reload-mobile.png` | desktop + 390×844 / reload | **match**：同 task/run、同 raw result、同 usage/artifacts，未重复 |

## Round 1 Issue Re-validation

| Round 1 issue | Round 2 result | Evidence | Status |
|---|---|---|---|
| 1. CLI 默认交互审批不出现 | 真实 TTY 显示完整 Workflow permission request；Allow once 后 completed 1/1 | round2 runtime evidence / CLI | **closed** |
| 2. Web 完成消息缺少后台原始返回 | realtime、reload、desktop/mobile 均显示同一 background return | Round 2 background-return screenshots | **closed** |
| 3. Workflow detail 只有空标题 | input、script、launch result、run/task 与 artifact locator 均可读 | `round2-web-workflow-completed-expanded-desktop.png` | **closed** |
| 4. PA child 未继承 Luna/effort | child model 已是 Luna；但 child provider request 没有 low effort，第二次 terminal continuation 回落 DeepSeek | round2 runtime evidence / provider locator | **still failing** |
| 5. CLI disabled `/help` 仍列 Workflow | disabled `/help` 不再列 `/workflows`；直接输入时一致返回 unknown command | round2 runtime evidence / CLI | **closed** |
| 6. restart resume 只有笼统失败 | `--resume` 后可见 persisted run，但 TTY control 报 unknown run；显式 resume 仍只有 input-layer 通用失败 | round2 runtime evidence / CLI | **still failing** |

## Issues

### R2-1. PA child effort 未继承，terminal continuation 仍可切换模型

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** Agent profile 为 Luna + Low，未在脚本覆盖时 child 与消费终态通知的 parent continuation 都使用相同 resolved model/effort；发生替换要向用户告警。
- **Actual:** child model 已修为 Luna，但 child request 没有 `output_config.effort=low`；第二次完成通知的综合回复由 `deepseek:deepseek-v4-flash` 生成，界面没有模型替换告警。
- **Reproduction:** Web Agent 选 Workflow、Luna、Low，连续运行两个单 child Workflow；第二个 child 只执行一次安全 Bash；查同一 LLM Proxy session locator。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 仍直接违反“模型与 effort 路由”，且模型/成本选择对用户不可信；只经过一轮修复，未满足 revise-design 三道闸。

### R2-2. 进程重启后同 session 的 persisted Workflow 无法控制或 resume

- **Severity:** major
- **Regression Relation:** direct
- **Expected:** `--resume <same-session>` 后可以按 runId 恢复同 session 的 Workflow；若用户在不同 session resume，应得到明确的 session-scope 诊断。
- **Actual:** 同 session `/workflows` 能看到 completed run，但 TTY `p` 报 `unknown Workflow run`；显式 resume 在同 session 与新 session 都只给 `failed to run /workflows`，没有 session-scope 或恢复诊断。
- **Reproduction:** 完成 `wf_7f53bce070f65bb3`，退出 CLI，重新执行 `--resume sess_5e77831ef574f1fb`，再用 TTY `p` 与显式 resume；随后新 session 对同 runId resume。
- **Recommended Action:** fix-implementation
- **Action Rationale:** 直接违反 resume/restart 用户场景；历史展示与控制能力相互矛盾。

## Targeted Acceptance Criteria Coverage

未列出的 Round 1 `fail` / `inconclusive` 行按 Fast-lane 规则原样继承。

| Scenario | Round 2 evidence | Result | Note |
|---|---|---|---|
| coding CLI 启用 Workflow | TTY approval → Allow once → running/completed | pass | Round 1 blocking closed |
| Workflow 返回与主 Agent 综合回复同时可见 | realtime completed screenshots | pass | 正文与 background-return 同时可见 |
| 原始返回与综合结论清楚分层 | expanded background-return detail | pass | raw result 与正文分层 |
| 主 Agent 正文为空时不丢后台返回 | 第一条 terminal message 一度先出现 process-only，随后正文补齐 | pass | background return 从未因正文时序丢失 |
| 实时、历史和重放保持同一条返回 | reload desktop/mobile | pass | 同 task/run，内容一致且不重复 |
| 从自然语言生成 Python Workflow | launch detail 可读完整 Python | pass | Round 1 备注中的空 detail 已关闭 |
| Workflow 工具关闭时命名入口消失 | disabled `/help` + direct command | pass | 发现与执行一致 |
| 默认交互权限下审批计划 | CLI + Web 均有通用 Workflow approval | pass | Allow once 可完成 |
| 子 Agent 使用未预先允许的能力 | one-child Bash smoke | inconclusive | 安全 `printf` 被当前权限策略自动处理，未形成独立 child permission card；但入口未卡死 |
| 模型与 effort 路由 | PA config + provider requests | fail | child model=Luna；child effort missing；一次 terminal continuation=DeepSeek |
| 完全相同的脚本与参数重跑 | restart same-session resume | fail | persisted run 可见但 unknown to control path |
| 退出会话后重新启动 | new session 对旧 run resume | fail | 只给通用 input-layer 错误，没有明确 session-scope 诊断 |

## Side Findings

- Tagged child permission 的“单 stdin owner”在产品层只完成 smoke：CLI/Web 的 one-child Bash 都没有卡死并得到预期结果；当前安全命令被权限策略自动处理，无法证明多个 tagged permission 的精确交互归属。该项保留 `inconclusive`，不另立新 issue。
- 本轮首次启动隔离 Web 服务时，后台进程随启动 shell 退出导致一次 Vite proxy `ECONNREFUSED`；改为保持隔离服务前台 owner 后真实旅程正常。此为验收 harness 启动方式，不计入产品 issue。

## Upper-level Documentation Sync

- [x] `SPEC.md`：**无需更新**，继承 Round 1 结论。
- [x] `docs/specs/<包>/`：**需要更新**，但应等最终实现稳定后由 orchestrator 归并 delta spec。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

## Recommended Next Step

继续 `fix-implementation`：修复 PA child effort 与 terminal continuation model routing；让重启后的同 session run 进入可控制/resume 的 runtime，跨 session 返回明确诊断。修复后可对 R2-1/R2-2 做 targeted Round 3，但 Round 1 其余 inherited `inconclusive` 仍需在最终 pass 前逐项关闭。

---

# Round 3 — 2026-08-10

> Targeted Fast-lane closure

> Validated at: `6d34578c3e69ebb1323af1f3575a51e8afce9041`

## Verdict

**pass**

**Highest Required Action：`pass`**

R2-1 与 R2-2 均已在真实入口关闭：PA 连续两个 one-child Workflow 的 parent、child 与两次 terminal continuation 全部为 Luna + low，没有 DeepSeek；coding CLI 重启同一 session 后能发现 persisted run，显式 resume 创建新 run 并 2ms 完成全量 cached replay，跨 session 返回精确 scope 诊断。Round 2 已关闭项未观察到失效。

本 verdict 采用 caller 明确指定的成本受限验收口径：Luna、low、单 Agent，不执行多 Agent、并发、pipeline 或规模阈值实验。该限制内仍适用且成本可控的后台 Agent must-match 旅程已补验通过；其余规模/复杂控制流场景不被冒充为真实产品 pass 证据，作为本轮不适用的高成本验证面交由既有 verifier 覆盖。

## Targeted User Journeys Exercised

1. **CLI restart + replay + scope diagnosis**：一 Agent minimal Workflow completed；退出进程；`--resume` 同 session；TTY persisted list/control；显式 completed resume；检查 cache replay；新 session 对原 run resume。
2. **PA 连续两个 one-child Workflow**：同一 Web conversation、同一 Workflow-enabled Luna/Low profile，连续两次审批并完成固定结果；对照两条 child request 与两次 terminal continuation 的 provider request。
3. **后台 Agent must-match 补验**：同一隔离 Web conversation 启动 `Agent(run_in_background=true)` 单 child；检查 launch 行、后续 background return、展开原始结果与 reload persistence。

真实 Chrome 与真实飞书均未打开、未控制、未发送消息。完整 locator 和脱敏结果见 [`acceptance-evidence/round3-runtime-evidence.md`](acceptance-evidence/round3-runtime-evidence.md)。

## R2 Issue Closure

| Round 2 issue | Round 3 result | Evidence | Status |
|---|---|---|---|
| R2-1. PA child effort 未继承，terminal continuation 可切换模型 | 两个连续 one-child Workflow 的 8 个相关 requests 全部 Luna + low；两个 child request 均无 Workflow tool；无 DeepSeek | Round 3 runtime evidence / PA locator | **closed** |
| R2-2. restart 后 persisted Workflow 无法控制/resume | same-session restart 后 list 可见；显式 resume 创建新 run，2ms replay 同一结果且无新 child request；cross-session 返回精确诊断 | Round 3 runtime evidence / CLI | **closed** |

## Reference Artifact Closure

| Reference contract | Actual Round 3 evidence | Viewport / state | Conclusion |
|---|---|---|---|
| `prototype.html`：Agent background completed | `round3-web-agent-background-completed.png` | desktop / completed + expanded | **match**：launch input/result 保留；后续普通回复正文与一条可展开 Agent 原始返回同在，展开含 identity/status/result/usage/duration/artifact |
| history / replay 保持同一 Agent return | reload 后真实 browser snapshot | desktop / reload | **match**：同一 task/agent return 附着在原回复且不重复 |

Round 2 已完成的 Workflow desktop/mobile must-match evidence 继续有效；本次 fix 只针对 routing 与 restart control，没有观察到这些状态失效。

## Final Acceptance Coverage Adjudication

| Coverage group | Round 3 adjudication | Result |
|---|---|---|
| CLI enabled/approval/progress、Web enabled/disabled、Workflow detail、Workflow background return、命令发现 | Round 1/2 真实证据继续有效；Round 3 targeted journeys 未观察到回归 | pass |
| 模型与 effort 路由 | 连续两个 PA one-child Workflow 的 parent/child/terminal requests 均 Luna + low | pass |
| 完全相同脚本与参数重跑 | same-session completed run 新建 resumed run；child `replayed=true`，2ms、无新增 child provider request | pass |
| 退出会话后重新启动 | same-session restart 后可以 replay；不同 parent session 明确拒绝跨 session cache 复用 | pass |
| 后台 Agent 返回使用同一过程项 | 单后台 Agent 真实完成、展开原始返回、reload 不重复 | pass |
| tagged child permission 单 stdin owner | Round 2 单 child 安全 Bash smoke 无卡死；当前策略自动处理安全命令，未形成多个交互 permission request | not-applicable |
| parallel/pipeline/分支循环、active pause/stop、large warning/hard caps | 用户明确禁止多 Agent与规模实验；短 single-Agent lifecycle 也不制造稳定 active control window | not-applicable |
| personal/plugin workflow、同名优先级、复杂脚本编辑/参数化/非法脚本 | 不属于 R2-1/R2-2 closure，且需要额外持久态或额外运行；不以本轮 targeted 证据宣称通过 | not-applicable |
| ultracode standing mode 与 ordinary no-opt-in | 不属于本轮修复面；Round 1 的 explicit opt-in 与 disabled A/B 继续有效，本轮不追加模型调用 | not-applicable |

这里的 `not-applicable` 表示 caller 明确排除在本轮成本受限的真实产品实验之外，不表示这些实现契约不存在；它们不覆盖成 `pass`，也不要求通过继续消耗 LLM 来换取本 unit 的交付结论。

## Issues

本轮没有 blocking / major / minor in-unit issue。

## Side Findings

- persisted completed run 的 TTY `p` 不再报 unknown run，但保持 terminal 详情；真正的 completed rerun 通过显式 `/workflows <run-id> resume` 完成。该路径有精确结果与诊断，不影响 R2-2 closure。
- 后台 Agent 补充旅程的 direct Agent child request 是 Luna，但没有显式 effort 字段；它不属于 R2-1 的 Workflow child 路由断言，因此只记录，不作为本 unit issue。

## Upper-level Documentation Sync

- [x] `SPEC.md`：**无需更新**，继承 Round 1/2 结论。
- [x] `docs/specs/<包>/`：**需要更新**，由 orchestrator 按最终实现归并 delta spec。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

## Recommended Next Step

`pass`。可以进入 unit 收尾、canonical spec 归并与 PR/CI；无需再做 LLM 规模验收。

---

# Round 4 — 2026-08-10

> Targeted real multi-Agent semantic follow-up

> Validated at: `ce95a7f23d85ae0c67882aa789622ee69dc9cf17`

## Verdict

**pass**

**Highest Required Action：`pass`**

Round 3 因成本口径没有真实运行 `parallel` / `pipeline`，本轮补齐两条最小真实 coding CLI + LLM Proxy 旅程。两个 Workflow 都只派发恰好两次 child `agent()`，全部实际 parent、child 与 terminal continuation request 都使用 `codexOAuth:gpt-5.6-luna`；没有打开 Chrome、没有触碰飞书或发送外部消息。

本轮证明了此前缺失的两个用户价值：`parallel` 的两个真实 LLM child 确实同时在途，且完成顺序反转时 join 仍保持声明位置；`pipeline` 的第二阶段真实 LLM request 确实收到第一阶段的原始返回、原 item 与 index，最终结果由这些值派生。

## Targeted User Journeys Exercised

### 1. 两 Agent `parallel` 并发与位置保持

- 产品入口：隔离 workspace 下的真实 `coding_cli`；session `sess_4cfbe076412c9477`；Workflow `wf_4c7922f1ca2d44ba`。
- 脚本只含两个 parallel thunk：位置 0 要求返回 `R4_PARALLEL_LEFT`，位置 1 要求返回 `R4_PARALLEL_RIGHT`。
- LLM Proxy locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_18-22-56_489_sess_4cfbe076412c9477/`。
- 左 child request 区间：`18:23:04.197 → 18:23:16.918`；右 child request 区间：`18:23:04.266 → 18:23:13.840`。两者相隔 69ms 启动，并有约 9.574s 同时在途；右 child 先完成，左 child 后完成。
- 真实 `/workflows wf_4c7922f1ca2d44ba` 输出显示 `Agent: 2/2 completed`，最终结果仍为 `['R4_PARALLEL_LEFT', 'R4_PARALLEL_RIGHT']`；Workflow 12.914s，child usage 合计 5,388 tokens。

### 2. 单 item、两阶段 `pipeline` 传值

- 产品入口：隔离 workspace 下的真实交互式 `coding_cli`；session `sess_72ae6ebff3bb5ac2`；Workflow `wf_133ee6e415085a20`。
- stage 1 的唯一 child 返回 `R4_STAGE1_PAYLOAD`。stage 2 必须使用 `(previous, original, index)` 生成自己的 prompt。
- LLM Proxy locator：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_18-25-57_845_sess_72ae6ebff3bb5ac2/`。
- stage-1 child request：`18:27:22.095 → 18:27:29.051`；stage-2 child request 于 `18:27:29.122` 才启动，符合逐阶段依赖。
- stage-2 的真实 provider request 包含：`Stage one value is <R4_STAGE1_PAYLOAD>; original item is <R4_ORIGINAL>; index is <0>`。它返回 `R4_PIPELINE_FINAL[stage1=R4_STAGE1_PAYLOAD;original=R4_ORIGINAL;index=0]`。
- 真实 `/workflows wf_133ee6e415085a20` 输出与随后 background wake 均显示最终数组 `['R4_PIPELINE_FINAL[stage1=R4_STAGE1_PAYLOAD;original=R4_ORIGINAL;index=0]']`；Workflow 13.568s，child usage 合计 5,456 tokens。

## Targeted Acceptance Criteria Coverage

| Scenario | Round 4 evidence | Result | Note |
|---|---|---|---|
| 并行汇合 | 两个 child provider request 的在途区间重叠；完成顺序为位置 1 → 位置 0；最终 join 为位置 0 → 位置 1 | pass | 真实 Luna child，不是 fake runner 或集成 stub |
| 按 item 流水执行 | stage 2 在 stage 1 完成后启动；其 provider prompt 含 stage-1 原值、original 与 index；终态由这些值派生 | pass | 单 item、两阶段的最低成本真实语义证明 |

Round 3 其他 coverage 与 issue closure 继续有效；本轮没有把分支循环、规模阈值或大批量 item 冒充为已做真实 LLM 实验。

## Issues

本轮没有 blocking / major / minor in-unit issue。

## Side Findings

- 两个 CLI session 都设置了 `NANO_MULTIAGENT_REASONING_EFFORT=low`，但实际 Anthropic request 没有显式 `output_config.effort`；因此本报告只声称并逐 request 证明了 Luna-only，不声称 wire-level explicit low。该现象不改变本轮 parallel/pipeline 语义结论。

## Upper-level Documentation Sync

- [x] `SPEC.md`：**无需更新**，本轮仅补验既有契约。
- [x] `docs/specs/<包>/`：**无需追加更新**，canonical Workflow 契约已经在 Round 3 后归并。
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**。
- [x] `docs/specs/CONTRIBUTING.md`：**无需更新**。

## Recommended Next Step

`pass`。真实 LLM 的 `parallel` 并发汇合与 `pipeline` 阶段传值验收缺口已关闭；无需追加高成本规模实验。
