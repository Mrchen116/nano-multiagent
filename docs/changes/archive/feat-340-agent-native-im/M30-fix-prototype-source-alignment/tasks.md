# feat-340-M30: fix-prototype-source-alignment — Tasks

> 对齐: `attachments/prototype/project/*.jsx` 源码原型

## 目标

把当前 IM 前端实现中与 `docs/changes/feat-340-agent-native-im/attachments/prototype/project` 原型源码不一致的可执行项拉回原型行为。范围聚焦用户已确认的原型代码，不把 spec-only 要求混入本 milestone。

## 退出标准

- [x] Chat MessageBubble 与原型一致: system 居中、用户消息无 avatar、agent 消息 Markdown、tool/token 仅 agent 消息展示。
- [x] Chat Header 与原型一致: direct-agent avatar 显示状态点，NodeChip 仅 direct-agent 显示。
- [x] Composer 与原型一致: 移动端 Enter 不发送，桌面 Enter 发送。
- [x] Conversation kind 推导兼容后端 `user-user/user-agent/agent-agent`，避免 direct-user 被误判成 direct-agent。
- [x] Agents `+ New` 进入通用新建页，新建页提供 Owning Node select；从 Node 入口进入时默认选中该 node。
- [x] Agent ID 输入按原型规整为 lowercase `[a-z0-9_-]`。
- [x] Agents 列表/rail avatar 不再硬编码同一颜色。
- [x] Agent detail 页 header/footer 与原型一致: 头像状态点 + inline node 状态、无额外 status pill、desktop header 有保存按钮、Discard 仅 dirty 时出现。
- [x] Nodes 卡片移除原型没有的 agents-on-node 列表。
- [x] 移除原型没有的 `/settings/policies` 主路由。
- [x] 移除旧 `.im-me-page` 全局样式，避免覆盖原型版 Me 页 utility layout。
- [x] 聚焦测试通过，前端 build 通过。

## 测试策略

用户路径分类: bug-regression + visual-only。该 milestone 是按源码原型修复 UI/交互偏差，主要风险是视觉/交互契约回归。

UI 状态矩阵:
| 状态 | 覆盖计划 |
|---|---|
| default | Chat、Agents、Nodes、Me 默认渲染由现有组件/页面测试覆盖 |
| loading | AgentCreate / AgentsList 现有 query loading 流程保留 |
| empty | MessagePane empty、AgentsList empty、Nodes empty 由现有测试覆盖 |
| error | AgentCreate API error、AgentsList load error 由现有测试覆盖 |
| disabled | AgentCreate submit disabled / Nodes save disabled 由现有测试覆盖 |
| submitting | AgentCreate mutation pending 由现有逻辑覆盖 |
| permission denied | N/A |
| long content | Chat Markdown/list/code 由组件渲染路径覆盖；未新增浏览器截图 |
| missing/nullable data | NodeChip null、agent color fallback、node fallback 覆盖 |
| mobile viewport | MessagePane mobile header/Enter 行为、Me mobile layout 覆盖 |
| desktop viewport | MessagePane desktop header/help、Agents desktop rail 覆盖 |
| dark mode | N/A（项目固定 IM theme） |

测试与验收映射:
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| Chat bubble 原型行为 | 更新 `message-pane.test.tsx` 回归断言 + `npm run build` | 是 |
| Agents 新建入口和 Owning Node select | 更新 `agent-create.test.tsx` / `agents-list-page.test.tsx` | 是 |
| Nodes 卡片结构 | `nodes-page.test.tsx` 聚焦回归 + build | 是 |
| Me 旧 CSS 覆盖 | `me-page.test.tsx` + build | 是 |
| Router 移除 Policies | `router.test.tsx` + build | 是 |

## Roadpoints

### R1 — Chat 原型行为对齐

- 步骤:
  1. 修改 `message-pane.tsx` 的 Header、MessageBubble、Enter 行为。
  2. 增加安全的轻量 Markdown 渲染路径与 `.im-md` 样式。
  3. 修复 conversation kind 推导。
  4. 同步组件测试断言。
- 验证:
  - `npm run test -- src/features/chat/v2/components/message-pane.test.tsx`
  - `npm run build`

### R2 — Settings/Agents/Nodes 原型行为对齐

- 步骤:
  1. 新增 `/settings/agents/new` route。
  2. Agents `+ New` 指向通用新建页。
  3. AgentCreate 支持 Owning Node select 与 Agent ID 规整。
  4. Agents avatar 使用稳定 seed 色。
  5. Nodes 卡片移除原型没有的 agents-on-node 列表。
  6. 移除 `/settings/policies` 主路由。
- 验证:
  - `npm run test -- src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx src/features/settings/nodes/nodes-page.test.tsx src/app/router.test.tsx`
  - `npm run build`

### R3 — Me 页旧样式清理与记录

- 步骤:
  1. 删除旧 `.im-me-page` 全局样式。
  2. 给 MePage 测试补 QueryClientProvider / listNodes mock，使测试真实覆盖当前组件依赖。
  3. 写 `tasks.md` / `progress.md` 记录本轮实现与证据。
- 验证:
  - `npm run test -- src/features/me/me-page.test.tsx`
  - `npm run build`

### R4 — Agent detail 页原型细节补齐

- 步骤:
  1. 对齐 `AgentDetailPanel` 原型 header: avatar 状态点、agent_id + node inline 状态行、desktop `Open chat ↗` + Save/No changes 按钮。
  2. 移除当前实现额外的独立 node status pill。
  3. 对齐 detail panel 背景、header/body/card/footer spacing。
  4. 底部 Discard 仅在 dirty 时渲染，保留现有保存/open chat API 行为。
- 验证:
  - `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx`
  - `npm run build`

### R6 — 后台 UI 审计细节补齐

- 步骤:
  1. 对齐 Chat list 移动端 header、搜索/过滤器 spacing、row avatar 尺寸与 direct/group/network 头像色。
  2. 修复 group / network 不显示在线状态点，状态点使用原型 wrapper + face + sibling dot，避免被裁切。
  3. 对齐 MessagePane 背景、header、消息列表 padding、agent bubble 色值/间距。
  4. 对齐 New Group 未输入群名时的 placeholder 为已选参与者拼接。
  5. 对齐 Agents 列表头像状态点、Create Agent header/form 背景。
  6. 对齐 Nodes / Account 移动端 padding、node status pill 尺寸、node create CTA、Account subtitle 与底部摘要。
- 验证:
  - `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/components/new-group-modal.test.tsx src/features/chat/v2/components/mention-picker.test.tsx src/features/chat/v2/components/message-pane.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/nodes/nodes-page.test.tsx src/features/settings/nodes/nodes-page-status.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx`
  - `npm run build`
