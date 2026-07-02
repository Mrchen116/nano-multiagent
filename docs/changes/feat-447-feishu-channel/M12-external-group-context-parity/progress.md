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
- Decision: Keep the implementation changes that preserve mention text and make delivered `@all`/`@Bot` paths parity-safe; add warning/config validation so operators can diagnose missing ordinary group-message delivery; add Feishu group history catch-up before @Bot triggers so an app with `im:message.group_msg` can compensate for missing ordinary push events; record the current app blocker explicitly instead of claiming ordinary-background live pass. `receiveAllGroupMessages=true` is a local operator declaration and does not make Feishu deliver events by itself.
- Rationale: The code path for `sync_only` ordinary messages is covered by pipeline unit tests, and the adapter now has a product-level compensation path that can fetch same-chat ordinary messages before processing the current @Bot event. No Gateway code can buffer a message that Feishu neither pushes nor allows the bot to read. The correct product behavior for this milestone is to surface a diagnostic and leave the live ordinary-background criterion unpassed until the Feishu app has ordinary group message delivery or `im:message.group_msg` history-read capability.
- Evidence:
  - Tests:
    - R3 red tests: `pytest -q tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py` initially failed on missing `receiveAllGroupMessages` validation/warning coverage.
    - R3 green narrow tests: `pytest -q tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py` -> 30 passed in 2.43s.
    - Focused M12 after live-discovered `@_all` patch: `pytest -q tests/unit/test_feishu_mentions.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py` -> 82 passed in 2.77s.
    - Focused M12 after history catch-up patch: `pytest -q tests/unit/test_feishu_mentions.py tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_group_history_catchup.py tests/unit/test_feishu_config.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/contract/test_test_naming_and_size_contract.py` -> 86 passed in 2.55s.
    - Contract/file-size fix after splitting mention regressions: `pytest -q tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_mentions.py tests/contract/test_test_naming_and_size_contract.py` -> 39 passed in 2.53s.
    - Full non-e2e final gate after history catch-up patch: `pytest -m "not e2e"` -> 3262 passed, 1 skipped, 22 deselected, 20 warnings in 147.98s.
  - Entry: Unit-level config/channel registry warning, Feishu parser/adapter, Gateway pipeline; live probes used real Feishu group `oc_6e3d14c5e910d3c1a2a984baff1c7eda`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
    - `tests/unit/test_feishu_config.py` validates optional `receiveAllGroupMessages` must be bool.
    - `tests/unit/test_feishu_integration.py` validates startup warning when Feishu config does not declare ordinary group-message delivery.
    - `tests/unit/test_feishu_mentions.py::test_parse_live_at_all_placeholder_keeps_visible_text_without_entity` covers live Feishu `@_all` content with no mention entity and normalizes it to `@所有人`.
    - `tests/unit/test_feishu_group_history_catchup.py` validates that a group @Bot event first injects fetched ordinary history as `sync_only`, and that missing history permission warns while still delivering the current trigger.
    - Pipeline tests still cover the desired behavior if an ordinary Feishu group event is delivered: `sync_only` background buffers under external key and pure mention drains it.
  - Visual/Interaction: N/A
  - Live Critical:
    - Auth/config identity matched before sends: `lark-cli auth status --json --verify` appId `cli_aac9315ef3f9dbda`, bot openId `ou_b33ae16df1338a00a77d4cdbec653b71`; local Gateway config used `feishu:default-agent.settings.appId=cli_aac9315ef3f9dbda`.
    - Test group: `oc_6e3d14c5e910d3c1a2a984baff1c7eda`.
    - Delivered-path live pass on patched Gateway (`nonce=feat-447-live3-1783000426`): Feishu history has ordinary bg `om_x100b6b529807a480b48bd70b7295ebf`, `@all` `om_x100b6b52999aaca4b4b3ec53e6b1847`, pure `@nano` `om_x100b6b5296c850a4b1c9d3871aaa196`, `@nano hi` `om_x100b6b5297694ca8b1a55833ce259dd`. IM DB shows `@所有人 feat-447-all-feat-447-live3-1783000426`, pure `@nano`, and `@nano hi feat-447-hi-feat-447-live3-1783000426`; chat history artifact `chat_history/sess_68afe29123146d97.jsonl` preserves LLM inputs `[你] @所有人 ...\n[你] @nano` and `[你] @nano hi ...`.
    - Ordinary background live NOT PASS: the Feishu history row `om_x100b6b529807a480b48bd70b7295ebf` (`feat-447-bg-feat-447-live3-1783000426 你会数学吗`) did not appear in IM DB, Gateway log, or `GroupContextStore`; pure `@nano` therefore drained the delivered `@所有人` context rather than the ordinary background.
    - Event-consumer blocker proof with Gateway stopped (`nonce=feat-447-eventonly-1783001020`): `lark-cli event consume im.message.receive_v1 --as bot --timeout 65s` emitted exactly 3 events and exited by timeout: `@_all feat-447-all-feat-447-eventonly-1783001020` (`om_x100b6b52b2b344a8b39b139e0d1939d`), `@nano` (`om_x100b6b52b3c1e0a0b489a88b77d4f76`), and `@nano hi feat-447-hi-feat-447-eventonly-1783001020` (`om_x100b6b52b31544b8b4980cd465e46dc`). The ordinary background `feat-447-bg-feat-447-eventonly-1783001020 你会数学吗` exists in Feishu chat history as `om_x100b6b52b53fe8a0b494e3985714d6c`, but was absent from the event stream.
    - Concurrent-listener diagnostic: while Gateway WS was connected, `lark-cli event consume im.message.receive_v1 --as bot --timeout 55s` failed before probing with `online_instance_cnt=1`, proving the Gateway Feishu WS was the app's active event connection. User-provided corroborating probe: ordinary message `feat447-orch-bg-1783000941 你会数学吗` exists in Feishu chat history as `om_x100b6b52b82dd0b0b2f14ffa9e2d478` at `2026-07-02 22:02`, but grep of current `.gateway.log` / `.live-m12-*` found no nonce.
    - Bot history-read blocker proof: `lark-cli im +chat-messages-list --chat-id oc_6e3d14c5e910d3c1a2a984baff1c7eda --as bot --page-size 5` failed with Feishu code `230027 access denied for this operation`. The same chat is readable with `--as user` because the user token has `im:message.group_msg:get_as_user`; Gateway uses app/bot credentials and needs `im:message.group_msg` for bot-side compensation.
- Rollback: Revert diagnostic commits `fe8ace78`/`013f0037`, parser live fix `fa183505`, test split `3feb38a5`, and history catch-up commit if the config warning, live `@_all` normalization, or bot history compensation must be removed. Revert R1/R2 commits for the broader mention/external-buffer changes.
- Commits: C1=fe8ace78, C2=013f0037 + fa183505 + 3feb38a5 + history-catchup commit, C3=final docs commit
- Next: Milestone complete
