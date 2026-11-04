# Verification Report: feat-711-context-short-ids

**当前结论（Round 6）：实现、设计、修正 delta-spec 对账及相关验证通过；最终可下载 artifact / 集成交付 pending。** 尚未通过公开下载、匿名 integrity、HTTPS 固定依赖 frozen install 与最终 artifact gate，因此不能标记 Full 全部门禁完成或交付完成。

## Round 1

- verification_mode: full
- review_round: 1
- executed_base: plugin `00f61960a6a81078cb9102347a277aa9147fe30b`; Nano `2ac60077e4988ab0db5789841b51f42bab02789c`
- validated_at: plugin `43f47ce952928b64c197fec393cc600e2070278d`; Nano same HEAD plus supplied source/test working changes
- requires_full_verification: false (a targeted fix plus pending acceptance evidence can close this report)
- verdict: issues_found — 0 CRITICAL, 1 WARNING; milestone acceptance evidence still pending

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | Core implementation and deterministic regression coverage present; final provider/model acceptance and immutable dependency handoff pending |
| Correctness | 2/3 requirements mechanically covered; original-content preservation has a confirmed collision defect |
| Coherence | Follows all seven design decisions except reliable ownership of stripped markers in decision 3 |

## Completeness

- Read spec.md, approved design/design-review and delta-spec, current Gateway default context/restore/authorization contracts, architecture boundary and Context/test standards.
- M1-short-ids implementation is present: ordered short IDs, pre-step inputs, final tool replacements, signed pricing/replay, History original/dedup/activity handling, unchanged host seq IDs, safeBoundary replacement skip, concise budgets and guidance.
- Independent minimum seam: plugin `pnpm exec vitest run tests/short-ids.spec.ts tests/history.spec.ts tests/tools.spec.ts` passed 3 files / 10 tests (2026-11-05 00:14:39 +08:00). Owner-reported plugin full suite 36 passed plus build/typecheck is supplementary; Nano focused run was still underway when dispatched.
- Existing tests were adapted where reference-table output was intentionally removed; pressure test continues distinguishing actual shrinking from marker pricing. No permanent tests were added by verifier.
- Prototype/reference: N/A, no UI change or prototype contract.
- The temporary local tarball pointer is allowed for this validation phase. Final immutable URL/integrity is a pending release handoff, not a source defect or production authorization.

## Correctness

| Requirement / Scenario | 实现位置 | 测试/直接证据 | 状态 |
|---|---|---|---|
| First consumption provides ordered short references without extra table query | plugin src/item-id.ts:15-41; src/index.ts:134-159 | tests/short-ids.spec.ts first-request/user/tool capture, errors/finalizer; independently passed | covered mechanically |
| Trim/reset/restart preserves IDs and original text, Unicode continuation | plugin src/history.ts:85-160,257-275 | tests/short-ids.spec.ts prune/reset/JSON replay; history.spec.ts Unicode/paging/provenance; Nano context-short-ids.test.ts real process restart fixture present | WARNING: terminal original marker loss |
| Original source evidence seq API unchanged; completed source boundary advances across replacement | plugin src/history.ts:297-309; Nano packages/dsh-integration/src/knowledge/memory-source-view.ts:58-71 | history.spec.ts public immutable view; memory-source-boundary.test.ts complete later step, cutoff and unpaired append | aligned; Nano execution result pending owner |
| Budget only remaining/unknown with estimate semantics | plugin src/tools.ts:50-73 | tools.spec.ts null/number structured results; renderer inspected (Approximately… / unavailable) | covered mechanically |
| Final model request marker delivery, stable runtime snapshot size; model uses latest correction after trim/reset/restart | pre-step/adapter and existing stable window contribution | scripted capture available; actual provider/model acceptance evidence not yet supplied | pending acceptance, not a claimed product defect |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| Derive IDs from first message identity in complete event order, including assistant gaps | 是 | src/item-id.ts:15-25 |
| Annotate admitted user and final tool content before next request, preserve source/error/meta | 是 | src/index.ts:134-159; src/item-id.ts:35-64 |
| Remove only plugin-owned dedicated final block; preserve original [id:] content | 否 | src/item-id.ts:29-32,54-55 (finding R1-W1) |
| Canonical earliest logical history with no replacement duplicates; marker-only is active | 是，受 R1-W1 影响 | src/history.ts:85-169 |
| Preserve seq-based host API and skip native replacements in source completion boundary | 是 | src/history.ts:297-309; Nano memory-source-view.ts:64 |
| Concise estimated budget, no reference table or intermediate telemetry | 是 | src/tools.ts:50-73; src/guidance.ts |
| Preserve pruning, pressure/overflow policy and stable snapshot identity | 是，模型实测待补 | src/index.ts:143-203,234-240; src/checkpoint.ts |

### Agent Context Review reuse

This verification reuses the same independent Mode B review recorded in code-review.md rather than running another complete context review. Assembly tests are scripted-adapter/llm-stream evidence, not true provider serialization or autonomous model behavior. Current session/tool selection and read authorization code remain intact; no new cross-session enumeration or business permission was introduced. The design itself is coherent after the prior two design-review closures.

## Issues

### CRITICAL

None.

### WARNING

- **R1-W1 / CONFIRMED — Original terminal marker collision loses source material.** plugin `src/item-id.ts:31` strips any terminal `\n[id: N]` block even from original unannotated logs; line 55 also skips annotating original tool content matching its ID. This violates design.md:32-34 and spec original recovery. Read-only direct Node reproduction showed original user block `\n[id: 123]` omitted, and original tool block `\n[id: 3]` treated as existing marker with zero events appended and omitted on recovery. Track plugin ownership reliably and add original/legacy multi-block roundtrip protection at own-History and host-view seams. See code-review.md for full Context surface, impact and evidence limitations.

### SUGGESTION

None.

## Remaining evidence / handoff

- Owner must complete final Nano focused execution/build checks and immutable dependency handoff against the actual fixed artifact.
- Milestone reviewer must supply actual provider input/response evidence for final marker delivery and representative latest-correction recovery after prune/reset/restart, plus stable runtime snapshot contribution. These are unverified at this snapshot; fixture success cannot stand in for autonomous behavior.
- Close R1-W1 with a bounded delta review and relevant regression; no speculative broader redesign requested.
- No services, worktrees or runtime data were created by this reviewer; only these reports were written. Shared checkout and report commit remain caller-owned.

## Round 2 — targeted closure and evidence update

- verification_mode: targeted-closure; focus: R1-W1 and affected original recovery/host-view/adapter projection.
- validated_at: plugin `ba81dc4b5de192d3e2e0f5a4ef29616d3c4e7f42`; Nano source remains the supplied working change plus updated local pack pending.
- requires_full_verification: false for this fix delta. **Full milestone verification is not achieved.**
- Current findings: 0 CRITICAL / 0 WARNING / 0 SUGGESTION in reviewed implementation; R1-W1 closed. Overall acceptance remains incomplete rather than pass.

### Finding closure

R1-W1 is closed by marker-owned `contextItemId` metadata, checked with exact block text before strip/idempotence. This preserves original marker-looking blocks and repeated input acceptance without altering IDs or model-facing marker text. Independent fixed-code reproduction covered original legacy user block, tool collision, own normalized History, host seq read, JSON replay and repeat markInputs; all passed. The native pi-ai adapter builds text from `block.text` and does not forward the internal field. See code-review.md Round 2 for exact version, adapter locators and evidence limits.

Independent focused suite on the frozen fix: 3 files / 11 tests passed. Owner reports plugin 37 tests, typecheck and build passing; Nano real-process short-ID capture → prune → reset → shutdown → restart → History tail regression passes, and source_history/boundary 17 tests pass. These latest owner reports supplement the direct review; no true-model behavior is inferred from scripted provider fixtures.

### Outstanding exit evidence

Owner reports Nano full-suite failures under investigation; do not claim aggregate Nano validation passed. Immutable tarball handoff and real provider/model latest-correction long-task acceptance remain outstanding. The implementation matches the reviewed design after R1-W1 closure, but final milestone/PR readiness requires those separate results and confirmation of the actual locked artifact.

## Round 3 — final integration delta and corrected delta-spec

- verification_mode: delta + corrected-delta reconciliation.
- Plugin validated_at: `21ce6d7c1a3245347616318eebdc8ba12645e00a`; Nano validated_at: `3fa3476ef` plus supplied source-neutral dirty fixtures and temporary package/lock pointer.
- requires_full_verification: false; prior full coverage and R1-W1 closure retained.
- Implementation findings: **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. Implementation/design/delta are aligned for this scope.
- Overall verdict: **incomplete; not yet ready for final gate**. Final immutable artifact, aggregate checks and independent true-model product acceptance are pending, so this is not an all-checks-passed statement.

### Completeness and correctness update

| Contract / consumer | Actual evidence | Result |
|---|---|---|
| Structured approval evidence retains original object representation and trust/source | plugin public stripContextItemId export; Nano policy/sources.ts:46 uses it before text/JSON projection; approval tests retain structured-result and side-effect/denial checks | implementation aligned; final aggregate run pending |
| Task receipts preserve exact business originals across restart/dedup/control | Nano task-context.ts:12-20 strips only returned receipt content, retains identity/turn/consumedSeq and same flush; task-context-sync tests retain independent exact receipt reconciliation, stop/resume and single ingestion across restart | implementation aligned; owner narrow sync 13 passed |
| Native replacement does not falsely terminate Memory source cut | memory-source-view.ts:62-69; memory-source-boundary cutoff/unpaired append; source_history seq unchanged | aligned; owner source/boundary 17 passed |
| First real-runtime capture → emitted ID → native prune/reset/process restart → original tail continuation | context-short-ids.test.ts:44-59; plugin short-ids/history/price/replay coverage retained | owner reports process test passed; scripted mechanism evidence only |
| Actual provider marker delivery, bounded snapshot contribution and autonomous latest-correction long-task delivery | separate product_review_711 run, not replaced with fixture output | pending independent product-review result |
| Fixed immutable distributable consumed by Nano | installed local `21ce6d7` pack; package/lock still file:/tmp validation dependency | pending immutable release URL/integrity handoff |

### Test review and evidence limits

Reviewed every changed test hunk. Native replacement copies are excluded from execution-result counts, while append execution results, independent sent/product-call arrays, denied outcomes, source and authority checks stay present. Original-content comparisons remove only plugin-owned display metadata, preserving all original blocks; the dedicated context-short-ids test asserts the raw marker separately. No product permission, side-effect or strict receipt acceptance criterion was weakened.

No aggregate rerun was started by this reviewer because the owner is running it. Build/typecheck successful endpoints were read from `/tmp/nano-id-projection-L6wMZV/{nano-build.txt,typecheck.txt}`. `/task-result.txt` captures the older 13-pass sync test and two subsequently corrected fixture failures; it is preserved as failure evidence, not relabeled green. At review time `/nano-all-tests.txt`, Python/frontend/iOS aggregate checks were in progress. Need final results/version attribution from owner.

### Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Short ordered references at first consumption | plugin item-id.ts / index.ts pre-step, frozen core unchanged | plugin short-ids; Nano context-short-ids captures raw request | aligned mechanically; real-provider acceptance pending |
| Stable original recovery after trim/reset/restart, no physical duplicates | canonical history normalization/active comparison; owned marker removal | independently passed core 11-test R2 run; process-restart fixture owner pass | aligned |
| Existing business evidence and authorization unaffected | policy/sources.ts:46; task-context.ts:19; memory-source-view.ts:64; host seq History default | approval, Task receipt strict matching, source/boundary tests inspected; source/boundary owner pass | aligned |
| Concise estimated budget or unknown | plugin tools.ts remaining renderer and structured value | plugin tools.spec.ts R2 pass; true-model result separately pending | aligned mechanically |

Uncovered observable behavior: none found in the implementation delta. Corrected scenarios only make already-approved marker/original/evidence semantics explicit and use required WHEN/THEN format. Internal ownership field/helper and temporary package installation are implementation details, not new standalone contract requirements.

Outcome: **aligned** (implementation/design/delta reconciliation); **overall gate incomplete** until final artifact, aggregate test results and true-model product evidence arrive.

## Round 4 — first-input reference stability correction

- verification_mode: delta; fixed validated_at plugin `9cbb3f719d5266aafeda2bd0c50dbff21d5e16aa`.
- Prior real-model candidate `21ce6d7` failed original-user reference stability; previous tool-only restoration success does not close this. The earlier completeness confidence was insufficient for native controls committed between marker assignment and durable user order.
- Design Round 5 is Approved; fixed implementation matches that bounded delta.
- Fixed-delta findings: 0 CRITICAL / 0 WARNING / 0 SUGGESTION. **Overall verification remains incomplete.**
- requires_full_verification: false for this bounded delta; requires the declared native-control runtime regression and targeted real-model product closure, not another speculative full review.

### Direct evidence

| Obligation | Evidence | Status |
|---|---|---|
| Pending allocation and full-log reconstruction exclude same native control sources | item-id.ts shared controlSources and itemMessage; read-only built-code preassign/control/user/JSON-replay scenario returns id1 before and after | aligned |
| Own short History matches short numbered domain | history.ts snapshotItems conditional calls itemMessage only for short user records; direct scenario returns only user1 | aligned |
| Host original seq API keeps native control records | createHistoryView remains short=false; direct host query returns catalog seq0/instructions seq1/user seq2 and original control content | aligned |
| Failure reproduced before fix | /tmp/nano-id-projection-L6wMZV/late-controls-red.txt: expected1 / actual3 after replay | confirmed plugin red |
| Locked-runtime Skill + AGENTS first request and both original tool/user restores across reset/process restart | updated context-short-ids.test.ts inspected; candidate installation/run pending | pending; current native-controls-red.txt fails absent AGENTS injection, not drift |
| New real-model candidate uses first-visible user1 after reset/restart | product_review_711 targeted new session | pending; prior failed product result retained |

The exclusion changes neither original persisted native-control delivery nor host seq projection, and it leaves business inputs, tool results and authorization metadata untouched. Known five native controls share the same eligibility rule at pending and committed phases. No broader exclusion of arbitrary system-looking text or Skill result content was introduced.

### Shared aggregate evidence update (owner reports)

- Plugin prior candidate `21ce6d7`: 37/37 plus typecheck/build passed; new `9cbb3f7`: 38 tests/typecheck/build passed.
- Python docs-check / pytest 135 passed, 28 deselected / ruff check+format passed; frontend 1077 tests in 113 files passed with critical audit gate passed; full build/typecheck and iOS runtime check passed. These are supporting owner-run results, not independent reruns. Final immutable artifact must still be the accepted candidate.
- Native fixture command updates (global-child-tools / knowledge-review first text command decoding) passed 11 tests at `/tmp/nano-id-projection-L6wMZV/fixture-closure.txt`. These preserve original command protocol while raw capture retains markers.
- Nano aggregate is not all green: personal-security hit 30-second timeout under aggregate concurrency. Its unchanged isolated rerun passed in 26.67 seconds; no product behavior or threshold was changed. Preserve both outcomes, and do not relabel the aggregate run as passed.

Current outcome: fixed implementation/design/delta **aligned** at the deterministic seam; full gate **incomplete** pending corrected native-control runtime fixture, new-candidate actual-model closure, immutable artifact and final aggregate accounting.

## Round 5 — product closure retained; performance delta pending

- verification_mode: delta and evidence-closure preparation.
- Reviewed source: plugin `9cbb3f7` plus current dirty lazy item-id scan change; Nano `809113b89d21ce9be760f90de441819b7a33d185` plus installed temporary lazy package/lock. Source has not yet been frozen into the final release candidate.
- Findings on source delta: 0 CRITICAL / 0 WARNING / 0 SUGGESTION. requires_full_verification: false.
- **Overall verdict remains incomplete** pending the actual installed lazy candidate's runtime Task stress and recovery result, final immutable artifact and final aggregate accounting.

### Product evidence closure

Acceptance Round 2 at report commit `809113b89` is pass for frozen `9cbb3f7`; product R1-1 is closed. It gives new-session actual input/response and delivered-product evidence: native Skill/AGENTS controls present; first user1 saved before material work; real tool pruning and original-ID continuation; direct user1 recovery after reset, after process restart and after another reset; latest correction recovered independently by its original reference; correct final four-line delivery including original literal marker text. Budget estimate and session-scope boundary evidence is retained with explicit applicable limits. No fixture result substitutes for that model behavior evidence.

The lazy delta changes only when redundant full-log ID mapping runs, leaving model-visible text/IDs, histories, tools, source/authorization and persistence unchanged. R2 may be retained for those unchanged semantic obligations. Its pass does **not** claim the subsequent performance candidate ran fast enough or that final packaging already occurred.

### Native-control regression closure evidence

- `/native-controls-red2.txt`: valid runtime red on old installed `21ce6d7`; first request really includes native catalog/instructions and final original user1 read returns Skill catalog/system instead of original user text.
- Earlier `/native-controls-red.txt` was merely a missing Skill-catalog activation failure (correcting R4's AGENTS attribution); not ID-drift proof.
- `/fixed-runtime-tests.txt`: on installed `9cbb3f7`, native controls plus two reset/process-restart original recoveries and Task graph checks pass (7 tests), while limits independently fails90s.

### Performance delta correctness

Empty pending now returns the same [] without map work; already-owned exact tool markers are left intact; the first actual unmarked tool builds the unchanged full-log map locally, and synchronous marker replacements do not add new logical identities. All source/error/meta/marker/pricing/replay/control exclusion/host seq code stays unchanged. Read actual Nano installed lib/item-id.js to confirm real installation of this delta. No process-spanning cache, new lifecycle or state format was introduced; no extra design Gate is needed for this bounded optimization.

Owner reports dirty candidate plugin38 tests/typecheck/build pass. Current `/lazy-real-tests.txt` execution must establish unchanged-threshold Task stress plus native-control recovery. Baseline rc.7 passed55.34s; prior `9cbb3f7` failed90s, and diagnostic380/384 at45s shows the work was still advancing. The old copied-integration experiment failed to load the intended package and is excluded from conclusions. Until the actual installed run finishes, do not classify this performance regression as closed.

Other shared gate results and prior aggregate failures remain as recorded in Round4; later narrow successes must be attributed individually rather than rewriting the original aggregate run as green. Final fixed artifact/URL/integrity and final result reconciliation remain owner handoff obligations.

## Round 6 — frozen implementation / relevant-validation closure

- verification_mode: targeted evidence closure + final corrected-delta reconciliation.
- validated_at: plugin `9a2a29078d264311a7d4327e1e4940d0c966f537`; Nano source and product-report base `809113b89d21ce9be760f90de441819b7a33d185` plus prepared final package.json/lock HTTPS pointer.
- review findings: **0 CRITICAL /0 WARNING /0 SUGGESTION**. requires_full_verification: false.
- **Verdict: implementation / relevant validation passed; final downloadable artifact / integration delivery pending.** This is deliberately not Full all-exit-gates pass.

### Completeness / correctness / coherence

| Dimension | Final reviewed state |
|---|---|
| Completeness | All planned implementation and corresponding behavioral evidence present; immutable public-artifact consumption/integration gate unfinished |
| Correctness | Original-marker loss fixed; late-native-control ID drift fixed; semantic runtime and stress regressions closed by named final-candidate tests; true-model R2 latest-correction delivery retained |
| Coherence | Approved design R1–R5 and corrected delta-spec aligned; performance delta has no new interface, persistent state, trust boundary or allocation algorithm |

### Decisive final checks

1. Frozen source `9a2a290` differs from product-tested `9cbb3f7` only by the Round5 reviewed lazy map change. Native sources, identity mapping, marker content/ownership, shadow pricing, canonical History, host seq API, structured approval and Task receipt semantics stay unchanged.
2. Read actual `/tmp/nano-id-projection-L6wMZV/lazy-real-tests.txt`: unchanged Task limits plus real Skill catalog/AGENTS first user1 → reset/process restart → original tool/user recovery pass,2 files/2 tests,67.57s test execution. This closes the remaining performance/recovery evidence item; no more blanket suite is required solely to repeat it.
3. Independently hashed final local rc.8 tgz: SHA-256 `94cea01fa13425aaa925e51789aea084072e1a24095c89263e889909461ad9a3`; SHA-512 exactly matches prepared lock integrity. All30 lib files in the final tarball equal the actual installed candidate bytes. Owner reports final tarball and tested lazy tarball byte-identical. Thus local content identity is verified; public download identity is not yet verified.
4. Final plugin38 tests/typecheck/build and PR4 CI run41872361129 green are owner-supplied evidence. Existing build/typecheck, Python/docs/ruff, Web1077 and critical-audit, iOS runtime checks remain as recorded; no standards or timeouts were relaxed.
5. Original aggregate outcome is preserved:213 files /1159 tests,207 files /1146 tests pass and6 files /13 tests fail. Implementation.md maps all13 failures to exact fixture correction or unchanged final-candidate narrow rerun. The global/knowledge11, Task graph6, isolated personal-security1, native-control1 and Task stress1 results close the affected paths; overlapping rerun counts are not added to misstate the original aggregate result. The full original command itself remains failed history.
6. Acceptance R2 is actual-model pass and R1-1 closed, with new-session original user/correction/material references surviving real prune/reset/restart and final correct delivery. Its semantic scope remains applicable to this frozen nonsemantic optimization; no new model execution is claimed on `9a2a290`.

### Final corrected-delta reconciliation

| Requirement / scenario | Implementation and evidence | Outcome |
|---|---|---|
| First task/tool read has ordered short IDs; controls have no task marker | shared native-control exclusion; pre-step marker; actual native controls fixture and modelR2 | aligned |
| Original references and literal original text survive trim/reset/restart; no duplicate logical History | canonical original/dedup/activity; owned marker normalization; plugin regression; final actual runtime recovery and modelR2 | aligned |
| Existing approval/Task original evidence, seq references and authorization preserved | public normalizer in policy/Task receipt; native replacement completion skip; source_history/permission regressions and retained true-model scope denial | aligned |
| Remaining budget is concise estimated number/unknown without internal table | reviewed renderer/schema, plugin tests; model numeric pathR1/R2 with unknown branch correctly limited to deterministic evidence | aligned |

Uncovered observable behavior: none found. Outcome: **aligned**.

### Explicit remaining handoff

Draft release publication is awaiting user authorization. package.json and pnpm-lock.yaml now name the final rc.8 HTTPS release asset and matching locally verified integrity, without /tmp pointers, but node_modules still comes from the byte-identical local tested candidate. Public anonymous asset download/integrity check, frozen install from that URL and final artifact/integration gate are pending; no release publication, canonical current-spec merge/archive, final Nano PR/CI or production deployment is claimed by this report.

The remaining condition is an external artifact/integration handoff, not an unconfirmed implementation finding. Keep the unit open until it is fulfilled and validated; do not mark all Full milestone exits complete from the implementation/validation pass above.
