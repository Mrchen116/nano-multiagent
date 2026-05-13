# feat-340-M29: fix-chat-layout-mention-multipart — Tasks

> 对齐: ../design.md v1 (Changelog 2026-05-14 M29 行)

## 目标

修复 M28 之后用户亲自验收发现的 4 个未修复/回归问题：
1. Token chip 切换标签页后"要等很久才会恢复出现"（M28 R1 未真修）
2. Chat 消息气泡中头像和消息内容上下布局（CSS `flex-direction: column` 覆盖 `flex-row`）
3. 群聊输入框 @mention 仍无法触发 picker（M28 R3 未真修）
4. 多段回复（文字A → 工具调用 → 文字B）被合并到同一消息气泡

## 退出标准

- [ ] R1: 切换浏览器标签页再回来后，已完成的 agent 消息的 token chip **立即**显示（不闪烁、不延迟）
- [ ] R2: agent 和用户消息气泡中，头像与消息内容水平排列（左右布局），与原型一致
- [ ] R3: 进入群聊 → 在输入框输入 `@` → mention picker 在 200ms 内出现，显示群聊中的 agent 列表；输入 `@A` 能过滤到名字以 A 开头的 agent
- [ ] R4: agent 回复中若包含"文字 → 工具调用 → 文字"多段内容，每段文字应在独立的消息气泡中（与原型 MessageBubble 行为一致）
- [ ] `npm run build` + `npx tsc -b` 干净通过
- [ ] `grep` 验证 dist bundle 包含修复后的代码
- [ ] 桌面 1440x900 + 移动 375x812 双 viewport 截图自查，附到 progress.md Evidence 段

## 测试策略

用户路径分类: bug-regression（4 个历史/新发现 bug 修复）

UI 状态矩阵:
| 状态 | 覆盖计划 |
|---|---|
| default | R1/R2/R3/R4 均覆盖默认态 |
| loading | R1: 标签页切换后消息列表 refetch 期间 token chip 不闪烁 |
| empty | N/A |
| error | N/A |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | N/A |
| missing/nullable data | R1: REST 返回不含 token_usage 时的 fallback |
| mobile viewport | 双 viewport 截图覆盖 |
| desktop viewport | 双 viewport 截图覆盖 |
| dark mode | N/A（项目固定暗色主题）|

测试与验收映射:
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| R1 token chip 标签页切换后延迟/闪烁 | 浏览器手动验收：切标签页 → 回来看 token chip 立即在 | 否（状态驱动，依赖浏览器环境）|
| R2 chat-bubble CSS flex-direction 冲突 | 浏览器截图验证 + 审查 CSS 与组件 className 一致性 | 否（视觉样式）|
| R3 @mention 正则/ID 前缀/事件监听 | 浏览器手动验收：群聊输入 `@` 触发 picker + 键盘选择 | 否（交互行为，依赖真实数据）|
| R4 多段消息合并 | 触发 agent 执行工具调用后观察气泡拆分 | 否（交互行为）|

## Roadpoints

### R1 — Token chip 切换标签页后延迟/闪烁

- 步骤:
  1. 在 `chat-workspace-page.tsx` 中审查 `tokenUsageCache` useRef 与 reset effect 的交互
  2. 确认问题根因：React Query `refetchOnWindowFocus` 触发时，`v.data` 先变为 `undefined`（loading）再变为新数据，期间 reset effect 可能用空/旧数据覆盖了 state
  3. 修复：reset effect 中加入 `v.isFetching` 守卫，只在数据稳定（非 loading）时执行 reset；或改用 `v.dataUpdatedAt` 作为依赖而非 `v.data` 引用
  4. 备选：直接在 `listMessages` query 中设置 `refetchOnWindowFocus: false`，避免不必要的 refetch（token_usage 只来自 WS，REST 历史数据不需要 window focus 刷新）
  5. 验证 `tokenUsageCache` 在组件 unmount 时不会被清空（useRef 持久性）
- 验证: 切换标签页再回来后，已完成的 agent 消息 token chip 立即显示，无闪烁

### R2 — Chat 消息气泡头像与内容上下布局

- 步骤:
  1. 确认根因：`src/IM/frontend/src/styles/global.css` 中 `.chat-bubble { flex-direction: column }` 覆盖 `message-pane.tsx` 中 Tailwind `flex-row`/`flex-row-reverse`
  2. 修改 `.chat-bubble` CSS：删除 `flex-direction: column`，改为 `flex-direction: row`（或交由组件 className 控制，移除 CSS 中的方向声明）
  3. 检查 `.chat-bubble--user` 和 `.chat-bubble--agent` 的 `align-items` 在 row 方向下是否正确（`items-end` 在 row 方向下是垂直底部对齐，原型用 `align-items: flex-start`）
  4. 检查 `chat-bubble-meta`、`chat-bubble-card`、`chat-bubble-status` 在 row 布局下的位置是否正确
  5. 全局检查 message-pane.tsx 中的 className 与 global.css 是否有其他冲突
- 验证: agent 和用户消息气泡中，头像在左/右，消息内容在同一行，与原型一致

### R3 — 群聊 @mention 仍无法触发 picker

- 步骤:
  1. 审查 `message-pane.tsx` 中 `MENTION_RE = /@([^@\s]*)$/` 是否正确定义和使用
  2. 审查 `chat-api.ts` 中 `listMentionCandidates` 的 `agent:` 前缀归一化逻辑
  3. 在浏览器 DevTools 中验证：输入 `@` 时 `mentionQuery` 是否为非 null
  4. 检查 `MentionPicker` 组件是否正确渲染（条件渲染、position、z-index）
  5. 检查是否有 CSS 覆盖导致 picker 不可见（如 `overflow: hidden` 截断）
  6. 检查 mention candidates 数据是否正确加载（`mentionCandidates` query 是否成功返回）
  7. 备选：在 `chat-workspace-page.tsx` 中为 `mentionQuery` 加 console.log 调试
- 验证: 群聊输入 `@` → mention picker 200ms 内出现；输入 `@A` 能过滤

### R4 — 多段回复合并到同一气泡

- 步骤:
  1. 审查原型 `im-components.jsx` MessageBubble：确认原型中每个 msg 只包含一段 content，多段内容由多个 msg 项表示
  2. 审查后端 WS 事件序列：当 agent 回复"文字A → 工具调用 → 文字B"时，后端是发送新的 `message.created` 还是继续 `message.delta` 到同一 message_id
  3. 若后端发送的是同一 message_id 的 delta，前端 `chat-stream-reducer.ts` 的 `message.delta` 处理会将内容追加到同一消息
  4. 修复方案：与后端协调，确保工具调用后的新文字作为新的 `message.created`；或前端在收到 `tool_call.upserted` 后，将后续 `message.delta` 视为新消息（需 backend 配合发新 message_id）
  5. 若 backend 已发送新 message_id，检查前端 `message.created` 处理是否正确接收（可能被 dedupe 过滤？）
  6. 检查 `chat-stream-reducer.ts` 中 `message.created` 的 dedupe 逻辑是否过于激进（`state.messages.some((m) => m.id === ev.message_id)`）
- 验证: 触发 agent 执行工具调用后，观察消息列表中文字A、工具调用面板、文字B 分别位于独立气泡
