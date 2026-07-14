# R3 real-stack browser regression report

- 日期：2026-07-13
- 范围：canonical Agent direct chat、M1 realtime consumers、shared user-stream continuity、desktop/mobile Chat 与 session refresh；均通过真实 IM + Gateway + LLM 代理驱动，不调用内部 reducer 伪造事件。

## Agent detail 与实时 Chat

- 从 `/settings/agents/default-agent` 点击 `Open chat`，网络出现唯一 canonical `POST /im/v1/conversations` 201，导航到新建 direct conversation；证据 `r3-agent-detail-direct-chat.png`。
- Desktop 1440×900：发送 `Reply with exactly: M2 realtime OK`，真实消息 POST 201；页面实时呈现 `M2 realtime OK`、thinking 与 token usage，sidebar preview 同步更新。证据 `r3-realtime-desktop.png`。
- Mobile 390×844：在同一会话继续发送并实时收到 `MOBILE OK`，消息、过程折叠、输入框和底部导航可用。证据 `r3-realtime-mobile.png`。
- 离开当前会话后再发起一轮带真实 bash 延迟的消息，停留 Agents 页时收到 `default-agent / TOAST OK / View message` 全局应用内 toast；该状态通过 Playwright accessibility snapshot 取证。系统通知仍受浏览器 permission/hidden gate 限制，其完整 gating 由全量 notifier Vitest 覆盖。

## Continuity 与状态

- Gateway 进程停止后，Agents 页不刷新即把 default-agent/plato/hume/luban 全部切为 offline；证据 `r3-agents-offline.png`。
- 在隔离 tmux 中重启同一 Gateway 后，shared stream/recovery refetch 把四个 Agent 全部恢复 online；证据 `r3-agents-reconnected.png`。
- Playwright context 真实切到 offline 再恢复 online，network 记录 recovery 后 `/im/v1/agents` 与 `/im/v1/nodes` 均重新请求并返回 200，页面保持一致。

## 长登录 refresh

- 另起隔离真栈，用该次 `.e2e-jwt-secret` 以 HS256 签发同用户、`type=access`、已过期 60 秒的真实 JWT；保留浏览器当前仍有效 refresh token，并写回真实 `im_auth_v1` 后 reload。
- 网络观察：过期 access 的初次 nodes/conversations/agents 请求为 401；`POST /im/v1/auth/refresh` 仅一次且为 200；所有原请求 replay 后为 200。
- reload 后仍停留已登录 Chat，localStorage user id 不变、refresh token 存在，新 access token 的 `exp` 已在未来。该专项的四个 401 是刻意注入过期凭证的预期首轮响应；普通登录、绑定、单聊、实时、断线恢复旅程 console 均为 0 error / 0 warning。

## 结论

canonicalization 没有破坏 Agent 单聊入口、消息实时渲染、sidebar/toast、Node/Agent 状态或断线恢复；桌面与移动 Chat 均保持既有交互，真实过期 access + 有效 refresh 的长登录恢复闭环成立。
