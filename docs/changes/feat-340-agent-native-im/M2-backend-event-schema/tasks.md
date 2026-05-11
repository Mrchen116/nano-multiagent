# feat-340-M2: backend-event-schema — Tasks

> 对齐: ../design.md v1

## 目标

让 IM 后端能持久化并实时广播 agent 运行期的 tool_calls 与 token_usage:
- `messages` 表新增 `tool_calls_json` / `token_usage_json` 列；domain `Message` 暴露 `ToolCall` / `TokenUsage` 嵌入类型。
- 新增 `IM.application.event_bridge` 模块,把 kernel `RuntimeEvent`(MESSAGE_UPDATE / TOOL_CALL / TOOL_RESULT) + usage payload 翻译为 ConversationEvent + 写入 messages JSON 列。
- 新增 `IM.api.ws.event_types` 模块,为前端 WS 事件 schema 提供类型常量。
- Gateway `inbound_pipeline` 通过回调把 kernel 流式 tool_start/tool_end 事件投递给 event_bridge。

## 退出标准

- [ ] `messages` 表新增两列,旧行兼容(NULL)。
- [ ] `MessageRepository.create_message` / `update_message_runtime_state`(新) / `list_messages` 能 round-trip tool_calls/token_usage。
- [ ] `IM.application.event_bridge.EventBridge` 单元测试覆盖 4 映射:`message.created` / `message.delta` / `tool_call.upserted` / `tool_call.completed` / `message.completed`(含 token_usage)。
- [ ] 集成测试:模拟 kernel SSE 流(assistant_message + tool_start + tool_end + run_status completed),Gateway 触发 bridge → DB messages 行写入 tool_calls/token_usage JSON,且 conversation_events 表里产生预期事件。
- [ ] 不破坏既有 unit 测试(54 passed)。

## 测试策略

- **单元(无 mock 真链路片段)**:`tests/im_service/unit/test_message_repo.py` 扩展—— round-trip tool_calls/token_usage 字段。
- **单元 event_bridge**:`tests/im_service/unit/test_event_bridge.py`(新)直接驱动 EventBridge 实例,断言 messages 表行 + conversation_events 表行。
- **集成(真实入口)**:`tests/im_service/integration/test_event_bridge_pipeline.py`(新)—— 用一个内存 KernelApiClient stub 产生真实 kernel SSE 帧序列,跑通 pipeline,断言 IM messages 行 tool_calls/token_usage 已落库 + WS broadcastable ConversationEvent 已产生。不用 mock event_bridge 本身。

## Roadpoints

### R1 — Domain + Persistence

- 步骤:
  - `Message` 加 `tool_calls: list[ToolCall] | None = None` + `token_usage: TokenUsage | None = None`(可空,旧 message 默认 None)。
  - 新增 `ToolCall` / `TokenUsage` dataclass。
  - `db.py` schema + 迁移函数加 `tool_calls_json TEXT` / `token_usage_json TEXT`(可空)。
  - `MessageRepository.create_message` 接受可选 tool_calls/token_usage 并持久化。
  - 新增 `MessageRepository.update_runtime_state(message_id, *, content_append=None, tool_calls=None, token_usage=None, delivery_status=None)`,供 bridge 在运行期增量更新。
  - `_message_from_row` / `_message_from_visible_event_row` 反序列化新字段。
- 验证:
  - 新增单元测试:create → list → 字段完整。
  - 旧测试无回归。

### R2 — WS event_types module

- 步骤:
  - 新增 `src/IM/api/ws/__init__.py` + `src/IM/api/ws/event_types.py`,把 design §4 中 IM→Browser 事件类型常量化。事件名称:`message.created` / `message.delta` / `message.completed` / `tool_call.upserted` / `tool_call.completed` / `node.status_changed` / `agent.status_changed`。
  - 提供 builder 函数 build_event_payload(...) 把 ToolCall/TokenUsage/Message 拼成符合前端 schema 的 dict(测试断言形态)。
- 验证:
  - 单元测试 `tests/im_service/unit/test_ws_event_types.py`: 构造 payload → 断言 keys/values。

### R3 — event_bridge.EventBridge

- 步骤:
  - 新模块 `src/IM/application/event_bridge.py`。
  - 类 `EventBridge`(依赖 MessageRepository, EventRepository, notify Callable[[ConversationEvent], None])。
  - 方法:
    - `on_turn_start(conversation_id, agent_user_id, agent_actor) -> Message`:create_message empty content,触发 `message.created` event。
    - `on_message_delta(message_id, delta_text)`:append 内容 + 触发 `message.delta` event(payload 带 delta_text)。
    - `on_tool_call_upserted(message_id, tool_call)`:upsert JSON 数组 + `tool_call.upserted` event。
    - `on_tool_call_completed(message_id, tool_call_id, output, duration_ms, status)`:update 对应项 + `tool_call.completed` event。
    - `on_message_completed(message_id, *, final_content=None, token_usage=None)`:更新 delivery_status=completed + token_usage_json + `message.completed` event。
- 验证:
  - 单元测试 `tests/im_service/unit/test_event_bridge.py`:每个方法都断言 DB 状态 + notify 收到了正确 event。

### R4 — Gateway integration

- 步骤:
  - 新增可选回调签名 `KernelEventBridgeCallback`,在 `InboundPipeline._consume_kernel_stream`(或等价处)逐事件传递 `tool_start`/`tool_end`/`assistant_message`(增量)/`run_status` 给回调。
  - `KernelEventBridgeCallback` 默认 None,启用时由 personal_assistant 注入(bootstrap 接 EventBridge);不破坏既有用例。
  - 单测 stub 验证回调被以预期顺序调用。
- 验证:
  - 集成测试 `tests/im_service/integration/test_event_bridge_pipeline.py`:跑通真实 KernelApiClient stub → InboundPipeline → EventBridge → DB messages 行 tool_calls/token_usage 已落库。

### R5(可选) — 文档/Changelog

- 在 design.md Changelog 加一行,progress.md 总结。
