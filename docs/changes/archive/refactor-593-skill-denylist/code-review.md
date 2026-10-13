# Independent Code Review

## Round 1 — full

- Unit: `refactor-593-skill-denylist`
- Branch/worktree: `codex/skill-denylist`, `/Users/czj/.codex/worktrees/workspace-skill-denylist/nano-multiagent`
- `executed_base`: `74bfff7f7118ed040f270491691f31f992393793`
- `validated_at`: `11f3ceafc6ffffc22dfe88b4684bab01d94de957`
- Range: `74bfff7f7118ed040f270491691f31f992393793...11f3ceafc`
- Independent reviewer did not implement the change. No source/test/design edits or commits were made by this reviewer. Parallel design-review report creation was left untouched.
- Implementation preceded the independent design review now being supplemented by another reviewer. This report does not claim the original Gate 2 ordering was followed.

### Findings

```json
[
  {
    "file": "apps/node/src/main.ts",
    "line": 53,
    "summary": "[P1] Do not let a Skill migration HTTP failure abort DSH recovery",
    "failure_scenario": "When a runtime restarts while the IM relay is ready and at least one Agent still has a legacy selection, onReady awaits migrateSkills before product recovery. An IM HTTP 503, timeout, or profile-version conflict escapes migrateSkills. RuntimeSupervisor treats any onReady rejection as execution startup failure, sets ready=false and terminates the successfully initialized DSH process; repeated failures consume its three recovery attempts. The relay ready callback at line 155 also lets the same failure skip managed-channel flush and all product/knowledge/workflow/usage recovery. A real RuntimeSupervisor plus KnowledgeUpdates probe with an IM 503 produced available=false, unavailable=1 and an exited child. Preserve legacy mode until migration succeeds, report/retry the migration separately, and allow normal execution/channel recovery to complete.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/im-server/src/control.ts",
    "line": 801,
    "summary": "[P2] Finish conversion after recovering a pending legacy configuration operation",
    "failure_scenario": "If a previously interrupted configuration operation still contains explicit_allowlist, /skills/migrate calls ops.recover and returns that recovered profile as HTTP 200. It never queries the Skill catalog or submits the denylist conversion. KnowledgeUpdates ignores the response mode and only migrates on relay-ready/runtime-ready events, so this connected Agent remains in the old allowlist until another such event; a subsequently copied/new Skill remains unavailable. A Fastify + real ConfigOperations probe seeded a pending old operation and observed HTTP 200, explicit_allowlist, skills=[keep], profile_version=2, with only agent.config.operation.status requested. Re-read the committed profile and continue/explicitly retry conversion rather than treating unrelated recovery as migration completion.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### Direct evidence

1. Recovery failure probe: `pnpm exec tsx /tmp/skill-denylist-recovery-review.ts`; raw output `/tmp/skill-denylist-recovery-review.log`:

   ```json
   {"error":"Error: IM external projection failed: 503","available":false,"unavailable":1,"exitCode":0,"signalCode":null}
   ```

   The probe uses the actual `RuntimeSupervisor`, actual `KnowledgeUpdates`, a temporary real DSH profile/process and a throwing IM port. It isolates the exact new `onReady → migrateSkills` dependency; it does not claim a live IM-network outage was induced. The production wiring is `apps/node/src/main.ts:53`; failure handling is `packages/dsh-integration/src/client.ts:116-122`, with retry budget at `:132-142`. Its temporary DSH home and process were cleaned up.

2. Pending-operation probe: `pnpm exec tsx /tmp/skill-denylist-migration-review.ts`; raw output `/tmp/skill-denylist-migration-review.log`:

   ```json
   {"status":200,"mode":"explicit_allowlist","skills":["keep"],"calls":["agent.config.operation.status"],"persisted":{"skills_selection_mode":"explicit_allowlist","profile_version":2}}
   ```

   This uses the actual IM database, Fastify route and ConfigOperations. Gateway responses are a port fixture for an interrupted then successfully recovered old config save. The expected catalog contains `keep` and `blocked`; a completed migration would store `explicit_denylist` / `[blocked]`. The in-memory database and Fastify app were closed. Necessary output is embedded here so the finding does not depend on `/tmp` retention.

### Coverage and retained evidence

Reviewed all 36 changed files and actual callers: canonicalization/fingerprints, Node YAML/runtime/IM mirror commit path, authenticated migration, provider catalog/list/get/explicit invocation, busy-session restriction, Web create/edit/preview/SlashPicker, native iOS draft/payload/command consumption, and creation-fact reconciliation. No DSH/private-import boundary change, tool-selection expansion or source/evolution-policy change was found in the diff.

Retained caller-supplied same-implementation evidence: runtime suite 71 files / 241 tests (`/tmp/nano-skill-denylist-full-final.log`); Web 91 files / 856 tests (`/tmp/nano-skill-denylist-frontend-final.log`), detail 21 tests; iOS AgentContractsTests 7 tests and simulator build; runtime build/typecheck and Vite bundle. The full Web TypeScript check still has the existing `message-pane.tsx:467` number/Timeout mismatch, independently reproduced on baseline in `/tmp/nano-skill-denylist-frontend-baseline.log`; no all-green Web tsc claim is made. These passed tests do not cover the two failing migration lifecycle conditions above.

No product-journey, physical-device or production acceptance is inferred from this static review.

## Round 2 — closure + patch

- `validated_at`: `42a02a49ae7f4c52221616d600286bb30aac4cb7`
- `executed_base`: `d07c7578f210ee7fe830e2e7de4407209e7c75fc`
- Finding-origin / patch range: `11f3ceafc6ffffc22dfe88b4684bab01d94de957..42a02a49ae7f4c52221616d600286bb30aac4cb7`, restricted to this unit and affected shared boundaries.
- Focus: Round 1 P1 runtime-recovery failure; P2 recovered-operation migration omission. No source/test/design changes or commits by reviewer.

### Findings

```json
[]
```

| Focus finding | Closure | Direct evidence |
|---|---|---|
| P1 — migration HTTP failure aborts execution/channel recovery | **closed** | `KnowledgeUpdates.migrateSkills` now catches/reports each Agent's failure at `packages/personal-assistant/src/knowledge.ts:70-77` and continues. Actual RuntimeSupervisor/KnowledgeUpdates/native-process probe now starts successfully, remains available and executes the next recovery action while retaining legacy selection. The regression also covers another Agent continuing and the failed Agent retrying on a later migration call. |
| P2 — recovered legacy operation returned as completed migration | **closed** | `apps/im-server/src/control.ts:798-812` reloads the committed profile after recovery, then performs conversion under the same serialized lock. The probe now queries full candidates, applies a new operation, returns explicit_denylist / `[blocked]` and advances profile_version to 3. Ordinary stale requests still check the input version; recovery uses the latest committed profile and existing operation fingerprint/CAS. |

### Independent closure evidence

- `pnpm exec tsx /tmp/skill-denylist-recovery-review.ts` (`/tmp/skill-denylist-recovery-review-r2.log`):

  ```json
  {"available":true,"recoveryContinued":true,"unavailable":0,"exitCode":null,"mode":"explicit_allowlist","errors":["Error: IM external projection failed: 503"]}
  ```

  The updated probe supplies the production-required `onError` callback; it uses actual RuntimeSupervisor + KnowledgeUpdates + a real temporary DSH child/profile. `recoveryContinued` is set after migration returns, proving downstream recovery is reached. IM 503 is injected through the port, not a claim of live-network acceptance. Shutdown/home cleanup completed after observation.

- `pnpm exec tsx /tmp/skill-denylist-migration-review.ts` (`/tmp/skill-denylist-migration-review-r2.log`):

  ```json
  {"status":200,"mode":"explicit_denylist","skills":["blocked"],"calls":["agent.config.operation.status","agent.capabilities.resolve","agent.config.apply"],"persisted":{"skills_selection_mode":"explicit_denylist","profile_version":3}}
  ```

  Same real Fastify/database/ConfigOperations scenario as Round 1, with fixture Gateway responses. App/database closed. Necessary results are embedded rather than depending on temporary-file retention.

### Patch/main-sync impact and retained results

- The unit's source patch only changes the two migration owners and adds their behavioral regressions. The R1-selected Skill provider, busy-selection restriction, canonicalization, Node YAML/apply wiring, member command projection, Web selector/create/detail/preview/chat consumers and native iOS files are unchanged in `11f3ceafc..42a02a49a`; their R1 inspection and applicable component/contract evidence are retained.
- Main's trajectory-navigation work adds `TrajectoryRuns` runtime observation and wraps maintenance subagent launch in `withKnowledgeRun`, which preserves the start return/error and supplies provenance through AsyncLocalStorage. It does not change Skill selection, roots, loading, maintenance prompt/tools/intervals or creation facts. The new trajectory UI package is an expressly documented browser-only exception in current `AGENTS.md` / `SPEC.md`; this unit adds no execution-runtime fork/private import. Main's explicit-release policy affects installer/publication, not Skill migration. Those upstream units were not re-reviewed wholesale.
- Post-sync installation, build and runtime typecheck passed. `/tmp/nano593-sync-runtime-tests.log` records 74 files / 262 tests passed, covering the merged runtime/knowledge/trajectory seams. The build log identifies merge head `08b42eb13`; final `42a02a49a` only adds rendered local-design documentation/evidence, so source-test applicability is retained.
- `/tmp/nano593-red-review.log` demonstrates both new regressions failed on the old implementation; `/tmp/nano593-green-review.log` records 17 tests passing after the fixes. No mechanical whole-suite rerun was added by this reviewer; the two independent reproductions directly verify the original failures.
- Web's existing full-tsc `message-pane.tsx:467` failure remains an explicitly retained baseline limitation. Product/physical-device/production acceptance remains outside this report.

### Effective through scoped documentation follow-up

The human user explicitly narrowed delivery to the internal mechanism and cancelled the additional frontend prototype/product-UI acceptance work. `3c09e7f7ea238e8a780a4eac1a6b6e461b38e142` removes those added demonstration assets and simplifies design/runbook; its diff changes no source, tests or delta. The actual validated_at remains `42a02a49a`, and the code-review closure is effective through `3c09e7f7e`. No prototype/must-match/product-UI gate is required by this review under that updated scope. The necessary client representation/preview changes remain within the requested internal configuration contract.

## Author resolutions

两项均确认属于本次改动。主 Agent直接修复：KnowledgeUpdates 按 Agent 捕获迁移错误并报告，保留旧模式供后续连接重试，避免异常传播到 DSH/产品恢复；迁移路由恢复 pending operation 后重读 canonical profile 并继续转换，沿现有序列锁和配置 CAS 完成新操作。两个针对性回归先红后绿（17 tests passed；/tmp/nano593-red-review.log 与 /tmp/nano593-green-review.log），后端 typecheck 通过。尚待独立 closure，不改写 Round 1 verdict。
