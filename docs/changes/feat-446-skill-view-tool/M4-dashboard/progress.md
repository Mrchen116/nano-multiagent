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

- Context: Added the frontend Skills usage dashboard inside the existing Agent detail shell without changing the existing config form fields.
- Decision: The Agent detail page now has a `Config / Skills` segmented navigation. The `Skills` section fetches `/im/v1/agents/{agent_id}/skills/usage` through `getAgentSkillsUsage` and provides `List`, `Agent`, and `Health` views. List view hides archived skills by default and supports `Show archived`; Agent view renders the 30-day heatmap; Health view renders the F3/F4 funnel numbers. Empty usage and RPC/offline failure are separate states.
- Rationale: This keeps the dashboard in the existing Agent detail context rather than creating a second settings surface, and it keeps offline state distinct from an empty `.usage.json` payload.
- Evidence:
  - Tests:
    - Red tests before implementation failed as expected: `getAgentSkillsUsage is not a function` and missing `Skills` button/dashboard UI.
    - `cd src/IM/frontend && npm run test -- --run src/features/settings/agents/im-agent-config-api.test.ts src/features/settings/agents/agent-detail-page.test.tsx` -> 2 files / 35 tests passed.
    - `cd src/IM/frontend && npm run test` -> 63 files / 570 tests passed. Existing warnings observed: `--localstorage-file` without path and React `act(...)` warnings in existing tests.
    - `cd src/IM/frontend && npm run build` -> passed. Existing Vite warnings: dynamic/static import overlap for `auth-store.ts`, chunk size > 500 kB.
  - Entry:
    - API client: `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts#getAgentSkillsUsage`.
    - UI: `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx#AgentSkillsUsagePanel`.
  - Frontend State Matrix:
    - default: tested list view with `deploy-check`, `3 uses`, `active`, and trend bars.
    - empty: tested `No skill usage yet` when API returns `skills: []`.
    - error/offline: tested `Gateway offline` when the usage query rejects with 503 detail.
    - archived filter: tested archived skill hidden by default and shown after `Show archived`.
    - agent view: tested `30-day heatmap` and `skills-agent-heatmap`.
    - health view: tested `Created`, `Still active`, and `Used at least once` funnel labels/numbers.
  - Browser QA: deferred to R3 final browser pass, which will cover dashboard and tool-card real entry screenshots together.
  - E2E/Regression: Frontend regression verifies dashboard queries the API client with `agent-core-1` and preserves real response fields.
  - Visual/Interaction: The dashboard uses existing `im-agent-card`, `im-btn`, and Agent detail shell patterns; no new page or separate Agent config rewrite.
- Rollback: Revert R2 commits to remove the `Skills` tab and API client; R1 API remains usable independently.
- Commits:
  - `b307e7f5 test(feat-446/M4/R2): cover skills dashboard`
  - `4c75a03e feat(feat-446/M4/R2): add skills usage dashboard`
- Next: R3

## R3 — skill_view tool card and browser QA

- Context: Completed the chat v2 `skill_view` presenter/card connection and the required browser QA pass for both the Skills dashboard and tool-call rows.
- Decision: `skill_view` now uses the skill-family emoji, has a summary fallback of `查看 skill：<name>` when historical rows do not carry `output`, and renders a bespoke detail card for name/location/content. `detail.success === false` keeps using the existing failed-row mechanism while the card shows the concrete error reason.
- Rationale: The presenter already emits `查看 skill：<name>` for current rows; the fallback protects persisted/in-flight rows where `output` is empty. Reusing `LongOutput` keeps long skill content behavior consistent with bash/write/tool detail cards, including preview + expand-all.
- Evidence:
  - Tests:
    - Red tests before implementation failed as expected: `skill_view` used generic `🔧`, no `.chat-tool-detail-skill-view` card existed, and failure detail fell through generic rendering.
    - `cd src/IM/frontend && npm run test -- --run src/features/chat/v2/components/tool-calls-panel.test.tsx` -> 1 file / 80 tests passed.
    - `cd src/IM/frontend && npm run test` -> 63 files / 573 tests passed. Existing warnings observed: `--localstorage-file` without path, React `act(...)`, and pre-existing query-data warnings in older tests.
    - `cd src/IM/frontend && npm run build` -> passed. Existing Vite warnings: dynamic/static import overlap for `auth-store.ts`, chunk size > 500 kB.
    - `PYTHONPATH=src pytest tests/im_service/unit/test_gateway_handler.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/integration/test_agent_config_api.py -q` -> 81 passed.
    - `python -m compileall -q src/IM src/personal_assistant` -> passed.
  - Entry:
    - `skill_view` collapsed/presenter helpers: `src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts`.
    - `skill_view` expanded card: `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx`.
    - Browser dashboard entry: `/settings/agents/agent-core-1` -> `Skills`.
    - Browser tool-card entry: `/chat/c-skill` with real chat v2 process panel fed by WS event envelopes.
  - Frontend State Matrix:
    - default/list: screenshot `dashboard-list-1280.png` shows `deploy-check`, `7 uses`, `active`, `F3`, and trend bars.
    - archived filter: screenshot `dashboard-archived-1280.png` shows archived `old-skill`.
    - agent heatmap: screenshot `dashboard-heatmap-1280.png` shows `30-day heatmap` with heat cells.
    - health funnel: screenshot `dashboard-health-1280.png` shows `Created=9`, `Still active=6`, `Used at least once=4`.
    - empty: screenshot `dashboard-empty-390.png` at 390x844 shows `No skill usage yet`.
    - offline/error: screenshot `dashboard-offline-390.png` at 390x844 shows `Gateway offline` after `/skills/usage` returns 503.
    - `skill_view` success: screenshot `chat-skill-view-success-1280.png` shows collapsed `查看 skill：change-spec-author` and expanded name/location/content preview.
    - `skill_view` failure: screenshot `chat-skill-view-failure-1280.png` shows the failed/red `skill_view` row and `skill not found`.
  - Browser QA:
    - Vite served from `http://127.0.0.1:60999/`.
    - Artifacts: `/tmp/feat446-m4-browser-qa/`.
    - Screenshots:
      - `/tmp/feat446-m4-browser-qa/dashboard-list-1280.png`
      - `/tmp/feat446-m4-browser-qa/dashboard-archived-1280.png`
      - `/tmp/feat446-m4-browser-qa/dashboard-heatmap-1280.png`
      - `/tmp/feat446-m4-browser-qa/dashboard-health-1280.png`
      - `/tmp/feat446-m4-browser-qa/dashboard-empty-390.png`
      - `/tmp/feat446-m4-browser-qa/dashboard-offline-390.png`
      - `/tmp/feat446-m4-browser-qa/chat-skill-view-success-1280.png`
      - `/tmp/feat446-m4-browser-qa/chat-skill-view-failure-1280.png`
    - Report: `/tmp/feat446-m4-browser-qa/report.json`.
    - Console/network conclusion: no unknown API calls; no unexpected failed requests. The only console/network error is the intentional `/im/v1/agents/agent-core-1/skills/usage` 503 used to prove the offline state. The same report records successful `/skills/usage` 200 requests for list/heatmap/health/empty states.
  - E2E/Regression:
    - `test_im_connection_handles_skills_usage_request` proves the Gateway provider reads a real workspace `.usage.json` fixture and returns active + archived skills with usage counts, trends, heatmap, and health numbers.
    - `test_get_skills_usage_calls_rpc_not_direct_file_read` proves the IM HTTP API returns the WS RPC payload and does not read workspace files on the IM host.
    - `test_get_skills_usage_reports_offline_when_rpc_times_out` proves disconnected Gateway returns HTTP 503 rather than empty data.
  - Visual/Interaction:
    - Skills dashboard is integrated into the existing Agent detail shell/navigation; no Agent config page rewrite.
    - Tool cards reuse existing process-panel rows and `LongOutput`; no nested card redesign.
- Rollback: Revert R3 commits to remove `skill_view` bespoke rendering; R1/R2 API/dashboard remain functional.
- Commits:
  - `d743f96c test(feat-446/M4/R3): cover skill view tool card`
  - `cd49d456 feat(feat-446/M4/R3): render skill view tool card`
  - `31a11abd fix(feat-446/M4/R3): type skill view summary fallback`
- Next: DONE
