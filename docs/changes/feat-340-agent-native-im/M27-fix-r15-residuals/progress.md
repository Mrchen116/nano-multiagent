# M27: fix-r15-residuals — Progress

## Roadpoints

### R1 — Chat page fixes
- Status: DONE
- R1-1: sidebar 时间戳已存在（ConvItem 右侧 formatDate）
- R1-2: sidebar status dot + unread badge 已存在
- R1-3: MessagePane header Avatar 使用 headerAgentContext 的 agentColor/agentInitials（chat-workspace-page.tsx:260-261）
- R1-4: agent bubble border-radius 为 `1rem 1rem 1rem 0.25rem`（global.css:1419）
- R1-5: bubble sender name 使用 senderColor（message-pane.tsx:272）
- R1-6: composer help text 仅在 `!isMobile` 渲染（message-pane.tsx:237-241）
- R1-7: workspace empty state 添加 💬 图标（chat-workspace-page.tsx:276）
- R1-8: new-group-modal agent 项右侧 online/offline pill badge（new-group-modal.tsx:106-119）
- R1-9: mention picker right:48px 避免 send 按钮遮挡（global.css:1547）+ Escape 关闭（message-pane.tsx:103-107）

### R2 — Rich component fixes
- Status: DONE
- R2-1: KindBadge 分色已存在
- R2-2: Avatar running 状态色已存在
- R2-3: TokenChip min-width 220px 已存在

### R3 — Settings page fixes
- Status: DONE
- R3-1: agents-list 空状态 light theme 已存在
- R3-2: detail header status chip 显示 node name 已存在
- R3-3: create page header Avatar 已添加（agent-create-page.tsx:215-218，size 38/42）

### R4 — Global CSS tweaks
- Status: DONE
- R4-1: .im-input border-radius 0.625rem 已存在
- R4-2: .im-agent-card border-radius 0.75rem 已存在

### R5 — Verification
- Status: DONE
- R5-1: `npm run build` 成功，`npx tsc -b` 无类型错误
- R5-2: 双 viewport 截图自查完成（桌面 1440x900 + 移动 375x812）
- R5-3: progress.md 已更新
