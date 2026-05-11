# M14 fix-r4: streaming wiring — tasks

## 目标

闭合 streaming 链路：kernel SSE → gateway WS → IM EventBridge → 浏览器 WS。
让用户看到 bubble 逐字出现 + Token Chip 显示真实数字。

## 退出标准

1. WS 捕获出现 `message.created` / `message.delta`(≥1帧) / `message.completed`(含 token_usage)
2. `relay.report` 含 `token_usage.total > 0`
3. 含 tool_call 轮次出现 `tool_call.upserted` / `tool_call.completed`
4. UI bubble 字符级递增（不一次性整段）+ Token Chip 显示数字
5. 跨租户：owner B 的 WS 不收 owner A 的 streaming 帧
6. 现有 relay.* 链路不破坏，单元测试全绿，前端 npm run build 无 error

## 测试策略

- 单元测试：`tests/unit/IM/test_streaming_chain.py` — EventBridge 调用路径 + 跨租户隔离
- 单元测试：`tests/unit/test_inbound_pipeline_streaming.py` — kernel_event_observer 触发
- e2e 测试：`tests/e2e/test_streaming_chain.py`（打 `@pytest.mark.e2e`，本地真跑）
- 前端：npm run build 无 error + 浏览器手动验证

## Roadpoints

| ID | 标题 | 状态 |
|----|------|------|
| R1 | gateway 端 kernel_event_observer → node.streaming_delta 发送 | TODO |
| R2 | IM gateway_handler 处理 node.streaming_delta → EventBridge → WS 推送 | TODO |
| R3 | relay.report 补 token_usage + message.completed 双侧携带 | TODO |
| R4 | 前端验证：bubble 逐字 + Token Chip 渲染 | TODO |
| R5 | 端到端真跑验证 | TODO |
