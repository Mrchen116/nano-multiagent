# Verification Report: bugfix-644

> Round: 1; verification_mode: full, including all current delta reconciliation.
> Validation snapshot: `1ef49808ffd2618c275b6e38683f93f74ff8455d -> 4ba1eefca3c547f40f9b1060c64941ee3cf6ee09`
> Branch: `unit/bugfix-644`; workdir: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-644`
> Verdict: **FAIL - 0 CRITICAL / 4 WARNING / 0 SUGGESTION**
> corrected-delta: **implementation-mismatch**; requires_full_verification: false (this round already is full).

## Summary

| Dimension | Result |
|---|---|
| Completeness | All R1-R11 and M1 exits inspected; unknown discovery, preview semantics and changed-directory feedback remain incomplete. |
| Correctness | Offline mutation gates, finite persistence, recovery and draft preservation are implemented; four blocking warnings remain. |
| Coherence | D1-D6 and the final R3 existing-UI decision are largely followed; see the specific deviations below. |

This is an independent static implementation verification, not the separate product tryout. Scope: complete dispatched diff, incident, final R3 design/reference contract, both deltas, current IM specs, SPEC and testing rules. No service was started/stopped; no production action or source/test/config/design/delta edit was performed.

## Completeness

The unit has one M1. No worker tasks/progress file is required for this simplified workflow.

| Exit | Evidence | State |
|---|---|---|
| M1-U1/U2/U3 | R1-R11 mapping below; implementation evidence; separate independent product reviewer | Static portion inspected; full real product journeys are not declared passed here. |
| M1-W1 | `M1-offline-settings/backend-evidence.md`; Fastify/SQLite tests in agent-settings/control/approval/plugins/PA | Main boundaries covered; W1 remains. |
| M1-W2 | Versioned implementation evidence: 9 agent-edit + 8 PA + 25 detail; 23 existing + 5 new channel cases | Draft/cancellation/pending/conflict/null-inheritance paths covered; W1-W4 need regression coverage. |
| M1-W3 | Real IM/Node/DSH self-check narrative and desktop/mobile/tablet screenshots; final R3 comparison | Representative configuration/draft evidence exists; not a replacement for full channel/PA/Global real acceptance. |
| M1-W4 | Implementation record: backend/frontend build, Python 65 pass/31 deselected, ruff; caller supplements typecheck/check:ios-runtime exit 0 and Web failed-file rerun | Backend full suite/native/final docs checks were still being collected by caller at this review. Do not convert their pending status into a pass. Final current-spec merge remains a delivery closeout step. |

The implementation record honestly says full Web was 969/973. This reviewer read `/tmp/bugfix644-web-recheck.log`: the three previously failing files subsequently passed all 85 tests; caller reports the other 101 files/888 tests had passed. Together these cover the frozen source files, but they are not a claim that a second monolithic full-suite execution occurred. No full suites were duplicated here.

## Correctness

| Requirement / Scenario | Implementation | Test/direct evidence | State |
|---|---|---|---|
| R1: durable display across refresh/browser; model/effort pair | `agent-settings.ts:43-96`, `control.ts:768-807`, `im-agent-config-api.ts:648-681` | Persisted snapshot/authorization HTTP tests; offline form tests; three-width self-check | Main path covered; W2 affects unknown discovery. |
| R2: explicit/inherited/unknown; unknown never empty/default | configurationDisplay, SettingsReadNotice, ModelReasoningField, independent section results | Backend empty/unavailable/timeout; frontend unavailable cron | **W2/W3** |
| R3: configuration/PA/plugins/cron read-only; reading/cancel retained | AgentDetailPageContent, PA controls, plugin/cron guards | Frontend 17+25 and offline route tests | Main guards covered; W3 preview feedback deviates. |
| R4: all new offline channel mutations rejected without side effects; dialogs guarded | `channels.ts:689-758`, AgentChannelsPanel | Every channel route preserves revision/credentials/receipt; five offline UI tests | Covered |
| R5: disconnect does not assert local work stopped; historical channel state labeled | ConnectionCard; existing Work persistence; no new local-stop code | Existing/offline channel tests; true Relay-only disconnect trial belongs to product reviewer | Static covered; stop-Node self-check alone is not full R5 evidence. |
| R6: form/dialog draft survives; cancel/discard available; no autosubmit | baseConfig/draft effect; channel dialog memory | Draft+remote-version UI test; channel offline dialog; real self-check | Covered |
| R7: accepted but uncertain results; duplicate prevention | Existing durable ConfigOperations; settings pending summary; channels unconfirmed; plugin/cron reread | Same-operation recovery HTTP test; single pending PATCH; response-loss channel case | Covered |
| R8: old pending/manifest/removal recovery retained | Existing recovery plus offline operation summary | Backend same-operation recovery and existing control/channel regressions | Covered |
| R9: online event cancels old reads; current section must refresh before unlock | use-agent-settings-state, applyAgentStatusEvent, connection-specific channel query, independent PA/section queries | Late response, stream recovery, independent sections | Covered |
| R10: version/capability changes and online read failure | baseConfig/versionConflict; reasoning stale; per-section freshness | Draft/version conflict tests; independent HTTP and SSR reproductions | **W1/W2/W3/W4** |
| R11: explicit online save/lifecycle; shared native error classification | PATCH/apply/receipt; online form save; channel lifecycle; Swift isAgentStateConflict | Versioned backend61; frontend online/channel; Swift source contract test | Main path covered; caller owns final native execution evidence. |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| D1 finite projection; profile authority; no secret/catalog/body replication | Mainly; unknown display and preview time differ | agent-settings.ts, new schema; W2/W3 |
| D2 one settings entry plus finite independent sections; old successful wire preserved | Mainly; optional-features compatibility differs | control.ts settings/sections and old routes; W1 |
| D3 global connection plus per-section current reads; unrelated failures independent | Yes | Hook connection boundary; independent plugin/cron/PA/channel queries |
| D4 reject before new intent, retain accepted recovery | Yes | PATCH before insert; channel writable; plugin/cron/PA guards; unchanged recovery |
| D5 base/draft/latest, no automatic defaults, existing discard conflict UX | Mainly; missing-directory feedback incomplete | AgentDetailPageContent and handleDiscard; W4 |
| D6 single complete milestone | Structure followed; completion cannot yet be claimed | One M1; warnings and external gates outstanding |
| SPEC dependency/runtime boundaries | Yes | IM-only new module; no Node/PA/DSH imports, private runtime access, second loop or kernel HTTP service |

### Prototype / Reference Contract

Current reference is final R3 in `design.md:200-234`, not historical R1/R2 mockups.

| Reference contract | Milestone | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Existing cards/field order/Skills grouping and original model/effort controls | U1/W3 | Existing DOM reused, selectors receive disabled; no new disabled suffix or merge panel | M1 desktop/mobile/tablet; reviewer actually viewed M1 offline-mobile and R3 offline-mobile | Static covered; no subjective visual score. |
| Offline notice; draft retained in original fields; unlock after reads | U1/U3/W3 | Hook and draft/base; original disabled selects | Versioned real browser self-check and three-width images | Main contract covered; W2/W3 affect state accuracy. |
| Existing channel provider/AppID/keep-replace/confirmation/mobile sheet | U2/W3 | ConnectionCard/ChannelDialog/ConfirmationDialog structure retained | Existing lifecycle + offline tests; separate real reviewer | Component inspection does not assert complete real channel journey pass. |
| Necessary unknown/conflict feedback and original discard | U1/U3/W3 | Existing error locations and handleDiscard; no field merge workflow | Version conflict UI regression | Mainly covered; W4 missing capability-conflict feedback. |

## Issues

### CRITICAL

None confirmed. In-progress caller checks and separate product acceptance are outstanding evidence, not assumed failures or passes.

### WARNING

1. **W1 / CONFIRMED: an optional Features field becomes mandatory and locks online older nodes.** `apps/im-server/src/control.ts:572`. Existing featureOptions normalization and frontend CapabilitySnapshot (`im-agent-config-api.ts:124`) explicitly accept older Gateways without features. Independent Fastify injection with real SQLite and a valid binding, same `{models:[{name:'model'}],skills:[],tools:[]}` payload: old `/capabilities` returned 200/features=[]; new `/settings` returned online/read_failed/ready:false/live_capabilities:null. Restore the existing optional-field normalization while keeping truly failed required reads locked. Add an HTTP regression for this payload. Same as code-review finding 1.

2. **W2 / CONFIRMED: unconfirmed discovered Skills appear enabled after a profile-version mismatch.** `im-agent-config-api.ts:670`, `skill-source-selector.tsx:59-61`. Backend `agent-settings.ts:81-83` correctly recomputes old derived values as enabled:null; frontend erases null and the selector recomputes all discovery entries as selected. Independent SSR of the actual component with default_discovery/readOnly/historical enabled:undefined produced a green `aria-pressed="true"` pill and 1/1 enabled count. This violates design:126 and R2. A generic incomplete-list note does not correct individual enabled assertions. Preserve unknown state/provenance and exclude unconfirmed derived values from current enabled claims using the existing component/feedback structure; do not revive R3-rejected suffix designs. Add a changed-version/offline display regression. Same as code-review finding 2.

3. **W3 / CONFIRMED: preview availability confuses read-only with offline, and previews have no acquisition time.** `agent-detail-page.tsx:438` sets hbMdNodeOnline=false for online refresh/pending/read errors; `599-602` then asserts the node is offline, and returning ready never resets it. Its catch also maps an online read failure to offline. BehaviorCard previewText and HeartbeatCard hbMdContent store no own capturedAt, so retained historical content cannot display its acquisition time. The top configuration-snapshot timestamp is not the file/generated-prompt acquisition time. This violates design:122/154, delta agents-nodes:186-190 and R10. Separate actual connection, refreshing and preview read failure; retain each successful body and its timestamp, label historical content in the existing preview area, and test online main-settings refresh without a false offline message. The false-offline part is code-review finding 3.

4. **W4 / CONFIRMED: changed current model/tool/Skill directories lack the explicit incompatibility feedback required by R10.** `agent-detail-page.tsx:1376-1384` only validates the display name and nonempty reasoning descriptor. `resolveModelOptions:110-119` silently reinserts a disappeared primary model; configured tools/Skills absent from current options are simply not rendered at `1942/1975`, while retained draft values still contain them. Concrete scenario: edit the name online, disconnect, remove its configured model (saved effort=null) or a selected tool/allowlist Skill from the node directory, then reconnect without changing profile_version. The successful current read unlocks saving with no incompatibility message; a removed model can fail only at apply, while missing tools/Skills have no visible configured item to adjust. Incident:174-178 requires the retained draft plus explicit actual incompatibility, and design:124 says all configured names remain visible. Retain affected configured/draft entries with truthful unavailable feedback in existing UI positions after a current-directory read, permit explicit correction, and preserve temporarily invisible denylist rules. Add a directory-change UI regression. This is incomplete target behavior, not a request for a new merge panel or UI redesign.

### SUGGESTION

None.

## Corrected Delta Reconciliation

Current reconciliation, updated at Round 3 validated source `feb2e1885129bc9479bd29821065101149b6584d`. The original Round 1 mismatch remains recoverable in report commit `a685d1aa4fff34a30d763a4e35cce4ea93fe5564`; its findings above are historical and their closure is recorded below.

| Delta item | Final implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| agents-nodes ADDED readable/read-only/recovery/unknown semantics | settings/snapshots/hook/sections/channels; preserved null Skill state; independent timed previews | Backend17 and frontend67 review-correction evidence; two final usage-failure cases | aligned |
| Configuration new offline rejection, accepted-op recovery, inherited null reasoning | Retained PATCH gate/ConfigOperations; pending fact now comes from durable settings response as well as local submission state | Retained no-offline-op/same-op recovery/null inheritance; pending reopen regression | aligned |
| Live capabilities plus read-only finite display; no false invalidation | Optional features normalization restored; unknown Skill state retained; current directory absence explicitly shown without losing draft entries | Optional-features HTTP test; unknown Skill component test; missing model/fallback/tool/allowlist Skill correction test | aligned |
| HEARTBEAT/prompt/cron: successful wire, unknown vs empty, timed retained previews | Preview body/capturedAt/stale/error separated; no readOnly-to-node-offline assignment; cron gates retained | Retained cron tests; independently captured heartbeat/prompt body retention test | aligned |
| Channel offline rejection and accepted manifest/removal convergence | Retained route gates; bodyless action headers delegated to authFetch; offline guidance corrected | Retained lifecycle/side-effect tests; bodyless action API regression | aligned |
| PA source/blocked-contact offline settings boundary, refreshed reads, chat protection | Retained settingsOwner/query guards; no merge or patch changes to this path | Retained PA backend/frontend evidence | aligned |
| Unknown discovered Skill collection versus explicit/confirmed empty selection | discoveryConfirmed comes from live capabilities or a profile-aligned display snapshot; explicit allowlist remains authoritative | I6 actual-page red/green plus five independent actual-component SSR boundaries | aligned |
| Online section read failure retains last result and offers retry | Usage transport errors and HTTP200 last_known/error use SettingsRead.error; empty and nonempty history both expose retry | Parameterized transport/envelope regression, 2 passed at final revision | aligned |

### Uncovered Observable Behavior

None at the final reviewed source. The unauthorized missing-features compatibility regression identified in Round 1 is repaired. Added catalog error feedback, pending-operation visibility, preview timestamps, bodyless request correction and section retries implement existing incident/design/delta obligations; no new product requirement or delta rewrite is needed. Native availability error classification remains the previously declared compatibility work.

Outcome: **aligned**. This is the current corrected-delta result; final CI and product acceptance remain independently reported gates.

## Round 2 - targeted closure and repair patch review

> Original executed base: `1ef49808ffd2618c275b6e38683f93f74ff8455d`.
> Finding origin: `4ba1eefca3c547f40f9b1060c64941ee3cf6ee09`.
> Initial Round 2 source: `82cf77613d5a40b400b0094dfc1a84a614dde85e`.
> Repair commits: `fc322942c94ba036cade0758c5d48e7383ee01ae`, then `acf0c72f2e799775311cca501dfb934d9174472f`.
> Final validated_at: `acf0c72f2e799775311cca501dfb934d9174472f`.
> Modes: code review patch + focus closure; verification targeted-closure + corrected-delta.
> Current static verdict: **PASS - 0 CRITICAL / 0 WARNING / 0 SUGGESTION**.
> requires_full_verification: **false**. Corrected-delta: **aligned**.

### Scope and evidence retained

This round inspected the repair patch, all four prior warnings, product findings I1-I5 at their implementation seams, the additional usage-envelope repair, and the effect of merging `origin/main` at `51072cb58`. It did not mechanically re-review unrelated runtime performance implementations or replace the independent real-product reviewer. Current `code-review.json` is `[]`; original JSON findings remain in Git at `a685d1aa4` and their individual dispositions are below.

The merge from fc322942c to 82cf77613 has no changes under IM backend, Web, native iOS, current IM specs, `apps/node/src/main.ts`, or integration knowledge code. Accordingly the original HTTP/SQLite permission, binding, snapshot and mutation side-effect evidence and unchanged frontend draft/channel/PA/native paths remain applicable. This retention is based on actual path and call-chain comparison, not simply on commit ancestry.

Upstream perf-648/649/650 and trajectory changes do touch runtime assembly, input reconciliation, model fallback replay, descendants and token-accounting `usage.read`. They warrant the caller's final integrated build/CI and real runtime acceptance. They do not change the settings Skill-usage seam: `apps/node/src/main.ts:224-227` continues to resolve `node.skills.usage.request` through `knowledge.usage`, not accounting `usage.read`. No shared settings contract or new dependency-boundary violation was identified; a full repetition of the unit's unchanged static review is not required. Real runtime conclusions are not inferred from static retention alone.

### Focus-finding closure

| Finding | Disposition | Evidence |
|---|---|---|
| W1 optional features locks older online Gateway | **closed** | `control.ts:572` now validates required models/skills/tools while retaining featureOptions normalization. New HTTP test compares old capabilities and new settings for the same missing-features response; 17 backend tests passed. |
| W2 unknown discovered Skills appear enabled | **closed** | Adapter and normalizer preserve enabled:null; selector excludes unknown derived states from enabled count and displays an indeterminate group/dash count. New actual-component test protects this state. Explicit allow/deny semantics remain unchanged. |
| W3 preview false-offline classification and missing acquisition time | **closed** | Heartbeat no longer derives node presence from readOnly. Both previews retain body, own capturedAt and stale/read-error state. Existing successful empty-body semantics remain. New frontend case retains independent heartbeat/prompt bodies and timestamps across disconnect and online read errors without Node-is-offline feedback. |
| W4 missing configured catalog entries and incompatibility feedback | **closed** | Missing primary/fallback models, tools and explicit-allowlist Skills remain visible in existing controls; current confirmed catalogs cause explicit unavailable feedback and block save until corrected. Missing denylist rules remain valid retained policy. New integration test preserves draft and verifies explicit user correction before one PATCH. |

No prior focus finding is silently dropped or superseded by a changed target. The implementation is corrected against the original target contracts.

### Product-review fix seams

| Product issue | Static repair assessment | Acceptance boundary |
|---|---|---|
| I1 accepted pending disappears after offline reopen | confirmationPending includes durable pendingOperation; availability notice explicitly retains submitted/waiting fact even when its primary reason is offline/refreshing | Pending reopen regression protects the API-to-UI seam. Separate reviewer must close the real delayed/accepted-operation journey. |
| I2 bodyless reconnect/delete return JSON-empty-body 400 | requestJson delegates headers to existing body-aware authFetch; bodyless reconnect/delete/removal-retry do not declare JSON while real payload writes still get JSON headers | API regression protects the three bodyless actions; actual channel lifecycle remains product acceptance. |
| I3 saved fallbacks cannot expand offline | Collapse/expand reading is permitted with retained values while selects/add/remove stay disabled; unknown saved fallback names remain in display options | Offline saved-fallback expansion regression passed. |
| I4 usage failure mislabeled offline / history lost | Usage transport and SettingsRead envelope failures preserve last body/time and show read-failure feedback; no Gateway-offline assertion | History/failed-read regressions passed. The HTTP200 retry gap found during this round is repaired as documented next. |
| I5 offline guidance promises new changes apply later | Existing localized offline guidance now accurately says read-only until connection and refreshed data return; accepted-pending guidance remains separate | Copy repair stays within R4 and does not introduce UI redesign. |

### Additional concrete gap found and closed during this round

Initial repair source returned a correct failed-read notice but showed Retry only when React Query `isError` was true. The real settings-section protocol also returns HTTP200 with `{source:last_known,data:<previous successful data>,error:{code:read_failed|timeout}}`; that result has isError=false and no section Retry. With main settings still ready, its global refresh notice cannot supply the missing action. This was a direct protocol/branch mismatch in delta's online-read-failure/retry scenario.

Commit `acf0c72f2` changes both empty-history and nonempty-history branches to use `read.error`, which covers transport errors after adaptation and successful HTTP failure envelopes. The existing regression was parameterized over transport rejection and HTTP200 last_known/error, and asserts Retry within the usage section rather than accidentally matching another page control. The final focused log records 2 passed / 13 filtered skips. Those skips are the deliberate test-name filter, not hidden product failures. The nonempty branch uses the same corrected condition and was inspected directly; no duplicate full suite was added.

A reviewer-created temporary external harness initially had path resolution and matcher-binding failures. Those runs are not valid product red/green evidence and are not counted as such. The protocol defect was independently established from the real backend response contract and frontend branches; final executable evidence uses the repository's normal test harness below.

### Validation evidence and limits

- `/tmp/bugfix644-review-w1-green.log`: 1 backend file / 17 tests passed for fc322942c's backend change; that backend file is unchanged in the merge and final usage-only correction.
- `/tmp/bugfix644-review-front-green3.log`: 4 frontend files / 67 tests passed for the substantive correction patch. The main merge leaves those source paths unchanged.
- `/tmp/bugfix644-review-front-build.log`: frontend production build passed before the final two-condition usage correction. Caller is performing final integrated build/CI; this is not relabeled as a final-revision build.
- `/tmp/bugfix644-review-usage-envelope2.log`: final correction's transport/envelope cases, 2 passed / 13 filtered skips, at final source acf0c72f2.
- `git diff --check fc322942c^..acf0c72f2`: passed.
- Original backend route, frontend channel/PA/native source evidence remains scoped to unchanged paths. Earlier broad/backend/native work and real screenshots retain their stated versions and limitations, not a newly invented final-CI pass.

This round does not declare M1-U1/U2/U3's separate real acceptance or M1-W4's final complete CI passed while caller/reviewer are still collecting them. The scoped static closure and delta gates pass; overall delivery remains contingent on those independent final gates. No business source, test, configuration, design or delta was changed by this reviewer; only these review reports are committed.


## Round 3 - I6 local patch and closure

> Review modes: local patch / targeted-closure / corrected-delta affected-area reconciliation.
> Effective PR base: `55376c111`; prior static source: `acf0c72f2e799775311cca501dfb934d9174472f`.
> Product Round 2 report parent: `37dea697`; final validated_at: `feb2e1885129bc9479bd29821065101149b6584d`.
> Static verdict: **PASS - 0 CRITICAL / 0 WARNING / 0 SUGGESTION**.
> I6 implementation seam: **closed**. Current `code-review.json`: **[]**.
> Corrected-delta: **aligned**; requires_full_verification: **false**.

### Scope and finding disposition

This is the requested local follow-up, not a repetition of the full review. Inspected all three affected source/test files in feb2e1885: `agent-detail-page.tsx`, `skill-source-selector.tsx`, `agent-edit.test.tsx`, plus the evidence-only implementation note. Product Round 2 independently closed I1-I5 and retained/passed R1/R3-R11 while finding I6 in R2. Those product findings and the static W1-W4 closure remain versioned evidence, not overwritten or reasserted as newly executed journeys.

**I6 - closed at the implementation/automated seam.** With no snapshot and `explicit_denylist=[]`, the discovered collection is unknown, so a numeric enabled total cannot be inferred. The page now passes `discoveryConfirmed` from a real live-capabilities result or `display.data.derived_current`, which the backend preserves only for the matching committed profile version. The selector's existing mode caption uses unconfirmed feedback when that evidence is absent for discovery/denylist modes; it no longer claims zero enabled Skills. A nonempty explicit disabled-name list stays visible/read-only. Per-entry enabled:null and indeterminate group handling from W2 are retained. Actual explicit allowlist selections remain authoritative and are deliberately exempt from needing a discovery census. A confirmed successful empty catalog still permits the existing zero-count meaning.

The new input defaults true for existing call sites, preserving creation-page behavior. The setting page supplies actual provenance explicitly. No selection mutation, PATCH payload, save/recovery condition, channel lifecycle, PA guard, preview or runtime dependency changes are present. No new label suffix, selector redesign or full-directory offline persistence is introduced. There are no surviving patch findings.

### Focused verification evidence

- `/tmp/bugfix644-i6-red.log`: the real Agent detail-page regression failed before the fix with expected unconfirmed feedback versus actual `0 selected`; this is a meaningful observable red, not a collection/import failure.
- `/tmp/bugfix644-i6-green.log`: two files / 23 tests passed after the fix. The page test covers no snapshot with both empty and nonempty explicit denylists and recovery to a genuinely confirmed empty result; existing selector tests retain explicit-allowlist/denylist conversion and enabled:null protection.
- `/tmp/bugfix644-i6-typecheck.log`: caller reports successful frontend tsc; the log was inspected and has no diagnostics. This is reused evidence, not an independently rerun compiler claim.
- Independent actual-component rendering at frozen feb2e1885, command `tsx --tsconfig src/IM/frontend/tsconfig.app.json /tmp/bugfix644-i6-static-boundaries.mts`, exit 0; output `/tmp/bugfix644-i6-static-boundaries.log`: unknown empty denylist, unknown nonempty denylist and old-derived-state all rendered `Default state has not been confirmed`; old-derived group retained its dash count; explicit empty allowlist and confirmed empty denylist both rendered `0 selected`.
- `git diff --check feb2e1885^..feb2e1885`: passed. No service or production manipulation and no business/test edits were performed by this reviewer.

### Retained evidence and delta impact

The effective main-base movement from `51072cb58` to `55376c111` changes only documentation, skills and CI. Actual diff inspection shows no product implementation movement in that base update. Changes to final CI dispatch affect what caller must execute/report, not the content or provenance of already recorded HTTP/UI results. This local patch itself changes only the Skills discovery-status caption input and its page regression. Consequently Round 2 static closure, mutation/authorization boundaries and the product review's expressly retained unaffected journeys remain applicable. There is no evidence requiring a fresh full static review.

Incident R2, design's unknown/default-discovery constraints and the added agents-nodes delta already require unknown information not to masquerade as an empty business value. I6 fixes the implementation to those same contracts; explicit empty selection and last-confirmed-source semantics are preserved. No delta edit is required, and no newly uncovered stable external behavior was identified. The canonical Corrected Delta Reconciliation table above is updated to this final source while Git retains earlier rounds.

The independent product reviewer is separately performing I6's final real-page closure. This static PASS does not preempt that result or invent final full-CI evidence. Overall unit delivery remains subject to the caller's final checks and the separate product verdict. Only this report is changed; `code-review.json` is revalidated and remains the empty current finding array.
