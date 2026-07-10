# feat-340-M30 — Progress

> 对齐: `attachments/prototype/project/*.jsx` 源码原型

## 状态

- [x] R1: Chat 原型行为对齐
- [x] R2: Settings/Agents/Nodes 原型行为对齐
- [x] R3: Me 页旧样式清理与记录
- [x] R4: Agent detail 页原型细节补齐
- [x] R5: Chat presence/avatar 细节补齐
- [x] R6: 后台 UI 审计细节补齐
- [x] Focused tests: 51 tests passed
- [x] Agent detail focused tests: 19 tests passed
- [x] Chat avatar/presence focused tests: 41 tests passed
- [x] UI audit focused tests: 64 tests passed
- [x] Build: `npm run build` passed
- [ ] Browser QA: 未执行真实浏览器截图验收

## R1 — Chat 原型行为对齐

- Context: 用户明确指定 `attachments/prototype` 为原型来源。当前 Chat 气泡与原型 `MessageBubble` 有多处偏差: 用户消息显示 avatar、system 消息被当 agent 气泡、agent 正文没有 Markdown、mobile Enter 会发送、Header avatar 没有状态点。
- Decision:
  - `MessageBubble` 中 system 消息改为居中文本。
  - 用户消息不再渲染 message avatar 和 sender meta。
  - agent 消息使用轻量 `MarkdownContent` 渲染，支持 paragraph / inline code / bold / list / fenced code。
  - tool calls 与 token chip 仅在 agent 消息上展示，token chip 保持在气泡内部，与原型 JSX 结构一致。
  - mobile 下 Enter 不再拦截发送，desktop 保持 Enter 发送。
  - direct-agent Header avatar 传入 node status，NodeChip 仅 direct-agent 显示。
  - `classifyConversationKind` 兼容后端 `user-user`，避免 user-user direct conversation 被误判为 direct-agent。
- Rationale: 原型源码是验收基准，不能用之前测试中“用户也有 avatar / TokenChip 在气泡外”的旧契约覆盖原型行为。
- Evidence:
  - Tests: `npm run test -- src/features/chat/v2/components/message-pane.test.tsx` 通过（包含在 51 tests 聚合命令中）。
  - Entry: Chat v2 message pane 组件入口。
  - Frontend State Matrix: default / empty / mobile / desktop / token usage / mention picker 由现有测试覆盖；Browser QA 未执行。
  - Browser QA: 未执行。
  - E2E/Regression: `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx` 已更新原型断言。
  - Visual/Interaction: 未截图；待后续真实浏览器 QA。
- Rollback: 回退 `message-pane.tsx`、`chat-types.ts`、`global.css` 中本 R 改动，并恢复旧测试断言。
- Commits: 未提交。

## R2 — Settings/Agents/Nodes 原型行为对齐

- Context: 原型 `SettingsPage` 在 Agents split view 内提供 `+ New`，新建 Agent 表单包含可选 Owning Node；当前实现把 Agents `+ New` 绑定到第一个 node 的 `/settings/nodes/:nodeId/agents/new`，且创建页 Owning Node 为 disabled input。Nodes 卡片还额外显示原型没有的 agents-on-node 列表，router 仍暴露原型没有的 Policies 页。
- Decision:
  - 新增 `/settings/agents/new` route，并让 Agents list / detail rail 的 `+ New` 指向该 route。
  - `AgentCreatePage` 支持通用新建: 拉取 nodes，默认选择 URL nodeId / 第一个非 offline node，并渲染 Owning Node `<select>`。
  - 保留 `/settings/nodes/:nodeId/agents/new`，从 Node 入口进入时默认选中该 node，但仍允许按原型切换。
  - Agent ID 输入时 lowercase 并过滤到 `[a-z0-9_-]`，validate 同步校验。
  - Agents list / desktop rail avatar 改为基于 agent seed 的稳定色，不再全部硬编码同一色。
  - Nodes 卡片移除 agents-on-node 列表。
  - Router 移除 `/settings/policies` 主路由。
- Rationale: 这些是用户能直接看到/点击的原型路径差异；创建页必须由页面本身负责 Owning Node 选择，而不是由列表页偷选第一个 node。
- Evidence:
  - Tests: `agent-create.test.tsx`、`agents-list-page.test.tsx`、`nodes-page.test.tsx`、`router.test.tsx` 通过（包含在 51 tests 聚合命令中）。
  - Entry: `/settings/agents`, `/settings/agents/new`, `/settings/nodes/:nodeId/agents/new`, `/settings/nodes`。
  - Frontend State Matrix: default / loading / error / disabled / submitting / nullable node data 由现有测试和 build 覆盖。
  - Browser QA: 未执行。
  - E2E/Regression: 对应页面测试已随原型契约更新。
  - Visual/Interaction: 未截图；待后续真实浏览器 QA。
- Rollback: 恢复 Agents `+ New` 到 node-scoped path，恢复 disabled Owning Node input，恢复 Nodes agents-on-node 列表和 Policies route。
- Commits: 未提交。

## R3 — Me 页旧样式清理与记录

- Context: 当前 MePage JSX 已按原型 utility 样式实现，但全局 CSS 残留 `.im-me-page` 旧规则会额外添加 padding/gap/nav/fieldset 样式，可能让真实页面偏离原型。
- Decision:
  - 删除 `.im-me-page` 旧全局样式块。
  - MePage 测试补 `QueryClientProvider` 和 `listNodes` mock，避免组件当前 query 依赖导致测试无法覆盖页面。
  - 新增本 milestone 的 `tasks.md` / `progress.md`。
- Rationale: 样式源应单一，原型版 MePage 的 spacing 已在组件 className 中定义，旧全局规则属于遗留覆盖。
- Evidence:
  - Tests: `me-page.test.tsx` 通过（包含在 51 tests 聚合命令中）。
  - Entry: `/me`。
  - Frontend State Matrix: default / language switch / sign out / identity card / nodes/account rows 覆盖。
  - Browser QA: 未执行。
  - E2E/Regression: `src/IM/frontend/src/features/me/me-page.test.tsx`。
  - Visual/Interaction: 未截图；待后续真实浏览器 QA。
- Rollback: 恢复 `.im-me-page` 全局样式块，回退 MePage test provider/mock。
- Commits: 未提交。

## R4 — Agent detail 页原型细节补齐

- Context: 用户指出 `http://127.0.0.1:8011/settings/agents/xxx` 与原型仍有差异。复查 `prototype/project/im-settings-page.jsx::AgentDetailPanel` 后，发现当前实现额外渲染了独立 node status pill，desktop header 缺少原型中的 Save/No changes 主按钮，footer Discard 常驻 disabled，panel/header/body spacing 与原型值不一致。
- Decision:
  - Header 改回原型结构: avatar 负责状态点；subtitle 为 `agent_id` + inline node 状态 dot/name。
  - 移除 `agent-detail-status-pill` / `.im-agent-panel-status-chip` 在 detail header 的使用。
  - Desktop header 渲染 `Open chat ↗` 和 submit button，submit button 文案随 saving/saved/dirty/no-changes 切换。
  - Footer 保持原型卡片样式，Discard 仅 dirty 时渲染；保留现有 `Open chat` 与 `PATCH /config` 行为。
  - CSS 对齐原型: detail panel 背景 `oklch(0.93 0.007 240)`，desktop header `18px 28px 14px`，body `20px 28px`，card `14px 16px`。
- Rationale: 这些差异是 `/settings/agents/:id` 首屏最显眼的视觉/交互偏差，且不影响后端 API 契约，可以直接按原型 JSX 回正。
- Evidence:
  - Tests: `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx` 通过。
  - Summary: 4 files, 19 tests passed.
  - Build: `npm run build` 通过。
  - Browser QA: 未执行。
  - Notes: Existing Vitest `--localstorage-file` warning and AgentsListPage `act(...)` warnings remain; command exit code was 0.
- Rollback: 恢复 `agent-detail-page.tsx` 的 status pill/header button/footer 常驻 Discard 逻辑，并回退 `global.css` 的 detail panel spacing。
- Commits: 未提交。

## R5 — Chat presence/avatar 细节补齐

- Context: 用户指出群聊不应显示在线/离线状态点，并进一步指出头像状态点呈现和原型不一致，当前点被裁切成缺角。后台 UI 审计也确认 `Avatar` 实现用固定白描边/被头像容器裁切，偏离 prototype `im-components.jsx::Avatar` 的 wrapper + face + absolute status dot 结构。
- Decision:
  - `ConversationSidebar` 只在 `direct-agent` row 上给 Avatar 传 `status`，group / agent-network 不再显示在线离线点。
  - `MentionPicker` 的 agent avatar 不再传 `status`，与 prototype mention dropdown 一致。
  - `MentionPicker` 无匹配时返回 `null`，与 prototype `filtered.length === 0 return null` 一致。
  - `Avatar` 改为外层 `.chat-avatar` wrapper + 内层 `.chat-avatar-face`，状态点作为 sibling 绝对定位，避免被头像圆形 `overflow:hidden` 裁切。
  - 状态点颜色/描边对齐 prototype: online `oklch(0.55 0.18 145)`，running `oklch(0.70 0.18 60)`，offline `#94a3b8`，border `2px solid var(--sidebar-bg, #fff)`。
- Rationale: presence 是用户一眼看到的状态信号。群聊显示单个 agent 的在线点会误导用户；缺角状态点是基础视觉 bug，必须优先修。
- Evidence:
  - Tests: `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/components/mention-picker.test.tsx src/features/chat/v2/components/message-pane.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx` 通过。
  - Summary: 5 files, 41 tests passed.
  - Build: `npm run build` 通过。
  - Browser QA: 未执行。
  - Notes: Existing Vitest `--localstorage-file` warning remains; command exit code was 0.
- Rollback: 恢复 `Avatar` 单层结构、恢复 Sidebar/MentionPicker 的 status 传递。
- Commits: 未提交。

## R6 — 后台 UI 审计细节补齐

- Context: subagent 对比 prototype 后指出仍有多个 P1/P2 视觉差异: chat list/mobile header、sidebar avatar 尺寸/颜色、KindBadge 色相、MessagePane 背景与气泡、New Group placeholder、Settings Agents/Nodes/Account 的细节 spacing 和 copy。
- Decision:
  - Chat sidebar row avatar 改为 36px，direct-agent 用 agent seed 色，group/network 分别使用 prototype 的 270/30 hue。
  - Chat filter tabs 保留横向溢出但隐藏浏览器原生 scrollbar，去掉原型中不存在的灰白条。
  - Chat sidebar 设置 `--sidebar-bg`，让 status dot 描边在深浅 sidebar 中都按原型贴合。
  - KindBadge 去掉额外 border，并把 group/network 色相改回 prototype 的 270/30。
  - New Group 群名 placeholder 在选中 agent 后显示参与者拼接名，提交 fallback 与 placeholder 一致。
  - Nodes/Account 移动端内容 padding 改为 `16px 14px`，node status pill 改为 11.5px/700/6px dot，node create CTA 改为 prototype 文案。
  - Account desktop subtitle 改为 prototype 固定说明，Gateway 底部摘要按 Member since → Owned nodes count 展示。
- Rationale: 这些都是首屏可见或交互中可见的 prototype parity 问题；其中头像/状态点/移动端 header 属于高频 UI 信号，不能继续用近似实现。
- Evidence:
  - Tests: `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/components/new-group-modal.test.tsx src/features/chat/v2/components/mention-picker.test.tsx src/features/chat/v2/components/message-pane.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/nodes/nodes-page.test.tsx src/features/settings/nodes/nodes-page-status.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx` 通过。
  - Summary: 9 files, 64 tests passed.
  - Regression sweep: `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/nodes/nodes-page-agents.test.tsx src/features/settings/nodes/nodes-page-ws.test.tsx` 通过，4 files / 10 tests passed.
  - Build: `npm run build` 通过。
  - Browser QA: 未执行。
  - Notes: Existing Vitest `--localstorage-file` warning, React `act(...)` warnings, and one query-data warning remain; command exit code was 0.
- Rollback: 回退本轮 chat/sidebar/new-group/nodes/account/i18n/CSS 改动。
- Commits: 未提交。

## Verification

- `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/components/new-group-modal.test.tsx src/features/chat/v2/components/mention-picker.test.tsx src/features/chat/v2/components/message-pane.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/nodes/nodes-page.test.tsx src/features/settings/nodes/nodes-page-status.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx`
  - Result: passed.
  - Summary: 9 files, 64 tests passed.
  - Notes: Existing Vitest `--localstorage-file` warning, React `act(...)` warnings, and one query-data warning remain; command exit code was 0.
- `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/nodes/nodes-page-agents.test.tsx src/features/settings/nodes/nodes-page-ws.test.tsx`
  - Result: passed.
  - Summary: 4 files, 10 tests passed.
  - Notes: Existing Vitest `--localstorage-file` warning and React `act(...)` warnings remain; command exit code was 0.
- `npm run build`
  - Result: passed.
  - Notes: Vite chunk-size warning and dynamic/static import warning remain; not introduced by this milestone.
- `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx`
  - Result: passed.
  - Summary: 4 files, 19 tests passed.
  - Notes: Existing Vitest `--localstorage-file` warning and AgentsListPage `act(...)` warnings remain; command exit code was 0.
- `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/components/mention-picker.test.tsx src/features/chat/v2/components/message-pane.test.tsx src/features/settings/agents/agent-detail-page.test.tsx src/features/settings/agents/agent-edit.test.tsx`
  - Result: passed.
  - Summary: 5 files, 41 tests passed.
  - Notes: Existing Vitest `--localstorage-file` warning remains; command exit code was 0.
- `npm run test -- src/features/chat/v2/components/message-pane.test.tsx src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agents-list-page.test.tsx src/features/settings/nodes/nodes-page.test.tsx src/features/me/me-page.test.tsx src/app/router.test.tsx`
  - Result: passed.
  - Summary: 6 files, 51 tests passed.
  - Notes: Existing React `act(...)` warnings in AgentsListPage tests and one query warning in NodesPage tests remain; command exit code was 0.

## Browser QA Gap

- 本轮尚未启动真实 IM 前端页面做浏览器截图/console/network 验收。
- 原因: 用户中途要求先补 milestone tasks/progress；当前已完成源码实现、组件/页面回归测试和生产 build。
- 后续建议: 用真实账号打开 `/chat`, `/settings/agents`, `/settings/agents/new`, `/settings/nodes`, `/me`，覆盖 desktop 1440 和 mobile 375 两个 viewport，并把截图补入本目录。
