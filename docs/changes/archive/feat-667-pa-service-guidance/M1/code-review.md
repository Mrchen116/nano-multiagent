# feat-667 M1 Code Review

## Round 1

- Reviewer: independent `/root/pa667_static_review`; did not implement the reviewed change.
- review_mode: `full`.
- Baseline: `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5`.
- validated_at: `7ddaceb942423436bc656fba6707b04f131c9cb1` (HEAD confirmed before review).
- Scope: complete 17-file diff, affected runtime assembly/product call paths, unit spec/design and three gateway delta-specs. No reviewed source, tests, configuration or design was changed.
- Context review: `agent-context-review`, Mode B / Implementation Review. Triggered by Persona/Skill changes, Global product-tool registration, role-sensitive guidance, and default native delegation depth.

## Verdict

No surviving CONFIRMED or PLAUSIBLE code defects found in the reviewed diff:

```json
[]
```

This is a code-review conclusion, not M1 completion or product acceptance. The required real-model journeys and limited baseline comparison were still in progress when this snapshot was written; see `../verification.md`.

## Reviewed behavior and evidence

| Surface / affected chain | Review conclusion and evidence |
|---|---|
| Default PA Persona and two Skills | `apps/im-server/src/personal-agent-defaults.ts:2-12`, `nano-ongoing-work/SKILL.md:9-59`, `nano-proactive-care/SKILL.md:6-27` separate private preparation from public delivery, preserve original author/addressee and user withdrawal, use actual executor IDs and existing records, and avoid treating acknowledgments as completion. Existing PA creation/configuration paths still supply defaults only on creation; no update/backfill logic was added. |
| Global registration and actual callable schema | `agent-config.ts:105-139` moves product chat tools from inherited preset to root Agent scope and gives Global children internal guidance. `capabilities.ts:70-75` leaves root-local names out of inherited masks without removing native internal `send_message`. `global-child-tools.test.ts` records the actual native runtime `llm/stream` tool projection and Agent schemas for ordinary Global and PA, root/spawn/fork/depth-2/cold resume; children have no inbox/conversations/representation or public target/text branch, while native agent_id/message remains callable. `/tmp/pa667-child-green6.log`: 2/2 passed. |
| Native internal messaging and lifecycle | The above test executes internal parent reporting, second-level creation, and cold continuation of the original child, checking tool results and no product messaging calls. `global-mode.ts:79-86` distinguishes continuable children, one-shot fork completion, accepted input and public sent state. These are runtime fixture results, not proof of autonomous model choices. |
| Product enforcement | `packages/personal-assistant/src/global-agent.ts:411-415` rejects child inbox/conversations/public send_message before execution; `ProductBridge` retains the bound-root representation guard. The existing Global product test now checks direct child send refusal and unchanged send count. `personal-child-delivery.test.ts` still exercises Task disclosure review with parent/child evidence while expecting public child messaging to fail; its corrected case passes in `/tmp/pa667-depth-green.log`. |
| Task static and dynamic guidance | `features/task-graphs.ts:12-45` keeps product responsibility on the main Agent and makes Global child feedback explicitly request internal parent reporting with the fixed conversation identity. A reviewer-run native runtime probe executed child Task.apply and captured the next assembled model request: the deferred feedback contains parent routing and agent_id/message, and does not contain the root public-send instruction. Locator: `/tmp/pa667-static-probe.log`. |
| Personal security and UI guidance | `personal-security.ts:134-136` preserves original authorization/source/withdrawal constraints for children and directs product source requests and delivery to the root. `features/intelligent-ui.ts:5-17` returns prepared interactive source to the parent for Global children rather than requiring a public send or claiming delivery. These branches use host origin; prompt text cannot confer root status. The shared preset still filters disabled Feature sections according to each Agent's current configuration. |
| Default depth and explicit overrides | `client.ts:26` prepends maxDepth=2 before caller patches. Existing `trajectory-runs.test.ts` now uses this default and verifies depth-2 execution plus a depth-3 native error; `/tmp/pa667-depth-green2.log`: 3/3 passed. Reviewer probe passes an explicit later maxDepth=1 patch and obtains `subagent depth 2 exceeds maxDepth 1`, demonstrating override precedence at runtime. No concurrency or authorization configuration changes. |
| Existing testing assets and architecture | Existing personal-child-delivery expectations were rewritten for the intended new boundary, and trajectory coverage retains its causal/cold-read assertions while checking default depth. No private runtime imports, new package bypass, second loop, schema migration or client implementation change was introduced. `/tmp/pa667-build.log` reports the workspace build succeeded. |

## Context scope and limits

The runtime tests intercept `llm/stream` after actual Agent/tool/prompt assembly and supply controlled responses. They prove runtime delivery/schema/enforcement and native tool execution; they are not real provider network traces or real-model selection/understanding evidence. The reviewer probe used the same locked runtime and isolated temporary home, then shut it down and removed its runtime data. Its retained local log records the successful explicit-depth override and the actual deferred Task feedback text; the temporary probe is not a permanent regression test.

The code review checked root/child Global policy, Task feedback, personal security, Intelligent UI and Skill interactions together. It does not claim that the candidate's real model has completed the required #361 two-level development journey, parallel correction/stop/resume, proactive private preparation/quietness, or actual Skill discovery/loading. Those missing completion proofs are tracked as verification evidence work, not speculative code findings. Further review should be bounded to supplied evidence or an actual fix delta.

## Round 2 — bounded patch and evidence reconciliation

- review_mode: `patch`; prior reviewed head: `7ddaceb942423436bc656fba6707b04f131c9cb1`; validated_at: `32e2fd74c0262e286ab8807dcb259c5572446a87`.
- Scope: only `7ddaceb..32e2fd74c` source/test delta and newly available verification evidence. Confirmed the sole application/package change is `packages/dsh-integration/tests/knowledge-review.test.ts:207`, which sets the existing cross-process error-state poll to `timeout:8000`. Product source is unchanged; Round 1's full code/Context review remains applicable. No second full review or real-product rerun was performed.
- Patch conclusion: no surviving CONFIRMED or PLAUSIBLE finding. The same error review, diagnostic, persisted writes, interval settlement and subsequent recovery assertions remain. Eight seconds matches the neighboring completion-state poll and remains within the 20-second test deadline; the change allows the actual maintenance completion to be observed without altering expected behavior.

```json
[]
```

New evidence reviewed: `implementation.md` records both prior full-suite timeouts and the constrained-concurrency retry. `/tmp/pa667-alltests-serialbudget.log` completes 143 files / 768 tests with `--maxWorkers=2`; `/tmp/pa667-frontend2.log` completes 108 files / 1,031 tests. The preserved Python, typecheck/build, docs, Ruff and native interactive asset/typecheck logs support their reported successful gates. Repeating these already-successful checks is unnecessary for this test-only patch.

`../acceptance.md` at `f37ce20c0` now supplies independent real-model product evidence on runtime `7ddaceb`: seven normal scenarios pass, with finite main-text/candidate comparisons and actual Skill consumption. Bounded original-evidence spot checks confirmed original-worker correction/stop/resume calls, real ongoing-work/proactive-care loads, actual root/child schemas, and custom/empty Persona provider inputs in `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/`. These narrow the earlier evidence limits; they do not complete the user-required #361 independent Ready PR/CI and two-level progressive delivery. The three dependent acceptance rows remain inconclusive, and M1 remains incomplete. See `../verification.md`, Round 2, for the remaining bounded gap.

## Round 3 — authorization-continuity delta

- Reviewer: independent `/root/pa_authorization_review`; did not implement the reviewed change. Review date: 2026-10-27.
- review_mode: `patch`; baseline: `79a78d716`; validated_at: `f0eca4c0586a53c644e02bffe9493420e6fd889a`. The checkout was clean at this frozen head before review.
- Scope: only the five files in `79a78d716..f0eca4c05`: default PA Persona, `policy/codex-context.ts`, `policy/sources.ts`, `nano-ongoing-work/SKILL.md`, and `M1/authorization-fix.md`. Unchanged A+B implementation retains the earlier review; this round does not reopen the full feature diff.
- Context review: `agent-context-review`, Mode B / Implementation Review, because both reviewer-visible evidence interpretation and PA-visible continuation guidance change. Reviewed their combination with the pinned policy, source projection, historical/Inbox provenance, fixed PA security and existing Skill stop/resume guidance.

No surviving CONFIRMED or PLAUSIBLE code/Context finding:

```json
[]
```

### Reviewed semantics and actual evidence

| Surface / chain | Conclusion |
| --- | --- |
| Codex Outcome Policy and adapter | `codex-context.ts:35` explicitly refers the reviewer back to the existing Outcome Policy. Its low/medium default still has the policy-deny and malicious-injection exceptions; configured hard denies remain absolute. The pinned policy/template/output assets, risk parsing, execution gating and review retry behavior are unchanged. The new wording does not authorize an action merely because a prior reviewer denied it; it requires assessment of the exact action and concrete prohibited effect. |
| Original authorization and parent limits | `sources.ts:9` preserves the original human grant only within its scope, through delegation and later turns. Parent clarification is expressly limited to the parent's own task restrictions and cannot create human permission or override human restrictions. The same passage retains stop/resume ordering and states that source labels never override security rules. The unchanged Inbox adapter retains actual sender/owner, participant/observer and historical/restored distinctions. Both captured requests actually contain the owner's original task in an application-labelled Inbox result, including isolated regression authorization and the prohibition on merging, deploying or releasing. No loss of that grant was demonstrated. |
| Aggregate versus raw export | The adapter and Skill distinguish a genuinely different payload/effect from moving the same refused export to stdout or another path. The candidate system still includes the pinned rule that material derived from sensitive data remains sensitive and its source/destination disclosure requirements. Excluding raw text therefore does not itself authorize outside disclosure. In the reproduced metrics case, the pending edit removes raw retention and produces bounded approval/retry/usage metrics; the parent message explicitly permits necessary read-only metrics while forbidding the same raw export through stdout. |
| Persona, ongoing-work and fixed PA security | `personal-agent-defaults.ts:6` continues work within the accepted scope; `nano-ongoing-work/SKILL.md:30-38` requires examination of the concrete refusal and original limits, normal review of a materially safer alternative, no same-action tool/path/medium switch and no repeated identical requests for luck. This agrees with the fixed root/child PA security guidance requiring a safer alternative or concrete blocker and forbidding disguised disclosure. Existing stop/resume text still requires explicit user continuation. The default remains editable and creation-only (`personal-agent.ts:343`); this patch does not backfill an existing PA's Persona. |

Local replay evidence was inspected at `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/authorization-fix/`, against original captures `/tmp/pa667-issue361-runtime/provider-requests/{1793095813556394000,1793096456519599000}.json`. Both use **`codexOAuth:gpt-6-luna`, low effort, 2048 output tokens**; returned model is `gpt-6-luna`. Independent comparison confirmed that the candidate `after-input-*` requests differ only by the two frozen adapter passages (plus non-streaming replay transport), with messages, pending action and schemas unchanged. These are actual captured proxy-input payloads and real model responses, not a fresh PA journey or an independently inspected final upstream wire capture.

- `1793095813556394000`: historical denial, baseline replay allow, candidate allow. This does **not** establish a reproducible failing baseline or a successful fix of that specific decision.
- `1793096456519599000`: baseline replay denies, expressly conflating the aggregate edit with the refused raw export; candidate allows. This is the bounded reproduced before/after result.
- The four `control-*.json` inputs/responses use the same fixed model/effort/budget: private preparation allows; outside disclosure, parent-claimed permission to export an SSH private key, and destructive work after a human stop deny. These are synthetic illustrative controls; the credential case also has an independent critical-risk reason to deny and cannot isolate parent-authority handling by itself.

The caller's recorded three-suite / 26-test pass and successful build in `authorization-fix.md` are reused, not rerun. No full suite, extra real-model replay or product-code change was made by this reviewer.

### Limits and remaining acceptance

This delta is reviewable without a policy expansion or an execution-layer bypass. The evidence supports the narrow adapter correction; it does not prove the adapter imbalance was the sole cause, guarantee deterministic Luna judgments, or demonstrate PA behavior after loading the new Persona/Skill. `reviewSourceInstructions` is also shared with the CC/DSH classifier; its new source semantics were checked against those unchanged policy boundaries in source, while the supplied real-model replays cover Codex policy only.

The fresh-PA second natural test is still pending at this review snapshot. It must use the user's original requirement, without execution coaching, alongside the existing #361 run. Autonomous completion, handling of an actual future refusal, and absence of repeat authorization requests must be established by that journey's own evidence. This review does not complete M1 or convert #361's previously guided run into an autonomous pass.

## Round 4 — bounded coordination patch

- Reviewer: independent `/root/pa_authorization_review`, reusing the existing review role; did not implement this patch. Review date: 2026-10-27.
- review_mode: `patch`; baseline: `87bcbe387`; product validated_at: `003c09589b540d012f1a284623b2886be9f7b0f7`; final document closure: `fdcd95ab5f246bccd2c6fd0e615096ac97718da8`. Clean checkout confirmed before review; the closure changes only the corrected delta document.
- Scope: three product guidance changes in `global-mode.ts`, `features/task-graphs.ts` and `nano-ongoing-work/SKILL.md`, plus their design/delta/`coordination-fix.md` explanation. Prior authorization and unaffected A+B conclusions remain unchanged.
- Context review: `agent-context-review`, Mode B / Implementation Review. Checked root/child system guidance, loaded ongoing-work text, Task static/dynamic feedback, native return modes, recovery-note updates and retained public-delivery/source constraints together.

No surviving CONFIRMED or PLAUSIBLE **code/Context implementation** defect:

```json
[]
```

The corrected-delta review's incomplete `MODIFIED` entry (V2) was closed by `fdcd95ab5`: the full initial-human-task and long-task scenarios retain no-reply, early acknowledgment and delivery semantics while expressing the new update cadence. The document-only closure was independently checked against the current contract and unchanged implementation; no new full review was performed. This is not acceptance of the whole unit.

### Implementation and consumer evidence

| Surface | Reviewed result |
| --- | --- |
| Root coordination and public updates | `global-mode.ts:19` gates interim child replies on new information/decisions/corrections that change the next action, and gates public updates on user-relevant results, material outcome changes, actionable blockers or agreed checkpoints. It retains first human acknowledgment before deep work, explicit status replies/update timing, original-conversation final delivery, actual sent/held/unknown handling, permission-denial follow-through and private-only closing notes. There is no hard rate limit or message-dropping code. |
| Child return and actionable exceptions | `global-mode.ts:85` and ongoing-work lines 13-20 preserve missing-fact/decision requests, material changes and agreed checkpoints, while allowing routine work/recovery without parent acknowledgment. Continuable children send a self-contained result before closing; one-shot forks return through completion. The locked `@deepseek-ai/dsh-subagent/lib/index.js:603` actually injects the continuable send-before-finish instruction, so this distinction aligns with native behavior. The Skill explicitly prevents a subsequent completion notification from duplicating an already handled result, while retaining genuinely new blockers/corrections/results. |
| Task and recovery notes | `task-graphs.ts:21` still requires confirmed waiting and finished results, including the fixed conversation. Its unchanged deferred feedback keeps waiting explanation, alternatives, next check, results, actual delivery and replay dedupe; narrowing routine progress does not suppress those transitions. Ongoing-work lines 26,31-33 preserve executor/source/result recovery when needed and change only redundant reads/writes when current context is sufficient. Stop, explicit continuation, permission limits and unknown-result checks remain. |

Evidence root: `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/coordination-fix/`.

Independent inspection of `native-context-final-{false,true}.jsonl` confirmed exact frozen root and child guidance, narrowed child Task guidance, and unchanged internal-only child tool schemas in the actual native-runtime model-input snapshots. The files contain 6/7 root requests and 8 child requests each; SHA-256 values match `native-context-final-summary.json`. This is locked runtime plus controlled-provider assembly evidence, including the fixture's cold-resume path, not real-model autonomous behavior.

The real-model replay inputs use `codexOAuth:gpt-6-astra`, medium effort, 32768 output tokens; responses return `gpt-6-astra`. Comparison against the bounded original captures confirms unchanged tools/configuration and unchanged history except loaded ongoing-work text; child-recovered intentionally truncates the captured history immediately before its historical send. `baseline-progress-before` sends the parent a receipt/continue message; `baseline-progress-after` and `environment-progress-after` end privately without tools. `child-recovered-after-final` contains the exact final child guidance and selects a next-step Bash check instead of reporting the already recovered problem. The command was not executed. `real-blocker-after` still proposes a concrete user decision request; `synthetic-status-after` proposes a status answer. Neither message was actually sent by the probe.

The two root quiet cases and communication controls used the first candidate; the final additional root text only refines delegation expectations, while the receipt/update decisions being probed remain the same. The final native captures cover delivery of the exact frozen text. These are bounded, reusable observations rather than a final-version long-task rerun. The first child candidate still sent routine recovered progress; that counterexample is retained. `child-recovered-before-extra` is explicitly a mislabeled extra baseline, not a candidate pass. The other child-progress case retains an explicit historical milestone-report agreement and still reports its plan difference; it is not claimed as a silent pass.

Reused the implementer's recorded relevant build and ten distinct existing checks (`global-child-tools`, `task-feedback`, `personal-child-delivery`, `communication-native`, `builtin-skills`); no unrelated full suite or security-review matrix was rerun. This reviewer executed no service or replay tool action and changed only review reports.

### Evidence boundary

No complete long-task product run under this coordination patch is supplied. Replay results establish next-step choices only; they do not establish end-to-end latency, notification counts over a full task, final duplicate-delivery absence, or an update of already loaded old Persona/Skill/explicit reporting agreements. The ongoing #361 PR/CI and root delivery remain separate completion evidence; the caller reports independent gates/archive completed and original executor preparing PR/CI, which this bounded patch review does not independently re-verify or treat as final product completion.

## Round 5 — long-task acknowledgment qualifier

- Reviewer: independent `/root/pa_authorization_review`; review date: 2026-10-28. Did not implement this patch.
- review_mode: `patch`; baseline: `d76a7c6cd`; validated_at: `985bc6f07883a55f70e293b65b3737370f08eab7`; clean checkout confirmed before review.
- Scope: only the two product wording changes and corresponding design/Global delta/coordination-fix update. `agent-context-review` Mode B applies because the root system instruction and loaded ongoing-work guidance change. Earlier unrelated conclusions are retained.

No surviving CONFIRMED or PLAUSIBLE finding:

```json
[]
```

Independent text comparison confirms `global-mode.ts:19` changes only `When you receive a task from a human` to `When you receive a long-running task from a human`; ongoing-work line 73 changes only its initial acknowledgment clause to `主 Agent 对长任务先简短确认`. This removes the blanket acknowledgment requirement for simple requests without adding examples, request classes, gates or another messaging protocol. Long-task early acknowledgment, no-reply exceptions, original-conversation delivery, actual receipt handling, status questions, blockers, correction/stop and continuable/fork return guidance are unchanged. The complete corrected Global delta retains these obligations and adds the intended simple-request direct-delivery scenario.

Bounded local evidence root: `/Users/czj/.codex/reports/feat-667-pa-service-guidance-20261027/coordination-fix/`. `simple-request-before.json` records session `85c9210b-1add-4d89-bd07-21b57f30f03e`, turn 4: the owner asks for a UI diagram of the existing explanation, and two public sends are confirmed, first a plain-text preview (`d179e82…`), then the interactive answer (`31d6060…`). This is an actual pre-fix counterexample, not a synthetic failure inferred from text.

`pa667-simple-ack-context-{false,true}.json` contain the exact frozen Global system section in ordinary Global and PA native model inputs, respectively; each includes the new long-task condition and no old unconditional sentence, while preserving both no-reply clauses. The PA capture also contains the fixed personal-agent security guidance. `pa667-simple-ack-build.log` records successful product-contracts/integration compilation; `pa667-simple-ack-tests-final.log` records 2/2 passes from the one-off copy of the existing native Global/PA fixture. Reused these bounded results without rerunning unrelated checks or adding permanent sentence-matching tests.

The fixture proves assembly and retained native execution/tool boundaries, not model interpretation. There is **no new real-model behavior validation** of simple-request direct delivery, no measured post-fix message count and no evidence that an already running PA loaded the new text. The change removes the existing instruction to pre-acknowledge every task; it does not add deterministic message suppression. No service restart, #420 interruption, product-code modification, commit or push was performed by this reviewer.

## Round 6 — Workflow-child scope clarification

- Reviewer: independent `/root/pa_authorization_review`; review date: 2026-10-28; did not implement the change.
- review_mode: `patch`; validated_at: `384ab2710f3270f7222a966bb60ab1f67a897985`; clean checkout confirmed before review. Scope is only its one-line delta from the parent: `workflow/tool.ts:40`, `A child` → `A Workflow child`. Round 5's long-task qualifier remains reviewed without reopening it.
- Context review: `agent-context-review`, Mode B / Implementation Review, limited to the workflow tool description/system-guidance consumer and actual child tool filtering.

No surviving CONFIRMED or PLAUSIBLE finding:

```json
[]
```

The restriction now names the exact child kind to which it already applies. `workflow/engine.ts:365-370` derives the Workflow child's allowed names from the parent schema and removes `workflow`, `subagent` and `subagent_fork`; the same list is passed to both child configuration `toolAllowlist` and native `toolFilter` in the Workflow `start` path. `workflow/tool.ts:110,224` uses the same instructions string for tool description and system guidance. The edit does not change that filtering, native depth, ordinary child capability, authorization, lifecycle or execution. It removes the misleading implication that all native children are barred from further delegation, consistent with the existing two-layer native-delegation delta.

The existing native schema/depth/communication evidence and Round 5 assembly checks are reused; no new full test or runtime replay is needed for this scope word. Neither this Workflow qualifier nor the prior long-task qualifier is claimed as loaded or personally tried in the running user runtime. The supplied user acceptance of the preceding real trial does not retroactively establish real-model consumption of these last two qualifiers.

### Final main synchronization compatibility

Bounded inspection of `8d428779..b45b529b1aebb68d164081b582c87114726af530` confirms PR #417 changes only tests, deterministic fixtures, E2E/archive-check scripts and documentation. Merge `8294c698c56040e88b8bff8dc41bf1049b74fc25` therefore retains the earlier product-code/Context and real-model evidence within its original version and scenario scope. The retained `checks/pa667-final-*` logs record the updated 14 backend/native checks, 75 frontend checks, 84 non-E2E Python checks, Ruff, workspace build/typecheck and packaged iOS-runtime check passing; the build footer names `8294c698c`.

The later external main `39ce046cc2f228fc2be41f1418452b512df4ff75` (PR #421) is integrated at `727be381aa0d4c6213f191a3da3c2a9a6b49f722`. Its runtime delta adds optional `RuntimeEvent.surfaceOp` typing and makes `toolPresentation` ignore model-context replacement events as new tool completions. The only callers are product Work projection and SingleThread card delivery; no provider request, native history, Skill, delegation or approval path changes. The accompanying store regression covers append/legacy success/error, live/replay equality and preservation of durable original events/content/timing. `checks/pa667-main421-{tests,build,typecheck}.log` record 22/22 store checks, changed-package build and complete typecheck passing. This is compatible with the reviewed feat-667 behavior and avoids treating context pruning as a second tool completion. Existing raw evidence keeps its actual execution provenance; historic displayed timing anomalies are not retroactively certified as accurate. No surviving code/Context finding was identified in this bounded compatibility assessment.

Final effective review bounds: base `39ce046cc2f228fc2be41f1418452b512df4ff75`, source through `727be381aa0d4c6213f191a3da3c2a9a6b49f722`, product-completion evidence at `5a1e0afa6a9fcc819dd289c9475529ed018b81e6`. Prior full review and bounded rounds compose to the final source; the independent acceptance now closes its remaining delivery gap with the explicit intervention/version limits retained. Final verification Round 5 reconciles V1 and all three corrected deltas. No surviving code/Context finding or further full-review requirement remains; canonical merge/archive and subsequent delivery may proceed.
