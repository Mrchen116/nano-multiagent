# Verification Report: feat-434

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 tasks complete；5/5 requirements covered |
| Correctness | 14/14 scenarios covered |
| Coherence | Followed（5/5 design 决策遵守） |

All checks passed. Ready for PR.

---

## Completeness

### Tasks（6/6 complete）

全部 tasks.md 退出标准已标 `[x]`：

- [x] allow 成功工具的 `approval=user_allow` 端到端到达前端（5 步链覆盖 + 内核单测）
- [x] `approval` 贯穿 内核→Gateway→IM→前端，IM REST 历史与 WS 均携带
- [x] 前端单测覆盖 ToolCallRow 闸门/结果分区 + denied 去重 + 已决并入
- [x] `failTag` 经 i18n，zh/en 各出对应文案
- [x] `npm run test` (461 passed) + `pytest -m "not e2e"` (2871 passed) 全绿
- [x] 真端到端跑通：live 栈下 allow 成功工具前端真显「已授权」（progress.md R5 含 DOM 实测 + 截图证据）

### Spec requirements 覆盖（5/5）

1. 技术动作收在同一个 agent 消息气泡内 ✓
2. 待决审批醒目且可操作 ✓
3. 用户决定后待决卡即时折叠并并入工具列表 ✓
4. 已决审批以工具行形态呈现，无独立卡片、无锁图标 ✓
5. 行内「是否授权」与「执行结果」分区，互不遮挡 ✓
6. 工具失败报错文案跟随界面语言 ✓

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| **Req: 技术动作收在同一气泡内** · Scenario: agent 调用工具并请求授权 | `message-pane.tsx:444-454`：PermissionCard 移入 `chat-bubble-card` 内；气泡外无独立审批卡渲染 | `message-pane.test.tsx:462-479`（pending 在气泡内断言 `.closest(".chat-bubble-card")`） | covered |
| **Req: 待决审批醒目且可操作** · Scenario: agent 请求授权 | `permission-card.tsx:115-128`：深色卡 + 脉冲圆点 `chat-permission-pulse` + 三按钮（允许/本会话内允许/拒绝），无锁图标 | `permission-card.test.tsx`：三按钮渲染 | covered |
| **Req: 待决醒目** · Scenario: 已有已决审批时又来新的待决审批 | `message-pane.tsx:444`：`.filter(req => req.status !== "resolved")` 只渲 pending；已决并入 `tool_call.approval` 闸门区（两者同在气泡内，同时可见） | `message-pane.test.tsx:520-552`（resolved+pending 只显 pending 卡断言） | covered |
| **Req: 用户决定后待决卡即时折叠并并入** · Scenario: 用户点允许 | WS `permission.resolved` 事件触发 reducer 把 `request.status` 改 `resolved` → message-pane filter 不渲；`tool_call.approval=user_allow` 经 WS/REST 流到 ToolCallRow 闸门区「已授权」 | `tool-calls-panel.test.tsx:856-910` | covered |
| **Req: 用户决定后待决卡折叠** · Scenario: 用户点拒绝 | `permission-card.tsx:105-107`：resolved → return null；ToolCallRow `isNotExecuted`（deny → 结果区「未执行」） | `tool-calls-panel.test.tsx:924-945` | covered |
| **Req: 已决审批以工具行形态呈现，无独立卡片、无锁图标** · Scenario: 展开工具列表查看已决审批 | `tool-calls-panel.tsx:152-188`：闸门区 `chat-tool-call-gate--allow/deny` 显「已授权/已拒绝」；`permission-card.tsx:105-107` resolved → null，不渲独立卡；global.css 无 `chat-permission-card--resolved` 样式 | `tool-calls-panel.test.tsx:856-960`（闸门区文案断言）；`message-pane.test.tsx:499-518`（resolved 不渲卡） | covered |
| **Req: 已决以工具行形态** · Scenario: 收起工具面板看授权概况 | `tool-calls-panel.tsx:46-109`：`N 次授权 · X 允许 · Y 拒绝`，绿/红点，非零分项才显 | `tool-calls-panel.test.tsx:980-1015`（分项计数 zh/en、空态无后缀） | covered |
| **Req: 已决以工具行形态** · Scenario: 本条消息没有任何授权（空态） | `tool-calls-panel.tsx:78`：`approvalCount > 0` 才渲授权后缀 | `tool-calls-panel.test.tsx:1007-1015`（空态无后缀） | covered |
| **Req: 行内「是否授权」与「执行结果」分区** · Scenario: 授权后执行成功 | `tool-calls-panel.tsx:182-188`（闸门区「已授权」）+ `:200-203`（行尾 duration） | `tool-calls-panel.test.tsx:862-879`（已授权 + 耗时并存） | covered |
| **Req: 行内分区** · Scenario: 授权后执行失败（关键边界） | 闸门区 `gateVerdict(call)==="allow"` 显「已授权」；结果区 `failTag(call,t)` 返失败文案；两者 CSS 并排各占一侧 | `tool-calls-panel.test.tsx:883-915`（两区同时在 DOM） | covered |
| **Req: 行内分区** · Scenario: 拒绝不重复呈现 | `REASON_BADGE_NAMES`（`tool-presentation.ts:80-87`）不含 `denied`，行尾不显 denied reason 徽标；闸门区仅一次「已拒绝」；结果区显「未执行」 | `tool-calls-panel.test.tsx:924-945`（denied 去重） | covered |
| **Req: 工具失败报错文案跟随界面语言** · Scenario: 中文界面 | `tool-presentation.ts:124`：`t("chat.messagePane.toolFailExit", {code})`；zh.json `"toolFailExit":"退出码 {{code}}"` | `tool-calls-panel.test.tsx:1017-1042`（zh 退出码 N / 失败） | covered |
| **Req: 工具失败文案跟随语言** · Scenario: 英文界面 | en.json `"toolFailExit":"exit {{code}}"` | `tool-calls-panel.test.tsx:1044-1070`（en exit N / failed） | covered |
| **历史 denied 行回退**（无 approval 字段兼容） | `tool-presentation.ts:99`：`call.reason === "denied" → return "deny"` | `tool-calls-panel.test.tsx:950-968` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| **决策1: approval 用新字段，不复用 reason** | 是 | `types.ToolResult.approval: str \| None`（`core/types.py:78`）；前端 `chat-types.ts:97`；`REASON_BADGE_NAMES` 不含 denied（`tool-presentation.ts:80-87`） |
| **决策2: 标识源头在内核 gate；deny 复用 reason_code 载体，allow 须新建传播链（五步）** | 是 | 1. gate 返回信号（`auto_mode_gate.py:697/704/711/717`）；2. runner block=False 保留（`runner.py:150-151`）；3. registry out_meta lift（`registry.py:207/217-218`）；4. tool_executor 成功/错误路径填充（`tool_executor.py:177-185/206-208/217`）；5. realtime_stream tool_end 携带（`realtime_stream.py:108`） |
| **决策3: 已决审批呈现改读 tool_call.approval，删除气泡外已决卡** | 是 | `message-pane.tsx:441-454`（PermissionCard 在 bubble 内 + filter resolved）；`permission-card.tsx:105-107`（resolved → null）；`global.css:3051-3052`（resolved 样式注释说明已删） |
| **决策4: 行内分区 + denied 去重** | 是 | `tool-calls-panel.tsx:152-205`：闸门区（名称右侧）+ 结果区（行尾）两区分离；`tool-presentation.ts:80-87` denied 从 REASON_BADGE_NAMES 移除，防双印 |
| **决策5: failTag 接 i18n** | 是 | `tool-presentation.ts:119-126`：`failTag(call, t)` 接 `t()` 参数；i18n 键 `toolFailExit`/`toolFailGeneric` 在 zh.json/en.json 均已落 |

### 架构自洽性（§4.3）

- **依赖方向**：`approval` 标识从 `agent.core` 产出，经 `agent.platform`（realtime_stream）到消费者；Gateway 只 import `agent.sdk`，不直接读 core 内部 ✓
- **跨机边界**：无假设——approval 标识经显式字段链（tool_end event → Gateway payload → IM encode/decode → WS/REST → 前端），无跨进程直读 ✓
- **复用 vs 平行**：approval 透传链沿用 feat-425 emoji 相同的逐字模板（domain + payload + encode/decode + event_types + Gateway forward），无另造平行机制 ✓

### 代码模式一致性（§4.2 表层）

- 注释风格：feat-434 相关改动均有行内说明（写"为什么"），符合 COMMENTING_GUIDE ✓
- TODO/FIXME 格式：无残留 TODO/FIXME ✓
- Commit message 格式：`feat/test/docs(feat-434/M1/R<N>): <desc>` 格式一致 ✓
- import 边界：已在 contract 测试(`tests/contract/`)守护 ✓

---

## Issues

### CRITICAL
无。

### WARNING
无。

### SUGGESTION
无。

---

## §7.0 Delta-Spec 软对账（Advisory）

### kernel delta-spec（`specs/kernel/spec.md`）

| Scenario | 代码实现 | 契约符合度 |
|---|---|---|
| 用户显式允许的工具调用 — 消费者可观察到「经用户授权允许」的标识 | `auto_mode_gate.py:697/704/711` + `runner.py:150` + `registry.py:207` + `tool_executor.py:184` + `realtime_stream.py:108` | **契约与实现一致** |
| 用户显式拒绝的工具调用 — 消费者可观察到「经用户拒绝」的标识 | `auto_mode_gate.py:717` + ToolError.details + `tool_executor.py:206-208` + `realtime_stream.py:108` | **契约与实现一致** |
| 自动放行 — 不携带授权决策标识 | gate 自动路径在 `_handle_ask` 前 return，不经过 approval 赋值分支 | **契约与实现一致** |

**delta 未覆盖的对外行为**：无。内核新增 `ToolResult.approval`（可选字段）对 CLI 无行为影响，delta-spec 已注明「cli: no spec delta」，正确。

### im delta-spec（`specs/im/spec.md`）

| Scenario | 代码实现 | 契约符合度 |
|---|---|---|
| 经用户授权的工具调用在历史加载中保留标识 | `repositories.py:2814-2815`（encode）/ `2888-2889`（decode）+ `messages.py:183`（REST 序列化） | **契约与实现一致** |
| 旧工具调用无标识仍可加载 | `repositories.py:2888`：`item.get("approval")` 默认 None；前端读 undefined 不显闸门区 | **契约与实现一致** |

**delta 未覆盖的对外行为**：`event_types.py:68-69`（WS 下发时若 approval 为 None 则省略字段），此行为在 delta-spec Scenario 里未单独枚举，但已在 IM 单测覆盖（`test_tool_call_detail.py:293`）。属实现细节、非功能 delta，不算遗漏。

### gateway delta-spec（`specs/gateway/spec.md`）

| Scenario | 代码实现 | 契约符合度 |
|---|---|---|
| 经用户授权的工具调用被中继 — Gateway 中继携带「经用户授权允许」标识 | `main.py:3643-3676`：从 tool_end event 取 approval，拼进 tool_call payload | **契约与实现一致** |
| 经用户拒绝的工具调用被中继 | 同上，approval=user_deny | **契约与实现一致** |

**delta 未覆盖的对外行为**：无。

---

*Round 1 · 2026-06-25*
