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
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: Red test command: `pytest -q tests/im_service/unit/test_db_init.py::test_initialize_schema_migrates_legacy_conversations_before_external_index tests/unit/test_feishu_config.py::TestParseFeishuChannels::test_missing_owner_open_id_does_not_block_startup tests/unit/test_feishu_integration.py::TestBuildChannelRegistryFeishuRealAdapter::test_build_channel_registry_allows_missing_owner_open_id tests/unit/test_feishu_adapter.py::TestFeishuAdapterGroupMention::test_group_inbound_metadata_includes_chat_name tests/unit/test_feishu_client.py::TestFeishuClientSendMessage::test_get_chat_name_returns_group_name tests/unit/test_feishu_client.py::TestFeishuClientSendMessage::test_get_chat_name_failure_raises_feishu_api_error` -> 6 failed as expected for old DB index-before-column, `ownerOpenId` hard requirement / `KeyError`, and missing `FeishuClient.get_chat_name` / group metadata.
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: Implement fixes.
