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

- Status: DONE
- Context: REST 历史已能返回 `Message | agent_config_changed` 的 timeline union；前端不能为了兼容旧 messages-only 状态而在页面或组件各自排序，否则 live replay、分页和 reload 会让 divider 漂移或重复。
- Decision: `ConversationState.timeline` 成为唯一顺序来源，`messages` 保留为兼容性投影。REST reset、older-page prepend、live `agent.config.changed` 和 anchor message 都通过 `mergeTimelineItems()` 合流，并按稳定 item id 幂等。boundary 仅在 anchor message 已加载时渲染，固定 separator 文案在该 message 前；它不经过 `MessageBubble`，没有消息 id、头像、发送者、时间、状态或菜单。
- Reset safety: reset 仅在 `state.conversation_id === targetConversationId` 时保留既有 boundary 与 `preserveMessageIds` 的 optimistic/live message。跨会话 reset 不会把旧 boundary 带入新会话；同会话 REST 暂未返回的 optimistic/live message 保留一轮，后续历史可收敛。
- Evidence:
  - C1: `ff0f883f9` 增加 typed reducer 与 MessagePane red tests；workspace REST/live 接线的精确回归不在该 SHA。
  - C2: `dbcae2d9c` 引入 typed API/reducer/workspace/render 合流与响应式 divider；随后补充 workspace integration regression，直接覆盖 typed REST boundary、shared user stream `agent.config.changed`、跨会话 reset 不泄漏，以及已有 optimistic send 跨 in-flight REST reset 的保留回归。
  - Tests: `npm test -- --run src/features/chat/chat-stream-reducer.test.ts src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace.integration.test.tsx` → `3 passed, 168 passed`；完整 `npm test -- --run` → `68 passed, 652 passed`；`npm run build` 通过（仅既有 bundle 大小告警）；`PYTHONPATH=src pytest -m "not e2e"` → `3667 passed, 1 skipped, 20 deselected`。
  - Frontend State Matrix: typed REST 初载、live boundary 先到/anchor 后到、REST reset/reconnect replay 与 older prepend 均按 boundary id 去重；anchor 不在当前页时 boundary 被保留但不孤立渲染；旧 bare `Message[]` query cache 在 API seam 归一为 typed `message` item。
  - Browser QA: 在隔离 IM `127.0.0.1:49888` 与独立 Vite `127.0.0.1:49966` 完成真实入口验收。`r3-chat-1440.png`、`r3-chat-1280.png`、`r3-chat-375.png` 验证三 viewport；reload 后 `r3-chat-375.png` 仍显示 divider 位于 anchor 前；IM restart/reconnect 后 `r3-reconnect-375.png` 仍保持同一锚定；`r3-older-prepend-1440.png` 显示 older page 加载后 divider 仍紧邻 anchor 前；`r3-fork-1440.png` 显示 fork 成功提示和 fork 会话中的同一边界。
  - Durable response evidence: `evidence/r3-browser-timeline.json` 是隔离 IM 对话 `954046b4a7ec450bbc1251d359737d1b` 的 REST union 响应，stable boundary `r3-browser-boundary-1` 直接指向 anchor `fd6e037016e74f7988f9a50b16a86a5f`。
  - Prototype Comparison: prototype `.boundary` 的固定文案、anchor 前位置和低优先级分隔线均匹配；产品实现使用现有 design tokens，长文案在 375px 自然换行且不产生横向滚动。sidebar、消息 bubble 与 composer 未改版。
- Note: 完整 Vitest 输出仍包含既有 test mock 未提供 `/im/v1/sync` 时的 user-stream 404 日志和 React `act(...)` 警告；隔离 IM 实际定义该 endpoint（`IM/api/routes/web_im.py`），上述真实浏览器流程可完成 reload/reconnect 和历史恢复。
- Commits: C1=`ff0f883f9`，C2=`dbcae2d9c`，C3=本提交。
- Next: M2 交付完成。
