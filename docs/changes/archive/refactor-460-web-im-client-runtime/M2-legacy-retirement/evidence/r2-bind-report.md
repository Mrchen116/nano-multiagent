# R2 bind convergence browser report

- 日期：2026-07-13
- 真栈：worktree `scripts/e2e-up.sh`，IM `http://127.0.0.1:51602`，Gateway `wt-refactor-460-M2-37675`；服务由隔离 tmux 会话持有。
- 前置热缓存：在同一 SPA document 中真实打开 Agents、Nodes、Account、Chat，确保 `agents`、`nodes`、`me`、`nodes/agents`、`nodes/detail`、`conversations` 均已有 observer/cache，再进入外部 `/bind/confirm` 路由。
- 绑定：用户只点击一次 Continue；网络中 `POST /im/v1/bind` 仅出现一次并返回 201。紧随其后的 `/im/v1/me` 与六组 owner-derived refetch 全部返回 200，完成后页面才导航到 Chat。
- Session：access/refresh token 未变化；同用户 auth snapshot 立即出现 `default_entry_node_id=wt-refactor-460-M2-37675` 与一个 owned node。报告不持久化 token 值。
- Agents：导航到 Agents 后无需刷新即显示 default-agent、plato、hume、luban，均 online；用户菜单同时显示 `1 owned · 1 online`。证据 `r2-bind-agents-immediate.png`。
- Account：无需刷新即选择新 node 为 Default entry node，gateway card 为 online、4 agents，Owned nodes 为 1。证据 `r2-bind-account-immediate.png`。
- Nodes：无需刷新即显示 Total nodes=1、Online=1、Total agents=4，并展示同一 live node。证据 `r2-bind-nodes-immediate.png`。
- Retry contract：Vitest 将 `/me` 首次 reconciliation 故障后重试，断言 bind POST 仍为一次，且六组 refetch 未全部 settled 前没有导航。
- Console：0 errors，0 warnings；未观察 failed request。
- 结论：一次性 bind 与可重试 reconciliation 已分离，session 与所有 owner-derived hot cache 在导航前形成一致快照。
