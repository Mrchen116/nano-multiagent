# Verification Report: bugfix-660-shared-agent-lifecycle

## Current final verdict

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION.** M1 implementation and required evidence are complete at `6769c89cb5fc9e693b45b6a8d87f2d7a7b02e127`, executed base `5b09dbe82292e0b5005d70b5561a74df1885d8f1`. The original full review through `60514ca8f` is retained, with bounded deltas through `f10168318` and `6769c89cb`; no unresolved code finding or verification issue remains. Lifecycle corrected-delta outcome: **aligned**. `requires_full_verification: false`.

| Dimension | Final result |
|---|---|
| Completeness | M1 complete; required native, real Context and independent Web evidence present |
| Correctness | All relevant regression risks covered; composite suite evidence and affected reruns pass |
| Coherence | Public DSH ownership, ordinary shared host, PA scope, history/Task rules and lifecycle delta aligned |

Reports remain uncommitted for caller consolidation. Spec consolidation/archive is the caller's closing action; this pass validates the implementation and already aligned delta and does not authorize production deployment or publication. Historical snapshots below preserve the findings and evidence gaps that were subsequently closed.

> Initial full validation snapshot: `5b09dbe82 → 60514ca8f`

## Round 1 — initial full verification summary

| Dimension | Result |
|---|---|
| Completeness | Implementation covered; M1 real-model and product exit evidence pending |
| Correctness | No surviving code finding; relevant native regressions pass |
| Coherence | Follows shared ordinary host / PA scoped design and public DSH boundary |

- reviewer: `/root/shared_static_review`, independent of implementation.
- verification_mode: full, including reconciliation of the complete lifecycle delta.
- verdict: **not yet pass** — 1 CRITICAL evidence gap; 0 WARNING; 0 SUGGESTION.
- requires_full_verification: false (this is already the full review).
- Reports are uncommitted for owner consolidation. This reviewer started no services and changed no implementation/test/configuration files.

## Completeness

M1 implementation is present: ordinary shared routing, per-owner handle disposal, selective recovery fencing, management/history paths, removal of the split migration, and PA boundaries. No worker tasks/progress document is required by the simplified workflow. The M1 exit standard also explicitly requires actual LLM history/preset evidence and real Web/product journeys; these were still being collected at this snapshot and are not inferred from native fixtures.

Prototype/reference: N/A. This unit reuses the existing Web/iOS UI and changes no frontend code. The lack of frontend diff removes a new visual contract, but does not remove the required real Web lifecycle checks.

## Correctness

| Requirement / scenario | Implementation evidence | Validation evidence | State |
|---|---|---|---|
| Stop only target A while ordinary B continues in same host | `runtime-partitions.ts:43`; `index.ts:697`; `owned-sessions.ts:73` | `agent-disable-native.test.ts:32`: A/B same PID, child/grandchild/continuable subtree, Bash and PTY stop for A, B continues, fresh A enable without restart; `shared-native-isolation.log` passes | covered at native seam |
| Failure is unconfirmed, no shared host kill, meaningful retry | `client.ts:170`; `index.ts:733`; `index.ts:754`; `agent-lifecycle.ts:80` | `supervisor.test.ts:37`; `agent-disable-native.test.ts:90,103`; `shared-retry.log` 2 pass | covered; closed retry finding |
| Cold inbox old work cleared once; fresh enabled work survives later restart | `runtime-lifecycle.ts:17`; `index.ts:324,763,831` | `agent-disable-native.test.ts:13,114`, supplied focused run and inspected assertions | covered at native seam |
| Disabled A's model/Knowledge/Workflow recovery cancelled without clearing B | `index.ts:167`; `model-policy.ts:153`; `model-fallback.ts:398`; `knowledge/runtime.ts:186`; `workflow/engine.ts:809` | `agent-disable-native.test.ts:136`; `shared-cold-owner.log` 1 pass; B reaches native compact and correctly gets empty-history error while B fallback/Workflow records remain | covered at deterministic native seam |
| Task and automatic entry admission remain owner-scoped | `index.ts:214,227,831`; `task-execution.ts:180,242`; `cron-owners.ts:21,52,65`; `main.ts:113` | Native schedule test; partition test `runtime-partitions.test.ts:155`; existing Task and lifecycle coverage reused | covered in code/fixtures; real lifecycle journey pending |
| Disabled/all-disabled management and history do not restore product Agents | `runtime-partitions.ts:248`; native `session.export`, work/descendant and trajectory query paths | `runtime-partitions.test.ts:136`; updated `trajectory.test.ts`; native cold history/fork tests | covered in code/fixtures; real all-disabled journey pending |
| Existing normal home directly reused; PA retains binding/epoch host boundary | `main.ts:103`; `runtime-partitions.ts:43,143`; `SPEC.md:42` | Partition sharing/PA tests; layout/migration and runtime-migration export removed; no migration startup call | covered |
| Human Web stop/status/retry/enable, old Task explicit resume, reconnect/offline stop and all-disabled management | Existing IM/PA/UI retained; Node native lifecycle replaced | Owner collecting isolated daily-stack product evidence | not yet evidenced |
| Real model after resume/enable sees existing history and preset; B Context unaffected by A cleanup | `owned-sessions.ts:18,53`; `index.ts:235`; once-only cold fence | Native history/fork tests establish mechanism; real provider capture and response not yet delivered | not yet evidenced |

File paths in the implementation column are repository-relative under `apps/node/src/` or `packages/dsh-integration/src/` as appropriate. Tests are the corresponding package/app `tests/` paths.

## Coherence

| Design decision | Result | Evidence |
|---|---|---|
| Ordinary shared host, original PA isolation; no control host or migration | followed | `RuntimePartitions.key`; `main.ts:103`; retired runtime-layout/runtime-migration/cold-history code and script |
| Root handles own disposal; native subagent drain, no provider-global unload/process fallback | followed | `owned-sessions.ts`; `index.ts:697-760`; `client.ts:170` |
| Close A admission before awaiting cleanup; wait for admitted creation | followed | `index.ts:702,710`; `OwnedSessions.pending/settle` |
| Per-Agent persisted cleanup and session inbox barriers | followed | `runtime-lifecycle.ts`; owner predicates in model/Workflow and explicit Knowledge agent identity |
| Keep old Tasks paused, skip missed timers, reject stale revision inputs | followed | retained IM/PA Task controls, native Task gating, `cron.skipMissed`, `submit` revision checks |
| Preserve history/fork/preset Context semantics | mechanism followed; real consumption pending | original preset mount, public seed builder, history attachment and native tests |
| UI and permissions retained | no net frontend/permission implementation change | full net diff inspected; real Web journey pending |

### Agent Context evidence boundary

Code reviewer performed Mode B Implementation Review; no second full Context audit was added. The affected surfaces are root/subagent history/configuration/preset mount, Schedule/Task messages and model/Knowledge/Workflow recovery. Native fixtures cover ownership and persisted state, but do not prove a real provider received and consumed the preserved Context. `docs/development/agent-context-engineering.md:98`, `llm-integration.md:32` and M1 require that distinction.

## Issues

### CRITICAL

1. **M1 exit evidence incomplete.** `design.md` M1 requires real LLM history/preset verification and real Web lifecycle journeys, including offline/reconnect/restart, old Task explicit resume and all-disabled management. At this snapshot no final product acceptance report or real provider request/response locators have been delivered. The complete backend test run also remains pending after the owner's first high-concurrency attempt hit machine load/timing failures. Complete these existing checks, inspect the actual request and response at the affected recovery point, and attach the final results before marking M1 complete or claiming full verification pass. This is missing required evidence, not a confirmed implementation defect.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Stop entire Agent, other Agents remain active | public owner handles + native drain + scoped cleanup | same-process native subtree/Bash/PTY test | aligned |
| Automatic input/recovery disabled through restart | per-Agent runtime state, cold fences, Task/Cron/continuation gates | cold inbox, schedule, selective durable owner tests | aligned; real exit evidence pending |
| Offline intent applied before ordinary recovery | lifecycle synchronize before runtime start and initialize states | lifecycle/partition fixtures | aligned; real journey pending |
| History and non-executing management remain available | read-only requests to resident host; native SessionQuery | disabled partition/trajectory tests | aligned; real journey pending |
| Shared runtime and existing data replaces old split migration scenario | original ordinary home, shared key, PA scoped key, no migration startup | partition/layout tests | aligned |
| External committed effects not rolled back | no cross-owner/remote rollback or process-tree kill introduced | net diff and cleanup paths | aligned |

### Uncovered Observable Behavior

None found. Shared `process_instance_id` now denotes the host, as specified in design and topology. Current service-lifecycle spec still contains the pre-660 migration scenario; the active delta explicitly replaces it, so this is intentional pending spec consolidation and is not an implementation mismatch.

Outcome: **aligned** for the delta/implementation relationship. Overall verification remains pending required exit evidence.

## Round 2 — bounded verification delta and evidence closure

> Validation snapshot: `5b09dbe82 → f10168318`; fix delta `60514ca8f..f10168318`.

- verification_mode: delta; previous full verification retained through `60514ca8f`.
- requires_full_verification: false. The patch only restores empty-node management startup and preserves the center's last execution identity in disabled reports; the shared owner implementation remains unchanged.
- code findings: `[]`; delta reconciliation remains **aligned**.
- Current overall verdict: **pending independent product Round 2**. The earlier combined evidence issue is partially closed: real Context and test gaps are resolved below; product evidence is the sole remaining exit item.

### Patch correctness and retained evidence

| Change / evidence | Observation | Result |
|---|---|---|
| `main.ts:497` empty-node management startup | Only `agents.length === 0` starts before relay registration; no configured Agent can be restored through this branch | aligned |
| Existing real CLI lifecycle case | `shared-empty-node.log`: start, status, native runtime crash recovery, stop and reused PID refusal pass after the empty-node fix | closed full-suite failure |
| `agent-lifecycle.ts:89` disabled process identity | Keeps the center's last execution identity while local confirmation still checks prior proof and actual cleanup host | aligned with IM report contract |
| Confirmed and unknown prior cleanup | `shared-reconnect-red.log`: both new cases fail before fix; `shared-reconnect-green.log`: 12 affected Node/IM lifecycle tests pass after fix | covered |
| Complete backend retained | `shared-backend-two-workers.log`: 732/733 pass, sole failed real empty-node case rerun above; populated-owner tests unaffected by the three-line empty-node branch | relevant suite evidence complete |
| Other gates | Inspected frontend 1,028 pass / 108 files; frontend build pass; Python 70 pass / 32 e2e deselected; final typecheck pass (`shared-frontend.log`, `shared-web-build.log`, `shared-python.log`, `shared-typecheck-final.log`) | covered; no native UI implementation change |

### Real Context evidence — closed

Reused code review's completed Mode B checks. Independently inspected actual provider upstream payloads at the three precise filenames recorded in `/Users/czj/.codex/reports/bugfix-660/context-evidence.md`, plus `context-lifecycle.json`, `context-messages.json` and `context-wire-summary.json`. Compared full system objects and full schema arrays before and after resume: exact equality, 24 tools. The system retains daily role/workspace and global Inbox/source/delivery rules. The original human-source Inbox result and sent receipt remain in order; the new human question omits the answer, and P correctly sends the remembered code to the same source conversation after disabled revision 2 / enabled revision 3 on the same host. Actual delivered product message is marked completed at revision 3. This demonstrates preserved preset/history delivery and real model consumption across the changed owner lifecycle.

Probe version `60514ca8f` remains applicable at `f10168318`: the subsequent populated-node change only repairs center report identity, and the empty-node startup branch cannot run in this populated daily environment. Scope remains one real `gpt-6.1-sol` high root probe. Fork seed/history and descendant/Job/PTY isolation remain covered by their native tests, without an unsupported claim of real-model coverage for every surface.

### Product evidence still pending

Product Round 1 in `regression.md` directly verified same-host P stop/E continuation, Task paused across enable, explicit human Task resume, historical Work readability and honest offline pending status. It also found the real reconnect failure `lifecycle_process_stale`; the report identity patch and red/green tests address that cause. This reviewer does not mark that user journey closed from source/tests alone: independent product Round 2 is running against `f10168318`. Its final report must establish reconnect recovery and remaining retry/all-disabled management exit criteria before the overall verdict changes to pass.

## Round 3 — cold Work projection verification delta

> Validation snapshot: `5b09dbe82 → 6769c89cb`; fix delta `f10168318..6769c89cb`.

- verification_mode: delta; prior full and bounded checks retained.
- requires_full_verification: false; this patch only returns previously omitted durable stop facts through the existing Work projection seam.
- code findings: `[]`; lifecycle delta remains **aligned**.
- Overall verdict at this snapshot: **pending independent product Round 3**, 1 CRITICAL for the final R2-1 user-visible closure evidence, 0 WARNING / 0 SUGGESTION.

### Product evidence resolved by Round 2

Read the appended `regression.md` Round 2 and its precise local locators. The offline P disable now converges to Disabled after reconnect, detail loads, and E independently delivers `E-R2-RESTART-OK`; R1-1 is closed. Freezing only the isolated host with SIGSTOP gives honest Stop unconfirmed/Retry stop; SIGCONT and real Web retry reaches Disabled with the same PID. All P/E/Q/PA disabled still permit native historical tool records, ordinary configuration save, model-services settings access and retained chat history with an explicit not-processing state. Earlier same-host main Bash isolation and old Task pause/explicit-resume evidence remains applicable. Native child/grandchild/Bash/PTY owner evidence is explicitly a separate seam, as required by M1, not misrepresented as a Web active-subtree observation.

Round 2 also directly confirmed R2-1: a gracefully stopped cold execution could still appear Running while P was Disabled. This was a real implementation gap in stop-history projection, not a false cleanup confirmation. It is addressed by `6769c89cb`, with final page-level closure pending.

### Patch and test evidence

| Requirement / decision | Implementation evidence | Validation | Result |
|---|---|---|---|
| Disabled history/Work reflect durable terminal facts after offline intent | `index.ts:744-768` observes cold target roots and descendants, returns bounded suffix with durable cursor/model/tool views | New native cold-stop regression RED on empty history, then GREEN; `shared-cold-stop-red.log`, `shared-cold-stop-green.log` | covered at native seam |
| History reads must not awaken disabled Agents | No resolve/create/resume in cold branch; `tool-presentation.ts:50` and `global-agent.ts:752` only transform/commit facts | New test asserts root-created file is still exactly one record after cold disable query | covered |
| Other Agents and PA scope preserved | Binding filter is `binding.agentId === agentId`; descendant traversal starts only at that root; unchanged live owner cleanup | 16 affected tests pass across native disable, PA lifecycle and trajectory | covered |
| Context preset/history/model behavior preserved | Pure persisted-history projection, no change to consumer assembly or activation | Previous precise real provider create/dispose/resume evidence retained | covered within recorded limits |

No new uncovered observable behavior or corrected-delta mismatch was found. The final remaining action is to inspect the independent product Round 3 report that checks cold P's Work status after restart, while retaining Round 1/2 passes. The report owner will provide its completion event; this reviewer is not polling or rerunning those journeys.

## Round 4 — final evidence closure

> Final snapshot: `5b09dbe82 → 6769c89cb`; evidence-only closure, no implementation delta since Round 3.

- verification_mode: targeted-closure of the remaining M1 product evidence / R2-1.
- verdict: **pass**; critical 0, warning 0, suggestion 0.
- validated_issues: initial M1 evidence gap closed; product R1-1 and R2-1 closed.
- requires_full_verification: false.
- report_commit: none, as instructed; caller owns consolidation.

Read the completed independent `regression.md` Round 3, inspected `/Users/czj/.codex/reports/bugfix-660/product/r3-disabled-interrupted.png`, and read `r3-native-history.txt`. At the final code version, the actual all-disabled Node restart uses Node 23117 / ordinary host 23122 with ready/connected true. The screenshot shows all four Agents Disabled, P Main Agent Idle, the former 23:32:29 execution ending 23:33:29 as Interrupted, and older Completed turns retained. Native historical tool calls/results remain readable. The product report records stable P/E/child sample counts 27/90/10 and unchanged host during read-only viewing. R2-1 is therefore closed by actual user-visible evidence, supplementing the native no-activation regression.

Retained final coverage is explicit: Round 1 real Web main Bash A/B isolation and Task pause/enable/explicit resume; Round 2 actual offline intent/reconnect/B public reply, honest timeout and Web retry, and all-disabled configuration/model/history management; Round 3 accurate cold Work terminal state and read-only history after restart. Actual DSH child/grandchild/continuable/Bash/PTY boundary tests run again in the final 16-test affected suite; their LLM stream is held by a stub and they are not claimed as real-model child acceptance. The separate real provider root create→dispose→resume probe proves preset/history/source delivery and actual remembered-answer consumption within its recorded single-model scope. No new native iOS UI was introduced; existing evidence remains applicable as specified in design.

Test evidence is compositional rather than a claim that an unperformed final whole-suite run occurred: the complete two-worker backend run had 732/733 pass; its only deterministic empty-node CLI failure passed after its isolated fix, followed by 12 affected Node/IM lifecycle tests and then 16 final native/PA/trajectory tests. The later patches do not invalidate the remaining successful cases. Frontend 1,028 tests, frontend build, Python 70 tests, typecheck and the documented architecture/tooling checks remain applicable. `git diff --check` passes at final HEAD; `origin/main` still matches the executed base.

### Final corrected-delta reconciliation

All six lifecycle delta scenarios remain **aligned**, with no uncovered observable behavior: target-only shared cleanup, disabled automatic entry/recovery, offline intent ordering, management/history without activation, retained original shared ordinary data and PA scope, and truthful external-effect boundaries. The corrected stop-history path supplies durable terminal facts instead of changing the promised contract. All necessary implementation, recovery, real Context and product exit evidence now exists; no CRITICAL or WARNING remains.

## Round 5 — Linux CI PTY ordering verification delta

> validated_at: `2f9765d3f75cf72445532089406214161b8f4a18`; executed_base: `5b09dbe82292e0b5005d70b5561a74df1885d8f1`; fix delta: `6b1245bc7..2f9765d3f`.

- verification_mode: delta; prior full verification and Web/Context gates retained.
- requires_full_verification: false; the actual change is limited to terminal/Job cleanup order.
- code findings: `[]`; corrected-delta outcome: **aligned**.
- Local implementation verification: pass, 0 confirmed implementation issues.
- Remote Linux gate: **pending**, not reported as pass. The previous final pass is historical and must not be used to claim all CI passed for this patched revision.
- report_commit: none; caller owns consolidation. No implementation/tests/services changed by this reviewer.

### Failure and corrected mechanism

CI run `40208579485` is direct affected-platform evidence: backend 735/736 pass, one real same-host A/B terminal-cleanup failure; frontend pass. The exact failure was `Runtime cleanup failed: kill ESRCH` in native LocalPtySession's interrupt path, not a model, frontend or product-state mismatch (`ci-first-failure.log`). `index.ts:714-724` now explicitly signals and awaits closure of each target-owned terminal before native Job cancellation. Public TerminalService awaits close before removing its record; failure is rethrown rather than suppressed. Root/descendant scopes are still disposed after Jobs settle, and genuine cleanup errors still prevent confirmation. Exact Agent ownership filters preserve B and PA scope. The existing narrow signal ESRCH catch is unchanged in scope and does not absorb kill/close failures.

### Evidence and retained gates

| Gate / contract | Evidence | Result at this snapshot |
|---|---|---|
| Target-only terminal/Job cleanup; B and shared host preserved | Inspected bounded source and public TerminalService/LocalPtySession close semantics; same-host native regression assertions retained | aligned |
| Final local build | `shared-pty-order-build.log`: rebuilt DSH TypeScript pass | pass |
| Complete affected native lifecycle tests | `shared-pty-order.log`: all 7 tests pass locally, no new skips | pass on macOS |
| Actual Linux failing seam at patched revision | Fixed revision remote CI not yet completed/provided | pending; no platform pass inferred |
| Real Web lifecycle/Task/offline/retry/all-disabled/Work/history | Existing R1–R3 product report and inspected artifacts; no entry/protocol/projection change in this patch | retained pass within recorded scope |
| Actual Context preset/history/source consumption | Prior precise real-provider create/dispose/resume probe; no model-visible assembly change | retained pass within recorded single-model scope |
| Lifecycle delta and architecture | Same target owner boundary, cleanup truthfulness, native public API and shared host/PA topology | aligned; no uncovered observable behavior |

The remaining delivery gate is the fixed revision's actual Linux CI result. Do not merge or report a cross-platform CI pass based solely on this local rerun. This pending check is an evidence limitation, not an additional confirmed code defect or a reason to invalidate unrelated Web/Context evidence. No speculative additional loops or broad reruns were requested by this review.
