# M16-fix-streaming: tasks

## 目标

真修 R6 reviewer 发现的 3 个 blocking：
- R6-1: 前端 WS 仍用 `?user_id=` 被 403，改为 `?token=<jwt>`
- R6-2: `message.created` 事件缺失（M15 pre-create 路径没触发 EventBridge WS 广播）
- R6-3: `message.completed` content 把用户消息与 agent delta 拼接（agent_user_id 不是 IM UUID，REST 失败，fallback 到用户 message_id）

## 退出标准

- 浏览器 console 无 403 WS 错误
- 向 agent 发消息后立即出现占位 bubble（`message.created` 触发）
- bubble 内文字逐字渐显（`message.delta` 正确 message_id）
- 完成后 Token Chip 显示数字
- 刷新后 user/agent 消息各自独立，无文本拼接

## 测试策略

- 前端单测（vitest）：覆盖 `resolveUserStreamWsUrl` 用 token 参数
- 后端单测（pytest）：覆盖 turn_start 路径触发 EventBridge + ack 返回 message_id；`run_context_store` 收到 message_id 后 delta/completed 用正确 message_id
- 端到端：截图 + WS 帧抓取

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | 前端 WS 改用 token 参数 | DONE |
| R2 | 恢复 turn_start 帧 + gateway ack 返回 agent message_id | TODO |
| R3 | 端到端验证截图 | TODO |
