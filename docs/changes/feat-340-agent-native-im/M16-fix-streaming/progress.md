# M16-fix-streaming: progress

### R1 — 前端 WS 改用 token 参数

- Context: R6 reviewer 抓到浏览器 console `WebSocket connection to '...?user_id=...' failed: 403`，连续出现，退避增大。`im-chat-api.ts:resolveUserStreamWsUrl` 用 `?user_id=` 连接，后端自 M12 删除了 legacy fallback，只接受 `?token=`。
- Decision: 改 `resolveUserStreamWsUrl(token)` 接受 JWT，`connectSharedUserStream`/`scheduleUserStreamReconnect` 同步加 token 参数，`attachUserConversationStream` 接口增加 `token` 字段，`streamConversationEvents` 同步增加 `token` 字段。调用方（nodes-page, agent-status-ws-consumer, use-global-message-toast）从 auth store 读 `accessToken` 传入。
- Rationale: 与 v2/chat-stream.ts 的正确实现对齐（已用 `?token=`）。
- Evidence:
  - Tests: vitest 239 passed (新增 `user stream websocket — R6-1 token auth` 测试，及更新旧测试 `opens user stream WebSocket with ?token=`)
  - Entry: 覆盖所有 WS 连接入口（chat 侧边栏 / nodes 页 / agent 状态消费 / 通知 toast）
- Rollback: `git revert 77e3dcf7`
- Commits: C1=f67e36c2, C2=77e3dcf7, C3=（本次）
- Next: R2 修复 message.created 缺失 + agent message_id 错误
