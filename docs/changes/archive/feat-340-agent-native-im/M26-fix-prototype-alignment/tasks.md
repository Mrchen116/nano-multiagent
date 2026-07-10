# M26: fix-prototype-alignment (Round 15)

## 背景

4 个 subagent 并行完成源码级原型 vs 实现对比，加上用户亲自验收反馈，共发现约 30 处视觉/布局/交互差距。本 milestone 统一修复，目标：实现与原型 `docs/changes/feat-340-agent-native-im/attachments/prototype/project/im-{chat,settings,components,mypage,extra}-page.jsx` 逐项对齐。

## Roadmap

### R1: Chat 页面修复
- [x] **R1-1** `global.css` `.chat-sidebar` 背景从 `var(--im-surface)` 改为 `oklch(0.24 0.012 240)`（深色 sidebar），同步调整 sidebar 内文字/placeholder/filter 颜色为浅色
- [x] **R1-2** `global.css` `.chat-node-chip` 添加 pill 背景色和边框（online: `oklch(0.93 0.07 145)` bg + border，offline: `oklch(0.92 0.005 240)` bg + border）
- [x] **R1-3** `global.css` `.chat-pane-header` padding 改为 `0.7rem 1.25rem`（水平 20px 对齐原型）
- [x] **R1-4** `global.css` `.chat-bubble-content` 添加 `box-shadow: 0 1px 3px oklch(0.05 0.01 240 / 0.08)`
- [x] **R1-5** `message-pane.tsx` TokenChip 从 status row（timestamp 旁）移到 bubble content div 内部（与 content、ToolCallsPanel 同层级），且只在 `message.status === "completed"` 时渲染
- [x] **R1-6** `message-pane.tsx` textarea rows 按 `isMobile` 动态设置（mobile rows=1，desktop rows=2）
- [x] **R1-7** `message-pane.tsx` 空状态添加图标（✨/💬）
- [x] **R1-8** `global.css` `.chat-pane-composer-send` 区分 mobile/desktop 尺寸（mobile 42x42，desktop 38x38）
- [x] **R1-9** `global.css` `.chat-modal` max-width 改为 420px
- [x] **R1-10** `global.css` `.chat-modal-agent--on` 背景/边框对齐原型（`oklch(0.93 0.06 180)` bg + `oklch(0.75 0.12 180)` border）
- [x] **R1-11** `new-group-modal.tsx` 添加 mobile bottom sheet 变体（从底部滑出、圆角顶部、安全区域适配）
- [x] **R1-12** `avatar.tsx` fontSize 从 `size * 0.3` 改为 `size * 0.35`，添加 `letterSpacing: "-0.02em"`
- [x] **R1-13** `kind-badge.tsx` 添加 `letter-spacing: 0.04em` 和 `gap: 4px`
- [x] **R1-14** `tool-calls-panel.tsx` output 条件从 `!== undefined` 改为 `!= null`

### R2: Settings 页面修复
- [x] **R2-1** `agent-detail-page.tsx` header 添加 Avatar 组件（42px desktop/38px mobile，彩色背景 + online/offline 状态指示）
- [x] **R2-2** `agent-create-page.tsx` 按原型 `im-settings-page.jsx` NewAgentPanel 重写视觉：白色背景卡片、header 有取消/创建按钮、底部 action bar、字段布局与原型一致
- [x] **R2-3** `agent-create-page.tsx` Skills/Tool Allowlist 从 AllowlistSelector 改为 PillSelector（与 detail page 统一）
- [x] **R2-4** `agent-detail-page.tsx` Footer 状态文字色值对齐原型（saved=绿色 `oklch(0.45 0.15 145)`、unsaved=橙色 `oklch(0.50 0.15 60)`、no changes=灰色，saved/unsaved fontWeight 700）

### R3: Shell / 导航修复
- [x] **R3-1** `app-shell.tsx` 添加品牌 Logo 图标（彩色方块 + "nano IM"）
- [x] **R3-2** `app-shell.tsx` Chat tab 添加 unread badge
- [x] **R3-3** `user-menu.tsx` 添加 Identity Strip（大 avatar + display_name + user_id）在 popover 顶部
- [x] **R3-4** `user-menu.tsx` 对齐菜单项结构：Account（带 subtitle）、Nodes（带 subtitle）、Language toggle、Sign out；移除 New agent 快捷入口（已在 Agents 页提供）
- [x] **R3-5** `user-menu.tsx` Avatar 尺寸改为 28px，initials 取前 2 字符
- [x] **R3-6** `user-menu.tsx` 语言切换改为文字链接式（EN │ 中），去掉按钮边框和填充背景
- [x] **R3-7** `global.css` `.im-shell-bottombar` 背景改为深色 `oklch(0.19 0.012 240)`，文字色适配
- [x] **R3-8** `global.css` `.im-shell-bottomtab` active 态添加顶部 2px accent 指示线
- [x] **R3-9** `global.css` `.im-shell-unread-badge` 背景改为 accent 青色 `oklch(0.52 0.14 180)`
- [x] **R3-10** `global.css` `.im-shell-tabs a` 未选中文字色改为 `oklch(0.60 0.01 240)`
- [x] **R3-11** `me-page.tsx` Nodes row subtitle 动态显示节点统计（"X owned · Y online · Z offline"）
- [x] **R3-12** `me-page.tsx` Sign Out 行添加 `›` chevron
- [x] **R3-13** `global.css` 添加 scrollbar 样式（5px 宽，`oklch(0.30 0.01 240)` thumb）
- [x] **R3-14** `global.css` Google Fonts 加载添加 800 字重
- [x] **R3-15** `global.css` `.im-user-menu-popover` shadow 添加 ring（`0 0 0 1px oklch(0.85 0.006 240)`）

### R4: 验证
- [x] **R4-1** `npm run build` 成功，dist bundle 含所有修改
- [x] **R4-2** `npx tsc -b` 无类型错误
- [x] **R4-3** Playwright / 手动：桌面 1440x900 + 移动 375x812 双 viewport 截图自查，与原型并排对比
- [x] **R4-4** 更新 `progress.md`，附"原型对照检查表"逐项列出布局/配色/组件/交互是否与原型一致
