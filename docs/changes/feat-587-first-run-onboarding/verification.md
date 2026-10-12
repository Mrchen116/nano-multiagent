# Verification Report: feat-587-first-run-onboarding

## Round 3 — targeted-closure / delta

- `review_round: 3`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05`
- `validated_at: 07f55e7140c0194dae3504ae03126e1e4dbee71a`
- `diff_range: 00dd42398d4b9ec9baf0e136d786299659cf8cd3..07f55e7140c0194dae3504ae03126e1e4dbee71a`
- Modes: targeted-closure, delta, retained corrected-delta reconciliation.
- Verdict: **PASS — 0 CRITICAL, 0 WARNING, 0 SUGGESTION**.
- `requires_full_verification: false`. R1 full coverage and R2 unaffected closure evidence remain applicable. This conclusion covers implementation alignment; independent product acceptance/recording/CI/archive remain separate gates.

### Closure and coherence

| Item | Result | Evidence / contract |
|---|---|---|
| V2-W1 lost Work registration after authorized handoff | closed | `Work.register(metadataOnly)` keeps scope and parent identity for a new revoked registration, retaining existing authorized metadata without accepting revoked title/content. The append path retains parent/child identity for session links, then acknowledges revoked events before event insertion/projection/broadcast. The exact R2 owner/space handoff sequence now accepts company seq3 and private seq4 and proves the revoked title is absent. S2/S5/S8/S11, fixed-space Work and whole-device handoff contracts are restored. |
| V2-W2 completion view hides subsequent offline state | closed | `step` checks actual offline state before the selected step. The same mounted page test creates successfully, receives offline state, then shows computer recovery and no start-task button. Existing initial-offline and connected-model tests still pass. S5/S8/S11 and prototype recovery requirement restored. |
| Private task guidance contradicts fixed space | aligned | System prompt and tool description now distinguish private owner plans from company-shared plans and state that join/target cannot publish or change space. IM and Gateway task graph deltas already require this. No routing, schema, permissions or approval flow changed; native ordinary deletion allow/deny behavior independently passes. Product reviewer owns the actual model-created private plan journey. |
| R1 W1/W2/W3 | retained closed | Revised Work metadata recovery closes the remaining R2 failure. Discovery refresh and transactional official Node staging remain unchanged and retain R2 tests. Existing two generated profile-link repairs also remain unchanged and retain R2 migration/native-initialize evidence. |
| Architecture and prototype | retained | Package boundaries and public DSH integration are unchanged; no second loop/server or private upstream imports. Offline fix restores the must-match recovery row. Remaining R1 scenario/design/reference mappings are retained. |

### Independent R3 evidence

| Command / inspection | Result |
|---|---|
| `pnpm exec vitest run apps/im-server/tests/tenancy.test.ts apps/im-server/tests/control-work.test.ts --maxWorkers=1 --no-file-parallelism` | 6 passed, 4.05s; mixed-scope discard/no-replay and post-handoff continuation included |
| `pnpm exec vitest run apps/im-server/tests/e2e/control-work.test.ts --maxWorkers=1 --no-file-parallelism` | 4 passed, 5.24s; real isolated socket transport and Work coverage |
| frontend `pnpm exec vitest run src/features/onboarding/onboarding-page.test.tsx --maxWorkers=1 --no-file-parallelism` | 6 passed, 1.49s; new same-component transition plus prior behavior |
| `pnpm exec vitest run packages/dsh-integration/tests/task-graph-permission.test.ts --maxWorkers=1 --no-file-parallelism` | 1 passed, 1.52s; isolated native tool allow/deny regression |
| `git diff --check 00dd42398..07f55e714` | passed |
| `.dsh-runtime/onboarding-e2e/web-final.log`, read-only reuse | 88 files / 833 tests passed, 62.58s; not independently rerun |

The first combined IM command included a nonexistent `tests/control-work.test.ts` filter; Vitest ran only tenancy (6 tests). The corrected `tests/e2e/control-work.test.ts` command above independently ran the other 4; no missing file is represented as a pass.

Frozen source `07f55e714` was checked against the shared checkout: only acceptance.md differed at inspection. No build, service restart, implementation/test edit or product journey was performed. Focused tests cleaned their own temporary homes/processes, and existing `output/` was preserved. Seven delta files have no R3 semantic/text changes; the single current reconciliation below supersedes the historical implementation-mismatch results while retaining both prior reports.

## Round 2 — targeted-closure / delta

- `review_round: 2`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05` (`origin/main`, caller's fetch result retained)
- `validated_at: 00dd42398d4b9ec9baf0e136d786299659cf8cd3`
- `diff_range: 59650f196642afbbc63f1475c0b874a6b1dc6ea9..00dd42398d4b9ec9baf0e136d786299659cf8cd3`
- Modes: targeted-closure, delta, retained corrected-delta reconciliation.
- Verdict: **FAIL — 0 CRITICAL, 2 WARNING, 0 SUGGESTION**.
- `requires_full_verification: false`: the two surviving deviations are bounded by this patch's Work recovery and onboarding offline repair. R1's unaffected implementation coverage remains applicable.

### Closure and new delta

| Item | Current result | Evidence / contract |
|---|---|---|
| R1 W1 suspended company journal blocks personal work | closed for the original trigger | `Work.append` now acknowledges revoked records without persisting or broadcasting their content. Existing mixed-scope regression covers private seq2 and prevents discarded seq1 replay after later eligibility changes. New recovery defect V2-W1 below remains. |
| R1 W2 discovery fixed for lifetime | closed | `ModelSetup.handle` rediscovers for each status; absent-to-available fixture passes without node restart. S6/S8/S11 preserved. |
| R1 W3 interrupted official Node extraction | closed | Installer extracts in a temporary directory, verifies Node/npm, then marks and promotes. Independent actual-shell failure/retry regression passes. S4/S5 preserved. |
| Product R1 duplicate already-connected model test | closed at code/API seam | Proxy/API model IDs and existing native Codex provider disable duplicate connect operations while the verified model keeps Continue enabled; existing-model Web regression passes. Independent product R2 owns final UI acceptance. |
| Product R1 offline assistant falsely ready | partial; WARNING V2-W2 | Initial offline mounting now selects computer recovery, but successful creation sets `viewStep=3`, overriding later offline query state in the same page. |
| Existing profile links retain old release | closed | `prepareProfile` replaces only its two generated symlinks when targets differ; generated link migration regression independently passes. Caller records actual old-release duplicate `web_fetch` initialization failure and successful official DSH initialize after repair. This is an installation recovery implementation detail within existing design decision 5, as recorded in the design supplement. |

### V2-W1 — Lost registration blocks work after an authorized device handoff

- Contract: S2/S5/S8/S11; `specs/im/auth-tenancy.md` personal use remains available; `specs/im/agents-nodes.md` full-device handoff preserves Agent/runtime continuity; `specs/im/agent-work.md` authorized users receive continuing Work. Design decisions 2, 3 and 5 require fixed-space access and recoverable persistent state.
- Location: `apps/im-server/src/work.ts:121–124`. A revoked `session_registered` is acknowledged with no server-side session, and future records require that missing session. `packages/personal-assistant/src/inbox.ts:149–156` retains event identity and advances the ACK; `GlobalAgent.main` emits the same stable registration ID, which InboxStore deduplicates.
- Independent reproduction uses actual IM Work/database and the owner/space mutation performed by `Identity.deviceCommit:830–849`: company registration seq1 is discarded while its owner is suspended; private registration seq2 succeeds. A different active approved member receives that same node (both profiles' owner changes, personal space follows its recipient). Company turn_started seq3 and private turn_started seq4 then throw `scope_not_allowed`, leaving journal through_seq=2 and private seq4 absent. The fixture exercises the server recovery seam and exact ownership transformation, not browser/local transfer confirmation; the actual transfer code establishes reachability.
- Action: make required registration recoverable when eligible work resumes after handoff without replaying content produced while revoked. Add a regression that advances beyond the discarded registration and proves later private work still succeeds. Merely replaying the original discarded batch, as the current test does, misses this failure.

### V2-W2 — Completion view hides subsequent offline recovery

- Contract: S5/S8/S11, `specs/im/agents-nodes.md` recoverable continuous setup, and the prototype's offline/recovery must-match row.
- Location: `src/IM/frontend/src/features/onboarding/onboarding-page.tsx:62–63`, with `create.onSuccess:80`. Changing `suggestedStep` does not override explicit `viewStep=3` after creation.
- Independent actual-component reproduction: render OnboardingPage with real React Query/router and API mocks; start online with a verified model; click Create successfully; leave that component mounted; replace onboarding response with an offline node and invalidate its query. Assert cached node status is offline, the ready heading remains, Start your first task remains enabled, and the reinstall/reconnect instruction is absent. All four failure assertions passed. The existing new offline test only mounts an already-offline state and passes, so it does not protect the transition.
- Action: give actual offline status precedence over the completed-step selection and protect this same-component transition through a behavioral test. Keep the existing initial-offline and connected-model tests.

### Independent verification evidence

| Command / exercise at frozen snapshot | Result |
|---|---|
| `pnpm exec vitest run apps/im-server/tests/tenancy.test.ts apps/node/tests/model-setup.test.ts apps/node/tests/installer.test.ts --maxWorkers=1 --no-file-parallelism` | 3 files, 12 passed, 7.25s |
| `pnpm exec vitest run packages/dsh-integration/tests/runtime-profile.test.ts -t repoints --maxWorkers=1 --no-file-parallelism` | 1 passed, 2 unrelated real-runtime tests skipped, 183ms |
| frontend `pnpm exec vitest run src/features/onboarding/onboarding-page.test.tsx --maxWorkers=1 --no-file-parallelism` | 5 passed, 1.15s |
| Temporary actual OnboardingPage offline-transition fixture | 1 passed, 5 skipped, 1.12s; assertions establish V2-W2's failure state |
| Temporary actual IM Work handoff-resume fixture | 1 passed, 5 skipped, 862ms; assertions establish V2-W1's rejected append and blocked private event |
| `git diff --check 59650f196..00dd42398` | passed |

Both temporary fixtures were removed. No production services, credentials, implementation or existing tests were changed by this verifier. The shared checkout began with only untracked `output/`; caller-owned edits appearing during report writing are excluded from this frozen review and will not be staged.

Reused versioned M1 progress evidence for the broad backend 178-test baseline, recovery and Work/trajectory tests, native setup/cold restart, Web fixture repair/build/audit, Python/architecture/Ruff, root build/typecheck and iOS test/archive. No broad suite competed with caller's browser/video work. Product R2, complete journey recording, CI, current-spec merge and archive remain their owners' gates; pending artifacts are not missing implementation findings. The unrelated upstream 502/empty-stream reply observed in M1 has separately recorded later successful real replies and is not reclassified as an offline setup regression.

## Round 1 — retained historical report

The following was the full-verification conclusion at `59650f196`; current closure and verdict are above. Its corrected-delta table is maintained once, in the current reconciliation below.

> Validation snapshot: `b70d4a7bd80b → 59650f196642afbbc63f1475c0b874a6b1dc6ea9`
> Modes: full, including corrected-delta reconciliation. Independent reviewer; no implementation, test, configuration or design edits.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All 12 first-document scenarios have implementation; S2/S5/S8 recovery has defects below |
| Correctness | 3 confirmed blocking deviations; no other surviving findings in the 71-file implementation diff |
| Coherence | Package/DSH boundaries followed; mixed-scope Work recovery needs correction |
| Corrected delta | implementation-mismatch |
| Verdict | FAIL: 0 CRITICAL, 3 WARNING, 0 SUGGESTION |

`requires_full_verification: false`: this report already reviews the full frozen implementation. Fixes need focused code review and verification of the affected shared Work, installer and discovery paths. Final product acceptance, complete journey video, CI and archival remain caller-owned completion gates; pending artifacts are not classified as missing implementation.

## Scope and evidence

- Read repository AGENTS, documentation routing, architecture SPEC, testing/coding guidelines, applicable current IM/Gateway contracts, unit spec/design, all seven delta files and M1 progress. Reviewed `git diff b70d4a7bd80b..59650f196` across all 71 changed files, including changes to existing tests and iOS compatibility.
- Independently ran `pnpm exec vitest run apps/node/tests/bootstrap.test.ts apps/node/tests/model-setup.test.ts --maxWorkers=1 --no-file-parallelism`: 2 files, 6 tests passed, 3.38 seconds.
- Independently ran `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q`: 11 passed, 0.79 seconds.
- Independently ran `git diff --check b70d4a7bd80b..59650f196`: passed.
- Reused the frozen implementation's [M1 evidence](M1-onboarding/progress.md): actual same-origin installer execution and binding on isolated IM 18489, empty-node bootstrap, real Node→DSH→proxy model verification, real global Agent creation and first reply, frontend build and focused tests, integration tests through locked DSH settings/credentials and cold restart, controlled OAuth notice/cancel. These are supporting evidence; this verifier did not repeat the browser journey or certify the video.
- Did not run the whole suite concurrently with caller-owned serial IM testing/iOS build. The prior broad concurrent IM timeout is not treated as a product failure or a passing final suite.
- Independent reproductions used frozen compiled modules, temporary fixtures and stubbed external/runtime inputs as described below. They establish the local failure mechanism, not third-party OAuth acceptance. No production services or credentials were changed; verifier-owned fixture data was removed. Existing `output/` was preserved.

## Completeness

M1 has implementation for personal tenancy, installer/bootstrap, async model setup, guided creation, chat handoff and native account compatibility. Worker validation is substantially evidenced above. M1's final reviewer/video/CI exit criteria remain to be completed by their designated owners; this report does not substitute for them.

| Scenario | Implementation and regression evidence | Result |
|---|---|---|
| S1 independent usable personal account | `identity.ts:251`, `db.ts:10`, `messaging.ts:612`; tenancy registration/contacts/task/Work isolation test | covered |
| S2 explicit company approval, personal use continues | `identity-routes.ts:189`, `identity.ts:471`, fixed resource spaces; tenancy approval/suspension test | WARNING W1: mixed-node pending Work blocks private work after suspension |
| S3 local Agent installation prompt | `onboarding-page.tsx:100`, same installer materials; current origin comes from `install.ts:12` | implemented; independent Agent-driven product proof remains reviewer-owned |
| S4 manual installation | `assets/install.sh`, `build-node-release.mjs`, `bootstrap.ts`, `cli.ts`; actual isolated installer run in M1 evidence | covered within observed macOS environment; Linux/WSL instructions are implementation-reviewed |
| S5 repeat installation/offline recovery | origin-scoped config and stable identity in `bootstrap.ts`; complete application release directory promotion in installer; bootstrap/device-binding tests | WARNING W3: official Node extraction is not transactional |
| S6 native Codex/local proxy | `node/model-setup.ts`, `dsh-integration/model-setup.ts`; real proxy call and controlled native OAuth test | implemented; W2 affects newly repaired discovery |
| S7 API/custom model test and local credential persistence | Node `run`, integration `test/finish`, DSH credentials, nonsecret `persistModels`; integration real HTTP/failure/restart test | covered |
| S8 failure and recovery | async operation states, sanitized failures, rollback and retry UI | WARNING W2: detection result never refreshes after local repair |
| S9 guided assistant | purpose/name/goal/workspace preview, existing create operation, global mode, heartbeat/cron off; frontend retry/ID test | covered |
| S10 first real work | actual createConversation and chat draft handoff; M1 records real reply and persisted history | implemented and directly evidenced; final video belongs to product review |
| S11 refresh/login recovery | actual node/model/Agent queries, owner-keyed nonsecret draft, stable candidate ID; frontend reopen/retry tests | covered except W2's stale discovery snapshot |
| S12 existing users, languages, narrow screens | accountEnabled compatibility, deep-link route, responsive CSS, bilingual controls, iOS optional flag/test | implemented; final visual/narrow-screen acceptance belongs to product reviewer |

### Test maintenance

Existing identity/control/device-binding and Web auth/company tests were extended at their established seams. iOS SessionTests adds optional-field/legacy account compatibility. New bootstrap, Node setup, native integration setup, IM onboarding and tenancy files have distinct owners and observable risks. No test was removed merely to bypass a failure. Missing mixed-scope journal, discovery recovery and interrupted runtime extraction protection is addressed in W1/W2/W3.

## Correctness

### W1 — Revoked company Work blocks otherwise authorized private work

- Contract: first-document S2 and S8; delta `specs/im/auth-tenancy.md`, "停用立即覆盖真人与机器" (personal space remains usable), and `specs/im/agent-work.md` (Work follows the Agent's fixed space). Design decisions 1–3 preserve personal eligibility independently of company membership.
- Location: `apps/im-server/src/work.ts:98`. `GlobalAgent.flushWork` (`packages/personal-assistant/src/global-agent.ts:309`) sends the single node-wide journal; `main` awaits flush at line 55 before `receive` can wake the private model at lines 80–81.
- Reachable setup: transfer an existing company node to an active personal-enabled company member, then create a private global Agent on it. Suspend company membership while a company event is still unacknowledged (for example while the node is offline). The machine remains valid for personal resources, but the queued company event fails agentAvailable.
- Reproduction A: real IM Work service, two global profiles on one node, owner `personal_space_enabled=1/membership_status=suspended`, shared journal seq1 company and seq2 private. Append fails `scope_not_allowed`; private-only seq2 returns `{journal_id:'shared',through_seq:0,expected_seq:1}`; private Work sessions count is 0.
- Reproduction B: real InboxStore/NodeStore/GlobalAgent and the same IM Work seam; put a company event in InboxStore journal, then call public `GlobalAgent.receive` with a private input. Runtime is stubbed only to record method calls. Output: `private receive failed: scope_not_allowed`; calls `[ 'session.ensure' ]`; `session.submit` false. This confirms private replies are blocked, beyond a missing display projection.
- Action: preserve the company authorization refusal while making journal progression/recovery independent for still-authorized private work. Add a mixed-scope revocation regression proving a pending company record cannot prevent a private `receive` from reaching submission and private Work delivery. Do not relax company access to make the journal pass.

### W2 — Local connection discovery cannot recover after first observation

- Contract: first-document S6/S8/S11; delta `specs/im/agents-nodes.md`, "页面完成模型连接 / 验证与失败恢复"; design decision 6 (reuse detected local connections) and decision 8 (recoverable setup).
- Location: `apps/node/src/model-setup.ts:64`: `this.discovery ??= this.discover()` memoizes the successful absence result for the whole node lifetime.
- Reproduction: construct ModelSetup with a discovery fixture initially returning `{codex:false}`; call public `handle({action:'status'})`, make a valid proxy available in the fixture, call status again. Both snapshots remain `{codex:false}` and discovery invocation count remains 1. Browser refresh creates no new node ModelSetup, so polling, query retry and re-login cannot repair this.
- Action: introduce bounded discovery refresh or an explicit rediscovery action reachable from the page. Protect absent/stopped→available recovery through the public setup status seam without requiring a node restart or manual API configuration.

### W3 — Interrupted official Node extraction poisons the advertised retry

- Contract: first-document S4/S5 and delta `specs/gateway/service-lifecycle.md`, "重复与失败": repeat/download/dependency failure preserves existing data and offers a working continuation, without selecting an incomplete version. Design decision 5 requires preparation before promotion.
- Location: `apps/im-server/assets/install.sh:29–30`. The existence test checks only executable final `bin/node`, while `tar` writes directly into that final runtime directory. The application's own release staging is transactional, but the downloaded Node runtime is not.
- Independent reproduction ran the actual frozen shell script with a PATH containing no Node/npm and local curl/tar fixtures. The fixture writes the expected official archive checksum; extraction creates executable final `bin/node`, then returns a simulated disk-full failure. Attempt 1 exits 1 and advises running the same command; attempt 2 skips extraction and exits 127, `npm: command not found`. No network download was performed. This proves the recovery mechanism under interrupted extraction, without asserting the extraction order/state of the separate product review's real disk-full run.
- Action: extract into a temporary runtime directory, validate required Node/npm entrypoints and promote after successful extraction. Recognize a completion marker rather than a partially written executable. Add a bounded installer failure/retry regression; preserve already complete versions and user configuration.

## Coherence

| Design decision | Evidence / conclusion |
|---|---|
| Personal account separate from company eligibility | `accountEnabled/defaultSpace/canAccessSpace` plus explicit join and admin checks; followed |
| Fixed spaces plus existing object permissions | migration, conversation participant checks, Agent owner/config checks, task receipts, Work and trajectory gates; followed except W1's shared recovery coupling |
| Revocation across HTTP/WS/async returns | requireSpace request scopes, browser replay/broadcast gates, setup owner recheck and connection-correlated Gateway pending replies; followed |
| One same-origin release and installer | build allowlist, SHA manifest, server-configured origin, 503 when absent; followed |
| User/IM-scoped bootstrap, repeat preservation | private config writes and per-origin directory, no sudo/global npm changes; W3 affects downloaded runtime recovery |
| DSH public native/API integration | only integration imports DSH public dependencies; dependency contract 11/11 passed |
| Node routes, DSH credentials and real verification | provider map initialization, async test, rollback, atomic nonsecret config; followed |
| Queryable long setup | one operation, notice/cancel/status, test outside IM request lifetime; followed; W2 affects recovery metadata |
| Guided real assistant/chat | existing create operation, stable retry ID, private default, genuine conversation and editable starter; followed |

### Prototype / Reference Contract

The six must-match rows all project into M1 and have corresponding real implementation. The verifier checks the evidence chain, not aesthetic quality.

| Reference contract | Milestone projection / implementation | Evidence status |
|---|---|---|
| Four steps/current main action | M1 S1–S12; OnboardingPage step state and standalone route | implemented; final real screenshots/visual review caller-owned |
| Two installation choices/copy/offline | M1 installation/recovery; same installMaterials and copy routine, offline guidance | actual installer in M1 evidence; W3 affects extraction failure/retry; independent prompt execution still reviewer-owned |
| Model sources/testing/error | M1 model/OAuth tests; discovery, API form, async state and cancellation | direct tests/proxy success; W2 blocks repaired discovery |
| Team application | M1 tenancy matrix; join page and company:default gates | direct tenancy regression; W1 blocks mixed-node personal use after suspension |
| Purpose/name/goal/device/path | M1 guided creation; form and actual workspace projection | frontend behavior test and real creation in M1 evidence |
| First real chat/reentry | M1 first reply/video; existing conversation reuse and starter draft | actual reply/history in M1 evidence; final recording pending separately |

## Corrected Delta Reconciliation

Current snapshot: `07f55e7140c0194dae3504ae03126e1e4dbee71a`. All seven corrected delta files remain unchanged from R1/R2. The table below explicitly retains previously verified unaffected coverage and closes affected implementation deviations; no delta was rewritten to fit a bug. R1/R2 summaries above are historical verdicts.

| Delta file | Current implementation / regression conclusion | Outcome |
|---|---|---|
| `specs/im/auth-tenancy.md` | R1 immediate registration, explicit company join, fixed spaces and native optional eligibility coverage retained. Work metadata-only recovery prevents blocked personal events after revocation and later approved-owner handoff. | aligned |
| `specs/im/agents-nodes.md` | R2 discovery/connected-model/profile-upgrade closure retained. R3 actual offline precedence and company/private Work handoff continuation now pass their behavioral regressions. Whole-device ownership/data boundary coverage retained. | aligned |
| `specs/im/agent-work.md` | R1 read/subscription/trajectory authorization retained. Revoked event contents are not stored/projected/broadcast; minimal registration structure allows later authorized continuous Work. Mixed-space and real socket tests pass. | aligned |
| `specs/im/task-graphs.md` | R1 fixed-space actor, receipt, source and transfer isolation retained. R3 guidance now correctly describes private owner plans and company plans without changing enforcement. | aligned |
| `specs/gateway/service-lifecycle.md` | R1 bootstrap/identity/config persistence plus R2 transactional official Node staging and generated-profile-link migration retained; no lifecycle source changed in R3. | aligned |
| `specs/gateway/agent-capabilities.md` | R1 local credential/real-model/native/API validation and R2 discovery-refresh closure retained; no capability implementation changed in R3. | aligned |
| `specs/gateway/task-graphs.md` | R1 fixed-space effective capability and Gateway identity checks retained. Corrected task guidance matches the existing contract; native ordinary deletion permission regression passes unchanged. | aligned |

### Uncovered Observable Behavior

- R1 branding, compatible proxy discovery, retry timing and optional native iOS eligibility remain accounted for in existing design/delta scope; no native onboarding is claimed.
- R2/R3 Work acknowledgment and minimal session-structure retention implement authorization and continuous recovery. They do not preserve or replay revoked content and introduce no new user-facing data-access contract.
- Runtime staging/generated-link migration, connected-model reuse and actual offline precedence implement existing install/setup recovery requirements. Task wording restores the already specified private/company split; it adds no new scheduling, mutation or approval behavior.
- No additional material public behavior omitted from the seven corrected deltas was found within this patch. Unaffected R1 full-diff coverage remains retained; current-spec merge is caller-owned at completion.

Outcome: **aligned**. `requires_full_verification: false`; no surviving implementation deviation in the requested R3 scope.
