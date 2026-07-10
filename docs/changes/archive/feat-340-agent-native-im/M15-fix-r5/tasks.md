# M15 fix-r5: streaming agent placeholder timing — tasks

## 背景

R5 验收（2026-05-12）发现 M14 streaming 链路已接通，但有两个 blocking 设计缺陷：

**R5-1**：`message.created` 从不触发。
根因：kernel `run_status=running` 在 SSE 客户端连接前就已发出；
`kernel_event_observer` 注册在 SSE 流打开之后，永远捕获不到 `turn_start` 信号；
`EventBridge.on_turn_start` 从未被调用，agent 占位消息从未创建。

**R5-2**：`message.delta`/`message.completed` 的 message_id 指向用户原消息，而非 agent 占位消息。
根因：`run_context_store` 存储的是用户消息的 message_id（由 InboundPipeline 接收用户消息时写入）；
R5-1 导致 agent 占位从未创建，EventBridge 只能用错误 message_id 追加内容，
streaming 增量写入用户发出的那条消息。

## 目标

修复 streaming 会话的 agent 占位消息创建时序，使 `message.created` 正确触发，
streaming 事件打到 agent 的回复消息而非用户发出的消息。

## 退出标准

1. WS 捕获出现 `message.created`（agent 占位消息，sender 为 agent）
2. `message.delta` 的 message_id 与 `message.created` 的 message_id 一致（agent 消息 id）
3. `message.completed` 含 token_usage，message_id 正确
4. 用户发出的消息内容不被 streaming 内容污染
5. 单元测试全绿，pytest 无新增失败

## 修复方向

Gateway `InboundPipeline` 在将消息转发给 kernel 之后、启动 SSE 监听之前：
1. 通过 IM REST API（`POST /im/v1/conversations/{id}/messages`）预创建一条 agent 占位消息
   （`sender_type=agent`，`content=""`，`status=pending`）
2. 将返回的 agent message_id 存入 `run_context_store[run_id]["message_id"]`，覆盖原来的用户 message_id
3. `kernel_event_observer` 的 `turn_start` 处理改为：从 `run_context_store` 取预创建的 message_id，
   调用 `EventBridge.on_turn_start` 时传入已有 message_id（不再新建）
4. 或者：简化方案——去掉 `on_turn_start` 的消息创建逻辑，统一由 Gateway 预创建占位消息

## 测试策略

- 单元测试：`tests/unit/test_inbound_pipeline_streaming.py` — 补 turn_start 时序断言
- 单元测试：`tests/unit/IM/test_streaming_chain.py` — 补 message.created event 断言
- 手动 e2e：`/tmp/ws_r5_v2.py` 抓帧，验证 message.created 出现且 message_id 与 delta 一致

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | Gateway 预创建 agent 占位消息 + run_context_store 注入正确 message_id | DONE |
| R2 | kernel_event_observer turn_start 改用预创建 message_id | DONE |
| R3 | 单元测试补全 + e2e 验证 message.created 帧 | DONE |
