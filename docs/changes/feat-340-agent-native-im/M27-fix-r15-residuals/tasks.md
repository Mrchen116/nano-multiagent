# M27: fix-r15-residuals (Round 15-bis)

## 背景

Round 15 reviewer 给出 `pass-with-issues`（4 minor issues），同时源码对比 agent 复核发现 15 项差距（5 major + 10 minor）。本 milestone 打包修复剩余差距，目标：将 viewport 评级从"近"提升到"精"，完成后直接提 PR。

## Roadmap

### R1: Chat 页面修复
- [x] **R1-1** `conversation-sidebar.tsx` sidebar 行添加最后消息时间戳（原型 `im-chat-page.jsx` ConvItem 右侧 `formatDate(conv.last_at)`）
- [x] **R1-2** `conversation-sidebar.tsx` sidebar 行添加 online/offline status dot + unread badge（原型 ConvItem 有 status dot 和 unread 数字徽标）
- [~] **R1-3** `message-pane.tsx` + `chat-workspace-page.tsx` MessagePane header avatar 使用 agent 真实 color/initials（非 seed hash）
- [ ] **R1-4** `message-pane.tsx` agent bubble 圆角改为 `1rem 1rem 1rem 0.25rem`（与用户 bubble 区分方向）
- [ ] **R1-5** `message-pane.tsx` bubble sender name 颜色使用 agent 品牌色（非固定 muted gray）
- [ ] **R1-6** `message-pane.tsx` composer help text 仅在 `!isMobile` 时显示
- [ ] **R1-7** `chat-workspace-page.tsx` workspace empty state 添加图标（💬）
- [ ] **R1-8** `new-group-modal.tsx` agent 选择项右侧添加 status badge（online/offline）
- [ ] **R1-9** `mention-picker.tsx` + `message-pane.tsx` group chat 中 `@` 触发 picker 修复（DOM 检查无 picker 元素）

### R2: 富组件修复
- [x] **R2-1** `kind-badge.tsx` + `global.css` KindBadge 按 kind 分色：agent=teal、group=purple、network=orange（原型 Badge variant 颜色映射）
- [x] **R2-2** `avatar.tsx` + `global.css` Avatar 添加 "running" 状态颜色 `oklch(0.70 0.18 60)`
- [x] **R2-3** `global.css` TokenChip detail min-width 从 200px 改为 220px

### R3: Settings 页面修复
- [x] **R3-1** `agents-list-page.tsx` 空状态改为 light theme 卡片（white bg + dark text），与周围 light 背景协调
- [x] **R3-2** `agent-detail-page.tsx` header status chip 显示 node name（非 node status），使用 pill 样式（背景色+边框+圆角）
- [ ] **R3-3** `agent-create-page.tsx` header 添加 Avatar（size 38/42，initials 从 display_name 计算）

### R4: 全局 CSS 微调
- [x] **R4-1** `global.css` `.im-input` border-radius 从 `0.5rem` 改为 `0.625rem`（10px 对齐原型）
- [x] **R4-2** `global.css` `.im-agent-card` border-radius 从 `0.85rem` 改为 `0.75rem`（12px 对齐原型）

### R5: 验证
- [x] **R5-1** `npm run build` 成功，`npx tsc -b` 无类型错误
- [ ] **R5-2** 桌面 1440x900 + 移动 375x812 双 viewport 截图自查
- [ ] **R5-3** 更新 `progress.md`，附"原型对照检查表"逐项列出修复项
