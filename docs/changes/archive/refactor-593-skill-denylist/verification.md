# Local verification

Implementation branch: `codex/skill-denylist`, base `74bfff7f7118ed040f270491691f31f992393793`.

- A new SkillSourceSelector denylist test failed against the original component: a disabled item was rendered enabled. The same regression now passes.
- `pnpm build` and `pnpm typecheck`: passed for all runtime packages/apps.
- `pnpm exec vitest run --maxWorkers=4`: 71 files / 241 tests passed. The native DSH capabilities regression creates a session, copies a new Skill onto disk, loads its body with the real `skill` tool, verifies disabled loading fails, then restarts and verifies both states persist.
- Migration HTTP tests cover old default discovery, selected allowlist and empty allowlist; verify persisted mode/names, canonical fingerprint and idempotent retry.
- Web Vitest: 91 files / 856 tests passed. After adding the extra denylist preview case, the detail-page suite passed 21 tests. Create/edit/source selector/API/SlashPicker all use the new representation.
- Web Vite bundle: passed. Full Web TypeScript check reports the existing `message-pane.tsx:467` timer typing mismatch. The same compiler invocation on unchanged main reports the identical error; this change leaves that unrelated file untouched.
- iOS Simulator build: passed. `NanoIMTests/AgentContractsTests`: 7 tests passed, including disabled-name persistence, future-name default enablement and preview payload semantics. No physical-device acceptance claimed.
- Documentation integrity and `git diff --check`: passed.

## Delivery state

Local implementation only. No production configuration, service or deployment was changed. This side conversation prohibits subagents, so independent design/code/product gates have not run; no approval or PR-readiness is claimed. Keep the unit active for that review.

## Migration boundary

Old allowlists did not record the historical candidate set. Migration preserves the choice of every candidate present at migration time; it cannot infer whether an unselected candidate was added after the user's last edit. Once converted, future names default enabled and known disables survive restarts. Offline nodes retain legacy behavior until their authenticated IM migration completes.

## Separate finding

Ordinary background Skill review may modify F1 skills; automatic per-Skill batch review and inactivity archival are limited to F3/F4. This matches Hermes' distinction at the level discussed here; the new Hermes read-before-write enforcement is not part of this selection change. No evolution policy was changed.

## Independent Verification — Round 1

| Field | Value |
|---|---|
| unit_id / review_round | `refactor-593-skill-denylist` / `1` |
| verification_mode | `full` |
| executed_base | `74bfff7f7118ed040f270491691f31f992393793` |
| validated_at | `11f3ceafc6ffffc22dfe88b4684bab01d94de957` |
| verdict | **FAIL — 1 CRITICAL, 2 WARNING, 0 SUGGESTION** |
| requires_full_verification | `false` (this round already covered the full unit) |
| report_commit | None; shared worktree reports handed to caller for commit |

The reviewer independently inspected the frozen implementation and reused applicable same-HEAD test evidence. Only reports were edited. The original Local verification, delivery boundary and migration limitation above are retained as historical implementation evidence. Implementation happened before the independent design review currently being supplemented; neither this verification nor that later review retroactively proves pre-implementation Gate 2 approval.

### Completeness

- M1-selection is implemented across contracts, DSH selection, Node/IM configuration, Web and native iOS, but its migration/recovery exit condition is blocked by C1/W1 below.
- All three motivation Requirements have implementation seams. New-name discovery and persistent disables have direct native DSH tests; migration success cases have HTTP/operation tests. Failure/recovery migration cases were independently reproduced and fail.
- `design.md` declares no layout reconstruction, retaining existing groups/pills/batch actions with a new default-on hint. No prototype or explicit must-match comparison table exists; prototype/reference contract is N/A for this verifier. Browser visual/product acceptance remains the separate product-reviewer's responsibility.
- Required unit delta-spec is absent at this snapshot. Caller explicitly owns completing it. Current IM spec still contains contrary legacy behavior; see W2. No claim of corrected-delta alignment is made.

### Correctness

| Requirement / Scenario | Implementation evidence | Test / observation | Result |
|---|---|---|---|
| New valid Workspace/global names default available without restart | `packages/dsh-integration/src/capabilities.ts:99-117` uses one deny predicate for native provider list/get; filesystem watching retained | `packages/dsh-integration/tests/capabilities.test.ts:117` creates a Session, writes a Skill, observes discovery and executes real native `skill`; same-Session import/restart passed in 241-test suite | Covered at native execution seam; not full product acceptance |
| Roots precedence and Agent scope retained | `apps/node/src/configuration.ts:85-92`; unfiltered settings catalog `capabilities.ts:60-67` keeps first name by ordered root | Existing runtime/source tests retained; no roots change in diff | Aligned |
| Disabled name absent from model/list/get/explicit gestures | `capabilities.ts:99-117`; explicit invocation uses selected `ctx.skills.get` at `:88` | Native copied-Skill test observes blocked tool execution before/after restart; existing explicit invocation seam unchanged | Aligned |
| Busy Session immediately withdraws rights while additions wait for idle | `packages/dsh-integration/src/agent-config.ts:76-84` unions deny names, subtracts new denies from legacy allows, invalidates native providers; `index.ts:390-397` waits idle before full replacement | Existing busy native capability regression retained; denylist transition additionally inspected statically | Aligned; no claim of live busy IM acceptance |
| Preview/SlashPicker/distillation use the same effective set | Node preview mode at `apps/node/src/main.ts:102`; Web preview at `agent-detail-page.tsx:161-162`; `slash-candidates.ts:85`; member commands `apps/im-server/src/conversation-actions.ts:161`; PA readiness `history.ts:123-135` uses configuration.selection | Web suite 856 tests + detail suite 21; native capabilities selection supplies backend shared seam | Aligned |
| Web/iOS save取消项, preserve temporarily absent disables and future names | `skill-source-selector.tsx:57-67`; `AgentModels.swift:69-81`; create defaults denylist, previews carry mode | SkillSourceSelector/create/edit/detail tests; 7 iOS AgentContractsTests including future names/hidden disables | Aligned at component/contract seams |
| Legacy default/selected allowlist/empty allowlist convert once | `apps/im-server/src/control.ts:787-812`; real full candidate catalog requested by `apps/node/src/main.ts:110` | HTTP table covers three success cases and idempotency; pending old config operation probe returns 200 **without** migration | **W1** |
| Versioned Node YAML/runtime/IM mirror agreement | `packages/personal-assistant/src/configuration.ts:44-76` fingerprints + durable receipt/persist/apply; `apps/node/src/main.ts:219-229`; atomic YAML write `configuration.ts:157-175`; IM commit `control.ts:334-441` | Existing configuration tests + migration canonical fingerprint assertion; actual interrupted-operation reproduction | Mechanism reused correctly; completion blocked by W1 |
| Offline/transient migration failure preserves usable legacy runtime | `apps/node/src/main.ts:53,155`; `knowledge.ts:67-74` does not catch migration failure | Real RuntimeSupervisor + KnowledgeUpdates 503 probe exits initialized child, available=false | **C1** |
| Creation facts do not override same-name disable; evolution/tool policy unchanged | `packages/personal-assistant/src/knowledge.ts:43-63` retains notifications/ack, removes enable side effect; provider filters still apply by name | `packages/personal-assistant/tests/knowledge.test.ts:10` confirms disabled names unchanged and notices retried; no policy code changed | Aligned |

### Coherence

| Design decision | Evidence / outcome |
|---|---|
| Keep existing `skills` field, add explicit_denylist, reuse fingerprint/config operation | Product contracts + IM/Node canonicalization include mode; no parallel persistence or config API was introduced |
| Preserve native discovery/registry/catalog rather than a second scanner | `FileSystemSkillProvider` public integration, watch and ordered catalog retained; filters applied to list/get |
| Authenticated migration uses full real Agent candidates and CAS | Gateway token, owner/node checks, actual capability request and existing operation owner reused; W1 means recovered old operations can terminate this flow prematurely |
| Offline remains legacy until authenticated conversion | Initial startup with relay not ready avoids conversion; C1 shows connected transient failure instead aborts recovery, inconsistent with the intended safe migration boundary |
| UI selected means enabled; hidden disabled names retained | Existing denylist arrays are used directly and toggles preserve absent names; both Web/iOS carry mode through previews |
| Creation only records/notifies; no automatic re-enable | Side effect removed, remaining facts/receipts preserved; no changes to evolution F1/F3/F4 policy |
| Package architecture | No new dependency, private export, upstream patch, HTTP kernel or second Agent loop in this diff; SPEC dependency direction remains intact |

### Issues

**C1 — CRITICAL: migration failure can kill otherwise healthy runtime recovery.** `apps/node/src/main.ts:53` awaits migration inside RuntimeSupervisor.onReady; `packages/dsh-integration/src/client.ts:116-122` shuts down initialized DSH on any callback rejection. A remaining legacy Agent plus HTTP 503/timeout/CAS rejection therefore prevents normal product recovery; recurring errors exhaust the three-attempt budget. `main.ts:155` also skips the remaining ready-recovery actions after this failure. This violates the safe legacy/offline boundary and M1 runtime completion. Separate migration failure/retry from execution/channel recovery, retain old mode until authenticated migration succeeds, and add the narrow failure regression. Direct output from the real-child probe is embedded in [code-review.md](code-review.md), with method and limits.

**W1 — WARNING: recovering an unrelated old operation is reported as successful migration.** `apps/im-server/src/control.ts:801` returns before conversion. Real Fastify + ConfigOperations reproduction: HTTP 200, explicit_allowlist, `[keep]`, profile_version 2, only agent.config.operation.status called. Node's caller at `packages/personal-assistant/src/knowledge.ts:72` accepts this result and schedules no further attempt while this connection remains ready. Reload the committed profile and complete conversion, or make the incomplete outcome explicitly retryable; preserve CAS semantics and test pending legacy-operation recovery. This fails motivation “旧选择保真迁移” and design M1 migration completion.

**W2 — WARNING: delta-spec and canonical reconciliation are incomplete.** At `11f3ceafc`, unit `specs/` is absent, although `docs/development/change-workflow.md:106-109,192` requires the Full delta and independent final alignment. Changed current `docs/specs/im/agents-nodes.md:770` says saves use denylist, but `:439-458` still says first selection editing uses explicit_allowlist and reconnect does not write mode. The latter contradicts this implementation's authenticated reconnect migration. Add the caller-owned delta, reconcile the superseded requirements/legacy boundary explicitly, and perform corrected-delta verification before current-contract merge/closeout. Do not change intended behavior to fit the old text.

### Reused and independent evidence

- Retained same-implementation runtime build/typecheck; 71 runtime files / 241 tests (`/tmp/nano-skill-denylist-full-final.log`); Web 91 files / 856 tests (`/tmp/nano-skill-denylist-frontend-final.log`) plus 21 detail tests; Vite bundle; iOS simulator build and AgentContractsTests 7 tests (`/tmp/nano-skill-denylist-ios-tests.log`). These pass the normal paths, not C1/W1.
- Full Web tsc is **not** green: existing `message-pane.tsx:467` number/Timeout error has matching unchanged-main reproduction `/tmp/nano-skill-denylist-frontend-baseline.log`. This file is outside the diff.
- Independently reproduced C1 and W1 using actual product owners and native DSH process where relevant; exact outputs/method/limits are durably embedded in [code-review.md](code-review.md). Temporary child/home/app/database were cleaned up; no persistent service was started.
- `git diff --check` passed before report writing. No production, physical iPhone or full browser/IM/Node journey acceptance is claimed. Independent design review is in progress elsewhere.

Top concern: remote migration availability must not own execution recovery; fix C1/W1 and reconcile delta/current contracts before PR readiness.

## Independent Verification — Round 2

| Field | Value |
|---|---|
| unit_id / review_round | `refactor-593-skill-denylist` / `2` |
| verification_mode | `targeted-closure` |
| executed_base | `d07c7578f210ee7fe830e2e7de4407209e7c75fc` |
| validated_at | `42a02a49ae7f4c52221616d600286bb30aac4cb7` |
| fix_delta_range / finding origin | `11f3ceafc..42a02a49a` / Round 1 |
| focus_issues | `C1`, `W1`, `W2` |
| verdict | **PASS — 0 CRITICAL, 0 WARNING, 0 SUGGESTION in this scope** |
| requires_full_verification | `false` |
| report_commit | None; shared-worktree reports handed to caller |

This pass closes the assigned static issues and verifies the supplied final delta. It does not rewrite the original Round 1 chronology. The user's later explicit scope correction cancels the extra prototype/product-UI gates; the internal logic and necessary client configuration representation remain in scope.

### Validated Issues

| Issue | Result | Contract, implementation and direct evidence |
|---|---|---|
| C1 — migration failures kill DSH recovery | **closed** | Design now explicitly keeps migration failure from blocking other Agents/runtime. `packages/personal-assistant/src/knowledge.ts:70-77` reports each failure and returns normally. Actual RuntimeSupervisor + KnowledgeUpdates/native DSH probe: `available=true`, `recoveryContinued=true`, `unavailable=0`, child `exitCode=null`, old explicit_allowlist preserved and 503 reported. The added regression covers cross-Agent continuation and retry on the next migration call. Production `onError` is supplied in both wiring and the closure probe. |
| W1 — pending old config recovery skips migration | **closed** | `apps/im-server/src/control.ts:798-812` reloads the recovered canonical profile and continues under the same serialized lock. Real Fastify/ConfigOperations probe: HTTP 200, explicit_denylist, `[blocked]`, version 3, requests status → full catalog → config apply. Existing durable operation still owns expected-current fingerprint/CAS. Recovery adjusts the stale pre-recovery profile-version input by operating on the newly committed profile; ordinary stale calls remain rejected. |
| W2 — missing delta and contradictory prematurely changed current | **closed for pre-merge reconciliation** | Both unit delta files now exist, replace the superseded allowlist Requirements, preserve unchanged modified-Requirement scenarios and explicitly express empty-selection/new-name, offline legacy and distiller-unavailable boundaries. `git diff d07c7578..42a02a49a -- docs/specs` is empty: current remains the merged-main baseline pending reviewed-delta integration. Old current text is therefore no longer a premature claim of this unit's target state. Corrected-delta results are below; caller still owns applying the verified delta during closeout. |

### Main Sync and Evidence Applicability

- Inspected the source diff and actual shared boundaries introduced by main. Skill providers/list/get, selection restriction, Node migration/recovery wiring, configuration serialization, member-command filtering, Web Skill/preview/chat consumers and all iOS sources are unchanged from the R1 implementation, apart from the two reviewed migration fixes. R1's applicable correct-behavior conclusions are retained.
- Main's `withKnowledgeRun` wrapper at `packages/dsh-integration/src/knowledge/runtime.ts:203` adds launch provenance; its `trajectory-runs.ts:32-34` implementation runs the same supplied start function and propagates its result/errors. Original maintenance history/system/tools, creation/write policy and native cache boundaries remain unchanged. `TrajectoryRuns` is added at runtime initialization; post-sync runtime evidence covers this shared seam. The browser-only trajectory UI exception is now explicit in AGENTS/SPEC and does not expand this unit's execution-runtime access.
- Release/install policy changes and trajectory viewer navigation are outside this unit's behavior; no Skill consumer is redirected through either. No full review of those already-merged upstream units is claimed.
- Retained `/tmp/nano593-green-review.log`: 2 files / 17 tests passed, with both new cases demonstrably red before the fix. Post-sync `/tmp/nano593-sync-runtime-tests.log`: **74 files / 262 tests passed**; install/build/typecheck logs also passed. Build source head is `08b42eb13`; `42a02a49a` only adds design-render evidence, so the runtime source is identical for these checks.
- Re-ran the two critical reproductions independently on frozen `42a02a49a`. Exact outputs and methods are embedded in [code-review.md](code-review.md) Round 2; temporary real DSH process/home and Fastify/database were cleaned up. No source/test/design changes or commits were made by this reviewer.
- Existing Web full-tsc timer mismatch remains the baseline limitation; unchanged Web/iOS component evidence is retained. Live Web/iOS user journeys and production/physical-device acceptance remain separate.

### Updated Scope and Effective Commit

After logic validation, the human user explicitly stated that this is an internal mechanism change and cancelled the additional frontend prototype/product-UI acceptance work. Follow-up `3c09e7f7ea238e8a780a4eac1a6b6e461b38e142` deletes those demonstration assets, simplifies design/runbook and records the scope correction. Inspected `42a02a49a..3c09e7f7e`: no source, tests or delta changed, so `validated_at` stays `42a02a49a` and all logic/corrected-delta conclusions are **effective through `3c09e7f7e`**. Prototype/reference must-match coverage is now N/A by explicit user scope, not an unfinished gate. Historical R1 findings/observations are preserved without treating cancelled UI work as a current blocker. Necessary Web/iOS configuration-field interpretation and preview payload semantics remain covered by their retained contract/component evidence.

## Corrected Delta Reconciliation

- `verification_mode`: `corrected-delta`
- `validated_at`: `42a02a49ae7f4c52221616d600286bb30aac4cb7`
- `executed_base`: `d07c7578f210ee7fe830e2e7de4407209e7c75fc`
- Compared both complete unit delta files to final source/tests and the unit's full observable diff from the executed base. Current docs intentionally remain unchanged until this review is integrated.

| Delta item | Implementation evidence | Test / retained evidence | Outcome |
|---|---|---|---|
| Gateway ADDED Workspace/global denylist — new names and scope/precedence | `capabilities.ts:99-117` filters native watched list/get; `configuration.ts:84-92` preserves ordered scoped roots; `skillCatalog` remains unfiltered for settings/migration | Native real-DSH same-Session import/load/restart regression and existing ordered-root/Agent isolation evidence | aligned |
| Gateway ADDED deny persistence across consumers and same-name recreation | Name-based filter plus provider invalidation; busy withdrawal union/subtraction at `agent-config.ts:76-84`; full replacement waits idle; explicit invocation/preview/readiness/commands all use selected view | R1 native denied loading/restart, existing busy regression, Web preview/selector/commands and iOS contract evidence; sources unchanged | aligned |
| Gateway ADDED legacy migration/default/empty allowlist and transactional persistence | Authenticated owner/node route obtains full candidates then uses existing operation; pending recovery now continues; Node canonical/YAML/runtime/IM commit owners retained | Existing 3-case migration/idempotency/fingerprint coverage; new pending recovery regression; independent version-3 conversion probe | aligned |
| Gateway ADDED creation fact respects disables | PA reconciliation only delivers/acknowledges facts; no enable-list write; provider denies same name regardless of creation origin | Existing knowledge notice-retry/disable-preservation regression | aligned |
| Gateway ADDED distiller-unavailable boundary | `packages/personal-assistant/src/history.ts:123-135` checks effective configuration.selection for conversation-skill-distiller before generating prompt; native selection applies either denylist or retained allowlist | Existing distillation and native selection regressions retained; no bypass in unit diff | aligned |
| Gateway ADDED offline old modes | Node only migrates on authenticated ready; configuration mapping preserves old mode until successful operation; per-Agent failure now reports/continues | Default/explicit-empty native tests retained, failure-isolation/retry regression and real runtime-ready 503 probe | aligned |
| Gateway MODIFIED self-evolution across terminal/reconnect | PA still consumes facts independently of run context, notification receipts/ack remain; no create-enable side effect; same-name deny wins | Knowledge fact recovery regression; merged native knowledge suite included in 262 passing tests | aligned |
| Gateway MODIFIED untouched prompt/tools/Memory/review-counter clauses | Complete unchanged paragraphs/scenarios retained in delta. Maintenance runtime still freezes inherited system/tools; main only adds provenance wrapper | Existing native knowledge/prefix-cache coverage retained and post-sync runtime suite passed | aligned |
| Gateway MODIFIED automatic new-skill prompt-prefix and manual toggle scenarios | Native discovery refresh does not issue configuration.apply from creation facts; manual config replacement keeps existing idle/prompt boundary | Existing knowledge prefix tests and config capabilities tests; unchanged R1 selection mechanism | aligned |
| Gateway REMOVED old default-vs-explicit-empty Requirement | Replaced by new denylist semantics; explicit empty now disables candidates present at save while later new names enable. Old offline default/allowlist and disabled distillation are explicitly preserved in new scenarios | Legacy default/empty tests, three migration cases and future-name default native/iOS tests | aligned |
| IM ADDED save取消项 including hidden disables | Web selector and native setSkill store denies; new drafts empty denylist; existing hidden deny entries retained | Web create/edit/selector tests, native AgentContractsTests | aligned |
| IM ADDED API modes, clear-current-candidates, cache refresh and read-only mirror | Payload/normalization support 3 modes; deselection computes current candidates; successful save retains command-query refresh; mirror GET doesn't write, migration POST owns conversion | Web API/preview/edit/commands evidence; HTTP mode/version operation tests and independent migration probe | aligned |
| IM REMOVED old first-edit allowlist/reconnect-no-write Requirement | Replaced with explicit denylist first-edit and read-only-vs-authenticated-migration distinction. All three old scenario concerns have a corresponding new scenario | Current baseline retained pending merge; delta's replacement accurately matches final client/API/migration behavior | aligned |

### Uncovered Observable Behavior

None within this unit's full diff: defaults, stored selection representation, canonical fingerprints, authenticated legacy migration/failure recovery, creation-fact handling, native discovery/loading, Web/iOS editing, previews and command/distillation consumers are represented. Tool authorization, evolution source policy and upstream trajectory/release changes are not silently recast as this unit's deltas.

Outcome: **aligned**. Static focus issues are closed and conclusions remain effective through the source-identical scope follow-up `3c09e7f7e`; caller may integrate the verified delta and complete the final internal-logic delivery checks. Additional prototype/product-UI acceptance is not required under the user's corrected scope.

## Final integration checks and user scope

User explicitly limited this delivery to the internal mechanism and necessary configuration semantics, cancelling extra UI prototypes and product UI acceptance. No product acceptance verdict is claimed; design/code/consistency review history remains intact.

Final base: `d07c7578f210ee7fe830e2e7de4407209e7c75fc`. Source under test: merge `08b42eb137f06b05d7ac1db36ffff602e58df8b7`; subsequent commits only changed review/design documentation and removed cancelled demonstrations. Corrected delta was independently aligned at `42a02a49a`, with scope retained through `3c09e7f7e`; its canonical merge applies only those reviewed clauses, preserves main's unrelated changes, and updates derived counts/alignment markers.

- `pnpm build` / `pnpm typecheck`: passed; `/tmp/nano593-sync-build.log`, `/tmp/nano593-sync-typecheck.log`.
- Runtime Vitest: 74 files / 262 tests passed; `/tmp/nano593-sync-runtime-tests.log`.
- Web Vitest: 92 files / 859 tests passed; `/tmp/nano593-sync-frontend-tests.log`. Vite bundle passed; `/tmp/nano593-sync-vite.log`. Full Web TypeScript baseline limitation above is unchanged.
- iOS full suite: 28 tests / 0 failures; Release archive succeeded; `/tmp/nano593-ios-all-tests.log`, `/tmp/nano593-ios-archive.log`. No physical-device claim.
- Python: 56 passed / 31 deselected; Ruff check and format passed; documentation integrity passed (237 maintained sources / 64 routes before archive); diff whitespace check passed.
- Independent Round 2 confirmed both migration issues closed using actual Fastify operation recovery and a real DSH child. Code review has no remaining findings; verifier PASS, corrected delta aligned.
- Isolated IM/Node stack was prepared and health-checked, then stopped; cancelled prototype HTTP server and both dedicated Simulators were cleaned. No production process/config or main-checkout file was changed. No production deployment or merge performed.
