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

## R2 — gateway observer 转发 thinking 过程项

- Context: observer 现状 `if not content: return None`（main.py:3406）整段丢弃空正文回合，绝大多数「思考+调工具不输出正文」的回合 reasoning 到不了 IM。
- Decision: assistant_message 分支改为：① 提取 `reasoning`，`not content and not reasoning` 才丢；② 多气泡 roll 仅由 `content` 触发（纯思考回合不 roll、不冒空气泡）；③ `if message_id` 分支思考过程项（kind=`thinking_segment` {message_id,text,run_id}）先于正文 delta 转发，纯思考回合只发 thinking、不动 kernel_message_id（保留 roll 判定基准）；④ roll 路径 / turn_start_then_delta 路径把本回合 reasoning 随新气泡一起发；⑤ heartbeat lazy 路径仅正文驱动，纯思考跳过。gateway 不算 seq（IM 持久化边界统一赋予）。
- Rationale: 思考事件必早于本回合工具事件到达 → 转发到当前气泡即正确时序锚点；不碰 tool_call 合并路径；多气泡场景思考随产出正文的那一回合的新气泡走，归属正确。
- Evidence:
  - Tests: `TestObserverForwardsThinkingSegment` 3 例红→绿（空正文+reasoning 转发不 roll/不发 delta、空正文+无 reasoning 丢、内容+思考双发）；observer 既有测试 25 例全绿。
  - Entry: gateway 中继层，真实入口验证在 R5 真栈。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: tests/unit/personal_assistant + streaming 658 passed；ruff 通过。
  - Visual/Interaction: N/A
- Rollback: revert R2 C2。
- Commits: C1=红测, C2=feat
- Next: R3 IM 持久化 + 序列化链。

## R3 — IM 持久化 + 序列化链

- Context: IM 无承载思考的结构。需 messages 加列 + domain/repo/event_bridge/event_types/gateway_handler/REST 全链路带思考段，且 seq 统一在持久化边界赋予。
- Decision: ① domain 加 `ThinkingSegment{seq,text}` + `Message.thinking`；② db.py messages 加 `thinking_json` 列 + 迁移；③ repositories `_encode/_decode_thinking` + `append_thinking_segment`（seq=当前 tool_calls 数=插入索引）+ `_message_from_row`/两处 SELECT 带 thinking_json；④ event_bridge `on_thinking_segment` 持久化+发 `thinking.segment`；⑤ event_types `EVENT_THINKING_SEGMENT` + `thinking_segment_to_dict` + `build_thinking_segment_payload` + message_created 带 thinking；⑥ gateway_handler `kind=thinking_segment` 分发；⑦ REST `ThinkingSegmentPayload` + MessageResponse.thinking。
- Rationale: seq 在 IM（持有 tool_calls 列表、思考事件早于本回合工具事件到达）算一次，live/历史回放同读持久化值，口径一致；列加法变更，旧行 NULL→thinking=None 天然兼容（不留空壳）。
- Evidence:
  - Tests: repo 往返/默认 None、event_bridge 持久化+发事件、gateway_handler 分发、event_types 两 builder、REST 序列化 共 7 例红→绿；tests/im_service 354 passed。
  - Entry: WS thinking.segment + REST thinking 字段（真栈在 R5）。
  - Frontend State Matrix: N/A（R4）
  - Browser QA: N/A（R4/R5）
  - E2E/Regression: tests/im_service 全绿（含 schema/db_init/golden 序列化）；ruff 通过。
  - Visual/Interaction: N/A
- Rollback: revert R3 C2（列为加法，回滚保留空列无数据迁移风险）。
- Commits: C1=红测, C2=feat
- Next: R4 前端过程时间线。

<!-- 每个 roadpoint 完成后追加一段。 -->
