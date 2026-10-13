# Verification Report: feat-587-first-run-onboarding

## Round 4 — targeted-closure / delta

- `review_round: 4`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05`
- `validated_at: f881314a469e97178cd91e59a308c0d3625404d9`
- `diff_range: eac3c2ffd7e0c5725b0647faf4aa3eb2f3fa094f..f881314a469e97178cd91e59a308c0d3625404d9`
- Verdict: **PASS for this implementation/contract review — 0 CRITICAL, 0 WARNING, 0 SUGGESTION**.
- `requires_full_verification: false`; R3's seven-delta reconciliation and all unaffected coverage are retained. This is not a product acceptance pass or a claim that product R3 #5 has received real-model green evidence.

### Scope and conclusion

Independent product evidence at `eac3c2ffd` establishes the red condition: ordinary private task request actually created `tg_021a12df`, with correct private isolation, but no `send_message` call or reply in source chat `c_rprqeogj`; Work alone contained the saved-result text. Neither successful mutation nor completed runtime receipt fulfills spec S10's real-result delivery.

The sole source edit (`packages/dsh-integration/src/global-mode.ts:18`) now instructs explicit answer/completion delivery for a direct human request before silent completion, except when that human requests no reply. It distinguishes successful tool action/private draft from delivery, preserves no extra completion after an actual sent result and background no-op silence, and retains `held_for_revalidation` as unsent with reread/reconsideration. It relies on true Inbox source identity and keeps quoted/Agent/system input from becoming human authorization.

This aligns with current `docs/specs/gateway/global-agent.md` (delivery responsibility, drafts remain private, source-based authorization, actual send status), `docs/specs/gateway/routing-delivery.md` (global explicitly chooses targets), and `docs/specs/im/gateway-relay.md` (Inbox completion is not user-result delivery). It also fulfills the implementation intent of unit S10 and design's explicit-public-delivery boundary. The design/progress supplement records the actual failure and bounded repair without introducing implicit draft publication, an assumed current chat, a second loop or changed tool/approval protocol.

The erroneous guidance is closed at implementation level. Independent product review must still verify an ordinary private save request reaches the original chat without user instructions to call send_message. Pending product evidence is kept distinct from this narrow code/spec consistency verdict, rather than represented as a passing real-model test.

### Reused evidence and limits

- Read `.dsh-runtime/onboarding-e2e/delivery-build.log`: root package builds complete and installer package is emitted for `f881314a469e`.
- Read `.dsh-runtime/onboarding-e2e/delivery-native-tests.log`: `communication-native.test.ts` 2 tests passed, 2.32s. Inspected both tests: public-send fields reach the product bridge; global silent completion after delivery/no-op and other failure/single-thread behavior remain covered. Their deterministic model fixture does not test prompt effectiveness.
- Independently ran `git diff --check eac3c2ffd..f881314a4`: passed. Read the actual source diff, relevant current contracts, product red report and design/progress additions. No tests or builds repeated; no string-only prompt test added.
- Seven corrected delta files are unchanged. Every R3 row below is retained; explicit direct-human result delivery refines existing global communication/S10 behavior and adds no new externally observable contract requiring an eighth delta.
- No source, configuration, production or runtime edits. Caller-owned README/operations edits and existing `output/` remain unstaged. Product acceptance, final evidence/CI and archival remain separately owned.

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

Current snapshot: `f881314a469e97178cd91e59a308c0d3625404d9`. All seven corrected delta files remain unchanged from R1/R2/R3. R3 rows below are retained; R4 changes only guidance for the existing explicit delivery contract. The table below explicitly retains previously verified unaffected coverage and closes affected implementation deviations; no delta was rewritten to fit a bug. R1/R2/R3 summaries above are historical scoped verdicts.

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
- R4 direct-human answer/completion delivery through send_message clarifies the existing global communication contract and S10. It does not automatically publish drafts, select targets or change permissions; product green remains separately required.
- No additional material public behavior omitted from the seven corrected deltas was found within this patch. Unaffected R1 full-diff coverage remains retained; current-spec merge is caller-owned at completion.

Outcome: **aligned** (R3 seven-delta coverage retained; R4 explicit-delivery guidance aligned with existing current contract). `requires_full_verification: false`; no surviving implementation deviation in the requested R4 source/contract scope. This does not certify the pending actual-model delivery acceptance.


## Round 5 — integrated completion audit after feat-588 merge

- `review_round: 5`; modes: targeted-closure, integration-delta, corrected-delta/completion audit.
- `validated_at: 77622d2152fe7e1bb2966fb656adf9e41613aed6`
- `executed_base: b7e367cc08a642133dea28e372816cd79038818d`; ancestry independently confirmed.
- Frozen tree: `85a9120442e4b5a7ed2df13360d77bf9da90558f`, identical to pre-merge `0247eb0e610bbf366f37b34f41015430cdaff8f7`.
- Verdict: **FAIL completion approval — 0 CRITICAL / 2 WARNING / 0 SUGGESTION**, both concrete current-documentation drift below. No newly confirmed runtime implementation defect. `requires_full_verification: false`.
- This appended round supersedes older pending-product statements and historical discovery/distribution assumptions only as expressly mapped below; prior evidence and failures remain intact.

### Requirement / Scenario disposition

| Original feat-587 scenario | Integrated disposition | Evidence retained / updated boundary |
|---|---|---|
| S1 personal space immediately usable | retained pass | 587 product R1 registration/contacts, R2 Work/task object matrix, R3 actual private save inaccessible to other accounts; unchanged tenancy enforcement. |
| S2 explicit team approval, personal use remains available | retained pass | 587 approved/pending/other-owner matrix plus Work mixed-journal and handoff regressions; joining never changes private resource space. |
| S3 local Agent install prompt | implementation/evidence retained; transport superseded | Self-contained same-IM prompt still drives the same installer. Historical actual execution retained; GitHub-fixed transport is now governed by 588 S9 and its isolated installation evidence. No current public Release is claimed. |
| S4 manual installation | implementation/evidence retained; transport superseded | 587 real no-preinstalled-Node install and 588 actual shell/bind/start/reinstall with exact download transport fixture. Official Node staging remains complete-before-promote. Linux/WSL real-machine validation and public anonymous GitHub download are not claimed. |
| S5 repeat/offline recovery | retained pass at tested seams | 587 actual same-page ready→offline→same-assistant recovery; 588 existing-install download/hash negative checks, private identity/config preservation and API-editor offline draft/revision review. |
| S6 discover existing local proxy/Codex | **superseded, not re-passed** | User's 588 original request states ordinary users use APIs and local proxy is developer-only. 588 S1/S3/S4 replaces discovery-first behavior with API-first catalog/custom setup; optional native Codex remains. Removed proxy scanning and its old test are deliberate. Manual custom loopback remains supported; no real third-party OAuth login is claimed. |
| S7 API configuration and credential privacy | covered by 588 S1/S3/S4/S5/S8 | Common initial/daily editor; actual tested API paths, local-only credential store, nested safe projection, blank-key retention, URL/key rotation and stable same-assistant choices. Test aliases forward real inference; not a claim of every vendor's live credential acceptance. |
| S8 failed connection and recovery | covered by 588 S6 plus retained OAuth boundary | Probe leaves live service intact; failed/cancelled/conflict/offline drafts survive with explicit review. Existing native code/link/cancel coverage retained. Failed key is held in component memory for correction, not browser durable storage or status output. |
| S9 guided assistant with few inputs | retained, updated model selection | Purpose/name/goal, stable retry ID and actual workspace remain; selected stable service-qualified model reference now comes from the shared editor/status. Existing create retry/nonduplication regressions and real creation retained. |
| S10 first real result in chat | retained pass; latest integration product check separately owned | 587 product R4 ordinary private task save produced real task tg_6bd77847 and actual result in source conversation, closing #5; 588 product first/edited model → original assistant actual replies retained. Explicit send_message guidance/execution is unchanged by 588. Do not equate task success, Work draft or Inbox receipt with delivered reply. |
| S11 reload/relogin/recovery | retained, strengthened by 588 S5/S6/S8 | Stable candidate, saved Agent/chat/Node identity; persisted model revision and credential store; Node cold restart, explicit stale-draft reconciliation and actual same-assistant reply evidence. |
| S12 existing users/language/narrow screens | retained with 588 updated UI evidence | Legacy model refs/id fallback, stable old-key binding and catalog fixes; auth/iOS optional flag remain. 588 three-width API editor/list and mobile/desktop menu review replace affected visuals. iOS CI archive/tests pass; browser mobile width is not a physical iPhone or native model-management acceptance. |

### Milestone / delivery completion

| Gate | Current conclusion |
|---|---|
| 587 M1 implementation and lowest relevant regressions | Covered by original full review and closure rounds plus 588 follow-up; no extra worker/task document required. All accepted implementation behaviors have reviewable seams. |
| 587 must-match | Install choices, team flow, guided creation and explicit real chat evidence retained. Model-source prototype row is superseded by 588 API-first/editor contract and its later approved UI design/product comparison, rather than pretending the old proxy screen still applies. |
| 588 M1 A/B/C | Product R2 passed provider identity after cold restart/removal, API-first/current-editor, error/cancel/conflict/offline/dependency and same-assistant real replies; R3 passed menu icons. Full R1 unaffected three-width and lifecycle evidence retained. |
| 588 M1 D/E | Public DSH/Node responsibility, roundtrip/wire ID, shared persistence queue, stage/YAML recovery, no-key projection and probe cleanup have full/static/targeted tests. Two actual prior defects were independently reproduced then closed. Final runtime source is unchanged since those semantic reviews. |
| 588 M1 F/G install distribution | Fixed manifest/download URL/hash, old-route redirect, download failure preservation and candidate→publication→anonymous verification→manifest promotion implemented/tested. The accepted design explicitly defers actual Release/anonymous download to a future authorized publication operation. |
| Current documentation / entrypoint reconciliation | **Not complete: W5-D1/W5-D2.** Canonical IM/Gateway specs contain the new contracts, but live operations/README still contradict them. Archived guidance cannot replace these current entrypoints. |
| Remote CI | Independently observed run 38349265822 SUCCESS for all three jobs including iOS Release archive. Run head 0247eb0e6 has the exact same tree as integrated head 77622d2, so this gate is retained without another broad test run. |
| New integrated product confirmation | Separately dispatched; this verifier does not certify the other reviewer's current session. Historical product gates retain their stated valid scope and fixture boundaries. |
| Requested replacement new-user video | Next caller-owned gate after completion review/product confirmation; should show API-first route and end at a real received reply. Old 587 discovery/proxy video is historical evidence, not the requested updated video. Pending recording is not an absent implementation defect. |
| Merge main / release / deployment | PR339 merged into PR337 only; PR337 remains OPEN with base main. User explicitly stops before merge main. No Release publishing, public anonymous asset-download acceptance, production upgrade or public-install availability is reported complete. |

### Current documentation deviations

**W5-D1 — current installation runbook instructs the obsolete build/deploy path.** `docs/operations/local-stack.md:13` says `pnpm build` generates `dist/node-release/manifest.json` plus the archive, and points IM at both. Actual `scripts/build-node-release.mjs:40–43` produces `manifest.candidate.json` only; `publish-node-release.mjs` promotes verified manifest.json only after fixed Release publication and anonymous byte/hash check. `apps/im-server/src/install.ts` requires that manifest and serves no archive body. A clean deployment following the runbook cannot make the advertised installer available; renaming the candidate would bypass the documented verification boundary. 588/guidance.md explicitly acknowledges this old text but is archived. Update the current runbook with the exact publication/verified-artifact handoff, metadata-only IM directory and matching build/manifest rollback. Contract: 588 S9, M1 F/G and canonical IM fixed-version installation requirement. This is a documentation fix, not a request to publish/deploy now.

**W5-D2 — live user entrypoints still promise removed proxy autodiscovery.** `README.md:12` presents existing local proxy before API; `docs/operations/gateway.md:9` explicitly promises direct discovery/testing. Current `docs/specs/im/agents-nodes.md` and actual Node/common editor implement API-first without developer proxy scanning, as the user's 588 requirements demand. Update these current entrypoints to built-in/custom API first, optional Codex subscription and manual custom loopback, with the constant model-services route. Keep the archived original S6 wording as historical/superseded. Contract: 588 S1/S2/S3/S4 and the modified model-connection requirement. This is not a missing automatic discovery feature.

### Retained corrected-delta reconciliation at integration

The prior single detailed 587 corrected-delta section remains historical at f881314a4; this integration disposition applies its seven rows against current canonical contracts and 588's already-verified two deltas. No frozen historical spec is silently rewritten to excuse implementation.

| 587 delta area | Integrated mapping / disposition |
|---|---|
| IM auth-tenancy | Retained aligned: immediate personal availability, explicit approval, fixed scopes and optional native eligibility; 588 does not change enforcement. |
| IM agents-nodes | Original continuous setup, device handoff and private data boundaries retained. Original discovered-source model requirement is explicitly superseded by 588 MODIFIED API-first and ADDED daily editor/recovery/dependency/install requirements; canonical merge inspected. Runtime alignment retained; current entrypoint docs W5-D2 remain. |
| IM agent-work | Retained aligned: authorization, minimal session metadata for handoff, no revoked content, actual Work/trajectory access and explicit delivery separation unchanged by 588. |
| IM task-graphs | Retained aligned: fixed-space private/company tasks, actor/source/receipt isolation; 587 actual private-task and chat-result acceptance closes historical product gap. |
| Gateway service-lifecycle | Empty/bootstrap/repeat/data-preservation retained. 587 same-origin archive transport is superseded by 588's fixed GitHub asset/direct download with same-origin script/metadata. Canonical lifecycle and IM install contract coexist; current runbook W5-D1 is still wrong. |
| Gateway agent-capabilities | Native/API verification and local credentials retained; 588 stable service/wire-model references, isolated probes, revision/dependency queue and rollback are the accepted extension. Removed proxy scanning is superseded, not failing recovery. |
| Gateway task-graphs | Retained aligned: effective capability/identity/space and explicit mutation authorization; model-service changes resolve primary/fallback/approval models without changing task permissions. |

Corrected-delta text/implementation outcome: **aligned with explicit supersession**. Completion verdict remains FAIL because two authoritative current entrypoints drift from the implemented/merged contracts. No additional material behavior omitted from the delta/current-contract chain was found in this bounded integration review; menu icons remain no-spec-delta.

### Verification execution and evidence limits

Read archived 587 original spec/design/M1/rounds 1–4, 588 original user request/design/M1, independent static/verification rounds 1–4 and product rounds 1–3. Traced current onboarding/shared editor/owner relay, Node model setup/probe/configuration/providers, native local credential/settings seam, installer/manifest/build/publish/workflow and current docs. Retained unaffected tenancy/Work/task/ios evidence; no repetitive full regression was run for a merge with an identical tree.

Independent read-only commands: checkout/status/branch; merge ancestry; `git rev-parse 0247eb0e6^{tree} 77622d2152^{tree}`; `git diff --stat 1bb8ff98e..77622d2` (only archived reports/progress/guidance); `git diff --check b7e367cc08..77622d2`; `bash -n apps/im-server/assets/install.sh`; `node --check scripts/build-node-release.mjs`; `node --check scripts/publish-node-release.mjs`; `gh run view 38349265822 --json databaseId,headSha,status,conclusion,jobs`; `gh pr view 337/339` metadata. All static syntax/range checks passed; remote metadata matched the statuses above. [CI run](https://github.com/Mrchen116/nano-multiagent/actions/runs/38349265822), [open PR337](https://github.com/Mrchen116/nano-multiagent/pull/337), [merged PR339](https://github.com/Mrchen116/nano-multiagent/pull/339).

No source/test/design/other report was edited; no services, build, publication, deployment or main merge initiated. Existing untracked `.runtime/` and `output/` were preserved. Two doc findings were delivered together for caller's single correction batch; no speculative review loop requested. Next static closure can be limited to those current-doc changes; integrated product and new video remain separately owned.
