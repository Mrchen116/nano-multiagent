# R1 canonical Chat browser report

- 日期：2026-07-13
- 真栈：worktree `scripts/e2e-up.sh`，IM `http://127.0.0.1:51602`，Gateway auto-bind；服务由隔离 tmux 会话持有。
- 用户入口：以 `nano` 登录后进入 `/chat`，页面从 canonical `features/chat/chat-workspace-page.tsx` 路由加载。
- Desktop（1440×900）：Chat 导航、Messages sidebar、搜索/tab/Group/Generate skill 入口与空会话状态正常；证据 `r1-canonical-chat-desktop.png`。
- Mobile（390×844）：Messages 列表与底部 Chat/Agents/Me 导航正常，无旧页面或版本路由；证据 `r1-canonical-chat-mobile.png`。
- Console：0 errors，0 warnings。
- Network：登录 200；nodes/conversations/agents 请求均 200；未观察 failed request。
- 结论：机械路径提升没有破坏桌面/移动 canonical Chat 入口；完整消息/绑定/恢复旅程在 R2/R3 继续验收。
