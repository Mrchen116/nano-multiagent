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

## Remaining
- 仍需补一条 fresh canonical runtime 最小验证，直接证明 direct-chat 真实回复、`relay_tasks` 与 `conversation_events` 完成闭环。
- 仍未生成 commit。
