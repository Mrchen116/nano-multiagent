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

---

### R1-R3 — streaming 链路接通 + token_usage

- Context: streaming 链三个根因：(1) kernel_event_observer 永远 None，(2) EventBridge dead code，(3) relay.report 不带 token_usage
- Decision:
  - `GatewayHandler.__init__` 加 `event_bridge` 参数，repos 齐全时自动构造
  - 新增 `handle_message("node.streaming_delta")` → `_handle_streaming_delta`，按 kind 分发到 EventBridge 5 个方法
  - `_persist_report_event` 在 relay.report payload 里嵌入 `token_usage` 字段
  - `main.py` 新增 `_build_kernel_event_observer`：kernel SSE 事件 → `node.streaming_delta` WS 帧
  - relay_lifecycle_callback.accepted 存 `run_id → {conversation_id, message_id, agent_id}`
  - observer 按 run_id 查 context，asyncio.create_task 异步发帧
- Rationale: 最小改动路径；gateway 已有 `kernel_event_observer` 接口只差注入；EventBridge 已完整只差调用点；relay.report payload 添加字段是加法不破坏现有消费者
- Evidence:
  - Tests: `tests/unit/IM/test_streaming_chain.py` 8 个测试全通
  - IM 单元测试 18 个通过（无回归）
  - personal_assistant 单元测试 15 个通过
- Rollback: C1 commit `86592d08`
- Commits: C1=86592d08, C2=69c1ab3b, C3=TBD
- Next: R5 端到端真跑验证

---

### R4 — 前端 WS 事件解析修复

- Context: chat-stream.ts 检查 `parsed.type` 但 IM WS 帧格式为 `{op:"event", event_type:..., data:{...}}`，`type` 字段在顶层 envelope 中不存在 → 前端静默丢弃所有 streaming 事件
- Decision: 改读 `envelope.event_type`，将 `data` 字段展开合并为扁平 WsEvent；保留对直接推送帧（携带顶层 `type`）的回退处理
- Rationale: 最小改动；不改 WsEvent 类型定义，只修解包逻辑；fallback 确保向后兼容
- Evidence:
  - `npm run build`（tsc + vite）无 error，仅一个动态/静态混合导入 warning（pre-existing）
  - `npm run test`（vitest）: 52 test files，238 tests 全通
  - 后端单元测试 251 passed，无回归（5 失败均 pre-existing SOCKS proxy 环境问题）
- Rollback: revert commit `1a7bd2b2`
- Commits: C2=1a7bd2b2, C3=TBD

