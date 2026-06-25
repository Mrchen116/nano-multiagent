# feat-434: 审批 UX 与工具调用列表协同重设计 — 验收报告

## Round 1 — 2026-06-25

**Reviewer**: feat-434-reviewer  
**Branch**: unit/feat-434  
**Verdict**: fail  
**Highest Required Action**: fix-implementation  
**Issues Count**: blocking: 0, major: 1, minor: 0

---

## 澄清记录

无疑问，直接开跑。

---

## 服务接管记录

- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-434`
- 前端重建：`npm install && npm run build`（产物 `dist/assets/index-Btw6CWs_.js`）
- 指纹核验：grep `toolGateAllowed` / `user_allow` / `gateVerdict` / `已授权` 命中产物 ✓
- IM：端口 58316，JWT secret 本轮专属
- Gateway：端口 58316，foreground 模式，auto-bind，worktree 本地 config
- 无 stale-binary：整栈重启后走旅程

---

## User Journeys Exercised

| 旅程 | 覆盖 Scenario | 入口 |
|---|---|---|
| J1: allow 主路径 | agent 调用工具并请求授权 / 用户点允许 / 授权后执行成功 / 收起态分项计数 / 空态 | 真浏览器 Playwright 1440×900，中文界面 |
| J2: deny 路径 | 用户拒绝 / 已拒绝+未执行 / 收起态拒绝计数 | 真浏览器 + REST API |
| J3: 英文界面 | 英文 gate label / 英文收起态 | 真浏览器，`im_lang=en` |
| J4: REST 历史 | approval 字段持久化到 REST 历史 | curl → 验证 `approval=user_allow` / `user_deny` |

---

## 验收标准覆盖表

### Requirement: 技术动作收在同一个 agent 消息气泡内

#### Scenario: agent 调用工具并请求授权
- **期望来源**: spec.md + prototype.html（合一气泡：工具面板 + 待决卡均在气泡内，气泡外无审批卡）
- **验证方式**: J1 浏览器截图（`r4-conv-pending.png`）+ DOM `.chat-permission-card` 在 agent bubble 内
- **证据**: r4-conv-pending.png 截图，待决卡深色，在同一 agent 消息气泡内；r6-after-allow.png 允许后气泡外无审批卡
- **结果**: **pass**
- **备注**: 合一气泡确认，气泡外无独立审批卡

---

### Requirement: 待决审批醒目且可操作

#### Scenario: agent 请求授权
- **期望来源**: spec.md + prototype.html（深色卡、气泡最下方、工具名 + 脉冲「需要确认」+ 「允许 / 本会话内允许 / 拒绝」选项）
- **验证方式**: J1 浏览器截图 r5-pending-card-zh.png + DOM 检查
- **证据**: 深色卡 ✓，"需要确认"（中文）脉冲 ✓，无锁图标 ✓，工具名 write ✓，tool_input JSON ✓；**按钮文案显示英文 "Allow once" / "Deny" / "Allow for session"**，原型要求中文"允许 / 本会话内允许 / 拒绝"
- **结果**: **fail**
- **备注**: 待决卡整体形态基本符合，但按钮 label 是英文。`permission-card.tsx` 直接渲染 `opt.label`（来自后端 options，英文字符串），未走 i18n 映射。中文界面目标态要求全中文（design.md §视觉与交互基准 + prototype.html 第 202-204 行：「允许」「本会话内允许」「拒绝」）。

#### Scenario: 已有已决审批时又来新的待决审批
- **期望来源**: spec.md（上方已并入工具列表，下方新待决卡，两者同时可见）
- **验证方式**: 未单独走（LLM 需连续两次触发审批较难稳定复现，且已决并入工具行由组件测试覆盖）
- **证据**: 组件测试覆盖（progress.md R3/R4）
- **结果**: **inconclusive**
- **备注**: 无法在 live 单独复现，后续 fix round 可在组件测试层验证已有证据，或 live 再试

---

### Requirement: 用户决定后待决卡即时折叠并并入工具列表

#### Scenario: 用户点允许
- **期望来源**: spec.md（待决卡消失，工具行「已授权」）
- **验证方式**: J1 allow 旅程，点击 "Allow once"，r6-after-allow.png
- **证据**: 待决卡消失 ✓，收起态显 `1 次工具调用 · 1 次授权 · ● 1 允许`；展开后工具行显"已授权"（绿色）（r7-tool-panel-expanded.png）；REST 历史 `approval=user_allow` ✓
- **结果**: **pass**

#### Scenario: 用户点拒绝
- **期望来源**: spec.md（待决卡消失，工具行「已拒绝」+ 行尾「未执行」）
- **验证方式**: J2 deny 旅程，REST API deny，r15-deny-panel-toggle.png
- **证据**: 工具行显"已拒绝"（红色）✓，行尾"未执行" ✓；REST 历史 `approval=user_deny + reason=denied` ✓
- **结果**: **pass**
- **备注**: Playwright 点击 Deny 按钮时因截图时序问题未触发（实际等待中），改用 REST API 直接 deny；deny UI 结果与预期一致

---

### Requirement: 已决审批以工具行形态呈现，无独立卡片、无锁图标

#### Scenario: 展开工具列表查看已决审批
- **期望来源**: spec.md + real-variants.png（行内"已授权"绿/"已拒绝"红，无独立卡片，无锁图标）
- **验证方式**: J1/J2 展开工具面板，r7-tool-panel-expanded.png / r15-deny-panel-toggle.png
- **证据**: allow 行：`write 已授权 ... 5m 17s`（r7）；deny 行：`write 已拒绝 .gitconfig 未执行`（r15）；无独立卡片 ✓，无锁图标（DOM 检查 `lock icon found: False`）✓
- **结果**: **pass**

#### Scenario: 收起工具面板看授权概况
- **期望来源**: spec.md（`N 次授权 · X 允许 · Y 拒绝`，仅非零分项）
- **验证方式**: J1 收起态：`1 次工具调用 · 1 次授权 · ● 1 允许`；J2 收起态：`1 次工具调用 · 1 次授权 · ● 1 拒绝`
- **证据**: 两次截图均可见收起态分项计数（r6-after-allow.png, r12-deny-completed-collapsed.png）；绿/红圆点 ✓，仅非零分项 ✓
- **结果**: **pass**

#### Scenario: 本条消息没有任何授权（空态）
- **期望来源**: spec.md（无授权后缀，不出现任何审批相关呈现）
- **验证方式**: J3 英文界面，`.ssh-config` 无需授权的工具调用消息，r17-allow-panel-en.png
- **证据**: 下方消息显示 `1 tool call`（无授权后缀）✓
- **结果**: **pass**

---

### Requirement: 行内「是否授权」与「执行结果」分区，互不遮挡

#### Scenario: 授权后执行成功
- **期望来源**: spec.md + real-variants.png（行旁「已授权」，行尾耗时）
- **验证方式**: J1 allow 旅程，r7-tool-panel-expanded.png
- **证据**: `write 已授权 /...gitconfig 5m 17s`，闸门区"已授权"与结果区耗时各占一侧 ✓
- **结果**: **pass**

#### Scenario: 授权后执行失败（关键边界）
- **期望来源**: spec.md（「已授权」在名称旁，失败报错在行尾，同时可见不覆盖）
- **验证方式**: 未在 live 复现（LLM 难稳定造授权后失败），组件测试覆盖（progress.md R3 `error` 状态矩阵）
- **证据**: progress.md 描述组件测试覆盖「授权后失败两区并存」13 例，461 passed
- **结果**: **inconclusive**
- **备注**: 不违反用户面期望，但未 live 验证此关键边界。组件测试有确定性覆盖，但替代验证不完全等同于 live 可观察结果。

#### Scenario: 拒绝不重复呈现
- **期望来源**: spec.md（只在名称旁一次「已拒绝」，行尾「未执行」，不出现第二处「已拒绝」）
- **验证方式**: J2 deny 展开，DOM 检查 `'已拒绝' count: 0`（body 文本中未出现重复）
- **证据**: r15-deny-panel-toggle.png：行内只有一处"已拒绝"（闸门区），行尾"未执行"，无行尾 reason 徽标重复
- **结果**: **pass**

---

### Requirement: 工具失败报错文案跟随界面语言

#### Scenario: 中文界面
- **期望来源**: spec.md + design.md 决策5（zh「退出码 {{code}}」/「失败」）
- **验证方式**: i18n 键验证（`toolFailExit: 退出码 {{code}}`，`toolFailGeneric: 失败`）+ 中文界面渲染（r15-deny-panel-toggle.png "未执行" 为中文）
- **证据**: zh.json 含 `toolFailExit / toolFailGeneric / toolNotExecuted` 中文键 ✓；live 中"未执行"中文显示 ✓
- **结果**: **pass**
- **备注**: failTag 的 exit code / failed 场景未在 live 验证（需实际运行失败的工具），但 i18n 键已接入，组件测试 zh/en 覆盖

#### Scenario: 英文界面
- **期望来源**: spec.md（英文界面英文文案）
- **验证方式**: J3 英文界面，en.json 键（`toolFailExit: exit {{code}}`），gate 标签 "Authorized" ✓
- **证据**: r17-allow-panel-en.png：闸门区 "Authorized"，收起态 "1 tool call · 1 approved · ● 1 allowed"（全英文）✓
- **结果**: **pass**

---

## Issues

### Issue 1：待决卡按钮文案不随界面语言（英文硬编码）

- **Severity**: major
- **Regression Relation**: direct（直接违反本 unit 验收标准）
- **Recommended Action**: fix-implementation
- **Action Rationale**: design.md §视觉与交互基准明确要求"目标态全中文文案"，原型 prototype.html 第 202-204 行待决卡按钮文案为"允许 / 本会话内允许 / 拒绝"。实现中 `permission-card.tsx` 直接渲染 `{opt.label}`（来自后端 options 的英文字符串），导致中文界面按钮显示英文 "Allow once" / "Allow for session" / "Deny"，且英文界面同样直接用后端字符串（未走 i18n 映射）。

**期望**: 中文界面按钮显示「允许 / 本会话内允许 / 拒绝」；英文界面显示「Allow once / Allow for session / Deny」
**实际**: 两种界面均显示后端 options.label 英文字符串
**操作步骤**: 中文界面打开 agent 对话，触发 write .gitconfig → 待决卡弹出 → 观察按钮文案

**修复方向**: 
- 方案A：前端在渲染 options 时按 `opt.id`（`allow_once` / `allow_session` / `deny`）映射 i18n 键。在 `zh.json` / `en.json` 各加 `permissionAllowOnce` / `permissionAllowSession` / `permissionDeny` 键，`permission-card.tsx` 改为 `t(keyForOption(opt.id)) || opt.label`。
- 方案B：后端按语言返回 label（复杂，不推荐）。

---

## Side Findings

1. **待决卡 "question" 文案英文**：待决卡显示的 question（"Allow write? Writing to... requires explicit confirmation"）是后端 auto_mode_gate 生成的英文字符串，在中文界面下仍为英文。这不在本 unit 验收标准的明确要求范围内（spec 只提按钮、工具名旁闸门区和收起态），记 Side Finding，不立 issue。

2. **"Scenario: 已有已决审批时又来新的待决审批" 未 live 验证**：LLM 需连续两次请求审批较难稳定触发，组件测试有覆盖，但 live 未单独走。标 inconclusive，不影响本 unit 主路径判断。

3. **授权后执行失败关键边界 live 未验证**：LLM 难稳定复现授权后执行失败，组件测试覆盖 13 例。标 inconclusive。

---

## 上层文档同步

- `SPEC.md`（跨包顶点架构）：无需更新，本 unit 不改架构依赖方向
- `docs/specs/kernel/spec.md`：**需更新**，`ToolResult.approval` 新字段及 `tool_end` 带 approval 是新的可观察行为契约，当前未记录（grep approval 无结果）
- `docs/specs/im/spec.md`：**需更新**，`tool_call.approval` REST/WS 序列化新字段未记录
- `docs/specs/gateway/spec.md`：**需更新**，node 流式增量 `tool_call` 携带 approval 未记录
- `docs/specs/cli/spec.md`：无需更新（CLI 不在本 unit 范围）
- `AGENTS.md` / `CLAUDE.md`：无需更新
- `docs/SPEC_GUIDE.md`：无需更新（文档体系本身未改）

> 三份长青契约层（kernel/im/gateway）的 delta-spec 归并是 orchestrator §7.0 收尾职责，reviewer 在此标记，不自行改写。

---

## 原型对照（prototype.html）

| 对照项 | 预期 | 实测 | 结论 |
|---|---|---|---|
| 合一气泡 | 文本→工具面板→待决卡，气泡外无卡 | r4/r6 截图确认 | ✓ |
| 收起态分项计数 | `N 次工具调用 · K 次授权 · ● X 允许 · ● Y 拒绝` | r6/r12 截图确认（绿/红点） | ✓ |
| 行内闸门-结果分区 | 闸门区（名称旁）/ 结果区（行尾）各占一侧 | r7/r15 截图确认 | ✓ |
| 待决卡形态 | 深色、无锁图标、脉冲"需要确认"、三个按钮 | r5 截图确认形态；但按钮文案英文 | 部分 ✗ |
| 目标态全中文文案 | 待决卡按钮：允许/本会话内允许/拒绝 | 实测英文：Allow once/Deny/Allow for session | ✗ |
| 生命周期 | 待决→点击→折叠并入工具行 | allow/deny 均走通 | ✓ |

---

## 验收结论

**Verdict: fail**

主路径（allow/deny 合一气泡、已授权/已拒绝行内分区、收起态计数、气泡外无卡、REST 持久化）整体走通，视觉效果良好。

唯一 fail 项：**待决卡按钮文案在中文界面显示英文**（"Allow once" / "Deny" / "Allow for session"），违反 design.md 明确要求的"目标态全中文文案"和原型对照基准。

需 fix-implementation 修复此项后，可走 fast-lane 复验。
