# feat-447-M8 — Progress

## Context

- Skill: `change-impl-worker`
- Unit: `feat-447`
- Milestone: `feat-447-M8 fix-live-startup`
- Base: `origin/unit/feat-447` at `9756b958650b5c4d5b8e228602a8289376889568`
- Scope: Round 4 acceptance/verifier fast-lane fixes only.

## Startup

- Sync Gate: local `unit/feat-447` equals `origin/unit/feat-447` at `9756b958650b5c4d5b8e228602a8289376889568`.
- Context read: `change-impl-worker` skill, `AGENTS.md`, `docs/TESTING_GUIDE.md`, `acceptance.md` Round 4, `verification.md` Round 4, `design.md` Runbook, M7 `tasks.md`/`progress.md`, and relevant IM/Gateway/Feishu code/tests.
- Baseline: `pytest -m "not e2e"` -> 3223 passed, 1 skipped, 22 deselected, 20 warnings in 140.00s.

## Roadpoint Progress

### R1 — Round 4 live startup fixes

- Context: Round 4 reviewer could not start real IM/Gateway from runbook. IM crashed on a legacy DB because `CREATE INDEX ... external_source` ran before legacy `conversations` had the M7 columns. Gateway crashed because `ownerOpenId` was hard-required even though the checked-in reviewer config omits it. Verifier also found Feishu group shadow titles fall back to `agent · 群聊 · feishu` because Feishu group metadata never supplies a real group name.
- Decision: Keep `ownerOpenId` optional at config-parse/registry time, then let Gateway startup auto-fill it from `lark-cli auth status --json --verify` only when the CLI `appId` exactly matches the Feishu channel `settings.appId`. Move old-DB external identity index creation behind the legacy column migration, backfill missing `messages.elapsed_ms`, and make runtime `node.register` provision the matching `agent:<id>` IM user row. Fetch Feishu group chat names best-effort and pass them as `chat_name`/`conversation_title`; lookup failure or an unstarted adapter falls back to the existing generic title without blocking inbound delivery.
- Rationale: Round 4 reviewer must be able to start the worktree config as-is, without hand-editing `.gateway-config.yaml`, while still preserving the "owner shows as 你" requirement when the live CLI is authenticated to the same Feishu app. The legacy DB bug was not just the first `external_source` column crash: live smoke showed the same old DB also lacked the agent participant row and `messages.elapsed_ms`, which broke IM shadow sync/runtime streaming after startup. Group title lookup is external API dependent, so failure cannot be allowed to drop user messages.
- Evidence:
  - Tests: Red test command: `pytest -q tests/im_service/unit/test_db_init.py::test_initialize_schema_migrates_legacy_conversations_before_external_index tests/unit/test_feishu_config.py::TestParseFeishuChannels::test_missing_owner_open_id_does_not_block_startup tests/unit/test_feishu_integration.py::TestBuildChannelRegistryFeishuRealAdapter::test_build_channel_registry_allows_missing_owner_open_id tests/unit/test_feishu_adapter.py::TestFeishuAdapterGroupMention::test_group_inbound_metadata_includes_chat_name tests/unit/test_feishu_client.py::TestFeishuClientSendMessage::test_get_chat_name_returns_group_name tests/unit/test_feishu_client.py::TestFeishuClientSendMessage::test_get_chat_name_failure_raises_feishu_api_error` -> 6 failed as expected for old DB index-before-column, `ownerOpenId` hard requirement / `KeyError`, and missing `FeishuClient.get_chat_name` / group metadata.
  - Tests: Green narrow commands:
    - `pytest -q tests/unit/personal_assistant/test_gateway_feishu_owner_open_id.py tests/unit/test_feishu_adapter_chat_title.py tests/unit/test_feishu_client_chat_info.py tests/unit/test_feishu_integration.py tests/unit/test_feishu_config.py` -> 35 passed, 7 warnings.
    - `pytest -q tests/im_service/unit/test_gateway_handler.py::test_handle_register_runtime_profile_provisions_agent_user tests/im_service/unit/test_db_init.py::test_initialize_schema_migrates_legacy_conversations_before_external_index tests/unit/personal_assistant/test_gateway_feishu_owner_open_id.py` -> 8 passed, 7 warnings.
  - Tests: `pytest -m "not e2e"` -> 3236 passed, 1 skipped, 22 deselected, 20 warnings in 137.88s.
  - Entry: true Lark inbound only; no UI fallback/stub. `lark-cli auth status --json --verify` at 2026-07-02 11:18:05 +0800 returned `appId=cli_aac9315ef3f9dbda`, bot openId `ou_b33ae16df1338a00a77d4cdbec653b71`, user openId `ou_e6d1591026cfdac8d131eb1fdd71bdb9`, matching `<WT_CFG>` channel `feishu:default-agent.settings.appId`.
  - Live startup: worktree-local `.gateway-config.yaml` was copied from unit worktree config with Feishu `ownerOpenId=nil`; reviewer-style Gateway start `PYTHONPATH=src python -m personal_assistant.main --config .../.gateway-config.yaml --im-service-url http://127.0.0.1:56110 --foreground --auto-bind` auto-bound IM and auto-filled `ownerOpenId=ou_e6d1591026cfdac8d131eb1fdd71bdb9` without manual owner edit.
  - Live old DB: IM started from a legacy DB whose `conversations` table lacked `external_source/external_chat_id` and whose `messages` table lacked runtime columns; after `initialize_schema`, `conversations` had `external_source/external_chat_id` + `idx_conversations_external_identity`, `messages` had `elapsed_ms`, and `users` contained `agent:default-agent`.
  - Live Lark command: `NONCE="feat447-m8-live3-20260702113138"; lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "$NONCE live shadow row final" --idempotency-key "$NONCE" --format json` -> `ok=true`, `chat_id=oc_1906eead0189484ce5ea8a4c245400a6`, `message_id=om_x100b6b69f771b0a4c234ed9ba65e8d3`, `create_time=2026-07-02 11:31:39`.
  - Live IM shadow evidence from `.m8-live-legacy.sqlite3`: conversation `ce0ddd9c7ddc468cab02931c5cc53153`, title `default-agent · feishu`, type `direct`, `external_source=feishu`, `external_chat_id=feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9`, `config_agent_id=default-agent`, owner `71ca97863250459e85697968ad58efc0`; user message `d4c4388237f547cfbd5ceaaae716fec9`, content nonce above, `sender_display_name=你`, `delivery_status=sent`, `created_at=2026-07-02T03:31:41.254465Z`.
  - Live Feishu visible evidence: `lark-cli im +chat-messages-list --as user --chat-id oc_1906eead0189484ce5ea8a4c245400a6 --page-size 3` listed user message `om_x100b6b69f771b0a4c234ed9ba65e8d3` with the same nonce and a Bot THINKING reaction. Caveat: final bot text for this third nonce was still running when services were stopped; this M8 fix verifies startup + IM shadow sync, and earlier live2 had a bot text response but was before the `elapsed_ms` migration fix.
  - Live log paths/caveat: local transient `.m8-gateway.log` and uvicorn PTY output showed `POST /im/v1/conversations/external/find-or-create` -> 201 and `POST /im/v1/conversations/ce0ddd9c7ddc468cab02931c5cc53153/messages` -> 201; `grep -E "Bad Request|external shadow sync failed|OperationalError|elapsed_ms" .m8-gateway.log` returned no matches for the final run. Live config/log/sqlite files are local artifacts and are not committed.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: true Feishu/Lark inbound smoke completed with `lark-cli im +messages-send --as user`; regression tests cover legacy DB migration, owner autofill degraded paths, group title metadata, and runtime agent-user provisioning.
  - Visual/Interaction: N/A
- Rollback: Revert C2 to restore Round 4 behavior. Operational impact would be the known reviewer failures: old DB startup/streaming may crash, missing `ownerOpenId` config will not self-heal, and group shadow titles fall back to generic labels. Revert C3 for docs only.
- Commits: C1=8399ee93, C2=fde97081, C3=`docs(feat-447/M8/R1): record live startup fix evidence`.
- Next: Commit C3 docs, push milestone, merge to `unit/feat-447`, push unit, then remove milestone worktree/branch.
