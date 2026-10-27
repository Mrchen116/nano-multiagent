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
