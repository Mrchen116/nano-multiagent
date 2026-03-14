# M172 - 修复 canonical 直聊消息已送达但 agent 不回复

## Summary
- 定位到 canonical direct-chat no-reply 的具体断点不在 relay task 入队或 receipt，而在 gateway 侧 `web_relay_adapter` 丢失了原始 `message_id`。
- `message_id` 丢失后，gateway lifecycle callback 的 running/completed `node.report` 分支被短路，IM 无法拿到驱动直聊回复闭环所需的完整关联键，导致消息表面 accepted/completed，但绑定 agent 不回消息。
- 修复后，adapter 会从 relay payload 顶层 `message_id` 或 `message.id` 回填到 `InboundMessage.metadata["message_id"]`，保证后续 report/receipt 均能关联原消息。

## Evidence
- 代码断点：`/Users/czj/Repos/nano-multiagent/.worktrees/M172/src/personal_assistant/main.py` 中 `_build_relay_lifecycle_callback()` 的 running/completed 分支都要求 `message_id` 存在，否则直接 `return`。
- 修复点：`/Users/czj/Repos/nano-multiagent/.worktrees/M172/src/personal_assistant/channels/web_relay_adapter.py` 现在在接收 `relay.message` 时把原消息 id 写入 inbound metadata。
- 回归覆盖：
  - `tests/unit/personal_assistant/test_m102_gateway_im_connection.py` 新增断言，证明 adapter 和 IM websocket downstream frame 都会保留 `message_id`。
  - `tests/unit/personal_assistant/test_gateway_pipeline.py` 新增 focused lifecycle test，证明 `message_id` 存在时 accepted/running/completed 三段回调都能带上同一个消息 id。

## Tests
- `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/unit/personal_assistant/test_m102_gateway_im_connection.py` -> 6 passed
- `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/unit/personal_assistant/test_gateway_pipeline.py` -> 13 passed
- `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/acceptance/test_im_gateway_real_acceptance.py` -> 2 passed
- `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/unit/personal_assistant/test_m102_gateway_im_connection.py /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/unit/personal_assistant/test_gateway_pipeline.py /Users/czj/Repos/nano-multiagent/.worktrees/M172/tests/acceptance/test_im_gateway_real_acceptance.py` -> 21 passed

## Fresh canonical runtime verification
- 通过 `PYTHONPATH="/Users/czj/Repos/nano-multiagent/.worktrees/M172/src:/Users/czj/Repos/nano-multiagent/.worktrees/M172" python - <<'PY' ... GatewayAcceptanceHarness.run_roundtrip() ... PY` 在全新临时目录跑了一次 canonical acceptance harness。
- 实际输出证据：
  - `reply_text= assistant:hello from web im`
  - `adapter_outbound= ['assistant:hello from web im']`
  - `relay_status= {'status': 'completed', 'receipt_status': 'completed', 'receipt_detail': 'assistant:hello from web im'}`
  - `event_names= ['message.sent', 'relay.accepted', 'relay.processing', 'relay.completed', 'message.delivered']`
  - `reports=[{'node_id': 'node-1', 'run_id': 'run-1', 'conversation_id': '<fresh-conversation-id>', 'message_id': '<fresh-message-id>', 'summary': 'assistant:hello from web im', 'status': 'running'}]`
- 该验证直接证明 fresh canonical runtime 下：直聊消息进入 relay 后，绑定 agent 产生真实 reply，`relay_tasks` 终态为 completed，`conversation_events` 包含 accepted/processing/completed/delivered 闭环事件。

## Commit
- `61fa30e` `fix(M172): preserve direct-chat message ids through relay pipeline`

## Merge readiness
- Ready to merge.
- Exit criteria 1/2/3/4/5 已满足：修复不依赖启动后手工 patch，直聊回复恢复，`relay_tasks` / `conversation_events` 有完成证据，M149 可在该基础上继续验证旧/新 prompt snapshot 行为。
