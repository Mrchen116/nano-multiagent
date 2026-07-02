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

- Context: R1/R2/R3 已让 IM shadow conversation schema、relay metadata、external session key 和 Feishu `sync_only` 入站可用；R4 需要把外部 channel 入站用户消息实际写入 IM shadow，并把 shadow conversation id 交给 accepted lifecycle seed `run_context_store`。关键约束是同步失败不能阻塞飞书回复，也不能让 observer 通过 `to_user_id=owner` 懒创建普通 direct chat；IM shadow 入口触发的 run 必须只写回 IM，不回写飞书。
- Decision: 在 `InboundPipeline` 增加 `ShadowConversationSync` 端口，外部 channel 入站（metadata 有 `external_source/external_chat_id` 且 `trigger_source != im`）在 mention/buffer 短路前 best-effort 调用 shadow sync；成功后把 `shadow_conversation_id` 放入当前 `InboundMessage.metadata`，失败则记录 warning 并继续原外部 channel 回复路径。`main.py` 新增 `_IMShadowConversationSyncClient`，使用 IM HTTP `external/find-or-create` + `POST /messages` 写用户消息，并在 `build_runtime` 中注入 Pipeline。`_build_relay_lifecycle_callback` accepted 阶段优先使用 `shadow_conversation_id` seed `run_context_store.conversation_id`；外部来源缺 shadow 时 `conversation_id=""` 且 `to_user_id=""`，禁用 lazy direct；同时记录 `trigger_source`，IM shadow relay run 使用同一 shadow conversation id。
- Rationale: Pipeline 是 Feishu/WebRelay 两个入口共同经过的唯一入站边界，放在这里能让正常回复与 `sync_only` 都共享同一 shadow 写入行为。HTTP sync client 留在 `main.py` 集成层，保持 Pipeline 只依赖小端口。run context 必须等 lifecycle accepted 拿到 `run_id` 后 seed，符合 design；shadow 不可用时不设置 `to_user_id`，才能满足“IM 离线时飞书对话不中断且暂不同步到 IM”，避免创建错误的普通 direct 会话。
- Evidence:
  - Tests: R4 red: `pytest -q tests/unit/personal_assistant/test_inbound_pipeline_session.py::test_external_inbound_syncs_user_message_and_seeds_shadow_metadata tests/unit/personal_assistant/test_inbound_pipeline_session.py::test_external_shadow_sync_failure_does_not_block_or_seed_lazy_direct tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_callback_seeds_external_shadow_run_context tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_callback_skips_lazy_direct_when_external_shadow_missing tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_callback_routes_im_shadow_run_to_shadow_conversation` -> 5 failed for missing `shadow_sync`, missing shadow seed, lazy direct still enabled, and missing `trigger_source`. R4 green: same command -> 5 passed. R4 related suite: `pytest -q tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_pipeline_channel.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_config.py` -> 81 passed.
  - Entry: Gateway Pipeline entry test proves external Feishu inbound calls the shadow sync port, writes returned `shadow_conversation_id` into message metadata before accepted lifecycle, and still routes final reply through `feishu:<agent_id>`. Failure-path entry test proves a missing/failed shadow returns a Feishu outbound reply while accepted lifecycle sees no shadow id. Lifecycle unit tests prove external runs seed `conversation_id=shadow_conversation_id`, external shadow-missing runs keep `to_user_id=""`, and IM shadow relay runs target the shadow conversation with `trigger_source=im`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Regression coverage in `tests/unit/personal_assistant/test_inbound_pipeline_session.py` and `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`; true live Feishu/IM E2E is deferred to R5 per tasks.
  - Visual/Interaction: N/A
- Rollback: revert `df613767` then `227a0074`.
- Commits: C1=227a0074, C2=df613767, C3=14b5f0f7
- Next: R5

### R5 — 非 e2e 门禁与真实飞书端到端验收

- Context: R1-R4 已完成代码与窄测；R5 只做非 e2e 门禁、worktree live runtime、真实飞书 user 入站和 IM shadow 证据收口。live config `.gateway-config-live.yaml` 是未跟踪本地文件，含 secret，不提交。
- Decision: 使用 worktree IM `http://127.0.0.1:56127` + foreground Gateway `--config .gateway-config-live.yaml --auto-bind`；从 config 读取 Feishu `settings.appId=cli_aac9315ef3f9dbda`，用 `lark-cli auth status --json --verify` 校验同 appId，取同 appId bot openId `ou_b33ae16df1338a00a77d4cdbec653b71` 作为 `lark-cli im +messages-send --as user --user-id ...` 目标。
- Rationale: R5 的 live-critical 证据必须从真实飞书入站进入 Gateway，不能用 stub/API/UI fallback。IM shadow 证据以 worktree IM SQLite 为准；飞书可见回复以 `lark-cli im +chat-messages-list --as user` 返回为准。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_pipeline_channel.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_config.py tests/im_service/unit/test_relay_service_payload.py tests/im_service/integration/test_messages_api.py` -> 104 passed, 1 skipped. `pytest -m "not e2e"` -> 3223 passed, 1 skipped, 22 deselected, 20 warnings in 134.12s.
  - Entry: Commands used with secrets hidden: `lark-cli auth status --json --verify` -> `verified=true`, `appId=cli_aac9315ef3f9dbda`, bot `openId=ou_b33ae16df1338a00a77d4cdbec653b71`, user `openId=ou_e6d1591026cfdac8d131eb1fdd71bdb9`; `lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "R5 live nonce: <nonce>" --idempotency-key <nonce>`. Passing nonce: `feat447-m7-r5-20260702093934`; send result `chat_id=oc_1906eead0189484ce5ea8a4c245400a6`, `message_id=om_x100b6b685bb610bcc2a5db880d234b8`, `create_time=2026-07-02 09:39:35`. 飞书可见 agent 回复: `message_id=om_x100b6b685b1bdc84c438291adddcf4b`, content includes `Acknowledged. R5 live nonce: feat447-m7-r5-20260702093934`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Live Feishu entry used real `lark-cli im +messages-send --as user` and real Gateway Feishu WS. Worktree IM shadow evidence in `data/feat447_m7_live.sqlite3`: conversation `903f3551ef474dc1980a95b4a1a400eb`, `title=default-agent · feishu`, `type=direct`, `external_source=feishu`, `external_chat_id=feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9`. Messages include user row `1fabb21559bf409e948c166501ec23a4`, `sender_display_name=你`, content `R5 live nonce: feat447-m7-r5-20260702093934`; agent rows `5098ce36b6ba4c80bc920c355deadba5` and `9e21f6866bec48ba814b28bb981ea61e` containing the same nonce. Related prior successful nonce `feat447-m7-r5-20260702093836` produced user row `cd5ea06d18fe4ce8acee52879d36c69d` and agent row `be72b0d6af6a458d846bbaca138fc516`.
  - Visual/Interaction: N/A
- Runtime/logs/caveat: IM ran as foreground process on port 56127 with DB `data/feat447_m7_live.sqlite3`; Gateway ran as foreground process with `.gateway-config-live.yaml`. The initial fresh live DB had no `agent:<id>` alias user rows and `.gateway-config-live.yaml` had stale `node.user_id`, causing early `external/find-or-create` 400s; R5 fixed only the untracked live config (`node.user_id` aligned to the transient IM owner) and invoked real IM `GET /im/v1/agents` to lazy-provision agent alias rows before final live evidence. Other same-app Gateway processes were present on the machine, so multiple nonces were sent; only IM shadow rows in this worktree DB were treated as passing evidence. `.gateway-config-live.yaml`, live DBs, PID files, and logs are local/untracked and intentionally not committed.
- Rollback: revert the R5 docs commit only; no R5 implementation changes.
- Commits: C1=N/A, C2=N/A, C3=381f0749
- Next: milestone DONE; merge to `unit/feat-447`.
