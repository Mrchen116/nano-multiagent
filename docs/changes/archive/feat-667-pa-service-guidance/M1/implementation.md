# M1 Implementation and Validation

## Implementation

Candidate `7ddaceb942423436bc656fba6707b04f131c9cb1`, based on `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5`. A updates the initial editable Persona and two on-demand Skills. B sets the public subagent profile default to depth 2, scopes Global product tools to the root, preserves native internal messaging, aligns child security/Task/UI guidance, and rejects direct child public-send calls at the existing product boundary. No DSH private import, runtime fork, Task schema or production migration.

The primary Agent implemented B and integrated A from the initial independent text worker. Later fixes belong to the primary Agent. Existing choices and source/approval boundaries remain in the existing runtime paths.

## Test strategy and existing coverage

| Regression risk | Existing coverage / disposition | Reason and observation seam |
| --- | --- | --- |
| Global descendant capability inheritance | New `global-child-tools.test.ts` | Existing root capability tests did not expose native spawn/fork/cold-resume tool schema inheritance. Captures actual runtime model requests and executes internal coordination at both child depths for ordinary Global and PA; observes no product calls. |
| Default depth and cold trajectory | `trajectory-runs.test.ts`, rewrite-merge | Remove explicit depth override so the native nesting case exercises the new default; depth 2 attempts depth 3 and gets a native depth error. Preserve existing parallel/causal/cold replay assertions. Read the actual task text block independently of native communication guidance appended by DSH. |
| Product entry guard | `personal-assistant/tests/global-agent.test.ts`, extend existing parameterized case | Exercise direct child public-send rejection alongside existing Inbox/conversations checks and preserve root sends. |
| Child Task disclosure and provenance | `personal-child-delivery.test.ts`, rewrite-merge | Old child public-send success is intentionally retired; the child still changes a Task through disclosure review with verified parent and child evidence. |
| Configuration/Skills/other capabilities | Existing personal-security, capability-state, runtime-profile, Task feedback/execution tests, keep | Retain user prompt/Skill selection, extension and source-control coverage. No text snapshot tests added for the new Skill. |
| Maintenance completion observation | `knowledge-review.test.ts`, narrow harness correction | Full suite exposed a default poll deadline before the maintenance fork settled (Skill write already succeeded, review still running); isolated rerun passed 4/4. Match the existing 8-second cross-process wait budget, without changing expected completion/error or runtime behavior. |

Controlled native runtime fixtures prove delivery/schema/enforcement and execution, not autonomous real-model task success. The independent static reviewer additionally exercised explicit maxDepth=1 override and child Task deferred feedback. Real-model products are separately judged in `../acceptance.md`.

## Validation evidence

Local logs are evidence locators, not committed runtime data. Node `24.22.1`, pnpm `11.7.0`, locked DSH `0.2.1-alpha.1`.

- Workspace `pnpm build`: pass (`/tmp/pa667-build.log`).
- `pnpm typecheck`: pass (`/tmp/pa667-typecheck.log`).
- New child scope test: 2/2 pass (`/tmp/pa667-child-green6.log`); default nesting/third-depth rejection/trajectory: 3/3 pass (`/tmp/pa667-depth-green2.log`).
- Affected regression batch: 82 passed with one old child-public-send expectation, corrected and passed (`/tmp/pa667-affected.log`, `/tmp/pa667-depth-green.log`).
- First full backend run: 767 passed, one maintenance observation poll timeout; isolated 4/4 rerun passed (`/tmp/pa667-alltests.log`, `/tmp/pa667-knowledge-focused.log`). A second unconstrained run overlapped frontend checks and hit the existing 45s Task-loop and 90s workspace-tools deadlines (766/768 passed; `/tmp/pa667-alltests2.log`). The complete suite with `--maxWorkers=2` then passed 143 files / 768 tests in 294s (`/tmp/pa667-alltests-serialbudget.log`); neither affected product implementation nor their timeout limits changed.
- Python non-E2E: 70 passed, 32 deselected (`/tmp/pa667-pytest.log`). Ruff check and format pass. Docs integrity pass, 289 maintained sources and 68 required routes (`/tmp/pa667-docscheck.log`).
- Native interactive runtime generated-asset check and typecheck pass (`/tmp/pa667-iosruntime.log`). Frontend locked-dependency install, generated-asset check, 108 files / 1,031 tests and the critical-severity audit gate passed (`/tmp/pa667-frontend2.log`, `/tmp/pa667-frontend-audit.log`); the audit reports 11 existing noncritical advisories, with no dependency changes.

## Real-model isolation and pending gates

- Candidate daily stack: `/tmp/pa667-review`, independent product reviewer owns the synthetic user journey. Same-runtime text baseline: `/tmp/pa667-text-baseline`, fresh PA with main `c4ebad992` Persona and ongoing-work Skill, proactive-care disabled because main lacked it. Both retain daily models, approval rules and separate identities/workspaces.
- User-specified nested development task: `/tmp/pa667-issue361-runtime` supplies candidate runtime; `/Users/czj/.codex/experiments/pa667-issue361/repository` is a distinct development repository at historical baseline `5454f3140`. Current workflow snapshot is supplied separately. The original user request and exact normalized product input are retained at `/Users/czj/.codex/experiments/pa667-issue361/request.md` and the runtime's `task-input.json`.
- Transparent local capture for each isolated stack forwards to the existing port 4000 service and stores only request bodies in that stack's `provider-requests/`. Shared proxy configuration is untouched. Capture is test-only and does not modify tool results or model responses.
- Native #361 root `5524e22e-d1af-44f3-bd49-93350fa059e9` started continuable executor `54612f0b-8c6a-41bd-a908-0427784264c0`, which started second-level author `478c29d9-b9f6-4866-81d7-a02c31132d78`. These are observed execution IDs, not proof of completed delivery.
- Product acceptance, verifier evidence closure, final sync, canonical merge, archive, Ready PR and CI remain pending. No production changes, merge or package release.

## Completed ordinary acceptance and environment cleanup

Independent product report `../acceptance.md` at `f37ce20c0` records seven passed scenarios, zero confirmed implementation defects, and the single remaining #361 completion gap (which keeps three dependent scenario rows inconclusive). The candidate and main-text comparison stacks and their capture proxies were stopped after this stage; ports 60038/50445/60394/50784 no longer listen. Runtime data and exact provider requests remain available for audit. The separate #361 runtime and its capture remain active until its task completes.

A fetch of origin/main after these checks found no new commits beyond the reviewed base. Final delivery must recheck before canonical merge/archive.

## Test protocol correction during execution

The primary Agent's #361 input explicitly prescribed a continuable background executor, nested delegation, role assignment and internal communication. The user correctly identified this as contamination of an autonomous-PA evaluation. Its eventual result can establish instructed execution and capability boundaries, but cannot establish autonomous organization. The earlier acceptance/verification reports remain historical stage reports; their claim that only #361 completion remains is superseded by this correction and must be reconciled in the final independent reports.

The user initially ordered the second trial after #361, then explicitly superseded that ordering: apply the bounded permission-coordination fix, keep Luna as reviewer, and start the fresh-PA trial in parallel with #361. Preserve #361 and its runtime. Submit the user's standard-test-startup repair request verbatim with only the new target repository path. Do not prescribe delegation, roles or tool mechanisms. The repair covers the existing e2e-up/down scripts, Vite proxy/Origin configuration and worktree-runtime documentation, with one fresh-environment login/chat/native-trajectory acceptance. It is an independent task result, not additional A+B product scope. A+B remains incomplete until the applicable autonomous-behavior evidence is independently assessed.

The user also corrected the test speaker: messages sent from the test owner's account must use normal first-person owner language. The #361 follow-ups used third-party framing such as “the owner said” and “external observer”; that was another artificial input and remains in the historical evidence. Future inputs must not add this framing, identity commentary or instructions about how a PA should organize itself.

## Fresh natural-input trial started

The isolated candidate runtime now includes `f0eca4c05`; bounded correction and replay evidence are in [authorization-fix](authorization-fix.md). The new service was created from the daily baseline with a new node, owner, PA, workspace, memory and Skill state. No earlier PA evolution or conversation was copied. Its main model is Astra medium and independent reviewer stays Luna low. At 2026-10-27 12:22:37 UTC the original requirement plus project path was delivered as owner message `a279d72cb5444fe3adce1136ca161680`; the PA acknowledged at 12:22:59. Acknowledgement is not completion.

Runtime: `/tmp/pa667-natural-runtime`, IM `http://127.0.0.1:54088`, PA `pa_d022e21145e7`, conversation `c_89ae03f315bb`. Target repository: `/Users/czj/.codex/experiments/pa667-startup/repository`, independent branch initially based on current main `c4ebad992`. Runtime backing checkout is separate from the repository the PA changes. No root implementation of the PA's assignment was supplied.


## Later natural-trial delivery and main synchronization

The completed successful-reply continuation is recorded in [authorization-fix](authorization-fix.md) and independent Acceptance Round 2. After that two-input trial, the human directly asked the PA “提pr了吗” and then “提个pr” at 13:40/13:43 UTC. The PA delivered [PR #416](https://github.com/Mrchen116/nano-multiagent/pull/416), head `2d1dcd25041a3939f2aab34e5e576d2409d6c0db`, four changed files, Ready/open/unmerged. GitHub CI run `40514929820` completed successfully; the assignment checkout is clean. These are two additional user inputs, not evidence of one-input PR completion. The caller supplied no assignment implementation and did not send those two inputs. Exact events and read-only GitHub confirmation are retained under local `pa667-natural/pr-delivery-followup/`. The earlier uncommitted state remains accurate for its historical checkpoint.

Main advanced from `c4ebad992` to `8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82` through two documentation-only commits adding the separate refactor-668 motivation/design/review. Merge `fca972d0a` contains those four files without conflicts or runtime changes. Existing implementation, model-input, product and engineering evidence retains its prior execution provenance; this main delta does not invalidate its covered behavior. Final independent closure remains required for #361, whose current full product verdict is NOT PASS due to the PA notice/inbox issue. No archive or A+B Ready claim is made.

## Long-work delivery latency analysis

The user requested that the observed delivery slowdown be retained in this unit. [交付耗时分析](delivery-latency-analysis.md) records the 2026-10-27 21:29 CST snapshot and the 21:45 follow-up: phase timing, permission blocks, coordination and ledger overhead, acceptance-harness rework, the unresolved PA notice/inbox failure, and measurement limitations. Proposed efficiency improvements remain unimplemented; this analysis neither replaces independent acceptance nor establishes a direct-Codex speed comparison.


## Final sync and user trial — 2026-10-28

The owner personally tried the fresh blank PA instance and explicitly accepted the real trial, then authorized completing the remaining checks, creating/merging this unit PR and deploying it. The initial fresh instance had zero messages, no main session and no child execution; its runtime used the coordination patch. This acceptance is separate from the independent synthetic journeys. The later long-task acknowledgment qualifier (`985bc6f07`) and Workflow-child scope qualifier (`384ab2710`) were reviewed and built but not reloaded into the active personal trial; no post-fix real-model behavior is claimed for those two tiny changes. Native provider-input assembly covers the long-task qualifier; the Workflow change only names the already-filtered child type.

Final sync integrated main `b45b529b1aebb68d164081b582c87114726af530` into `8294c698c56040e88b8bff8dc41bf1049b74fc25`. The main increment is PR #417's tests/fixtures, E2E/archive checks and documentation; it changes no product runtime source. Existing full backend/frontend and real-model evidence remains applicable; independently reviewed source/Context conclusions are retained. Updated local checks: four backend/native suites 14/14, four changed frontend suites 75/75, non-E2E Python 84/84, Ruff check/format, complete workspace build/typecheck and packaged iOS runtime check all pass. Logs are retained under the evidence root `checks/pa667-final-*`. No iOS client change requires native simulator/device rebuilding.

The personally tested instance was stopped after read-only confirmation that no turn was running or awaiting permission. All earlier owned preview environments remain stopped; runtime data and evidence are preserved outside the development checkout. No production service was changed during these checks. Final independent completion reconciliation, canonical merge/archive, remote CI and deployment are recorded in their final closure/PR/deployment records rather than inferred from this checkpoint.


A second external main increment, PR #421 (`39ce046cc2f228fc2be41f1418452b512df4ff75`), was integrated as `727be381aa0d4c6213f191a3da3c2a9a6b49f722`. Its runtime delta is an optional `RuntimeEvent.surfaceOp` type and skipping replacement results in product tool presentation; native execution/context, delegation, Skills and authorization are unchanged. Independent bounded source review retained the earlier feat-667 conclusions with their original version boundaries. `store.test.ts` passed 22/22 and both changed packages built successfully; exact logs are `checks/pa667-main421-*`. No assumption is made that historical tool-display durations are newly corrected in preserved evidence.


Independent Acceptance Round 3 at `5a1e0afa6` closes the final #361 completion gap: Ready PR #419, exact-head CI success and real two-level internal return followed by root public delivery. The original coached input, owner clarifications, source-version switch and Git credential-helper intervention remain explicit. Its bounded offline indexes are additionally preserved under `issue361-final-review/` in the durable evidence root. Whole-workspace typecheck after #421 also passed.


## Delivery closure

Independent final code/Context review has no surviving finding; Verification Round 5 closes V1/V2 and aligns all three corrected deltas. The reviewed requirements were merged into current Gateway specs and their area-index counts updated. The entire unit was moved intact to archive. Documentation integrity passes (281 maintained sources / 68 routes), the explicit feat-667 archive check passes, and `git diff --check` passes. No product code changed after source `727be381a`; subsequent commits only close evidence and archive/merge the verified contract. PR creation, remote CI, authorized merge and production deployment follow this completed local gate.
