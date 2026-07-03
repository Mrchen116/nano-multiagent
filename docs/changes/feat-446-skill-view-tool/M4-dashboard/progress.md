# feat-446-M4 — Progress

## Startup

- Context: 按 `change-impl-worker` full 模式执行，worktree 为 `/Users/czj/Repos/nano-multiagent/.worktrees/feat-446-M4`，分支为 `milestone/feat-446-M4`。M1/M2/M3 已合入 `unit/feat-446`，本 milestone 只负责 dashboard/API/tool-card 接线。
- Evidence:
  - Read: `AGENTS.md`、`SPEC.md`、`CLAUDE.md`（指向 `AGENTS.md`）、`docs/TESTING_GUIDE.md`、`LOGBOOK.md`、`docs/changes/feat-446-skill-view-tool/spec.md`、`design.md`、`prototype.html`、`prototype-f2.html`、`specs/kernel/spec.md`、`specs/im/spec.md`、`specs/gateway/spec.md`、M1/M2/M3 `progress.md`、`change-impl-worker/SKILL.md`。
  - Baseline backend: `PYTHONPATH=src pytest tests/im_service/unit/test_gateway_handler.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/integration/test_agent_config_api.py -x` -> 76 passed.
  - Baseline frontend: first run failed because the new worktree lacked `node_modules` (`vitest: command not found`); after `cd src/IM/frontend && npm install`, `npm run test` -> 63 files / 565 tests passed. Existing warnings: `--localstorage-file` without path and React `act(...)` warnings in existing tests.
  - Scope confirmation: range is IM HTTP API `/im/v1/agents/:agentId/skills/usage` + gateway WS RPC provider + `IM/frontend/src/` Skills panel + `IM/frontend/src/features/chat/v2/components/tool-*` `skill_view` display; no M1/M2/M3 core/Curator/F2 rewrite.

## R1 — usage API and gateway RPC

- Context: Added the backend data path for the M4 dashboard: IM HTTP route -> `GatewayHandler` downstream WS RPC -> personal-assistant gateway reads workspace-local `.usage.json` and returns an aggregated dashboard payload.
- Decision: The new HTTP route is `/im/v1/agents/{agent_id}/skills/usage`. IM returns 503 only when the target gateway node is not connected or times out; missing/invalid `.usage.json` is a successful empty payload from the gateway. The gateway payload includes per-skill `use_count`, `state`, `source`, `session_refs`, `recent_call_keys`, 30-day `trend_buckets`, agent-level 30-day `heatmap_data`, and F3/F4 health funnel numbers.
- Rationale: This preserves the existing heartbeat/cron RPC architecture: IM never reads gateway workspace files directly, while frontend can still distinguish true empty data from offline gateway state.
- Evidence:
  - Tests:
    - Red tests before implementation failed as expected: missing `GatewayHandler.request_node_skills_usage`, missing `_skills_usage_waiters`/`_handle_skills_usage`, unsupported downstream `node.skills.usage.request`, and missing route monkeypatch target.
    - `PYTHONPATH=src pytest -q tests/im_service/unit/test_gateway_handler.py::test_request_node_skills_usage_returns_none_when_node_offline tests/im_service/unit/test_gateway_handler.py::test_handle_skills_usage_resolves_waiter_with_usage_payload tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_handles_skills_usage_request tests/im_service/integration/test_agent_config_api.py::test_get_skills_usage_calls_rpc_not_direct_file_read tests/im_service/integration/test_agent_config_api.py::test_get_skills_usage_reports_offline_when_rpc_times_out` -> 5 passed.
    - `PYTHONPATH=src pytest tests/im_service/unit/test_gateway_handler.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/integration/test_agent_config_api.py -q` -> 81 passed.
    - `python -m compileall -q src/IM/ws/gateway_handler.py src/personal_assistant/ws/im_connection.py src/IM/api/routes/agents.py` -> passed.
  - Entry:
    - IM route: `src/IM/api/routes/agents.py#get_agent_skills_usage`.
    - IM WS RPC waiters: `src/IM/ws/gateway_handler.py#request_node_skills_usage` and `_handle_skills_usage`.
    - Gateway provider: `src/personal_assistant/ws/im_connection.py` handles `node.skills.usage.request` and reads `<workspace>/.nanoassistant/skills/.usage.json`.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
    - Integration test `test_get_skills_usage_calls_rpc_not_direct_file_read` proves the HTTP route calls the WS RPC and returns the RPC payload.
    - Unit test `test_im_connection_handles_skills_usage_request` proves the gateway reads a real `.usage.json` fixture from workspace and returns archived + active skills, recent call keys, 30-day series, and health numbers.
    - Offline test `test_get_skills_usage_reports_offline_when_rpc_times_out` proves the IM API returns 503 with `target_node_id is not connected`.
  - Visual/Interaction: N/A
- Rollback: Revert R1 commits to remove the API/RPC path; no database schema or persistent config migration was added.
- Commits:
  - `551aa2b9 test(feat-446/M4/R1): cover skill usage rpc`
  - `0a3468e3 feat(feat-446/M4/R1): add skill usage rpc`
- Next: R2

## R2 — Agent detail Skills dashboard

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: TODO
- Next: R3

## R3 — skill_view tool card and browser QA

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: TODO
  - Browser QA: TODO
  - E2E/Regression: TODO
  - Visual/Interaction: TODO
- Rollback: TODO
- Commits: TODO
- Next: DONE
