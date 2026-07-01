# feat-447-M7 — Progress

## Context

- Skill: `change-impl-worker`
- Unit: `feat-447`
- Milestone: `feat-447-M7 external-channel-full-sync`
- Base: `origin/unit/feat-447` at `a49b10c6ea8066bb028bab4b8548ac981c3ed5c6`
- Scope: files listed in `docs/changes/feat-447-feishu-channel/design.md` M7 row.

## Startup

- Sync Gate: local `unit/feat-447` equals `origin/unit/feat-447` at `a49b10c6ea8066bb028bab4b8548ac981c3ed5c6`.
- Context read: `spec.md`, `design.md` M7 decisions and Runbook for Reviewer, `AGENTS.md`, `CLAUDE.md`, `LOGBOOK.md`, `docs/TESTING_GUIDE.md`, and existing IM/Gateway/Feishu code/test structure.
- Baseline: `pytest -m "not e2e"` started before implementation; final result will be recorded in R1/R5 evidence.

## Roadpoint Progress

### R1 — IM 影子会话与消息持久化

- Context: M7 需要 IM 侧能以外部身份幂等创建 shadow conversation，并能保存外部群成员显示名。现状 conversations/messages schema 缺外部来源字段，HTTP API 也没有 find-or-create 入口。
- Decision: 在 `conversations` 增加 `external_source` / `external_chat_id` 与联合索引；在 `messages` 增加 `sender_display_name` 行级覆盖；新增 repository/service/API 的 `external/find-or-create`，影子会话 agent 维度复用 `config_agent_id`。
- Rationale: 幂等键按 design 使用 `(external_source, external_chat_id, config_agent_id, owner_id)`，避免同一个飞书群绑定多个 agent 时混淆；`sender_display_name` 放 message 行上，避免给外部成员创建 fake IM user。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_user_conversation.py::test_external_conversation_find_or_create_is_agent_scoped_and_updates_title tests/im_service/unit/test_repositories_message.py::test_message_roundtrip_preserves_external_sender_display_name tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip` -> 5 passed; `pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_repositories_message.py tests/im_service/integration/test_messages_api.py` -> 33 passed, 1 skipped.
  - Entry: HTTP `POST /im/v1/conversations/external/find-or-create` integration test creates/reuses a shadow conversation and `POST /messages` returns row-level sender display name.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R1 regression lives in `tests/im_service/unit/test_db_init.py`, `tests/im_service/unit/test_repositories_user_conversation.py`, `tests/im_service/unit/test_repositories_message.py`, and `tests/im_service/integration/test_messages_api.py`.
  - Visual/Interaction: N/A
- Rollback: revert `e42f74a8` then `2a0d2e02`.
- Commits: C1=2a0d2e02, C2=e42f74a8, C3=TODO
- Next: R2

### R2 — IM relay metadata 回环到 Gateway

- Context: IM shadow 会话里的用户消息会经 relay.message 回到 Gateway；如果 payload 不带外部身份，Gateway 会把 IM conversation id 当 kernel session identity，跨入口上下文会断。
- Decision: RelayService 从 `conversations.external_source/external_chat_id/config_agent_id/type` 回环 `trigger_source=im`、外部身份、agent id 和 conversation type；WebRelayAdapter 保留 `message.conversation_id` 为 IM delivery id，并在 shadow group metadata 下补 `mentioned_agent_ids=[agent_id]`。
- Rationale: delivery/shadow conversation identity 与 external session identity 必须分离；shadow group 的 agent 是会话主角，用户不应手动 @，因此 Gateway 入站前就要有等效 mention。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_relay_service_payload.py::test_external_shadow_relay_payload_loops_back_external_identity tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_preserves_shadow_identity_and_group_target_agent` -> 2 passed; `pytest -q tests/im_service/unit/test_relay_service_payload.py tests/im_service/unit/test_relay_service_mention_routing.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py` -> 16 passed.
  - Entry: Relay payload now carries shadow metadata expected by Gateway; WebRelayAdapter converts it into `InboundMessage(channel_name=web_relay, external_chat_id=<im conversation id>, metadata.external_chat_id=<feishu chat id>)`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Regression coverage in `tests/im_service/unit/test_relay_service_payload.py` and `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`.
  - Visual/Interaction: N/A
- Rollback: revert `4d3b84bb` then `0934e99a`.
- Commits: C1=0934e99a, C2=4d3b84bb, C3=TODO
- Next: R3

### R3 — Gateway 外部 session identity、sync_only 与 group buffer

- Context: R1/R2 已让 IM shadow 会话和 relay metadata 可用；R3 需要让 Gateway 不再把 `web_relay` 的 IM conversation id 当 kernel/session/buffer 身份，并让飞书群聊未 @ 消息进入统一的 sync+buffer 短路路径。用户巡检要求确认 `feishu_client.py` 的改动仅为真实 Feishu SDK event 提供 `sender_display_name` 输入。
- Decision: `build_session_key` 与 Pipeline group buffer key 优先使用 `metadata.external_source + metadata.external_chat_id + agent_id`，普通 channel 保持旧 key；FeishuAdapter 对未 @ 群消息发出 `metadata.sync_only=true` 的 `InboundMessage`，不再本地 append/drain `GroupContextStore`；Pipeline 对 `sync_only` 只写 group buffer 后返回 `None`，不创建 kernel session/run；Feishu config 必填 `ownerOpenId` 并传入 adapter，owner 消息显示名映射为「你」；`FeishuClient` 只新增从真实 SDK sender 上提取 display name 的字段，供 IM shadow sender display 使用。
- Rationale: session/buffer identity 和 delivery identity 必须分离，才能让飞书入口和 IM shadow 入口复用同一 kernel session 且共享未 @ 背景；adapter 若继续本地 buffer 会和 Pipeline sync_only 重复写入/重复 drain。`sender_display_name` 必须从真实飞书 event 进入 adapter metadata，否则外部群成员消息无法在 IM 历史中显示原发送者名，owner 也无法稳定渲染为「你」。
- Evidence:
  - Tests: Baseline before R3: `pytest -m "not e2e"` -> 3212 passed, 1 skipped, 22 deselected. R3 red: `pytest -q tests/unit/personal_assistant/test_gateway_channel_and_session.py::test_build_session_key_prefers_external_identity_metadata tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py::test_sync_only_group_message_buffers_without_creating_run tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py::test_external_group_buffer_key_is_shared_across_feishu_and_shadow_im tests/unit/test_feishu_adapter.py::TestFeishuAdapterGroupMention::test_group_no_mention_delivers_sync_only_inbound tests/unit/test_feishu_adapter.py::TestFeishuAdapterGroupMention::test_owner_open_id_maps_sender_display_name_to_you tests/unit/test_feishu_config.py::TestParseFeishuChannels::test_missing_owner_open_id_raises` -> 6 failed for expected missing external identity/sync_only/ownerOpenId behavior. R3 green: same command -> 6 passed. R3 related suite: `pytest -q tests/unit/personal_assistant/test_gateway_channel_and_session.py tests/unit/personal_assistant/test_gateway_pipeline_channel.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_adapter_send.py tests/unit/test_feishu_client.py tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py` -> 90 passed.
  - Entry: Unit-level Gateway entry tests prove IM shadow relay and Feishu native inbound now produce the same external session key; Feishu non-mention group messages enter Pipeline as `sync_only`, adapter `GroupContextStore.append/drain` is not called, and Pipeline stores the message under `feishu:<external_chat_id>:<agent_id>` before short-circuiting.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Regression coverage in `tests/unit/personal_assistant/test_gateway_channel_and_session.py`, `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py`, `tests/unit/test_feishu_adapter.py`, `tests/unit/test_feishu_config.py`, and `tests/unit/test_feishu_integration.py`.
  - Visual/Interaction: N/A
- Rollback: revert `f5aacf0f` then `905e14ca`.
- Commits: C1=905e14ca, C2=f5aacf0f, C3=TODO
- Next: R4

### R4 — Shadow conversation 同步、run context 与出站路由

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R5

### R5 — 非 e2e 门禁与真实飞书端到端验收

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: milestone DONE after live evidence is complete.
