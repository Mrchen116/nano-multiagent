# Verification Report: feat-587-first-run-onboarding

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

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| `specs/im/auth-tenancy.md`: immediate personal registration, fixed spaces, explicit join, revocation | identity/db/messaging/Gateway checks; tenancy and migration tests | implementation-mismatch W1: personal use blocked by mixed shared Work |
| `specs/im/auth-tenancy.md`: native iOS optional personal eligibility | CommonModels.accountEnabled, app/ChatStore/MeView gates, SessionTests | aligned; caller owns Xcode result |
| `specs/im/agents-nodes.md`: continuous setup/model failure recovery | installer/onboarding/ModelSetup; bootstrap/model/onboarding/Web tests | implementation-mismatch W2 |
| `specs/im/agents-nodes.md`: full-device handoff, private Work follows, old chats/tasks stay | Identity.deviceCommit, transfer recipient check, identity transfer tests, task receipt isolation | aligned; no implicit private-history migration |
| `specs/im/agent-work.md`: fixed-space Work/trajectory read and subscription | Work routes and broadcasts, TrajectoryObservers.valid; tenancy live/replay/trajectory regression | implementation-mismatch W1 for shared journal progression |
| `specs/im/task-graphs.md`: personal/company actor scope, receipts, source projection | TaskGraphService eligibility/list/get/save/receipt; tenancy task and transfer receipt tests | aligned |
| `specs/gateway/service-lifecycle.md`: empty bootstrap, repeat/failure preservation | bootstrap/cli/installer/main, bootstrap/device-binding tests, real empty node in M1 evidence | implementation-mismatch W3 |
| `specs/gateway/agent-capabilities.md`: native/API validation and persisted local secrets | ModelSetup/NativeModelSetup, real native integration HTTP and restart test | aligned except shared setup discovery recovery W2 |
| `specs/gateway/task-graphs.md`: fixed-space effective Agent capability | TaskGraphService agent feature/allowlist/online checks plus scope, Gateway command identity | aligned |

### Uncovered Observable Behavior

- The shell no longer displays the `internal` badge (`src/IM/frontend/src/app/shell/nano-brand.tsx`). This is a branding adjustment consistent with the public-first-use goal, not a separate stable behavioral contract requiring a new delta.
- Model discovery now prefers proxy profiles supporting OpenAI Chat, falling back to Anthropic-compatible models. Design's implementation supplement records this, and protocol-filtering tests cover it; the broader model delta already covers compatible local proxy discovery.
- Device prepare now waits three seconds and observes 429 Retry-After. Existing device-binding recovery tests cover this, and the implementation supplement records it; this refines the existing retry contract.
- The small native iOS eligibility change is expressly represented in the corrected auth-tenancy delta. There is no native onboarding implementation or claim.
- No additional material externally observable behavior was found omitted from the seven deltas. Current specs remain unchanged while the active unit is unfinished.

Outcome: **implementation-mismatch**. Correct W1/W2/W3 and recheck the affected seams; retain the separate final product/video/CI gates.
