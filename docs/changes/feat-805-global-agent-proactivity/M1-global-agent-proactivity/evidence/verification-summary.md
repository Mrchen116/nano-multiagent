# feat-805 M1 Verification Summary

## Environment & Baseline

- **Unit**: `feat-805-global-agent-proactivity` (`M1-global-agent-proactivity`)
- **Branch**: `unit/feat-805-global-agent-proactivity` (base `origin/develop` `63aca5de0` / `0b844c772`)
- **Host**: `air` (macOS; `python3 scripts/dev_host.py check` `configured: true`, `xcodebuild` unavailable `NO_XCODE`)
- **Isolated E2E Stack**: `./scripts/e2e-up.sh --profile daily` (`NANO_E2E_LOGICAL_CLOCK_SOCKET` over 0600 Unix socket, `NanoApproval` enabled with `auto_mode.rules="codex"`, `dangerously_skip_permissions=false`)

## Build, Typecheck & Narrow Automated Suites

| Check | Command | Result |
|---|---|---|
| Workspace build | `pnpm build` | Pass (`0` errors) |
| Workspace typecheck | `pnpm typecheck` | Pass (`0` errors across all packages + `evals`) |
| Web IM TypeScript & test | `(cd src/IM/frontend && npx tsc -b && npx vitest run src/features/settings/agents/proactive-planning-toggle.test.tsx)` | Pass (`4/4` tests) |
| Shared capabilities contract | `pnpm --filter @nano/product-contracts test` | Pass (`14/14` tests in `capabilities.test.ts`) |
| Node capability plumbing | `pnpm exec vitest run apps/node/tests/capabilities.test.ts` | Pass (`5/5` tests) |
| IM Server mode gating & 1v1 DM focus | `pnpm exec vitest run apps/im-server/tests/task-proactivity-focus.test.ts` | Pass (`4/4` tests) |
| PA coordinator & short-ref projection | `pnpm exec vitest run packages/personal-assistant/tests/tool-references.test.ts packages/personal-assistant/tests/proactive-coordinator.test.ts` | Pass (`12/12` tests) |
| DSH integration memory, Dreaming & ROLE approval | `pnpm exec vitest run packages/dsh-integration/tests/approval-sources.test.ts packages/dsh-integration/tests/proactive-memory-hygiene.test.ts packages/dsh-integration/tests/proactive-dreaming-feedback.test.ts packages/dsh-integration/tests/global-proactivity-dreaming-approval.test.ts` | Pass (`24/24` tests) |
| Wire prefix cache replay (`NoSilentPrefixRewrite` & `SubagentPrefixPreserved`) | `pnpm exec vitest run packages/dsh-integration/tests/context-cache-prefix-provider.test.ts packages/dsh-integration/tests/global-child-tools.test.ts` | Pass (`8/8` replay scenarios) |
| Python unit & architecture contracts | `NANO_TEST_BASE_REF=origin/develop pytest -m "not e2e" -q && ruff check scripts/verify_global_agent_proactivity_24h.py` | Pass (`143/143` passed, `0` lint issues) |

## Multi-Day Live-LLM Acceptance (`scripts/verify_global_agent_proactivity_24h.py`)

Executed against isolated `daily` stack (`agent_id="daily-quality"`, root session `a53c39ef-2133-43b5-95e3-6fe7db1e8b56`, `64` live LLM steps) using natural human dialogue with zero tool/enum prompt hints:

1. **Scenario 4 — Mode-Aware Capability Contract (`global` vs `single_thread`)**
   - `GET /im/v1/agents/daily-quality/capabilities` (`work_mode="global"`) exposed `proactive_planning` (`default_on: true`, `depends_on_features: ["task_graph"]`, `depends_on_tools: ["task_graph"]`).
   - Creating a `single_thread` Agent hid `proactive_planning` from `GET /im/v1/agents/:id/capabilities`, persisted `proactive_planning != true`, stripped `nano-proactive-care` from default skills, and allowed `PATCH /im/v1/agents/:id/config` to disable `task_graph` cleanly without dependency deadlocks.

2. **Scenario 1 — Multi-Conversation Origin Routing, Quiet Review & Pre-Schedule Sync**
   - **Quiet `proactive_review` (`+17m` after conversation settle)**: `0` outbound chat messages across `#发版群`, `#研发群`, `Bob ↔ Q` 1v1 DM, and bound-admin DM.
   - **Night 1 (`03:05 Dreaming` -> `03:20 proactive_nightly`)**:
     - `#发版群` (`c_684png`) received `status="proposed"` card `「1.2 发版回归｜登录鉴权与跨源权限」` with `proposed_for_user_id` resolved (`u_xxxxxx -> Alice UUID`), entering Alice's `GET /im/v1/task-graphs/focus?scope=mine` `needs_you` (`count=2`).
     - `Bob ↔ Q` 1v1 DM (`c_6degmi`) received `status="proposed"` card `「验证批量上传的 1.5 秒超时是否导致偶发失败」` strictly inside `c_6degmi`, auto-attributed `proposed_for_user_id = Bob`, entering Bob's `needs_you` (`count=1`) with `0` morning-greeting schedules and `0` cross-leakage to Alice, bound admin, or group boards.
     - Bound administrator's standing hands-off rule on personal draft branches (`sandbox-toy`) produced `0` task cards across all conversations.
   - **Pre-schedule `<schedule-observation-sync>` (`09:55 -> 10:05`)**: Alice fixed `release-env.yaml` and posted an un-mentioned update in `#发版群` at `09:55` (inside the 10m group batch window). Before Q's `10:00` scheduled check executed, `agent/pre-step` ran `product.proactive.sync_observations` and injected `<schedule-observation-sync>`, preventing a stale conflict warning.

3. **Scenario 2 — Zero-History `ROLE.md` Standing Duty Attribution & Approval**
   - `#研发群` (`c_ru1i1k`) had `0` prior human messages. From `ROLE.md` standing duty + `smoke-status.md` (`checklist_sync_regression` failure), Q created `status="proposed"` card `「冒烟回归失败｜checklist_sync_regression 空游标返回 HTTP 500」` directly in `#研发群` (`admin_dm_proposed_count = 0`), passing `NanoApproval` via host-attested `.nanoassistant/ROLE.md` `<agent_instructions>`.

4. **Scenario 3 — Multi-Actor Two-Tier Memory Calibration, Scope Isolation & Prefix Reuse**
   - **Night 2 (`seen: 1` stateless implicit UI feedback)**: Bob closed the Night 1 `proposed` card via UI (`status="closed"`) with zero chat messages; stateless `peekPendingForDreaming` delivered the unconsumed `[task context]` update to `Dreaming`, recording `seen: 1` in `knowledge/proactivity-signals.md` without premature `MEMORY.md` promotion.
   - **Night 3 (`MEMORY.md` + `entities/*.md` two-tier promotion & collaborator isolation)**:
     - Memory Git history recorded 4 clean commits (`ebd16bf`, `e412cb4`, `bb63be2`, `67e4d5c`).
     - `MEMORY.md` (`697` UTF-16 code units) maintained `## 主动性与介入偏好` (`### 积极盯紧与提前备料`, `### 免打扰禁区`) with 1-line collaborator triggers linking to `entities/alice.md` and `entities/bob.md`, and promoted Bob's signal out of `knowledge/proactivity-signals.md`.
     - Despite a newly seeded regression in `scripts/log-cleaner.py`, Night 3 created `0` `proposed` cards in Bob's 1v1 DM (`bob_dm_proposed_night3 = 0`) while creating `「1.2 第二波回归｜跨节点令牌轮换与会话吊销（P0/P1）」` in `#发版群` following Alice's P0/P1 checklist format from `entities/alice.md`.
     - Root session durable trace verified `<updated-formal-memory>` tail delivery and monotonic prompt KV-cache reuse (`cacheReadTokens` rising smoothly to `81,408 -> 98,560` tokens without silent prefix rewrite).
