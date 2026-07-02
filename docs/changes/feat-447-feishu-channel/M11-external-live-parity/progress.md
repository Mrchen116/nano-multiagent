# feat-447-M11 — Progress

## Baseline

- Context: M11 在 `unit/feat-447` 基础上实现 external live parity，涉及 Gateway reply mirror、IM live event payload、frontend reducer 和 Feishu reaction lifecycle。
- Evidence:
  - `pytest -q tests/unit/test_feishu_adapter_send.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/im_service/integration/test_messages_api.py` -> 76 passed, 1 skipped.

## R1 — IM live `message.created` payload

- Context: 外部 channel 用户消息由 Gateway 调 IM `POST /im/v1/conversations/{id}/messages` 写入，且设置 `suppress_relay=true`；此前该路径只产生 `message.sent` / `message.delivered`，打开的 shadow 会话无法用前端 canonical `message.created` 插入新气泡。
- Decision: `MessageRepository.create_message` 增加默认关闭的 `emit_created_event` 开关；messages API 在 `suppress_relay=true` 时开启它，按 `message.sent` -> `message.created` -> `message.delivered` 顺序写入 events。`message.created` payload 增加 `sender`、`sender_display_name`、`attachments`，并保留 delivery/progress events 的现有语义。
- Rationale: 外部同步写入没有浏览器 optimistic insert，因此必须由服务端发完整 live insert 事件；普通浏览器发消息和 relay-backed 写入不自动开启 `message.created`，避免改变已有提交/投递状态机。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_ws_event_types.py::test_build_message_created_payload_carries_external_insert_fields tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip` 先红，失败点为缺 `attachments` 和缺 `message.created`；实现后 `pytest -q tests/im_service/unit/test_ws_event_types.py tests/im_service/unit/test_repositories_message.py tests/im_service/integration/test_messages_api.py` -> 43 passed, 1 skipped。
  - Entry: FastAPI `POST /im/v1/conversations/external/find-or-create` + `POST /im/v1/conversations/{id}/messages` 集成测试覆盖外部 shadow API 写入，断言 DB `conversation_events` 有 canonical `message.created` payload。
  - Frontend State Matrix: default/empty/missing data 的后端 payload 已可支持；前端 reducer 行为在 R2 覆盖。
  - Browser QA: N/A，R1 是 backend live event payload；真实浏览器/live path 在 R4。
  - E2E/Regression: `tests/im_service/unit/test_ws_event_types.py::test_build_message_created_payload_carries_external_insert_fields`；`tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip`。
  - Visual/Interaction: N/A。
- Rollback: revert `0b7d974d` 后再 revert `bf89fd25` 可回到 R1 前状态。
- Commits: C1=`bf89fd25`, C2=`0b7d974d`, C3=`99718957`
- Next: R2 前端 reducer 使用 `message.created` payload 的 sender display name 并去重。

## R2 — 前端 reducer display name 与去重

- Context: R1 后后端 `message.created` live payload 已带 `sender` / `sender_display_name` / `attachments`；此前 v2 reducer 插入消息时只查本地 `sendersById`，外部 channel 用户不是 IM agent map 成员，会先显示 `null`/UUID 且附件被置空。
- Decision: 扩展 `WsEvent.message.created` 类型接收 canonical payload 字段；reducer 插入消息时优先使用 `ev.sender.display_name`，再用 `ev.sender_display_name`，最后回退 `sendersById`，并从 `ev.attachments` 写入 Message。既有按 `message_id` 去重逻辑保持不变。
- Rationale: display name 和附件属于后端 canonical event payload，前端不应靠刷新历史或 agent map 修正外部消息；保持 `message_id` 去重可兼容浏览器 optimistic insert 和 websocket echo。
- Evidence:
  - Tests: `npm run test -- chat-stream-reducer.test.ts` 先红，失败点为 `expected null to be 'Alice'`；实现后同命令 -> 23 passed。
  - Entry: Frontend reducer 单元入口覆盖 websocket `message.created` 事件插入当前 conversation state。
  - Frontend State Matrix: default/empty 覆盖从空列表插入外部用户消息；missing/nullable data 覆盖有 payload display name 时优先使用；重复事件覆盖 `message_id` 去重；loading/error/disabled/submitting/permission denied/long content/mobile/dark mode 不适用或未改。
  - Browser QA: R2 仅改纯 reducer；真实浏览器打开 shadow 会话的 live 验收在 R4 执行。
  - E2E/Regression: `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts` 新增 external `message.created` payload regression。
  - Visual/Interaction: N/A，未改 CSS/布局；渲染字段由 reducer 回归覆盖。
- Rollback: revert `9db14613` 后再 revert `f44c962c` 可回到 R2 前状态。
- Commits: C1=`f44c962c`, C2=`9db14613`, C3=`d29a3ec2`
- Next: R3 Gateway external reply mirror 与 Feishu reaction lifecycle。

## R3 — Gateway external reply mirror 与 reaction lifecycle

- Context: Feishu 入站 run 已通过 observer 在 IM shadow 中生成可见 assistant 气泡，但回飞书仍只走 `_run_turn` terminal `reply_text`，导致中间气泡没有外部回复、最终气泡可能被 observer/terminal 双路径重复，且 Feishu THINKING reaction 在第一条中间回复发送后就被删除。
- Decision: relay lifecycle accepted 阶段把外部入站的 reply channel、target chat、thread id 和 `feishu_message_id` 写入 run context；kernel event observer 在旧气泡 roll 前发送 `reply_phase=intermediate`，在 `turn_end` 发送当前气泡 `reply_phase=final`，并跳过空文本/纯 thinking/tool-only/`NO_REPLY`。`OutboundRouter` 以 `reply_dedupe_key` 做进程内去重；terminal direct send 为外部入站附同一 final dedupe key 和 `reply_phase=final`。Feishu adapter 只在 `reply_phase in {"final","terminal"}` 时删除 THINKING reaction。
- Rationale: observer 是唯一知道“每个用户可见 assistant 气泡完成边界”的位置；terminal `reply_text` 只能表达最后答案，不能覆盖中间气泡。把 phase/dedupe 放进通用 `ReplyContext.metadata` 可复用现有 channel abstraction，并让 terminal fallback 在 observer 不可用时仍能发 final 和清 reaction。
- Evidence:
  - Tests: R3 C1 红测 `pytest -q tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_kernel_event_observer_mirrors_external_visible_bubbles_on_completion tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_kernel_event_observer_does_not_mirror_im_triggered_shadow_runs tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_outbound_router_dedupes_by_reply_dedupe_key tests/unit/test_feishu_adapter_send.py::TestFeishuAdapterSend::test_send_removes_ack_reaction_only_after_final_reply` -> 4 failed（observer 参数缺失、router 未 dedupe、reaction 提前删除）；实现后同组加 lifecycle context test -> 5 passed。
  - Entry: Gateway runtime wiring `_build_kernel_event_observer(... external_reply_sender=...)` 覆盖真实 observer -> `OutboundRouter` -> Feishu adapter 出站路径；`InboundPipeline._run_turn` terminal fallback 覆盖 observer 不可用时的最终回复。
  - Frontend State Matrix: N/A，本 roadpoint 不改前端 reducer/样式；R1/R2 覆盖 live 插入，R4 覆盖真实浏览器 shadow 会话。
  - Browser QA: R3 是 Gateway/adapter 后端路径；真实浏览器/live path 在 R4。
  - E2E/Regression: `test_kernel_event_observer_mirrors_external_visible_bubbles_on_completion` 覆盖中间+最终气泡镜像和 final dedupe key；`test_kernel_event_observer_does_not_mirror_im_triggered_shadow_runs` 覆盖 IM shadow 入口不回写 Feishu；`test_outbound_router_dedupes_by_reply_dedupe_key` 覆盖 terminal 重复防护；`test_send_removes_ack_reaction_only_after_final_reply` 覆盖 THINKING reaction lifecycle。相关套件 `pytest -q tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/test_feishu_adapter_send.py tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_inbound_pipeline_sse.py tests/unit/personal_assistant/test_relay_kernel_message_id.py tests/unit/personal_assistant/test_steer_reply_relay_regression.py tests/unit/test_inbound_pipeline_streaming.py` -> 92 passed。
  - Visual/Interaction: N/A。
- Rollback: revert `0b6a0918` 后再 revert `6f13586c` 可回到 R3 前状态。
- Commits: C1=`6f13586c`, C2=`0b6a0918`, C3=<pending>
- Next: R4 真 IM/Gateway/Feishu live-critical 与全量非 e2e 门禁。

## R4 — live-critical 与全量门禁

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix:
  - Browser QA:
  - E2E/Regression:
  - Visual/Interaction:
- Rollback:
- Commits:
- Next:
