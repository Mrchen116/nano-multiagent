# Design Review: feat-540

## Round 1

### Metadata

- reviewer: `feat-540-design-reviewer`
- review_mode: `full`
- mode_reason: R1 首次完整审查，按 skill 要求覆盖全部承重原子与四角度架构进攻
- started_at: `2026-08-17T23:25:00+08:00`
- completed_at: `2026-08-17T23:58:00+08:00`
- duration: `33 min`

### Verdict

Issues Found — 1 CRITICAL / 1 WARNING / 0 INFO

### Coverage

本轮通读并核对以下文档与代码：

- `docs/changes/feat-540-agent-list-node-label/spec.md`
- `docs/changes/feat-540-agent-list-node-label/design.md`
- `docs/changes/feat-540-agent-list-node-label/prototype.html`
- `docs/changes/feat-540-agent-list-node-label/specs/im/agents-nodes.md`
- `docs/specs/im/agents-nodes.md`
- `docs/specs/CONTRIBUTING.md`
- `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
- `src/IM/frontend/src/features/settings/agents/agents-list-page.test.tsx`
- `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.tsx`
- `src/IM/frontend/src/features/settings/agents/agents-rail-desktop.test.tsx`
- `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
- `src/IM/frontend/src/features/settings/account/account-page.tsx`
- `src/IM/frontend/src/features/chat/components/avatar.tsx`
- `src/IM/frontend/src/features/chat/components/node-chip.tsx`
- `src/IM/api/routes/agents.py`
- `src/IM/api/routes/nodes.py`

### Ledger

#### 1. 现状断言

| # | 断言 | 结论 | 证据 |
|---|---|---|---|
| 1.1 | 首页侧栏 `AgentRow` 已使用共享 `Avatar`（含状态角标），右缘另有独立状态圆点；桌面非选中文字为深底深字 `oklch(0.18)` / `oklch(0.50)` | 成立 | `agents-list-page.tsx:63-100`, `:71-84` |
| 1.2 | rail 使用裸 `<span>` 头像（无状态角标），右缘独立状态圆点；文字色正确 `oklch(0.86)` / `oklch(0.64)` | 成立 | `agents-rail-desktop.tsx:81-100`, `:89-93` |
| 1.3 | `/im/v1/agents` 返回的 `AgentSummaryResponse` 不含 `node_name`，但含 `node_id` 与 `node_status` | 成立 | `agents.py:117-135`, `:396-406` |
| 1.4 | `/im/v1/nodes` 返回 `NodeSummary.node_name`；前端已有 `listNodes()` | 成立 | `nodes.py:71-84`, `im-agent-config-api.ts:125-137`, `:596-598` |
| 1.5 | 首页侧栏已查询 `listNodes`，rail 未查询 | 成立 | `agents-list-page.tsx:110`, `agents-rail-desktop.tsx:24` |
| 1.6 | Account 页对设备的展示文字使用 `node.alias || node.node_name` | 成立 | `account-page.tsx:215`, `:250` |
| 1.7 | `NodeSummary` 接口包含 `alias` | 成立 | `im-agent-config-api.ts:125-137` |

#### 2. 决策

| # | 决策 | 拍死 | 无歧义 | 自洽 | spec 驱动 | 备注 |
|---|---|---|---|---|---|---|
| 2.1 | 抽出共享 `agent-row.tsx`，合并首页侧栏与 rail 的行实现 | 是 | 是 | 是 | 是 | 根因（两份实现漂移）与 Q7 颜色修复需求共同驱动 |
| 2.2 | 设备名由前端按 `node_id` join `/im/v1/nodes` 取 `node_name` | 是 | 否 | 否 | 部分 | 与 spec「与 Account 页显示的设备名一致」冲突：Account 页优先 `alias`，design 漏 `alias` |
| 2.3 | 三者视觉规范（字号/字色/右对齐/截断规则） | 是 | 是 | 是 | 是 | 与 Q2/Q4/Q5 澄清记录一致；prototype 已覆盖 |
| 2.4 | 颜色修复 = 首页侧栏统一到 rail 的浅色值 | 是 | 是 | 是 | 是 | 与 Q7 用户指令一致 |

#### 3. spec 约束

- 多设备下逐条标注：design 决策 1/2/3 + prototype 对齐表覆盖。
- 设备离线仍显示归属：决策 2 回退规则 + 决策 3「离线不变灰」覆盖。
- 无归属信息的条目右缘留空：决策 2 `nodeLabelOf` 回退到 `null` 覆盖。
- 移动端同样标注：决策 3 移动端排布 + prototype 覆盖。
- 名字两行与行高不被挤压：决策 3「截断只截自己」覆盖。
- 在线状态由头像角标表达：决策 1「rail 换 Avatar + 删除右缘圆点」覆盖。
- 深色侧栏文字可读：决策 4 覆盖。
- 非目标：未做筛选/分组/搜索、未改 chat/Account/Nodes、未改后端——均守住。
- **冲突点**：spec「与 Account 页显示的设备名一致」要求与 Account 页展示一致，但 Account 页展示为 `alias || node_name`，design 仅取 `node_name`。

#### 4. delta-spec 条目

- `docs/changes/feat-540-agent-list-node-label/specs/im/agents-nodes.md` 存在，路径正确对应 `docs/specs/im/agents-nodes.md`。
- 使用 `ADDED Requirements`，未误用 `MODIFIED`/`REMOVED`（本次未修改既有 requirement）。
- Scenario 的 `THEN` 均从用户/浏览器可观察角度书写，无内部函数名、类名或日志串断言。
- **问题**：颜色可读性被包在标题为「Agents 列表条目右缘标注归属设备，状态由头像角标表达」的 requirement 内，未单独成条；标题未反映「深色侧栏文字可读」这一新增契约。

#### 5. milestone

- 仅 `feat-540-M1`，垂直切片（前端展示 + 测试 + 截图验收），非横切（不是 M1=数据/M2=UI/M3=测试式拆分）。
- 范围明确：`src/IM/frontend/src/features/settings/agents/` 内新增 `agent-row.tsx` + 改两个入口 + 测试 + 截图。
- 退出标准两轨齐备：`[reviewer]` 引 spec Scenario / prototype，`[worker]` 引 `npm test` 与截图。

### 架构进攻

#### 角度一 · 归属

- 新增共享行组件落在 `features/settings/agents/`，与既有两份行实现同域，自然。
- 共享组件引用 `features/chat/components/avatar.tsx` 的 `Avatar` 与 `colorForAgent`，方向为上层 settings 依赖 chat 的共享展示组件，无反向依赖，不违反 AGENTS.md 的跨产品边界。
- 纯前端展示层变更，未触碰 `agent.sdk` / `agent.core` / `agent.platform`。

#### 角度二 · 该不该存在

- 共享 `AgentRow` 不是“为将来多态预造抽象”：当前已有两处实现漂移的实例，合并直接消除重复并防止下次改动再双写。
- `nodeLabelOf` / `statusOf` 这类纯函数把 join/回退语义集中一处，避免两份组件分别实现，合理。
- 未引入额外间接层（如工厂、策略、Protocol）。

#### 角度三 · 深还是浅

- `AgentRow` 接口简单：`agent`、`nodes`、`isActive`、`isMobile`、`onSelect`，与其内部“头像 + 两行文本 + 设备名”的渲染责任对等，没有暴露与实现同复杂度的 props。
- 设备名展示未复用 `NodeChip` 是正确的：`NodeChip` 含圆点，与“状态由头像角标表达”冲突，且形态为 chip 而非右缘文字。

#### 角度四 · 治本还是补丁

- 颜色修复从“改两份实现”变为“合并后只改一处共享组件”，治本而非补丁。
- 设备名在前端 join `/im/v1/nodes` 是 spec 明确非目标（不改后端）下的合理折中；若去掉该非目标，后端直接返回 `node_name`（甚至 `alias`）会更优，但 design 只能在该约束内工作，不算补丁冒充长远方案。

### Issues

- [R1-C1][CRITICAL] [决策 2 / 接口与数据流 / spec 约束]: 设备名取值只写 `node_name`，未处理 `alias`，与 Account 页 `node.alias || node.node_name` 的展示不一致，违反 spec「与 Account 页显示的设备名一致」。若按此实现，用户在设置了 alias 的多设备账号上会看到 Agents 列表设备名与 Account 页不同，验收标准中的「多设备下逐条标注」Scenario 在 alias 场景下失败。
- [R1-W1][WARNING] [delta-spec / design.md §契约层增量]: 颜色修复这一新增用户可观察契约被包在「Agents 列表条目右缘标注归属设备，状态由头像角标表达」的 requirement 中，未单独成条，标题也未体现「深色侧栏文字可读」。长期维护者按标题检索时容易遗漏该契约，回归时可能只验设备名而漏掉颜色可读性。

### Recommendations

- [R1-R1] 将决策 2 的设备名 join 改为 `node.alias || node.node_name ?? agent.node_id ?? null`，并在 prototype、M1 退出标准与单测 fixture 中显式覆盖「节点设置了 alias」的场景；保持后端零改动。
- [R1-R2] 在 delta-spec 中把「深色侧栏文字可读」拆为独立的 ADDED Requirement（或至少将现有 requirement 标题扩展为同时覆盖设备标注与文字可读），使标题与契约内容一致。

### Author Resolutions

- **R1-C1: accepted**。亲自核实 `account-page.tsx:215` 与 `:250`,Account 页设备名确为 `node.alias || node.node_name`,design 漏 alias 属真。修复:决策 2 与「接口与数据流」的 `nodeLabelOf` 改为与 Account 页同优先级(`alias || node_name`,节点表缺失回退 `node_id`,无归属不渲染);现状分析补 alias 事实;prototype.html 桌面面板新增别名设备行(「工作室」)+ 取值说明;原型对齐契约必验状态加「别名设备」;M1 退出标准 1/6 显式覆盖别名场景;delta-spec 新增 Scenario「设备设置别名时显示别名」。顺带记录:chat 头部 `NodeChip` 现状取 `node_name`(`chat-workspace-page.tsx:509`),与 Account 页不一致,属本 unit 范围外,不处理。
- **R1-W1: accepted**。delta-spec 拆为两条独立 ADDED Requirement(「Agents 列表条目右缘标注归属设备,状态由头像角标表达」与「三处列表条目文字在深色侧栏上清晰可读」),与 unit spec 验收标准的 Requirement 结构一一对应。
- **R1-R1: 采纳**,已含于 R1-C1 修复(单测 fixture 覆盖别名场景属 worker 实施细节,由退出标准 8 兜底)。
- **R1-R2: 采纳**,按拆分方案执行(见 R1-W1)。

## Round 2

### Metadata

- reviewer: `feat-540-design-reviewer`
- review_mode: `delta`
- mode_reason: 本轮仅修订 R1 issue 涉及的决策 2、delta-spec、prototype 与 milestone 退出标准；范围有界，未改需求范围、核心架构边界或共享契约
- started_at: `2026-08-18T00:10:00+08:00`
- completed_at: `2026-08-18T00:25:00+08:00`
- duration: `15 min`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 设备名 join 改为 `alias \|\| node_name`，补 alias 现状，prototype 与退出标准覆盖别名场景 | `design.md:15` 已补 Account 页 `alias \|\| node_name` 事实；`design.md:70-78` 决策 2 明确同优先级；`design.md:111-114` 数据流 `nodeLabelOf` 已改为 `(n.alias \|\| n.node_name)`；`prototype.html:150-155` 新增别名设备行「工作室」；`design.md:149` 原型对齐表必验状态含「别名设备」；`design.md:189` M1 退出标准 1/6 显式覆盖别名 | closed |
| R1-W1 | delta-spec 拆为两条独立 ADDED Requirement | `specs/im/agents-nodes.md:8-46` 为设备标注+状态表达 requirement，含独立 Scenario「设备设置别名时显示别名」；`:47-54` 为深色侧栏文字可读 requirement；标题与 unit spec 的 Requirement 结构一一对应 | closed |

### 本轮变更原子核查

| 原子 | 变更位置 | 结论 | 证据 |
|---|---|---|---|
| 决策 2 | `design.md:70-78` | 已拍死 `alias \|\| node_name`，拒绝纯 `node_id` / 裸 `node_name` | 与 Account 页 `account-page.tsx:215,250` 一致 |
| 接口与数据流 `nodeLabelOf` | `design.md:111-114` | 优先级与 Account 页一致，回退路径清晰 | `n.alias \|\| n.node_name` → `agent.node_id \|\| null` |
| 现状分析 | `design.md:15` | 已补 alias 事实，并引用 Account 页行号 | `NodeSummary` 含 `alias`（`im-agent-config-api.ts:135`） |
| 原型 | `prototype.html:150-155`, `:119`, `:268` | 新增别名设备行「工作室」，并注明取值优先级 | 覆盖状态列表已更新为含「别名设备」 |
| 原型对齐契约 | `design.md:149` | 必验状态增加「别名设备」 | 对应 M1 退出标准 1/6 |
| Milestone 退出标准 | `design.md:189` | 标准 1 与 6 均显式提及别名场景 | reviewer / worker 双轨保留 |
| delta-spec | `specs/im/agents-nodes.md:8-54` | 拆为两条 ADDED Requirement；Scenario THEN 均为用户可观察结果 | 新增「设备设置别名时显示别名」Scenario |

### 受影响架构进攻角度

- **角度一 · 归属**：`nodeLabelOf` 仍放在前端展示层，依赖 `/im/v1/nodes` 的 `alias`/`node_name`，未引入新的跨层依赖。
- **角度四 · 治本还是补丁**：使用 `alias \|\| node_name` 与 Account 页一致，消除了 R1 中“补丁式只取 node_name”的不一致；仍是在 spec 非目标（不改后端）约束内的合理前端实现。

其余原子与架构角度自 Round 1 以来未发生变化，结论继承自 Round 1。

### Issues

无。

### Recommendations

无。
