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
