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

## Author resolutions

两项均确认属于本次改动。主 Agent直接修复：KnowledgeUpdates 按 Agent 捕获迁移错误并报告，保留旧模式供后续连接重试，避免异常传播到 DSH/产品恢复；迁移路由恢复 pending operation 后重读 canonical profile 并继续转换，沿现有序列锁和配置 CAS 完成新操作。两个针对性回归先红后绿（17 tests passed；/tmp/nano593-red-review.log 与 /tmp/nano593-green-review.log），后端 typecheck 通过。尚待独立 closure，不改写 Round 1 verdict。
