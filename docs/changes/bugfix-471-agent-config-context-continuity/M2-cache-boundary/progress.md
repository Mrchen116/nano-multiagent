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

- Status: DONE
- Context: actual-applied runtime 必须在 submit 前与 boundary intent 同事务持久化；外部 Feishu ingress 在 IM 暂时不可用时仍须回复，并在恢复后以相同外部事件身份补齐 Web IM shadow history。
- Decision: Gateway 使用 ACK-gated SQLite boundary outbox；确定性拒绝进入 quarantine，连接和 ACK 不确定性以 durable exponential backoff 保留。external shadow saga 先于 Kernel 持久化 canonical source fact，以 `(app_id, event.message_id)` 形成 Feishu identity；用户 anchor、Agent output 和 pending boundary 按 user → Agent → boundary 顺序恢复。离线的 terminal output 由 coordinator 仅在 typed `shadow_saga_id` 存在且 `shadow_ref` 缺失时持久化，已确认 anchor 的输出继续由 streaming observer 负责，避免双写。
- Rationale: actual-applied 与 provider-visible reply 分别是 Gateway 和外部 adapter 才能确认的事实，必须先成为本地 durable fact，不能由 IM 临时可达性或内存队列决定是否存在；typed ownership 条件确保 online observer 与 outage fallback 不会竞争同一个 output identity。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/contract/test_gateway_protocol_contract.py tests/im_service/unit/test_db_init.py tests/unit/personal_assistant/test_gateway_boundary_delivery.py tests/unit/personal_assistant/test_session_run_coordinator_admission.py` → `32 passed, 7 warnings`；nullable provenance 的 WS contract 与旧 NOT NULL boundary 表迁移均在该门禁覆盖。
  - Entry: 真 Feishu outage 旅程以临时 profile `13 → 14`、policy `ALWAYS` 和 marker `1983A314` 执行。IM outage 期间接收的用户 event 是 `om_x100b6ac22f27c8acb2e5d0ac0929808`，provider 在 IM 恢复前以 `om_x100b6ac22cf840a0b1de40d17d723f5` 回复精确文本 `R2-LIVE-1983A314`。详见脱敏摘要 `evidence/r2-live-feishu-outage.json`。
  - Recovery: saga `d5d938a3c723375ca42178075302d5a240ec629fa9442c373dc1fae651e82e77` 在 outage 中无 IM anchor；其 `run_671b881f5725c2f3` final output 在 provider 可见前已 durable。IM 恢复后补写 user anchor `f2c907c20b35497c82d9d69c2db1837c` 和 Agent mirror `af5b32e442cd4aadb20bd1662cc69001`，conversation 为 `5a78be2c00db4eeaa5edee07ec1dd7fb`。该 saga 的 nullable-provenance boundary `4aee39f3-…`（event `11574`）在修复后首轮 Gateway/IM restart 获 ACK，`profile_version=null`，outbox 与 pending shadow 均为 `0`，anchor 下 IM boundary 唯一 `1` 行；第二次 Gateway restart 后仍为 outbox `0`、pending shadow `0` 与唯一 `1` 行。
  - E2E/Regression: `test_gateway_boundary_accepts_nullable_provenance_once_after_im_restart` 经真实 Gateway WebSocket 和 IM restart 断言可空 provenance ACK 与唯一 divider；`test_initialize_schema_migrates_boundary_profile_provenance_to_nullable` 保留旧行迁移。真实 Feishu provider/shadow 与 restart 取证见 `evidence/r2-live-feishu-outage.json`；worktree reconnect 与 controlled typed shadow 取证见 `evidence/r2-gateway-live.json`。
  - Frontend State Matrix: N/A，R3 负责。
  - Browser QA: N/A，R3 负责。
  - Visual/Interaction: N/A，R3 负责。
  - Prototype Comparison: N/A，R3 负责。
- Rollback: `cc59baf94`（R2 原实现）；nullable provenance 修复可回退 `2c9beba98`。
- Commits: C1=`a0d728331`、`44f254e4d`、`8017c2e4a`，C2=`94a4e5176`、`cc59baf94`、`2c9beba98`，C3=本提交。
- Next: R3 将 REST、live/reconnect 和 older-page prepend 归并为 typed timeline reducer，并以真实浏览器覆盖全部 prototype must-match 状态。

## R3 — Web IM timeline union 与真实浏览器验收

- Status: TODO
