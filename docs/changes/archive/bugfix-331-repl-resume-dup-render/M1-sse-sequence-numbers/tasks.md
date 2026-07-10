# M1: SSE Sequence Numbers + Per-Client High-Water Mark

## 目标

根治服务端每次 poll 都回退 `history[-max_events:]` 导致的重复事件问题。引入全局单调序列号，客户端只请求序列号之后的新事件。

## 设计原则

- `after_sequence` 为**必需参数**，服务端不再支持无高水位线的 poll
- 所有 3 个客户端同步升级，代码不携带旧行为分支
- `encode_sse_event` 的 `id:` 字段直接放 `str(sequence_num)`，原 `event_id` 仅保留在 data 内供调试

## 影响面

3 个客户端消费 `/v1/sessions/{id}/events`：

| 客户端 | 文件路径 | 当前 `id:` 解析 |
|--------|---------|----------------|
| coding_cli | `src/coding_cli/client.py` | `"event_id"` |
| gateway (PA) | `src/personal_assistant/client/kernel_api_client.py` | `"id"` |
| SDK | `src/agent/platform/sdk/client.py` | `"event_id"` |

## Roadpoints

### RP1: EventStreamHub 序列号

**文件**: `src/agent/platform/http_api/sse.py`

- `StreamEvent` 新增 `sequence_num: int`
- `EventStreamHub.__init__` 新增 `_next_sequence_num: int = 1`
- `EventStreamHub.publish` 分配并递增序列号
- `EventStreamHub.stream` 新增 `after_sequence: int` 参数，过滤 `sequence_num > after_sequence`
- `encode_sse_event` `id:` 放 `str(sequence_num)`

**验收**: EventStreamHub 单元测试验证序列号单调递增、after_sequence 过滤正确

### RP2: HTTP API 接入序列号

**文件**: `src/agent/platform/http_api/routes/session.py`, `src/agent/platform/http_api/routes/event.py`

- `stream_session_events()`: `after_sequence: int = Query(ge=0)` 必需参数
- `stream_global_events()`: 同样新增 `after_sequence` 必需参数
- 透传给 `event_hub.stream()`

**验收**: 不传 `after_sequence` 返回 HTTP 400；传值后只返回后续事件

### RP3: coding_cli 客户端升级

**文件**: `src/coding_cli/client.py`, `src/coding_cli/events/repl_events.py`

- `stream_session_events()` 新增 `after_sequence` 参数
- `_parse_sse_events` 解析 `id:` 为 `"sequence_num"` (int)
- `send_message_with_async_events` 跟踪 `last_sequence_num`，每次 poll 后更新
- `consume_async_run_events` 返回值增加 max seen sequence_num

**验收**: CLI 连续 poll 不再收到重复事件

### RP4: gateway 客户端升级

**文件**: `src/personal_assistant/client/kernel_api_client.py`, `src/personal_assistant/gateway/inbound_pipeline.py`

- `KernelApiClient.stream_session_events` 新增 `after_sequence` 参数
- `_parse_sse_events` 解析 `id:` 为 `"sequence_num"`
- `InboundPipeline._await_terminal_run` 跟踪 `last_sequence_num` 传入下一次 poll

**验收**: Gateway 事件消费无重复

### RP5: SDK 客户端升级

**文件**: `src/agent/platform/sdk/client.py`

- `stream_session_events` 新增 `after_sequence` 参数
- `_parse_sse_events` 解析 `id:` 为 `"sequence_num"`

**验收**: SDK 消费者可正常获取增量事件
