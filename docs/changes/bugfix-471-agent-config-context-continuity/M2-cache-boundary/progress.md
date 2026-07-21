# bugfix-471-M2 — Progress

## 启动记录

- 已读取 incident、design、prototype、AGENTS、LOGBOOK 与 `docs/TESTING_GUIDE.md`。
- M2 范围：Gateway durable boundary outbox / external shadow saga、IM typed timeline 与协议、Web IM typed reducer/render，以及相应回归和真实产品入口证据。
- 前端原型必须匹配：固定文案、首条采用新配置用户消息前、非消息语义，以及 reload/reconnect/older-page prepend 的稳定锚定；证据将写入 `evidence/`。
- 基线：实施前的 `PYTHONPATH=src pytest -m "not e2e"` 有一个既存的 40ms watchdog 时序 flaky（`test_quiet_run_heartbeats_prevent_idle_reap`）；精确重跑通过。R1 实现后的完整 non-e2e 树全绿。

## R1 — IM typed timeline 与配置边界协议

- Status: DONE
- Context: runtime 实际生效必须在 anchor 用户消息之前留下一条可恢复的时间线实体；它既不能伪装成 `Message`，也不能由到达时间决定顺序。
- Decision: `agent_config_boundaries` 保存 durable provenance 与稳定幂等键 `(conversation_id, before_message_id, runtime_fingerprint)`；`conversation_events` 保存不含 runtime provenance 的 `agent.config.changed` replay event。REST 使用 typed union，分页先选择 message 再插入其 anchor boundary；fork 用 source→target message id 映射复制范围内 boundary。
- Rationale: 既有 `conversation_events`、user stream 和 message cursor 已提供 owner-scoped replay/high-water 与分页基础，复用该链路避免额外的 event cursor 或把 divider 泄漏进模型消息领域。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_event_repository.py tests/im_service/unit/test_user_stream.py tests/im_service/unit/test_fork_conversation.py tests/im_service/contract/test_events_contract.py tests/im_service/contract/test_gateway_protocol_contract.py tests/im_service/integration/test_messages_api.py` → `60 passed, 1 skipped`；`PYTHONPATH=src pytest -m "not e2e"` → `3642 passed, 1 skipped, 20 deselected`。
  - Entry: `tests/im_service/contract/test_gateway_protocol_contract.py` 通过真实 IM Gateway WebSocket 注册、boundary ACK、HTTP timeline 读取，验证重复投递只落一行；`tests/im_service/contract/test_events_contract.py` 经真实 user-stream resume 验证 `agent.config.changed` 以相同 `event_id` 回放且不暴露 fingerprint/profile provenance。
  - Frontend State Matrix: N/A，R3 负责 Web IM 状态与视觉渲染。
  - Browser QA: N/A，R3 负责真实浏览器验收。
  - E2E/Regression: boundary HTTP page 不消耗 message limit、cursor 保持 message id、older page 不携带不属于该页 anchor 的 divider，以及 fork anchor remap 均有 IM regression；稳定 boundary id 的冲突重用经 Gateway wire contract 拒绝。
  - Visual/Interaction: N/A，R3 负责。
  - Prototype Comparison: N/A，R3 负责。
- Rollback: `f0a3fe6ab`。
- Commits: C1=`f0a3fe6ab`，C2=`aa80518fc`，C3=`ee9a527d7`。
- Next: R2 实现 Gateway durable outbox 与 external shadow saga。

## R2 — Gateway outbox 与外部 shadow saga

- Status: TODO

## R3 — Web IM timeline union 与真实浏览器验收

- Status: TODO
