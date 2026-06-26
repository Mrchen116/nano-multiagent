# feat-439-M2 — Progress

> 设计：design.md 决策 4 + §1 架构事实 A/B。
> seq 设计：思考段 seq = 到达时所属气泡已有 tool_calls 数（= 插入索引），由 IM 持久化边界统一赋予。

## R1 — 内核事件带 reasoning_content

- Context: gateway observer 要把整轮每回合的思考作为过程项转发，但内核 message_end / assistant_message 事件现状只带 content，不带 reasoning。
- Decision: loop.py message_end payload 加 `reasoning_content=msg.reasoning_content`；realtime_stream on_message_end assistant_message payload 加 `reasoning_content=event.get("reasoning_content") or ""`。
- Rationale: msg.reasoning_content 已落在 Message 上（loop.py:402/410），只是没暴露进事件；纯 additive，CLI 消费者忽略未知字段。
- Evidence:
  - Tests: `tests/unit/test_agent_loop.py::test_message_end_observe_event_carries_reasoning_content` + `test_realtime_stream_events.py::test_message_end_assistant_message_carries_reasoning_content` 红→绿；全 tests/unit + contract 2541 passed。
  - Entry: 内核事件层，真实入口验证在 R5 真栈。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/unit + tests/contract 全绿（含 CLI contract 边界，确认忽略新字段无回归）。
  - Visual/Interaction: N/A
- Rollback: revert R1 C2（字段带默认值，回滚无影响）。
- Commits: C1=红测, C2=feat
- Next: R2 gateway observer 转发 thinking 过程项。

<!-- 每个 roadpoint 完成后追加一段。 -->
