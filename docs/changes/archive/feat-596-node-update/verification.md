# Verification Report: feat-596-node-update

> Effective validation snapshot: `0e0c567978a89b33248cf1c342fb3311df45025b → 56f1f577691db6a4046eaefca3dff1f7200c0c9f`, retaining the original full verification and applying the bounded deltas below.

- `validated_at`: `56f1f577691db6a4046eaefca3dff1f7200c0c9f`.
- `executed_base`: `0e0c567978a89b33248cf1c342fb3311df45025b` (main at this execution).
- `effective_base`: `0e0c567978a89b33248cf1c342fb3311df45025b`.
- `effective_through`: `56f1f577691db6a4046eaefca3dff1f7200c0c9f`.
- `delta_from`: `f5fcb1da95182a4867cd145ae59114f6a8a2e738`.
- Original full-review range start: `0b2bab6cf30ebad2fd1ee0915019913d529deea1` (`a9fc640^`); preserved as the historical review range, not the current effective main base.
- Integrated main baseline: `0e0c56797`; caller reports the final-sync recheck still matches this baseline.

- Verification scope: **full implementation / milestones**, plus **corrected-delta reconciliation** of all three delta specs and omitted observable behavior.
- Verdict: **pass**. Implementation, corrected deltas, final independent product acceptance and requested durable overall video align. **0 CRITICAL / 0 WARNING / 0 SUGGESTION**; V1 closed.
- `requires_full_verification: false`: original full review and bounded deltas retain their valid conclusions. Final evidence-document commit `5464927b0` changes no product code; `validated_at/effective_through` remain the frozen product head `56f1f5776`.

## Delta verification: `f5fcb1da9..56f1f5776`

Mode: `delta`; verdict **pass**, 0 new CRITICAL / WARNING / SUGGESTION; `requires_full_verification: false`. Original full/static and unaffected product acceptance conclusions are **retained**.

Contract: `spec.md:56` / `specs/im/gateway-relay.md:7` require a visible durable wait when sending during update. The real recording found a race in the frontend projection, then a red integration test reproduced it. `chat-workspace-page.tsx:224` now lets the existing durable-id merge replace the earlier incomplete WS echo with the full POST message. `chat-stream-reducer.ts:51` guarantees one timeline item per message id and keeps normal ordering/boundaries. The regression at `chat-workspace.integration.test.tsx:1694` asserts the actual waiting text and one bubble after the echo-first/POST-second sequence. Caller reports the complete workspace file **55 passed**, Web build passed; independent patch diff-check passed.

Outcome: **aligned**, no new spec delta needed and no omitted observable behavior. The issue is closed at both implementation/test and actual product seams: independent R4 passes no-refresh wait at 1280/390, refreshed wait and one recovered reply. No Node, IM, native barrier, release installation, authorization or persisted relay code changed. Prior acceptance is retained for unaffected journeys; final video confirms the corrected flow. Final whole-frontend rerun **93 files / 865 passed**, independently checked from its log tail.

## Delta verification: `e5cbeec26..f5fcb1da9`

Mode: `delta`; prior static conclusions **retained**. Delta verdict: **pass**, 0 new CRITICAL / WARNING / SUGGESTION; `requires_full_verification: false`. V1 subsequently closed by the final evidence reconciliation below.

| Delta | Contract / evidence | Outcome |
|---|---|---|
| Real native background review busy protection | M1-W2 and safe waiting in `spec.md:45`; existing `packages/dsh-integration/tests/knowledge.test.ts:91` now observes review start, asserts public prepare busy, releases the fixture, and retains successful facts/recovery assertions. Caller reports 4 passed. | aligned; stronger protection, no product change |
| Clear obsolete failure when manually restored to current release | `spec.md:39`, `specs/im/agents-nodes.md:15`; panel `:39` prevents historical non-success from masking the actual recommended current version; recovery/active precedence is retained. Panel test `:36` protects current heading and absent Retry; 5 passed plus build. | aligned; no new spec needed |
| Contain expanded upgrade guide at 390px | `design.md:91` must-match mobile layout; panel `:45` adds the minimum-width constraint required for the command `pre`'s existing horizontal overflow. Build passed; independent R3 actual 390/820 guide/recovery checks passed. | aligned; A2 closed |
| Operational docs and M1 durable evidence | Gateway operation guide describes the actual authorization, waiting, recovery and legacy/source paths; docs and operations indexes link it. No current spec was silently altered. | aligned |

`git diff --check e5cbeec26 f5fcb1da9` independently passed. These changes do not invalidate prior runtime/relay/process evidence: production Node/IM/barrier code is unchanged in this delta.

### V1 evidence received at this delta

Read [M1-update/evidence.md](M1-update/evidence.md). It states exact baseline, isolated IM/identity/config topology, genuine Node/DSH/worker/CLI/SQLite/browser components and controlled download/model/startup conditions. Candidate 0.2/0.3 came from `a9fc640`; candidate 0.4 came from `40a60f9`. Later changed UI/test/docs do not alter those runtime package claims. No GitHub release or production deployment is claimed.

- Busy/cancel: operation `25236614-772b-4897-84ad-a6ffffdd5b2f` waited while a real 90-second model turn continued; 390px cancellation retained old Node PID 17807 / 0.2.0, and the original task completed. Operation `ac579d41-d730-4379-9f4d-87983d0942f7` succeeded only after real 0.3 Node/DSH PIDs 25848/25853 registered.
- Durable switching message: operation `256417a1-c564-4a25-a929-54f7f3050429`, message `c1563d50cc8f415ba6d27f094dcf6778` and stable relay key ending `:update-assistant` were observed across queued → sent → completed; same message/wait survived reload and exactly one final reply followed real 0.4 PIDs 27623/27642, ready/connected and matching release. Durable record identifies screenshots and the observation JSONL locator.
- Failure/recovery: download failure `370ac02a-efc5-4619-aa07-579b5f2250b5` left real 0.3 usable; startup failure `461e14a6-bb07-473c-a6e4-c51124a38ad6` completed actual CLI rollback and old-version online confirmation before `rolled_back`. Independent acceptance now confirms actual legacy-source bridge and retained-state results.
- Final regression evidence: backend **79 files / 294 passed**, frontend **93 files / 863 passed**, subsequent affected panel **5 passed**, native Knowledge **4 passed**, typecheck/build, pytest **56 passed / 31 deselected**, Ruff checks, and existing iOS **28 passed / Release archive succeeded**. Independently inspected the stated backend/frontend log tails; other exact commands/results are reused from the durable M1 record. iOS checks do not claim a native update-management UI.
- Local initial browser recordings are explicitly labelled debugging/partial recordings. They do not yet satisfy the requested final durable overall-operation video.

Formal independent [acceptance.md](acceptance.md) has now been read and handed off, with `validated_at/effective_through=f5fcb1da9` and `executed_base/effective_base=0e0c56797`. Final Round 3 is **pass**, all required scenarios pass, A1/A2 closed. It records actual 1280/820/390 reference comparison, fresh computer `computer-87bea7e9`, real legacy/source paths, unchanged config/work-file hashes, browser-close completion, another computer's unchanged PID, and new+old startup failure followed by automatic single message recovery. Final narrow-screen guide/recovery screenshots are durable in `/Users/czj/Movies/Nano-Node-Update-20261014/independent-review/`.

Independently checked the durable directory inventory: the claimed 390/820 guide/recovery, 1280/820 restored-current, fresh-install, close/reopen-success, queued-message screenshots and preservation JSON are present. This checks artifact reachability; the independent acceptance report supplies their product conclusions.

### Final V1 closure

**Closed** after the independent R4 and final media handoff. Read the final acceptance report with `validated_at/effective_through=56f1f5776`: 1280/390 actual no-refresh waiting, refreshed waiting and one recovered reply all pass; R1-R3 unaffected journeys remain valid. Independently located all six durable R4 screenshots.

Final requested video: `/Users/czj/Movies/Nano-Node-Update-20261014/01-node-update-overall.mp4`. Independently checked ffprobe: H.264, **1280×900**, **78.480 seconds**, 1,290,215 bytes; inspected the contact sheet and located the original WebM plus immediate-wait/refreshed/completed screenshots in the same durable directory. The caller's committed M1 record (`5464927b0`) states continuous real recording with transcode only, covering update/wait/cancel/retry/send/immediate-wait/refresh/reply/success. Actual success operation `12baed71-ef25-4d6d-b1ee-b130ec7060a7` completed at 01:05:53.661; user message `639a01da0d6d47ea8b4bf8dc48bcc81b` has one completed relay key and only reply `1690f50a41d64d9ebab6fa1e4bda2f78` at 01:05:53.892. Metadata/contact-sheet inspection checks artifact identity and readable journey samples; real behavior is additionally supported by independent R4 and the durable runtime record.

Final frontend log `/tmp/nano596-final-frontend-race-tests.log` independently shows **93 files / 865 passed**. Backend294, native Knowledge4, typecheck/build, pytest56/Ruff and existing iOS28/archive evidence remains valid at the stated unchanged-runtime scopes. No GitHub release, production deployment or real-model output quality is implied. No remaining verification issue or required repeat full review.

## Delta verification: `2690627d6..e5cbeec26`

- Mode: `delta`; prior implementation/static conclusions **retained**. Delta verdict: **pass**, 0 CRITICAL / 0 WARNING / 0 SUGGESTION. V1 closure is recorded above after the later final handoffs.
- `requires_full_verification: false`: main's already-reviewed bugfix-595 changes are limited to onboarding/member UI and the first-setup scroll contract; its added CSS selectors do not apply to the update settings/chat surfaces. No shared update protocol, runtime or relay seam changed.

| Delta | Contract and implementation/test evidence | Outcome |
|---|---|---|
| New release available after a previous successful update | `spec.md:33` and `specs/im/agents-nodes.md:7` require discoverable available version/notes. `node-update-panel.tsx:39` gives the new availability precedence over obsolete success; existing version/notes/action rendering at `:50`, `:52`, `:57` is reached. `node-update-panel.test.tsx:31` protects the visible version and notes. Caller reports all 4 panel tests and frontend build passed. | aligned |
| Ignore private local updater state | Repository rule forbids committing journals/locks; `.gitignore` now covers `.node-update.json`, `.node-update-handoff.json`, `.node-update.lock/`. No observable behavior added. | aligned; no spec delta needed |
| Merge main bugfix-595 | Scoped onboarding/membership selectors/markup and additive short-window setup paragraph only; no collision with this unit's delta sections or update runtime behavior. | prior conclusions retained |

`git diff --check 2690627d6 e5cbeec26` independently passed. No unit spec/design rewrite is required for the repeated-release fix: it restores the existing discovery requirement. No omitted observable behavior or new implementation deviation was found. This bounded delta does not repeat the full static review or the product review currently assigned elsewhere.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All 5 requirement groups / 9 primary scenarios have implementation, final independent acceptance and durable overall video |
| Correctness | Static protocol, safety and persistence seams align; two caller-found defects are closed by reviewed working-tree repairs |
| Coherence | Node owns installation; IM owns authorization/queue facts; PA owns durable product work; DSH is reached only through integration's public boundary |
| Corrected delta | `aligned`; no omitted externally observable requirement found in the bounded unit diff |
| Issues | 0 CRITICAL, 0 WARNING, 0 SUGGESTION; V1 closed |

## Completeness

The unit uses one integrated milestone, not worker task files. The implementation covers M1 code scope. M1 cannot be marked complete merely from static review or fixture tests.

| M1 exit criterion | Available evidence | Status |
|---|---|---|
| R1: all primary scenarios and understandable identities/versions/actions | Independent acceptance Round 3 pass at f5fcb1da9; required scenarios and A1/A2 closure recorded | Passed |
| R2: download continues work; busy wait/cancel; send/refresh/recover exactly once; truthful failures; bridge/source distinction | M1 runtime identities plus independent acceptance's real legacy/source, browser-close and recovery-required tests | Passed with fixture limits stated |
| W1: desktop/mobile screenshots, prototype comparison and requested real video | Independent acceptance's 1280/820/390 comparison, durable screenshots/R4 and 78.48-second 1280 overall-operation video received | Passed |
| W2: metadata, authorization, cancellation, idle barrier, download failure, process rollback and idempotency coverage | Inspected parser, Node, IM, native barrier/Workflow/model-setup and PA tests; caller reports focused suites passed | Supported at tested seams; retain stated fixture limits |
| W3: package build/typecheck/regressions/architecture/docs/local CI | Final M1 record: backend294/frontend863 + affected panel5/Knowledge4, typecheck/build, pytest56/Ruff, iOS28/archive; independent architecture13/docs/diff checks | Passed at stated snapshots; docs inventory must include final reports when tracked |

## Correctness

| Requirement / Scenario | Implementation evidence | Test / evidence seam | Status |
|---|---|---|---|
| Discover and click exactly one computer update | `apps/im-server/src/node-updates.ts:42`, `:62`; `src/IM/frontend/src/features/settings/nodes/node-update-panel.tsx:25`; chat NodeChip | Manifest parser; IM target/owner/request receipt test; panel one-click test; acceptance discovery scenario | Covered |
| Offline and current versions offer no executable update | `node-updates.ts:42`; panel `:40`, `:57` | IM view logic and frontend offline test | Static aligned |
| Download/install then wait for existing work | `apps/node/src/update-worker.ts:19`, `:120`; `apps/node/src/main.ts:258`; native barrier `:41` | Package/native idle/Cron/inbox/Workflow/model/Knowledge and PA tests; acceptance real busy task completion | Covered |
| Cancel before switch; duplicate operations do not restart twice | `node-updates.ts:62`, `:88`, `:104`; worker `:124`; `NodeUpdater` config lock and handoff | Atomic cancel/claim/request tests; lease death; acceptance cancel/doubleclick | Covered |
| Send and refresh during switching; recover without resend or duplicate reply | `apps/im-server/src/messaging.ts:507`, `:523`, `:529`; `node-updates.ts:155`, `:160`, `:180`; message pane `:1803` | Durable relay/key tests; M1 exact message/relay identities; acceptance refresh/recovery single reply | Covered |
| Closing webpage does not stop update or lose identity/data | Detached worker in `apps/node/src/node-updater.ts:54`; original config reused in worker `:49`, `:86`; state read through IM | Process fixture with stated limits plus acceptance actual close/reopen-success and preservation hashes | Covered |
| Download/checksum failure leaves old version usable and allows retry | Worker installs into independent staging, `:19`; old stop begins only at `:150`; IM new request receipts and panel retry | Fixed HTTPS/checksum tests; actual failure in M1 and acceptance | Covered |
| New startup failure rolls back; result requires actual online expected version | Worker verify `:89`, rollback `:158`; IM terminal checks `node-updates.ts:129` | OS-process/IM tests; M1 real rollback; acceptance new+old failure, recovery-required and resumed reply | Covered |
| First install and legacy one-time bridge preserve existing state | `apps/im-server/assets/install.sh:64`; `apps/node/src/cli.ts:50`; `apps/node/src/release.ts:13`; source distinct in IM view | Release/parser/publisher tests; acceptance actual fresh install, historical old CLI bridge, hashes and source branch | Covered |

### Direct validation performed by this reviewer

1. `pnpm exec vitest run apps/im-server/tests/node-updates.test.ts` — **7 passed** on the full-server hook repair. This establishes runtime report authentication both before and after handler execution while disconnected; normal nodes management still rejects runtime credentials.
2. `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py` — **13 passed**.
3. `git diff --check a9fc640^ a9fc640` and `git diff --check` — passed.
4. `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` — passed, 238 maintained Markdown sources / 64 required routes. Newly written untracked reports were not included in this Git-tracked inventory.

Initial focused handoff covered recursive/frontend builds, parser 8, IM updates 6 (superseded by the independently run 7), frontend update-related 4 files/9 cases, Node updater/lifecycle 6 files/21 cases, process/lifecycle 12 cases and native barrier/Cron/inbox/cold-recovery/model-setup protection. Earlier backend293 and frontend failure reports are superseded by M1's final backend294/frontend863 results. Subsequent changes are bounded UI/test/docs patches covered by the panel5/Knowledge4 tests, latest Web build and independent final acceptance; unchanged Node/IM/runtime results are retained rather than silently relabelled as re-executed at each documentation/UI commit.

## Coherence

| Design decision | Adherence and evidence |
|---|---|
| Metadata checks do not authorize payload downloads | IM GET/view reads manifest only; worker can start only from a persisted authenticated operation (`node-updates.ts:62`, `NodeUpdater.request`) |
| Displayed version/hash and stable request identity | Target comparison and durable request alias table; old request ids return old operation, active aliases converge |
| Independent worker prepares new content before stopping old Node | `update-worker.ts:19`, `:49`, `:150`; exact fixed GitHub parser and compatible metadata verified |
| Gate before local prepare; resume before IM replay | Worker `:127`, `:78`; local prepare/resume at `main.ts:258`; IM transition/terminal replay |
| Bind ready handoff to operation, worker and Node process identities | `node-updater.ts:106`; worker `:130`; verify before claim and stop |
| Short local lease and truthful loss recovery | `NodeUpdater.tick:70`, lease `:22`; IM `sweep:189`; recovery projection and reconnect gate release |
| Preserve native idle; do not cancel active tasks to acquire update barrier | Native barrier `:41`, `:44`; all live registry agents, inbox queues, tracked continuation services and PA work seams |
| Exact real release registration before success/rollback | Worker `:89`; IM terminal state branch `:129`; gate blocks premature relay replay |
| Membership/owner epoch revalidation on replay | `messaging.ts:523`; Gateway send validity remains in force; per-relay gate keeps other computers independent |
| Legacy bridge/source deployment remain distinct | `cli.ts:50`; managed package identity in `release.ts`; IM legacy/source reasons and UI instructions |

The static architecture check passed. No private DSH import, alternate agent loop, runtime fork, new node HTTP execution service, or forbidden package dependency was introduced.

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation | Durable implementation evidence | Status |
|---|---|---|---|---|
| Computer update region at 1280 / 820 / 390, including available/download/wait/switch/success/failure/offline/legacy | M1-R1/W1 (`design.md:91`) | NodeUpdatePanel and NodesPage; separate alias controls and live-field merging | acceptance Reference Artifacts table; `review596-guide-fixed-390/820.png`, `review596-recovery-fixed-390/820.png` and current/available/busy screenshots in durable independent-review directory | Covered; A1/A2 closed |
| Chat entry and waiting indication at 1280 / 390, including send/refresh | M1-R2/W1 (`design.md:92`) | NodeChip, chat update invalidation and MessageBubble wait projection | acceptance `real-queue-390`, `queue-desktop`, `restored-1280`, `recovery-resumed` in durable independent-review directory | Covered |

## Issues

### CRITICAL

None. Historical V1 (M1-W1 / `spec.md:83` required overall video and complete acceptance evidence) is **closed** by the final reconciliation above.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/agents-nodes.md`: owner action, waiting/cancel, truthful result, offline/current/unpublished/legacy/source | IM updates `:42`, `:62`, `:88`, `:104`; runtime report route and both hook exclusions; update panel | Parser/IM/panel tests; full server hook test independently 7 passed | aligned |
| `specs/im/gateway-relay.md`: persisted switching waits, multi-target independence, access changes, ordinary offline, cancel/recovery replay | Messaging `:507`, `:523`, `:529`; gate/projection/replay/reconnect; frontend wait state | IM durable sent-row projection and cancel replay; existing input-key dedup/recovery; native lease death | aligned |
| `specs/gateway/service-lifecycle.md`: authorized immutable prepare/safe switch, cancellation/data preservation, truthful rollback, first/legacy/repeated install | Worker `:19`, `:49`, `:89`, `:124`, `:158`; controller lease; CLI setup/installer/release identity | Package-integrity, real OS-process switch/rollback fixture, native idle/Cron/inbox/Workflow/model setup tests | aligned |

### Uncovered Observable Behavior

None found. The unit's temporary runtime-report authentication exception and explicit setup request use the same authorized lifecycle; they do not introduce a second public update policy. Source identity, terminal recovery messaging, paused-work waiting, compatible package epochs and repeated setup are represented by the existing delta scenarios and design. No delta was silently rewritten to accommodate implementation errors.

Outcome: **aligned** for corrected-delta; full milestone verification **pass**, V1 closed. The initial four repairs are bound to `2690627`, subsequent bounded code deltas through `56f1f5776` retain the full/static conclusions, and final independent acceptance plus media evidence closes completion. Remaining spec merge/archive/report commit work is the caller's delivery responsibility and changes no reviewed product code.
