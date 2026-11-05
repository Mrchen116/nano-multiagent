# Code Review — M1-short-ids

**当前结论（Round 7）：代码审查及最终发布接入门禁通过，findings 为 `[]`。可进入已审 delta 的 canonical 归并、unit 归档与 Nano PR 交付；不表示 Nano 远端 CI、合入或生产部署已完成。** 历史失败与 pending 按原执行时间保留。

- Reviewer: independent `/root/static_review_711`; no implementation changes.
- Mode: full code review plus agent-context-review Mode B.
- Snapshot: plugin `00f61960a6a81078cb9102347a277aa9147fe30b..43f47ce952928b64c197fec393cc600e2070278d`; Nano `2ac60077e4988ab0db5789841b51f42bab02789c` plus the supplied source/test working changes. The temporary local tarball dependency is a validation pointer; release URL replacement is an owner handoff, not a defect.
- Trigger/surfaces: final user/tool input, stable IDs, History/Memory source normalization, budget result rendering, guidance and window/reset lifecycle.
- Covered: all plugin diff files and affected public DSH projection/token-meter seam; first-identity numbering; pending-user pre-step order and exclusion; native tool replacement/pricing; canonical originals/dedup/activity; host seq API; Nano safeBoundary and tests; budgets/guidance. Public exports only; no runtime patch/private import observed.
- Independent regression run: `pnpm exec vitest run tests/short-ids.spec.ts tests/history.spec.ts tests/tools.spec.ts` — 3 files, 10 tests passed on this snapshot. Owner also reported full plugin 36 tests plus build/typecheck passing; those reports are supplementary.
- Evidence limits: scripted adapter and llm/stream fixtures establish deterministic assembly, not provider wire or autonomous recovery. Actual-model long-task acceptance and final release artifact are separate owner/reviewer work pending at this review snapshot. No speculative findings were promoted.

## Findings

```json
[
  {
    "file": "/Users/czj/Repos/opensource-hub/dsh-agent-context-feat-676/src/item-id.ts",
    "line": 31,
    "summary": "[P2] Preserve original terminal [id:] text rather than stripping by shape",
    "failure_scenario": "A legacy user/assistant message or original tool response ends in a dedicated text block matching \\n[id: N]. stripItemId removes this original block from both own History and createHistoryView even if the plugin never annotated it. If an original tool block equals the allocated ID, markToolResults:55 additionally skips annotation, so History permanently omits original material from recovery. The source log remains intact but the exposed recovery text is lossy.",
    "review_mode": "full",
    "status": "CONFIRMED",
    "surface": "Original user/tool material → active marker projection → own History and host source_history",
    "expected": "Only the marker added by this plugin is removed; original [id:] content, including terminal dedicated blocks and pre-upgrade logs, survives recovery (design.md:32-34).",
    "observed": "On plugin 43f47ce, an unannotated original user with content blocks [\"preserve literal block\", \"\\n[id: 123]\"] normalizes to \"preserve literal block\". An original tool result ending \"\\n[id: 3]\" with assigned ID 3 causes markToolResults to append zero events and normalized History omits that original block.",
    "impact": "Agent and Memory source consumers can lose source facts or quoted references while recovering supposedly original records. The failure is deterministic, independent of model interpretation.",
    "recommendation": "Distinguish plugin-owned marker blocks using durable, unambiguous provenance rather than terminal text shape alone; preserve unannotated original/legacy blocks and avoid treating a coincidental original block as proof of prior annotation. Add a narrow original-content roundtrip regression for own History and seq-based createHistoryView.",
    "severity": "WARNING",
    "evidence": "Read-only Node reproduction against built lib on HEAD 43f47ce (2026-11-05 00:13–00:14 Asia/Shanghai): Session.create + append original multi-block user/tool messages + normalizedItems; markToolResults tool case returned no revision change. src/item-id.ts:29-32,54-55; src/history.ts:129,154-160. Existing short/history/tools tests pass 10/10 and do not cover original terminal marker collision. No provider behavior claim."
  }
]
```

## Round 2 — bounded closure of R1-W1

- review_mode: closure; focus_findings: R1-W1; finding_origin_head: `43f47ce952928b64c197fec393cc600e2070278d`; fixed validated_at: `ba81dc4b5de192d3e2e0f5a4ef29616d3c4e7f42`.
- Reviewed only fix delta `43f47ce..ba81dc4` (`src/item-id.ts`, `tests/short-ids.spec.ts`) and the affected native adapter projection. No design semantic change: block ownership implements design.md:32 preservation/idempotence requirement.
- **R1-W1: closed / CONFIRMED.** Markers carry `contextItemId` on the dedicated internal text block; stripping and idempotence require both ownership and exact marker text. Coincidental terminal marker-looking text remains original content.
- Independent reproduction on built fixed code: legacy unmarked user `\n[id: 123]` survives; original tool `\n[id: 3]` is retained and receives its separate owned marker (two native events appended); own History and seq-based host view retain original block; JSON log replay retains it; repeated markInputs is unchanged; stripping one owned block recovers original input. All seven checks true.
- Independent focused regression: `pnpm exec vitest run tests/short-ids.spec.ts tests/history.spec.ts tests/tools.spec.ts` passed 3 files / 11 tests at 2026-11-05 00:16:21 +08:00. Owner additionally reports full plugin suite 37 passed, build/typecheck passed.
- Adapter boundary: installed Nano `packages/dsh-integration/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js:1163-1164,1188-1213,1292-1311` constructs native text from `block.text` via flattenText/userContent; it does not forward `contextItemId`. `@deepseek-ai/dsh-llm/lib/index.js:29-30` clone/freezes the complete message so marker ownership persists in the session; JSON replay was independently checked. Thus ownership metadata does not inflate the model-visible marker. This is source-level deterministic projection evidence, not a captured provider wire request.
- Remaining source findings:

```json
[]
```

Code finding closure passes for the frozen fix. Full milestone verification remains open for owner-reported Nano suite failures under investigation and actual-provider/model acceptance; this closure does not claim those gates passed.

## Round 3 — final integration delta / Mode B

- review_mode: delta, retaining R1 full coverage and R2 closure.
- Plugin target: `ba81dc4b5de192d3e2e0f5a4ef29616d3c4e7f42..21ce6d7c1a3245347616318eebdc8ba12645e00a` (public `stripContextItemId` export and README).
- Nano target: `2ac60077e4988ab0db5789841b51f42bab02789c..3fa3476ef` plus supplied dirty `context-revalidation-provider.test.ts`, `dreaming-incomplete-runtime.test.ts`, `knowledge.test.ts` and temporary dependency/lock changes. No implementation changes by reviewer.
- Approved design deltas: design-review.md Round 3 / Round 4; unchanged short-ID/recovery/budget design retained.

### Coverage and conclusions

- **Public helper / structured approval:** plugin src/index.ts re-exports the reviewed owned-marker stripper without changing its semantics. Nano `policy/sources.ts:46` strips the owned marker before original text concatenation/parseJson. This restores object-valued Inbox/conversations/send results instead of leaking an appended marker into JSON parsing; source, call IDs, error outcomes, live/restored and participant/observer classifications are untouched. Literal marker-looking original text is preserved under R2's ownership rule.
- **Task original receipt:** `task-context.ts:12-20` flushes and extracts the same original task-context events and seq/turn identity, stripping only the owned marker from the returned evidence content. Both prepare and commit reuse this path. Product digest and Inbox strict content matching remain unchanged; this does not accept a queue acknowledgment as consumption, alter pause/resume authority, or change original persisted/model-visible content.
- **Memory boundary:** `memory-source-view.ts:64` ignores native replacement records before call/result pairing; time cutoff still applies first, genuinely unpaired appended results still stop the boundary. Existing source_history seq view remains unchanged and qualifiedEvents already excludes replacement copies.
- **Tests preserve meaningful behavior:** filtering `tool/result` with non-object surfaceOp excludes native replacement copies, whose public shape is an object, while real executions remain append records and still count. Existing independent sent arrays, product RPC counts, approval sources, denial/error and source identity assertions remain. No side-effect counter or allowed/denied expected value was relaxed. Repeated genuine execution would still appear in the append counts and/or sent/product-call assertions.
- **Test content adaptation:** Task/provider original-content assertions call the public owned-marker stripper but still strictly compare the whole remaining block array, source, input ID and consumedSeq. Task fixture reconcile independently compares actual receipt content against unmarked originals, so receipt correctness is not manufactured by the assertion helper. Incomplete-Dreaming fixture parsing removes only the display marker from captured raw results; all failure/progress/unchanged-Memory assertions remain. Knowledge fixture reads the first original text block of its single-block input to match its existing command script; it does not alter product behavior.
- **Delivery/recovery evidence seams retained:** `context-short-ids.test.ts:44-59` captures the first user request and next tool request, reads the emitted short ID, asserts real native pruning (`middle pruned`), resets natively, shuts down and restarts the real runtime process, and restores original tail by that captured ID/continuation offset. Its scripted recovery arguments prove mechanism and wiring, not autonomous model tool choice. Plugin short-ids/history tests retain Unicode continuation, normal/error/finalizer results, physical dedup/activity, original marker preservation, signed token delta, idempotence, replay and host seq API protection. Existing engine/safety tests retain stable runtime-window contribution and reset pressure checks.
- **Validation scope:** no full suite rerun by reviewer while owner runs aggregate gates. Reuse R2 independently executed 11-test result for unchanged core plugin semantics. Owner reports plugin full 37 tests/build/typecheck and Nano restart/short-ID + source_history/boundary narrow checks passed. `/tmp/nano-id-projection-L6wMZV/nano-build.txt` and `typecheck.txt` end successfully; `/task-result.txt` is intentionally historical (Task sync 13 passed plus two later-fixed original-content fixture failures), not asserted as all-green. Aggregate outputs and independent actual-model product acceptance remain in progress.
- **Delta-spec reconciliation:** converted existing requirements to explicit scenarios per prior design-review R1-R1. Added only already-approved observable preservation of literal original content, marker-only activity, structured approval/Task evidence and unchanged source_history seq/authorization. No canonical current spec was overwritten and no new implementation target was introduced.

### Findings

```json
[]
```

No new confirmed or plausible code defect in this bounded delta. R1-W1 remains closed. Code review passes the reviewed implementation; full verification/PR readiness is **not** declared before final immutable artifact, aggregate checks and actual-model acceptance evidence.

## Round 4 — native controls / first-visible ID stability delta

- review_mode: delta / Mode B; retained_from R1–R3 outside this fix.
- Target plugin: `21ce6d7c1a3245347616318eebdc8ba12645e00a..9cbb3f719d5266aafeda2bd0c50dbff21d5e16aa` (`src/item-id.ts`, `src/history.ts`, `tests/short-ids.spec.ts`). Nano dirty integration fixture also inspected; no implementation edit by reviewer.
- Design delta: design-review.md Round 5 Approved. The previous real-model candidate failed first-input ID stability; that failure is retained and is not superseded by older successful tool recovery. Prior deterministic coverage did not include this native-control assembly ordering.

### Finding origin and affected consumer

Native `skill-catalog` and `agent-instructions` can be committed ahead of a user after its marker was assigned. Old `21ce6d7` counted those control messages during later full-log reconstruction, so the first-visible user `[id: 1]` became item 3. `/tmp/nano-id-projection-L6wMZV/late-controls-red.txt` shows expected 1 / actual 3 in the new regression. Design R5 independently cites the actual failed candidate event sequence. This is a confirmed reference defect in the prior candidate, not a model-choice issue. The fixed candidate needs a new product closure.

### Delta review and direct verification

- The shared `controlSources` now excludes exactly runtime-context, compact-checkpoint, agent-context, skill-catalog and agent-instructions in both committed-log `itemMessage` and pending `itemIds` allocation. Because markInputs gets IDs from the same map, these controls neither consume a short number nor receive a task-material marker. Real user/nano-system task materials, assistant records and actual tool results remain in the numbered domain.
- Own short History uses `itemMessage` to exclude the two newly excluded user control sources before normalization/dedup, so it no longer falls back to a seq item ID for an unnumbered control. This keeps pending allocation, durable replay and model-facing own-History consistent.
- `createHistoryView` invokes snapshotItems with short=false; the added condition is short-only, while existing exclusion of the original three control types is unchanged. Thus the host's existing inclusion of skill-catalog/agent-instructions and their physical seq references is preserved. Native sources are selected by actual metadata, not text heuristics, and source logs/model injection are not deleted.
- Independently ran a read-only built-code scenario on `9cbb3f7`: assign user before logging either native control, append both controls then user, JSON replay. Result: first marker id1, rebuilt user id1, own normalized items only user1; host seq view retains controls at 0/1 and user at 2, with readable original control bodies. This checks actual exported host behavior in addition to source inspection.
- Locked public DSH code confirms the relevant seams: AgentLoop prepares the decision at `dsh-agent-loop/lib/index.js:911-926`, then commits decision user messages at `:1061`; native Skill pre-step middleware builds source-tagged catalog decisions in `dsh-tool-skill/lib/index.js:839-872` and source metadata at `:892,916`. The exclusion is bounded to native controls implicated by the actual failed trace; it does not silently exclude Skill result bodies or Task/human input.
- The new plugin regression directly checks preallocation → intervening controls → user append → JSON replay and canonical user1. Owner reports 38 plugin tests, typecheck/build pass. No full suite rerun was performed by reviewer.
- Updated Nano fixture adds real skill directory and AGENTS injection, first request presence checks, user1 assertion and two separate native reset/process-restart restores (tool tail then first user). This is the appropriate missing runtime seam; its new result is pending. **Important instrument limit:** `/native-controls-red.txt` currently fails the agent-instructions-presence assertion at line 52, not user-ID drift. It cannot be cited as the runtime ID-drift red result. The plugin expected1/actual3 red remains valid independently. Caller was notified to repair/verify native AGENTS injection before using this fixture result.

### Findings on fixed delta

```json
[]
```

No surviving code defect identified in the frozen fix delta. Confirmed old-candidate first-user reference defect is mechanically repaired at the reviewed seam; product issue remains open until new installed runtime and independent actual-model targeted acceptance pass. Final immutable artifact and aggregate result accounting remain separate unfinished gates.

## Round 5 — bounded performance delta / evidence closure preparation

- review_mode: delta / Mode B; origin `9cbb3f719d5266aafeda2bd0c50dbff21d5e16aa`, reviewed current dirty `src/item-id.ts` (4 insertions / 3 deletions), not yet a frozen release commit. Nano HEAD `809113b89d21ce9be760f90de441819b7a33d185`, with a temporary installed local lazy candidate. No implementation changes by reviewer.
- Installed artifact check: read Nano `packages/dsh-integration/node_modules/dsh-agent-context/lib/item-id.js`; it contains the actual empty-pending return and lazy map below. It is the real worktree-installed candidate, rather than the earlier invalid copied-integration experiment.

### Delta reasoning

1. Empty pending inputs formerly built a full-log map then returned pending.map = []; returning [] before the scan has the same result and introduces no persistent state.
2. For a valid existing owned final marker, text and contextItemId already identify the annotation written for this message; the new check uses the same ownership/exact-text predicate as stripItemId and leaves that annotation untouched without reconstructing the entire log. Original unowned marker-looking blocks still fail the ownership check and are annotated normally.
3. The first actual unmarked tool lazily builds itemIds from the same full log and unchanged algorithm. Additional replacement events appended synchronously in this loop reuse existing message identities, so retaining that one local map for the current loop cannot renumber subsequent original tool results. The previous eager map also did not rebuild after each replacement. No cache survives the invocation and no new persistent index/protocol is added.
4. New marker construction, source/error/meta preservation, native replacement adjacency/shadow pricing, History normalization, control-source exclusions and host seq view are unchanged. On valid messages generated by the accepted numbering algorithm, owned-marker idempotence and JSON replay remain equivalent; this change removes redundant validation work on already-owned markers, not a new allocation or recovery rule. No compatibility with the earlier unpublished, known-failed candidate's wrong numbering is inferred.

### Acceptance evidence retained and corrected

- Acceptance Round 2 committed at Nano `809113b89` freezes plugin `9cbb3f7`, records a new real-model session with genuine native catalog/AGENTS input, direct initial/user1 recovery after reset and after process restart, subsequent latest-correction recovery, Unicode/original literal `[id: 777]` preservation and correct delivered four-line result. It explicitly closes product R1-1 and retains R1's unchanged budget/access-boundary observations.
- That behavior evidence is applicable to this nonsemantic lazy-scan delta: it changes neither delivered content/IDs, tools/schema, recovery selection, state persistence, source nor authorization. A new full model journey is not required solely for removing empty/redundant scans. The actual automatic-turn performance and restart seam still require the pending real installed-candidate tests.
- Valid old-candidate runtime red: `/tmp/nano-id-projection-L6wMZV/native-controls-red2.txt` reaches the final read of saved user1 and returns system Skill catalog instead of user USER_REQUEST; this is actual drift evidence for installed `21ce6d7`. Correction to R4's instrumentation note: the earlier `/native-controls-red.txt` line52 was the Skill-catalog presence check, not AGENTS; it only exposed incomplete fixture activation. The corrected fixture enables skill and creates the native project boundary/AGENTS.
- `/fixed-runtime-tests.txt` records new native-controls/first-user restoration and Task graph checks passing on installed `9cbb3f7` (7 passed), but Task limits timed out at the unchanged 90s overall limit. Preserve the distinct results.
- Actual performance comparison reported by owner: original rc.7 baseline passes in 55.34s; `9cbb3f7` times out, and `/limits-debug-result.txt` shows 380 of expected384 automatic turns after45s with work continuing, rather than proof of duplicate/lost inputs. The current real-installed lazy candidate is running the same unchanged Task limit and native-controls recovery tests; runtime success is not yet established.
- The copied-integration lazy-experiment did not load its intended bundle (no profiling callback); it is invalid evidence and supports neither performance success nor failure.

### Findings

```json
[]
```

No new defect identified in the lazy source delta. Runtime performance closure, final immutable candidate and aggregate outcome reconciliation remain pending; no final verification pass is claimed in this preparation round.

## Round 6 — frozen performance candidate and final evidence closure

- Frozen plugin: `9a2a29078d264311a7d4327e1e4940d0c966f537`; clean source checkout. Final delta from `9cbb3f7` is exactly the already-reviewed Round5 seven-line lazy-scan change, with no additional semantic/code delta.
- Nano source/report base: `809113b89d21ce9be760f90de441819b7a33d185`; final planned HTTPS rc.8 package/lock pointer is prepared but pending public artifact integration. Reports remain caller-owned for commit.
- Final local candidate `/tmp/nano-id-projection-L6wMZV/final/dsh-agent-context-0.3.0-rc.8.tgz`: independently computed SHA-256 `94cea01fa13425aaa925e51789aea084072e1a24095c89263e889909461ad9a3`; SHA-512 matches the prepared lock integrity `sha512-ckYUAHiXyMksSaw0ngU/19ijcoTLY4dF+6t+W/tPudolQ2bXlNN8z/BF92Qd0s3gQinYhXnNS/O4vwflSHDs0Q==`. Independently compared all30 packed lib files against the actual installed Nano candidate: zero byte mismatches. Owner also reports final tgz is byte-identical to the tested lazy pack.

### Performance and runtime closure

Read `/tmp/nano-id-projection-L6wMZV/lazy-real-tests.txt`: 2 files /2 tests passed, tests67.57s (67.88s total). This is the actual installed-candidate run of unchanged Task execution limits and genuine catalog/AGENTS first-user recovery across reset/process restart. No threshold or test behavior was changed for this final run. Original rc.7 baseline and earlier candidate timeouts remain recorded separately; no conclusion is derived from the invalid copied-integration experiment. The runtime performance regression is now closed for this declared stress case, without claiming a benchmark improvement beyond the passing gate.

### Final evidence reconciliation

- Plugin final source: owner reports38 tests/typecheck/build passed and PR4 CI all green (run41872361129,23s); no additional test suite was rerun by this reviewer.
- Nano initial aggregate remains6 files/13 tests failed and207 files/1146 tests passed. Every failed case has a named narrow closure in implementation.md: global-child-tools+knowledge-review11 pass, Task graph6 pass, personal-security unchanged isolated pass, genuine native-control recovery pass, Task limits unchanged final pass. This is a reasoned relevant-validation closure, not a claim that the original full command became green or that the final tree was rerun end-to-end in that same aggregate command.
- True-model acceptance R2 pass for `9cbb3f7` is retained for the nonsemantic performance delta per R5; R1-1 remains closed. Original literal-marker finding R1-W1 remains closed, as do design/native-counting gaps.
- Corrected delta-spec fully covers the implemented observable first references, original recovery, marker/physical-copy behavior, existing evidence/authorization and concise budget; no uncovered behavior or new design divergence found.

### Final source findings

```json
[]
```

**Implementation and relevant validation pass. Final downloadable artifact / integration delivery remain pending.** Draft release is awaiting user publication authorization; anonymous HTTPS download/integrity verification, frozen install from the prepared public URL, final artifact gate and subsequent Nano delivery/CI are not complete. No Full-all-exit-gates pass, final PR readiness or completed delivery is asserted here.

## Round 7 — public artifact and handoff gate closure

- review_mode: targeted artifact/handoff closure; retained_from R1–R6, including Mode B.
- executed_base: Nano `2ac60077e4988ab0db5789841b51f42bab02789c`.
- validated_at: Nano `ebea3cf8da9b6dd28495741794faedd7f5bda175`; plugin `9a2a29078d264311a7d4327e1e4940d0c966f537` / `v0.3.0-rc.8`.
- effective_base: Nano `2ac60077e4988ab0db5789841b51f42bab02789c`; current origin/main and merge-base independently checked equal this value.
- effective_through: Nano `ebea3cf8da9b6dd28495741794faedd7f5bda175`, including final HTTPS package/lock. Only reports changed in this round; implementation/canonical untouched.

### Independent checks

- `git ls-remote` confirms public tag v0.3.0-rc.8 points to `9a2a29078d264311a7d4327e1e4940d0c966f537`. Release API returns draft=false, prerelease=true and that target. PR4 CI run41872361129 is completed/success with the same headSha.
- Reviewer independently read the public HTTPS asset using unauthenticated curl. SHA-256 is `94cea01fa13425aaa925e51789aea084072e1a24095c89263e889909461ad9a3`, matching the accepted Round6 candidate. Public availability is directly checked, not inferred from the former draft/local file.
- `/tmp/nano-feat711-rc8-release/public.tgz` has the same SHA-256. Independently computed SHA-512 is `sha512-ckYUAHiXyMksSaw0ngU/19ijcoTLY4dF+6t+W/tPudolQ2bXlNN8z/BF92Qd0s3gQinYhXnNS/O4vwflSHDs0Q==`, exactly matching committed rc.8 lock integrity. package.json, repository lock and installed lock use the same HTTPS asset, without file:/tmp dependency.
- Read `install.txt`: lock up-to-date, downloaded1/added1 and supply-chain policy passed; caller records execution of `pnpm install --frozen-lockfile`. Independently compared every packed lib file against installed Nano node_modules: all30 byte-identical, version0.3.0-rc.8.
- Read new `build.txt` and `typecheck.txt`: successful after HTTPS installation. `runtime-tests.txt` passes two files/two tests, tests65.15s (total65.51s): genuine native catalog/AGENTS first-user recovery across reset/process restart and unchanged-threshold Task automatic-turn stress. No full suite or real-model journey rerun by reviewer.

### Retained gates and limits

`809113b89..ebea3cf8` only adds existing reports/implementation evidence and the reviewed final package/lock integration; no new product source or test semantics. Publication/installation introduces no code delta. R6 review, corrected-delta alignment, plugin38 tests/typecheck/build, other named narrow closures and independent modelR2 therefore remain applicable. Original Nano aggregate207 files/1146 tests passed and6 files/13 tests failed remains recorded with its later individual closures, never rewritten as the original command all-green.

The old `/tmp/nano-id-projection-L6wMZV/` evidence directory was cleaned by the environment. Previously reviewed and committed execution facts remain as recorded; absence of temporary raw logs neither reverses those valid historical findings nor implies reruns. New artifact/install/build/type/runtime evidence is in `/tmp/nano-feat711-rc8-release/`.

### Findings / handoff

```json
[]
```

**Pass: final artifact/handoff gate closed.** Public bytes equal the accepted candidate and HTTPS frozen installation passes recovery/stress validation. Ready for unchanged reviewed delta canonical merge, unit archive and Nano PR. Caller performs those document/delivery steps. No Nano PR exists yet, so no Nano remote CI result is claimed; plugin CI/local checks are not relabeled Nano CI. No production deployment is authorized or performed by this report.


## Round 8 — window-local IDs follow-up / independent code review

- review_mode: full specified plugin delta + targeted Nano follow-up, Agent Context Mode B. Reviewed plugin `2fa5911cb035caef2afb762d0715ed93d073079b..1b35100f4559e2d319268209c4a0d0353f76eaff` (12 files), and Nano `a4533edeaedf34595322ca313b359d2f196d247f` plus the uncommitted window-local spec/design/review/delta-spec and `packages/dsh-integration/tests/context-short-ids.test.ts`. Design R6 Approved is the target. Reviewer did not modify product source or tests.
- Covered shared successful-window detection; logical first-occurrence grouping and physical replacement ownership; legacy persisted markers and unprinted assistant positions; pending-input reannotation after a same-step reset; guidance/reminder/fallback composition; paired History addressing; host seq view; restart/replay integration assertions. Existing source/error/provenance and authorization boundaries remain unchanged in this delta.
- Reused execution evidence: `/tmp/feat711-window-ids-plugin-tests.log` records 41 plugin tests passing; `/tmp/feat711-window-ids-nano.log` records the real RuntimeClient subprocess restart fixture passing (stub LLM); `/tmp/feat711-legacy-window-replay.json` records the prior real child log's 77 logical IDs across three windows with zero changes. These are applicable evidence, but do not establish compatibility for every old-window shape.
- New independent verification uses an isolated archive of the exact old plugin base at `/tmp/feat711-static-review-rc8`, with its original actual AgentLoop harness and the existing hard-cap-pressure script shape from `tests/safety.spec.ts`. The reviewer-only test `/tmp/feat711-static-review-rc8/tests/review-zero-anchor.spec.ts` compares the old plugin's History output against the candidate's reconstruction of that exact old event log. No preview, production process or caller model run was touched.
- Evidence locator: `/tmp/feat711-static-review-legacy-zero-anchor.log:5-6` contains the old successful read, upgraded read failure and compact ID changes; `/tmp/feat711-static-review-legacy-zero-anchor.json` contains the summary; `/tmp/feat711-static-review-legacy-zero-anchor-events.json` retains the complete synthetic event log. The regression assertion is intentionally red (1 file / 1 failed test); this is new confirmed compatibility evidence, not a failing claimed candidate-suite execution.

### Findings

```json
[
  {
    "file": "/Users/czj/Repos/opensource-hub/dsh-agent-context-feat-676/src/item-id.ts",
    "line": 46,
    "summary": "[P2] Preserve legacy IDs for windows without a persisted marker",
    "failure_scenario": "Original rc.8 can produce a window containing only an assistant tool call and a result that triggers pressure before markToolResults runs, or a window containing only a final assistant response. Such a window has no contextItemId anchor. The old actual AgentLoop hard-cap script creates window review-legacy-hardcap:26 with History IDs assistant=6/tool=7, and :36 with assistant=8. Candidate reconstruction changes them to 1/2 and 1 because anchor<0 chooses base=0. Old History search/read returns :26/6 successfully; candidate read of that same saved pair returns not_found. Thus legacy references and unprinted assistant positions drift despite the explicit compatibility target.",
    "review_mode": "full specified plugin delta; Agent Context Mode B",
    "status": "CONFIRMED",
    "surface": "History / Compaction durable short references and Notes recovery",
    "expected": "Already-issued old window_id/item_id pairs and old rc.8 assistant positions remain stable; only windows created under the new numbering epoch restart at 1.",
    "observed": "An old window without an inline-marker anchor is treated as a newly numbered window, although rc.8 History can already have issued its global IDs.",
    "impact": "Saved references to valid archived actions/results fail recovery after upgrade; the current legacy assistant-only window also changes its numbering basis.",
    "recommendation": "Distinguish old unanchored windows from new numbering windows using durable upgrade/numbering provenance, preserve the old global positions for the former, and add this actual rc.8 pressure/replay case to the compatibility regression.",
    "severity": "WARNING",
    "evidence": "/tmp/feat711-static-review-legacy-zero-anchor.log:5-6; /tmp/feat711-static-review-legacy-zero-anchor.json; /tmp/feat711-static-review-legacy-zero-anchor-events.json; synthetic actual rc.8 AgentLoop execution, not a real-provider behavior claim"
  }
]
```

**Changes required for the confirmed legacy-window finding.** The current candidate's ordinary new-window reset, anchored legacy windows and same-step pending-input behavior have relevant passing evidence. This review does not claim immutable release/integration delivery, canonical merge, final verifier or independent real-model acceptance are complete. The tracked Nano dependency remains rc.8 while the caller's candidate linkage/model verification is in progress; that declared unfinished step is not reported as an implementation defect.


## Round 9 — final window-local rule / requirement-change closure

- review_mode: patch + closure / Agent Context Mode B; fixed plugin `1b35100f4559e2d319268209c4a0d0353f76eaff..76e7a421ec9191540ebb0fa3d0279a26c7070c96`. Nano source base remains `a4533edea` plus the declared follow-up docs/test and in-progress package wiring. Design R8 Approved and the latest user instruction “不需要！不用兼容旧版本” supersede the legacy compatibility target.
- R8-P2: **superseded by requirement change, not fixed**. The original rc.8 zero-anchor counterexample remains factually valid; preserving its old global IDs is outside the final scope. No migration metadata/epoch/fallback was implemented. The abandoned R7 compatibility design remains history.
- Read all three patch files: `src/item-id.ts` removes published-marker anchors/group bases and uses next=1 at each shared successful compaction end, maintaining one global message.id dedup map; `tests/short-ids.spec.ts` removes only the canceled compatibility test; README explicitly disclaims old session-wide-reference migration while preserving logs/Notes. Remaining marker ownership, pending reset reannotation, physical replacement, History paired lookup, source/authorization, budget, host seq and guidance are unchanged from reviewed Round8.
- Mechanically, a successful end is a non-message boundary, so resetting next before that event preserves History's subsequent-message window assignment. Replacements already in the global identity map consume no position in the new window. Failed/unclosed boundaries are absent from the same shared successfulCompactions result. Pending annotation does not participate in allocation; same-step reannotation strips the owned old block and creates one final block.
- Reused `/tmp/feat711-window-ids-plugin-final.log`: 40 tests /10 files pass on final source. Reviewer independently reran `/tmp/feat711-new-model-replay.mjs`: the actual R3 new-session log's nine persisted markers across three windows all match final allocation, zero changes (`/tmp/feat711-final-model-replay.json`). The patch does not alter guidance, Notes/History schema, underlying content or tool selection; R3 true-model behavior is retained for the supported new-rule scope, without claiming R3 originally ran on final source.
- Independently hashed local rc.9 tgz SHA-256 `af18a7df4a852fe3c1517f4f30f305a1036ce7d2950f784bc1c4cc0ffab3a296` and compared all33 packed lib files with Nano's normally installed candidate: zero mismatches, installed version0.3.0-rc.9. Read `/tmp/feat711-window-local-build-final.log`: normal peer-topology install builds successfully. The earlier temporary cross-repository symlink's duplicate DSH type identity error is not evidence of a product code defect, and its failure is not rewritten as success.

### Findings / closure

```json
[]
```

No surviving finding in the fixed patch under the final authorized requirements. Source review / R8-P2 scope closure complete. Final anonymous HTTPS artifact, lock/integrity installation, applicable post-install runtime checks and canonical reconciliation remain separate pending handoff conditions; this report does not claim those steps complete or production deployment authorized.


## Round 10 — public rc.9 artifact / final fixture delta closure

- review_mode: targeted artifact + one-line fixture patch closure; retained source review R9 / Mode B. Validated at Nano `326663749da12f1e8f179eca330cb1e9b755479a` (merge parents `a4533edea`, main `fc447faee`) plus the declared current follow-up diff; plugin source/tag `76e7a421ec9191540ebb0fa3d0279a26c7070c96` / `v0.3.0-rc.9`.
- Reviewer independently checked public tag and GitHub release API: tag resolves to the frozen source, draft=false, prerelease=true, named tgz asset present. Anonymous HTTPS download to `/tmp/feat711-review-public-rc9.tgz` yields SHA256 `af18a7df4a852fe3c1517f4f30f305a1036ce7d2950f784bc1c4cc0ffab3a296`; SHA512 `sha512-Ne3CiiV+n4D+R2wuN/xLYpxlqsWAZAUu4JqipcCuFoAlEkNKXYXKNcJreOxwZoIGlhMCbKdAR2ATZYxrYERflg==` exactly matches repository lock. All33 public packed lib files equal current normally installed HTTPS pnpm package bytes, versionrc.9. package.json and repository lock now use that HTTPS URL, with no local-tar pointer or cross-repository plugin linkage.
- One-line fixture patch at `packages/dsh-integration/tests/agent-disable-native.test.ts:67` resolves the actual `@deepseek-ai/dsh/package.json` before constructing createRequire, instead of anchoring resolution to a literal node_modules symlink path. This uses standard package resolution and the same declared DSH dependencies; it changes no product source, assertions, timeout or subprocess behavior. Reviewer independently resolved both terminal packages through this exact new anchor, confirming terminal-bash is a declared DSH dependency. `/tmp/feat711-window-local-native-fixture.log`: seven tests pass. No new finding in this patch.
- Final actual-model product R4 is fresh-state evidence, not merely retention of R3: acceptance.md R4 plus `/tmp/feat711-fresh-review/clean-start.json` establish empty newly allocated home before initialize, new Agent `fresh-review-8b2a1fc1-0554-4515-b794-d524096daddd` and session UUID `6b927f06-ca3f-4271-a6bd-bca5cddeed27`, without copied Notes/History. Final normally installed tgz bytes match the public release. `home-iqOJxx/checks.json` records nine real-model requests, input1/tool3 in all three windows, exact two-original recovery after two compact/process-restart boundaries, correct final result and all three processes exited. This is isolated RuntimeClient/real-model behavior, not IM/UI/provider-wire or production acceptance.
- `/tmp/feat711-window-local-public-runtime.log`: public-package cross-process recovery fixture1pass. `/tmp/feat711-window-local-host-contracts.log`: five files/22 tests pass for approval sources, Task originals, Memory/source-history/Dreaming boundaries. Normal installed-tar build/typecheck evidence remains applicable to these identical published bytes; publication adds no source delta. Reviewer did not rerun blanket suites.
- Current canonical short-reference Requirement independently compared byte-for-byte with corrected delta: equal. New-window scenario is present; existing original recovery/business evidence/authorization scenarios are retained.

### Findings / final handoff

```json
[]
```

**Pass: scoped code-review and final artifact handoff closure.** R8-P2 remains superseded by the explicit requirement change, not repaired legacy compatibility. Public artifact content, normal HTTPS installation, affected runtime/host-contract checks and fresh-Agent actual-model behavior are now evidenced; canonical reconciliation is complete. The local full-suite attempt was stopped after a concurrent global-child-tools PA=true case failed; all three unchanged case combinations subsequently pass independently. Preserve both facts: this report does not call the interrupted aggregate green. Nano remote complete CI, PR creation/merge and deployment remain subsequent delivery steps, with production outside this review authorization. The inspected install log records a normal HTTPS install; no frozen-lockfile execution is inferred from it.
