# M14 fix-r4: streaming wiring — progress

## 架构决策（实施期确认）

**Kernel SSE 事件格式**（gateway 消费的）：
- `{"event": "tool_start", "run_id": ..., "call_id": ..., "name": ..., "arguments": {...}}`
- `{"event": "tool_end", "run_id": ..., "call_id": ..., "name": ..., "status": ..., "duration_ms": ..., "error": ...}`
- `{"event": "assistant_message", "run_id": ..., "content": "...完整文本"}`
- `{"event": "turn_end", "run_id": ..., "usage": {"prompt_tokens": N, "completion_tokens": M}}`
- `{"event": "run_status", "run_id": ..., "status": "running"|"completed"|"failed"}`

**注意**：kernel SSE 没有逐字 delta 事件——`assistant_message` 是完整文本。
streaming delta 由 gateway 在收到 `assistant_message` 时推全文作为单个 delta 帧。

**最小改动路径**（设计 §工程约束"最小改动"）：
- gateway 新增 `node.streaming_delta` 子类型 WS 帧（不动现有 node.report）
- IM handler 新增 `node.streaming_delta` case → 调 EventBridge
- `node.report` payload 补 `usage` 字段（已有字段名，只是 handler 端没提取并放入 relay.report）

实际检查后：`_persist_report_event` 已接收 payload，但构造的事件 payload 里没有 `token_usage` 字段。`_persist_report_usage` 写入了 UsageMetric，但 `relay.report` 事件 payload 没带 `token_usage`。

