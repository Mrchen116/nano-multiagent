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
