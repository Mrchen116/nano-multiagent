# feat-447-M12 — Progress

## Startup

- Context: M12 starts from `origin/unit/feat-447` after M10/M11 are merged. Scope is restricted to Feishu mention parsing, external group context parity, config/channel diagnostic warnings, and focused tests.
- Decision: Split into R1 mention parsing/metadata, R2 external group buffer/drain, R3 diagnostic warning plus live/non-e2e verification.
- Rationale: These roadpoints map directly to the three failure modes in design.md: deleted mention content, disconnected group buffer identity, and platform configs that only deliver @Bot events.
- Evidence:
  - Baseline: `pytest -m "not e2e"` -> 3250 passed, 1 skipped, 22 deselected, 20 warnings in 155.21s.
  - Read context: `spec.md`, `design.md`, `AGENTS.md`, `LOGBOOK.md`, `docs/TESTING_GUIDE.md`, current Feishu/Pipeline code and tests.

## R1 — Mention 正文保真与结构化 metadata

- Context: Feishu 原始 text 用 `@_user_N` placeholder 表示 mention。旧实现把 placeholder 从正文删除，导致 `@bot hi` 只剩 `hi`，纯 `@bot` 变成空串，`@所有人` 也丢失用户可见内容。
- Decision: `FeishuClient` 将 placeholder 规范化为用户可见 `@DisplayName`/`@所有人`，并在 `FeishuMessageEvent` 上保留 `raw_text` 与 `mention_only`；`FeishuAdapter` 透传 `raw_text`/`mention_only`，并继续只用结构化 `mentions.open_id == botOpenId` 写入 `mentioned_agent_ids`。
- Rationale: mention 是用户消息正文的一部分，IM 展示、GroupContextStore 和 LLM current message 必须使用同一份可见文本；触发判断则使用结构化 metadata，避免 `@所有人` 或其他人的 @ 被当成 Bot 触发。
- Evidence:
  - Tests: `pytest -q tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py` -> 37 passed in 2.28s.
  - Entry: Unit-level Feishu event parse/adapter delivery boundary; R3 记录真实 Feishu live-critical 入口。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Regression tests in `tests/unit/test_feishu_client.py` cover `@bot hi` not deleting @, mention-only non-empty text, and `@所有人` visible text; `tests/unit/test_feishu_adapter.py` covers `mention_only` and `mentioned_agent_ids` metadata.
  - Visual/Interaction: N/A
- Rollback: Revert C2 `16ea5540` and C1 `87704611` if mention preservation must be removed.
- Commits: C1=87704611, C2=16ea5540, C3=59ac2b70
- Next: R2

## R2 — External group buffer key 与纯 @ drain

- Context: M7 已实现 external `GroupContextStore` key，但 M12 需要明确覆盖未 @ Feishu 背景消息可被后续纯 @Bot drain，且 `@所有人` 只作为普通群上下文进入 buffer。
- Decision: 在现有 pipeline group-context 测试中补 verify/regression：`sync_only` Feishu 背景消息写入 `feishu:<chat>:agent` key；后续纯 `@plato` 使用同一 key drain，并把当前 mention-only message 作为非空 current part；`@所有人` 消息不触发 run，只缓存为普通上下文。
- Rationale: 行为 owner 是 `InboundPipeline` + `GroupContextStore`，不是 FeishuAdapter 私有 buffer；扩展现有 pipeline 测试比新建 milestone 测试文件更符合 TESTING_GUIDE。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py` -> 14 passed in 0.22s.
  - Entry: Unit-level Gateway pipeline boundary; R3 记录真实 Feishu live-critical 入口。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py::test_feishu_background_is_drained_by_pure_bot_mention` and `::test_feishu_at_all_message_is_buffered_without_triggering_bot`.
  - Visual/Interaction: N/A
- Rollback: Revert C1 `528accd1` to remove the verify/regression coverage. No R2 production-code commit was required because existing external-key implementation satisfied this roadpoint after R1 preserved non-empty mention text.
- Commits: C1=528accd1, C2=N/A verify-only, C3=1cb868c9
- Next: R3

## R3 — 普通群消息投递能力 warning/health 诊断与收尾验收

- Context: M12 live-critical requires ordinary Feishu group messages to enter Gateway/IM/GroupContextStore before a later pure `@Bot` drains them. In the real app `cli_aac9315ef3f9dbda`, Feishu chat history contains ordinary group messages, but the bot event connection only receives mention-class events (`@all`, `@nano`, `@nano hi`). Bot identity also cannot pull the group history in the current app, so both event delivery and history compensation are blocked by app permission/scope.
- Decision: Keep the implementation changes that preserve mention text and make delivered `@all`/`@Bot` paths parity-safe; add Feishu app scope warning so operators can diagnose missing ordinary group-message delivery without inventing a local `receiveAllGroupMessages` config flag; add Feishu group history catch-up before @Bot triggers so an app with `im:message.group_msg` can compensate for missing ordinary push events; record the current app blocker explicitly instead of claiming ordinary-background live pass. Gateway cannot make Feishu deliver ordinary group events; it can only warn when scope verification fails or `im:message.group_msg` is absent.
- Rationale: The code path for `sync_only` ordinary messages is covered by pipeline unit tests, and the adapter now has a product-level compensation path that can fetch same-chat ordinary messages before processing the current @Bot event. No Gateway code can buffer a message that Feishu neither pushes nor allows the bot to read. The correct product behavior for this milestone is to surface a diagnostic and leave the live ordinary-background criterion unpassed until the Feishu app has ordinary group message delivery or `im:message.group_msg` history-read capability.
- Evidence:
  - Tests:
    - R3 red tests: `pytest -q tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py` initially failed on missing ordinary group-message delivery diagnostics.
    - R4 adjustment after openclaw comparison: removed `receiveAllGroupMessages` local config, moved diagnostics to Feishu app scope inspection; focused tests `pytest -q tests/unit/test_feishu_config.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_integration.py` -> 64 passed.
    - Focused M12 after live-discovered `@_all` patch: `pytest -q tests/unit/test_feishu_mentions.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py` -> 82 passed in 2.77s.
    - Focused M12 after history catch-up patch: `pytest -q tests/unit/test_feishu_mentions.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_group_history_catchup.py tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/contract/test_test_naming_and_size_contract.py` -> 86 passed in 2.55s.
    - Contract/file-size fix after splitting mention regressions: `pytest -q tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_mentions.py tests/contract/test_test_naming_and_size_contract.py` -> 39 passed in 2.53s.
    - R5 runtime CLI boundary fix: removed Gateway/runtime `lark-cli` identity inference; `botOpenId` is filled only from Feishu app-credential probe, `ownerOpenId` is no longer auto-inferred, and `lark-cli` remains only a reviewer live-test tool / built-in `feishu-doc` skill tool. `pytest -q tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py tests/unit/test_feishu_config.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_adapter_scope_warning.py tests/unit/test_feishu_integration.py tests/contract/test_test_naming_and_size_contract.py` -> 73 passed.
    - R6 live-discovered `group_reply_policy=ALWAYS` fix: FeishuAdapter no longer marks current non-@ group events as `sync_only`; it emits `mentioned_agent_ids=[]` so InboundPipeline can apply the agent reply policy. History catch-up remains `sync_only`. `pytest -q tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py tests/unit/test_feishu_config.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_group_history_catchup.py tests/unit/test_feishu_adapter_scope_warning.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py tests/contract/test_test_naming_and_size_contract.py` -> 97 passed.
    - R7 live-discovered THINKING ack fix: Gateway accepted lifecycle now calls the Feishu adapter ack hook for any Feishu message that actually enters a run, so `group_reply_policy=ALWAYS` non-@ triggers get the same processing reaction as @Bot triggers; adapter ack is idempotent. `pytest -q tests/unit/test_feishu_adapter.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/test_feishu_integration.py` -> 59 passed.
    - R8 owner identity binding fix: `ownerOpenId` is no longer a manual or CLI-derived requirement; Gateway passes a Feishu owner binder into the adapter, and the first real inbound sender for that channel is written back to config and used for subsequent `"你"` display. History catch-up does not bind owner. `pytest -q tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py tests/unit/test_feishu_config.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_scopes.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_adapter_owner_binding.py tests/unit/test_feishu_group_history_catchup.py tests/unit/test_feishu_adapter_scope_warning.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_test_naming_and_size_contract.py` -> 121 passed.
    - Full non-e2e final gate after history catch-up patch: `pytest -m "not e2e"` -> 3262 passed, 1 skipped, 22 deselected, 20 warnings in 147.98s.
  - Entry: Unit-level config/channel registry warning, Feishu parser/adapter, Gateway pipeline; live probes used real Feishu group `oc_6e3d14c5e910d3c1a2a984baff1c7eda`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
    - `tests/unit/test_feishu_client_scopes.py` validates Feishu app scope inspection for `im:message.group_msg`.
    - `tests/unit/test_feishu_adapter_scope_warning.py` validates startup warning when Feishu app scope inspection says ordinary group-message delivery is unavailable.
    - `tests/unit/test_feishu_mentions.py::test_parse_live_at_all_placeholder_keeps_visible_text_without_entity` covers live Feishu `@_all` content with no mention entity and normalizes it to `@所有人`.
    - `tests/unit/test_feishu_group_history_catchup.py` validates that a group @Bot event first injects fetched ordinary history as `sync_only`, and that missing history permission warns while still delivering the current trigger.
    - Pipeline tests cover both ordinary Feishu group modes: non-@ current events with `mentioned_agent_ids=[]` honor `group_reply_policy=ALWAYS`, while `sync_only` history/background messages buffer under the external key and pure mention drains it.
    - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_relay_lifecycle_accepted_acks_feishu_message_processing_started` validates accepted lifecycle Feishu ack for non-adapter-decided triggers.
    - `tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py::test_feishu_owner_open_id_binder_persists_first_sender` and `tests/unit/test_feishu_adapter_owner_binding.py` validate first-inbound owner binding, immediate `"你"` display, existing-owner preservation, and history catch-up non-binding.
  - Visual/Interaction: N/A
  - Live Critical:
    - Auth/config identity matched before sends: `lark-cli auth status --json --verify` appId `cli_aac9315ef3f9dbda`, bot openId `ou_b33ae16df1338a00a77d4cdbec653b71`; local Gateway config used `feishu:default-agent.settings.appId=cli_aac9315ef3f9dbda`.
    - Test group: `oc_6e3d14c5e910d3c1a2a984baff1c7eda`.
    - R6 live smoke after enabling `group_reply_policy=ALWAYS`: `lark-cli im +messages-send --as user --chat-id oc_6e3d14c5e910d3c1a2a984baff1c7eda --text "feat447-always-smoke-1783040379 不要@也请回复：收到 always smoke"` produced IM shadow rows for the user message and an agent reply `收到，always smoke 测试已收到。`.
    - R7 live ack smoke: `lark-cli im +messages-send --as user --chat-id oc_6e3d14c5e910d3c1a2a984baff1c7eda --text "feat447-ack-long-1783041079 不@也请处理：请先用工具查看当前目录，再简短回复。"` produced IM shadow user/reply rows, and Gateway foreground output showed `im.message.reaction.created_v1` followed by `im.message.reaction.deleted_v1`, confirming THINKING add/remove on a non-@ ALWAYS trigger.
    - Delivered-path live pass on patched Gateway (`nonce=feat-447-live3-1783000426`): Feishu history has ordinary bg `om_x100b6b529807a480b48bd70b7295ebf`, `@all` `om_x100b6b52999aaca4b4b3ec53e6b1847`, pure `@nano` `om_x100b6b5296c850a4b1c9d3871aaa196`, `@nano hi` `om_x100b6b5297694ca8b1a55833ce259dd`. IM DB shows `@所有人 feat-447-all-feat-447-live3-1783000426`, pure `@nano`, and `@nano hi feat-447-hi-feat-447-live3-1783000426`; chat history artifact `chat_history/sess_68afe29123146d97.jsonl` preserves LLM inputs `[你] @所有人 ...\n[你] @nano` and `[你] @nano hi ...`.
    - Ordinary background live NOT PASS: the Feishu history row `om_x100b6b529807a480b48bd70b7295ebf` (`feat-447-bg-feat-447-live3-1783000426 你会数学吗`) did not appear in IM DB, Gateway log, or `GroupContextStore`; pure `@nano` therefore drained the delivered `@所有人` context rather than the ordinary background.
    - Event-consumer blocker proof with Gateway stopped (`nonce=feat-447-eventonly-1783001020`): `lark-cli event consume im.message.receive_v1 --as bot --timeout 65s` emitted exactly 3 events and exited by timeout: `@_all feat-447-all-feat-447-eventonly-1783001020` (`om_x100b6b52b2b344a8b39b139e0d1939d`), `@nano` (`om_x100b6b52b3c1e0a0b489a88b77d4f76`), and `@nano hi feat-447-hi-feat-447-eventonly-1783001020` (`om_x100b6b52b31544b8b4980cd465e46dc`). The ordinary background `feat-447-bg-feat-447-eventonly-1783001020 你会数学吗` exists in Feishu chat history as `om_x100b6b52b53fe8a0b494e3985714d6c`, but was absent from the event stream.
    - Concurrent-listener diagnostic: while Gateway WS was connected, `lark-cli event consume im.message.receive_v1 --as bot --timeout 55s` failed before probing with `online_instance_cnt=1`, proving the Gateway Feishu WS was the app's active event connection. User-provided corroborating probe: ordinary message `feat447-orch-bg-1783000941 你会数学吗` exists in Feishu chat history as `om_x100b6b52b82dd0b0b2f14ffa9e2d478` at `2026-07-02 22:02`, but grep of current `.gateway.log` / `.live-m12-*` found no nonce.
    - Bot history-read blocker proof: `lark-cli im +chat-messages-list --chat-id oc_6e3d14c5e910d3c1a2a984baff1c7eda --as bot --page-size 5` failed with Feishu code `230027 access denied for this operation`. The same chat is readable with `--as user` because the user token has `im:message.group_msg:get_as_user`; Gateway uses app/bot credentials and needs `im:message.group_msg` for bot-side compensation.
    - Post-permission live pass after user enabled `im:message.group_msg` for app `cli_aac9315ef3f9dbda`:
      - Bot history-read check: `lark-cli im +chat-messages-list --chat-id oc_6e3d14c5e910d3c1a2a984baff1c7eda --as bot --page-size 5` succeeded and returned real group messages.
      - Ordinary event check: `lark-cli event consume im.message.receive_v1 --as bot --timeout 25s --max-events 1 --quiet` received ordinary group message `feat447-permcheck-1783003472 普通群消息事件验证` (`om_x100b6b53dbda68b4b1b2b3b2cf58fb5`).
      - Final live nonce: `feat447-final-1783004883`. Sent with `lark-cli im +messages-send --as user`: ordinary background `om_x100b6b53a3f0a4a0b4a1af2732ace0a` (`feat-447-bg-feat447-final-1783004883 请回答这个问题：你会数学吗？`), `@all` `om_x100b6b53a394e0a0b1288d47ac4f013`, pure `@nano` `om_x100b6b53a3bbe4a0b1bc76fd7aa59b7`, and `@nano hi` `om_x100b6b53a0b484acb16e2ae61aeeabd`.
      - Feishu-visible replies: after pure `@nano`, bot replied `会一些数学。你可以把具体题目发给我，我帮你算。` (`om_x100b6b53a31ae0b0b28d66d5a4dfc7d`); after `@nano hi`, bot replied `在呢，有什么可以帮忙的？` (`om_x100b6b53a00b6ca0b481791d432cf1d`).
      - IM/kernel evidence: `data/im_service.sqlite3` contains the background, `@所有人`, pure-mention reply, `@nano hi`, and final reply with no empty messages; `GroupContextStore` empty-text count was 0; `.gateway.log`/`.im.log` had no `external shadow sync failed` or `400 Bad Request`. Kernel JSONL `default-agent/chat_history/sess_3e053fbbe884eb56.jsonl` first user turn was exactly `[你] feat-447-bg-feat447-final-1783004883 请回答这个问题：你会数学吗？\n[你] @所有人 ...\n[你] @nano`, followed by the math-aware answer.
    - Live-discovered fixes after permission unblock: Feishu history list items may carry text in `body.content`; history catch-up must skip empty parsed text, skip bot/app self messages, and only retain pending context after the last bot reply. `scripts/e2e-up.sh` also needed a yq fix so each configured agent gets its own worktree-local workspace, plus cleanup of local Gateway state stores to avoid stale session/context pollution between live runs.
- Rollback: Revert diagnostic commits `fe8ace78`/`013f0037`, parser live fix `fa183505`, test split `3feb38a5`, and history catch-up commit if the config warning, live `@_all` normalization, or bot history compensation must be removed. Revert R1/R2 commits for the broader mention/external-buffer changes.
- Commits: C1=fe8ace78, C2=013f0037 + fa183505 + 3feb38a5 + history-catchup commit, C3=final docs commit
- Next: Milestone complete
