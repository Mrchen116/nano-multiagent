# Verification Report: refactor-581-dsh-personal-assistant

> Validation snapshot: `4915c44cb7f7b829414a19087877ad9b73d69ea1 → e89179da8956577b288ee374fe791c2ce82d5047`

Round 1 · `verification_mode: full` · `verdict: fail` · `requires_full_verification: false`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1–M5 implementation owners present; required final product/physical-device exit evidence incomplete |
| Correctness | All R1–R12 / S01–S33 mapped; three confirmed implementation defects |
| Coherence | Core ownership, public stock DSH integration and five Feature scopes followed; execution observability and usage boundary deviate |

**2 CRITICAL, 2 WARNING, 0 SUGGESTION. Fix and close required evidence before PR.** Source findings apply to the frozen implementation, not parent-owned fixes now in progress.

## Completeness

- M1: native runtime, session acceptance/flush/lookup, cancellation and approval owners exist. Retained tests and real text/tool/restart journeys support the implementation. Full three-client S01 acceptance is not established by API results alone.
- M2: both work modes, Inbox, Feishu, Task Graphs, native schedule and product Heartbeat owners exist. Retained real native-center and dedicated Feishu results support delivery; final physical iOS/UI observation remains incomplete.
- M3: native capabilities, two-layer extensions, selection, Auto policy, fallback, new history, knowledge maintenance and configuration continuity exist. Token-usage wire shape violates the retained clients (W1).
- M4: JavaScript catalog and one nested level, pause/resume/restart, durable prefix reuse, actual-child execution and shared accounting exist, with native and product regressions documented in M4 progress.
- M5: independent TypeScript center and new Node entrypoints exist; old kernel and Coding CLI are retired and test disposition is explicit. Public readiness after runtime loss/recovery is stale (W2), quiet execution liveness is missing (C1), and final reviewer evidence is incomplete (C2).
- No `tasks.md` checklist is required for this simplified Full workflow. Milestone exits, not worker implementation claims, determine completion. Current canonical specification merge/archive/local docs CI is a pending workflow step under the parent’s ownership; its intentionally pre-merge state is not counted as an implementation defect.
- Prototype / Reference coverage: **N/A**. Design retains existing client layout and interaction and explicitly adds no page/form/navigation prototype. It still requires actual Web/Swift/Feishu observation of the new data and native tool presentation.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 / applicable evidence | 状态 |
|---|---|---|---|
| R1 S01–S02: three clients, text/image follow-up and identity | `packages/personal-assistant/src/{single-thread,global-agent,external}.ts`; `apps/im-server/src/{identity,messaging,media,gateway}.ts`; retained React/Swift clients | PA/channel/IM regressions; M1/M2/M5 live text, image, dedicated Feishu and identity evidence | Implemented; final physical/UI gate pending C2; usage defect W1 |
| R2 S03–S04: global Inbox, concurrent source attribution and late correction | `packages/personal-assistant/src/{global-agent,inbox,single-thread}.ts`; `packages/dsh-integration/src/global-mode.ts` | Inbox/global product tests; actual native-center cross-chat/same-child and real group API journeys retained by parent | Covered by implementation and retained evidence |
| R3 S05–S07/S32: tools, native names, two extension layers and true selection | `packages/dsh-integration/src/{capabilities,extensions,web}.ts`; `assets/social-tools.ts`; `apps/node/src/configuration.ts` | Capability/profile/social/web tests; public-export dependency contract independently 8 passed | Covered; approved native replacements applied |
| R3 S33: five independent Feature lifecycles | `packages/dsh-integration/src/features/`; agent preset lifecycle; PA Heartbeat and knowledge subscription owners | Capabilities/profile/cron/knowledge and product tests; M1–M5 progress records on/off/restart/agent isolation | Covered at implementation/regression level; final product observation belongs to C2 |
| R4 S08–S09: child/background continuation and cancellation | Native DSH subagent/jobs integration; PA single-thread/global and Workflow delivery owners | Native child/history/profile tests; parent’s actual foreground/background/failure/stop journeys | Covered; healthy quiet operations fail watchdog C1 |
| R5 S10–S11: JS parallel/pipeline, named discovery/save and nesting | `packages/dsh-integration/src/workflow/{guest,catalog,engine}.ts` | Workflow catalog/native/lifecycle tests; M4 retained actual-child scenarios | Covered |
| R5 S12–S13: pause/restart and durable completed prefix | `packages/dsh-integration/src/workflow/{control,state,engine}.ts` | Workflow control/lifecycle/native tests with attempt and replay state | Covered |
| R5 S14: shared parent/child output budget | `packages/dsh-integration/src/workflow/budget.ts`; model attempt/settlement integration | Workflow budget/native tests, M4 usage evidence | Covered; accepted target semantics, not a hard streaming cap |
| R6 S15–S18: one Auto consumer, selectable rules, human/global/unattended approval | `packages/dsh-integration/src/policy/`; PA approval routing; `packages/channels/src/feishu.ts` | Approval/workflow-approval regressions; real native-center allow/deny and three reviewer selection/escalation journeys | Covered except long pending waits C1 |
| R7 S19–S20: memory and Skill use/maintenance/enable | `packages/dsh-integration/src/knowledge/`; independent Feature scopes; PA knowledge updates | Knowledge profile/product/builtin-skill regressions; M3/M5 retained evidence | Covered |
| R8 S21–S23: native parent-session schedule, overdue recovery, manual/history | Native Schedule owner via integration Feature/Cron owners and schedule evidence | Cron/profile tests; actual native-center one-shot journey; cold-recovery/receipt evidence in M2 | Covered; approved schedule semantics applied |
| R9 S24: Heartbeat quiet/busy/active-time policy | `packages/personal-assistant/src/{heartbeat,heartbeat-policy}.ts` | Heartbeat policy/product regressions and actual native-center journey | Covered |
| R10 S25: next-turn configuration, model fallback and usage | Node/PA configuration operations; integration model policy/fallback; `presentation.ts:4–18` | Config/fallback/usage tests; actual configuration and accounting journeys | Material usage schema mismatch W1 |
| R10 S26–S27: new history, compact/fork/distill and development cutover | Integration NativeHistory/compaction; PA history/session controls; Node migration | History/catalog/migration tests; real `/compact`, focused summary, restart and fork-config evidence | Covered; no old-chat compatibility required |
| R11 S28–S29: graph/send facts, disconnect/runtime recovery | `apps/im-server/src/{task-graphs,work,gateway}.ts`; durable Node/PA stores and outboxes; `server.ts:276–305` | IM actual HTTP/WS/control/usage tests; resilience scripts and native-center journeys | Missing execution liveness C1; readiness mismatch W2 |
| R12 S30–S31: operational entrypoints, executable readiness and retirement | `apps/node/src/{cli,lifecycle,main}.ts`; integration supervisor; root/scripts/CI | Lifecycle/device-binding tests; actual launchd/resilience evidence; boundary contract independently passed | Runtime readiness does not track recovery W2 |

Implementation scope was reviewed against current product invariants plus the approved five delta areas. Old tool names/private runtime algorithms were not treated as preserved requirements. Shared task graphs intentionally follow company-wide qualification, not per-owner filtering; chat and attachment access remains a separate boundary.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| Independent TypeScript IM → product Node → managed DSH child | Yes | `apps/im-server`, `apps/node`, `packages/personal-assistant`; no IM runtime dependency |
| Stock pinned DSH, no fork/patch/private imports | Yes at reviewed source/dependency surface | Integration package/profile and lockfile; `tests/contract/test_runtime_dependency_contract.py` independently passed |
| Product identity/delivery owners separate from native execution | Yes structurally; liveness incomplete | Product contracts, durable PA stores, IM identity/gateway; C1 |
| Native tool names, native schedules to parent session, no old-history converter | Yes | Capabilities, schedule Feature owner, NativeHistory, migration blockers |
| Five separately disposable Features, stable shared bridge | Yes | Feature plugin registrations and scoped preset effects; product subscriptions |
| Own Workflow control/prefix/budget atop public PTC and subagents | Yes | `workflow/{engine,control,state,budget,guest,catalog}.ts` |
| Retain HTTP/WS schema and client behavior | No | `presentation.ts:10–14` emits a different usage shape; W1 |
| Separate connection online from execution ready; identify live runtime | No | `apps/node/src/main.ts:215` writes readiness once; W2 |

### Prototype / Reference Contract

N/A: no new prototype/must-match rows. Existing client interaction requires real observation under the design’s Runbook; C2 tracks missing final evidence rather than subjective visual quality.

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — execution-specific liveness has no producer in the replacement path.** Current `docs/specs/gateway/routing-delivery.md` execution-liveness scenarios and `docs/specs/im/gateway-relay.md` watchdog scenarios remain applicable; target architecture §11 preserves long-running execution visibility. `apps/im-server/src/server.ts:283` expires replies from the last conversation event; the `run_heartbeat` receiver in `gateway.ts:806` has no replacement Node/PA producer, and pending approval time is ignored. Independent shortened-timeout reproduction failed both a healthy quiet-tool record and a fresh approval wait. Later text deltas are ignored for failed messages. **Action:** wire actual per-execution liveness and pending approval semantics through native execution to the center; add a regression distinguishing healthy quiet execution/approval from lost execution liveness. Merely keeping the node socket online or disabling the watchdog would not prove the contract.
- **C2 — required final product/physical-device exit evidence is incomplete.** `design.md` Runbook requires real Web/Swift/Feishu observation and expressly rejects simulator/mirroring as physical-device substitution; M1/M2/M5 exits require applicable S01/S17/S29/S30 and final three-client behavior. M5 progress records signed iOS build/install but explicitly says UI acceptance was blocked by the locked Mac. Installation and API/native integration successes do not establish actual iOS chat/image/tool/approval/foreground/background behavior. **Action:** product reviewer must finish the required final client journeys on the installed physical device and attach versioned observations/results; retain pending status until then. This verifier does not substitute its static review for that independent gate.

### WARNING（提 PR 前必须修）

- **W1 — usage projection breaks unchanged client schema.** Design’s “IM、Web、iOS产品协议: no spec delta” and event/client mapping retain the public accounting boundary. `packages/personal-assistant/src/presentation.ts:10–14` emits `prompt/completion/cache_read/cache_total_input`; the unchanged center persists it, while Web `TokenChip` needs `context_used/output/cache_read_tokens/cache_total_input_tokens`. Independent frozen-source execution confirmed missing `output`, NaN context percent and a TypeError on details expansion. Swift consumes the same retained names. **Action:** normalize the product object to the retained schema with correct native disjoint input/cache/output meaning; keep missing provider counters unknown. Verify the serialized real message shape and both client consumers, not only internal accounting totals.
- **W2 — public readiness reports a dead DSH PID after recovery.** R12 S30, service-lifecycle delta and target architecture §11 distinguish Node connection from executable readiness. `apps/node/src/main.ts:215` persists readiness once; `RuntimeSupervisor` loss/recovery updates only private state. Independent real-process reproduction observed DSH replacement PID33287 but public status still `RUNNING pid=33254 ready=true DSH=33272`. Retry exhaustion also leaves readiness true. **Action:** persist unavailable/recovered state from supervisor transitions, clear dead PID and record replacement PID only after successful initialization/recovery; verify public `pa status` through crash/recovery and exhausted retries.

### SUGGESTION（可以修）

None.

## Evidence and verification boundaries

- Independently executed boundary test: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest tests/contract/test_runtime_dependency_contract.py -q` → **8 passed in 0.07s**. Initial worktree-local `.venv` invocation failed because that interpreter does not exist; it is not a test failure.
- Independently reproduced C1 and W2 with private temporary state; real node/server processes were stopped and temporary directories removed. W1 was executed directly from frozen Git source through TypeScript transpilation, so parent’s in-progress edits were excluded.
- Reused versioned worker/parent integration evidence recorded in M1–M5 progress: backend **49 files / 113 tests**, frontend **86 files / 809 tests**, native build/typecheck and Python selected **51 tests**; runtime/history/feature/workflow/policy/accounting regressions; isolated resilience/autostart/device-binding exercises; real native-center global/child/approval/configuration/compact/schedule/Heartbeat journeys. These results establish their actual scopes, not a blanket product acceptance.
- Dedicated actual final TypeScript-center Feishu platform + IM response is recorded at ignored `.dsh-runtime/native-feishu-fixed/acceptance.json` and summarized in M5 progress. It is local real-platform evidence, not a production deployment or physical iOS result.
- Legacy dispositions are authoritative in `M5-decommission/test-disposition.md`; old private Python implementation tests are not required to survive the approved replacement. Research/evaluation material remains outside retirement.
- Parent is making source fixes during this report. No post-`e89179da8` source, tests or client edits were included. A precise patch/closure pass must close C1/W1/W2 and update evidence; C2 remains the product reviewer’s gate. No report commit was made in the shared worktree.
