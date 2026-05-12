# M16-fix-streaming: progress

### R1 — 前端 WS 改用 token 参数

- Context: R6 reviewer 抓到浏览器 console `WebSocket connection to '...?user_id=...' failed: 403`，连续出现，退避增大。`im-chat-api.ts:resolveUserStreamWsUrl` 用 `?user_id=` 连接，后端自 M12 删除了 legacy fallback，只接受 `?token=`。
- Decision: 改 `resolveUserStreamWsUrl(token)` 接受 JWT，`connectSharedUserStream`/`scheduleUserStreamReconnect` 同步加 token 参数，`attachUserConversationStream` 接口增加 `token` 字段，`streamConversationEvents` 同步增加 `token` 字段。调用方（nodes-page, agent-status-ws-consumer, use-global-message-toast）从 auth store 读 `accessToken` 传入。
- Rationale: 与 v2/chat-stream.ts 的正确实现对齐（已用 `?token=`）。
- Evidence:
  - Tests: vitest 239 passed (新增 `user stream websocket — R6-1 token auth` 测试，及更新旧测试 `opens user stream WebSocket with ?token=`)
  - Entry: 覆盖所有 WS 连接入口（chat 侧边栏 / nodes 页 / agent 状态消费 / 通知 toast）
- Rollback: `git revert 77e3dcf7`
- Commits: C1=f67e36c2, C2=77e3dcf7, C3=（本次）
- Next: ✓ R2 DONE

### R2 — 恢复 turn_start 帧 + gateway ack 返回 agent message_id

- Context: M15 错误路径：REST pre-create 用了 `sender_user_id="alpha"`（agent 名，非 IM UUID），导致 IM validate 失败；fallback 写了 user message_id；observer 对 `run_status=running` 改成 `pass`，turn_start 帧从未发出，`EventBridge.on_turn_start()` 从未被调用，`message.created` WS 事件永不触发；后续 delta/completed 全用错误的 user message_id。
- Decision:
  1. 删除 `_create_agent_placeholder_message` 及所有 REST 预创建代码
  2. accepted phase 仅在 `run_context_store` 写 `message_id=""` 占位
  3. observer `run_status=running` 恢复发送 `kind=turn_start` 帧，用 `send_json_await_ack` 等待 gateway ack
  4. `gateway_handler._handle_streaming_delta(turn_start)` ack payload 增加 `message_id` 字段（从 `EventBridge.on_turn_start()` 返回的 Message.id 取得）
  5. observer 收到 ack 后将 `run_context_store[run_id]["message_id"]` 更新为 gateway 分配的 UUID
- Rationale: 让 IM gateway 侧创建消息（gateway 已持有 DB 连接，能正确 lookup agent_user_id），PA 只收通知；避免 PA 直接做 REST 创建时 agent_user_id 转换问题。
- Evidence:
  - Tests: pytest 15 passed (`tests/unit/IM/test_streaming_chain.py tests/unit/test_inbound_pipeline_streaming.py`)
  - `TestTurnStartAckReturnsMessageId.test_turn_start_ack_includes_message_id_from_event_bridge` 验证 ack 含 message_id
  - `TestObserverSendsTurnStartAndUpdatesStore` 3 tests 验证 run_context_store 被正确更新
  - `TestAcceptedPhaseSeedsRunContext` 2 tests 验证 accepted phase 只写空 message_id
- Rollback: `git revert 0a16199f`
- Commits: C1=（test RED 已在上一轮提交）, C2=0a16199f, C3=（本次）
- Next: ✓ R3 DONE

### R3 — 端到端验证

- Context: E2E 测试发现 `message.created/delta/completed` 三个事件全部缺失，原因是内核 SSE 流不发 `run_status=running`（直接 `assistant_message` → `turn_end` → `run_status=completed`），导致 observer 的 `turn_start` 触发条件永不满足，`message_id` 始终为空，delta 被 `if content and message_id:` 静默丢弃。
- Additional fix: 在 observer `assistant_message` 分支加入 fallback：当 `message_id` 为空时返回可等待 coroutine，先 `send_json_await_ack(turn_start)` 获取 message_id，再发 `message_delta`（`_turn_start_then_delta`）。新增 2 个单测覆盖该路径。
- E2E evidence (2026-05-12 14:22):
  - WS connects with `?token=` (no 403) ✓
  - `message.sent` (user) → `relay.accepted` → `message.sent` (agent placeholder) → `message.created` → `message.delta` (delta_text="4") → `message.completed` (content="4") ✓
  - All 3 target events received for conv `76a545d34f444e6fb034844031496625` ✓
  - Unit tests: 17 passed
- Rollback: `git revert 7e808f89`
- Commits: C2=7e808f89, C3=（本次）
