# Verification Report: feat-569-task-graphs-mvp

> Validation snapshot: `499774a56 → cb45a06a5`
>
> `f6062432f` is the frozen implementation snapshot. `99f6e1633` only merges the unrelated `refactor-570` motivation document, and `cb45a06a5` adds the reviewed `change_note` regression assertions; neither alters the implementation verdict.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Static implementation and regression coverage complete; the separately assigned real-product review remains its own evidence gate. |
| Correctness | Aligned for all source/test-verifiable requirements and corrected deltas. |
| Coherence | Followed. |

Static verification passed with 0 CRITICAL and 0 WARNING. The independent product reviewer is responsible for the live S01–S20 / P1–P6 journey evidence; this report neither replaces nor pre-claims that work.

## Completeness

- M1's IM document, HTTP/WS read paths, PA four-action tool and bridge, Web-only browsing, navigation, i18n, and permanent tests are present.
- W1–W5, W7, and W8 are supported by implementation plus domain, API/WS, PA bridge/tool, frontend component, build, contract, and full-suite evidence. W6 and the reviewer R1–R7 visual/live journeys are intentionally owned by the independent product reviewer.
- The prototype's must-match contract has source projections for P1–P6 in the router/shell, layout, page, stale-cache and mobile-detail code. Its real viewport comparison is pending that review and is not inferred from fixture tests.

## Correctness

| Requirement / Scenario | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| R1 / S01–S03: Chat and Tasks entry, genuine empty state | `src/IM/frontend/src/features/tasks/task-graphs-page.tsx:20`, `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:1125`, `src/IM/frontend/src/app/router.tsx:35` | `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:114`, `:151` | source/test aligned |
| R2–R4 / S04–S10: DAG, exploration and nested scopes | `src/IM/domain/task_graphs.py:106`, `:232`; `src/IM/frontend/src/features/tasks/task-graph-layout.ts:8` | `tests/im_service/unit/test_task_graph_rules.py:44`; `tests/im_service/integration/test_task_graph_api.py:80`; frontend test `:69` | source/test aligned |
| R5 / S11–S13, S20: same durable graph and channel-independent tool | `src/personal_assistant/tools/task_graph.py:64`; `src/personal_assistant/gateway/task_graphs.py:21`; `src/personal_assistant/gateway/internal_dispatch.py:505` | `tests/unit/personal_assistant/test_task_graph_bridge.py:51`; `tests/unit/personal_assistant/test_task_graph_tool.py:10`; reported real loopback creation | source/test aligned |
| R6 / S14–S19: atomicity, conflicts, persistence, ACL and browser read states | `src/IM/application/task_graphs.py:81`; `src/IM/infra/repositories/task_graphs.py:56`; `src/IM/frontend/src/features/tasks/task-graphs-api.ts:53` | `tests/im_service/integration/test_task_graph_api.py:80`, `:207`, `:262`; frontend test `:99` | source/test aligned |
| R7: no scheduling/approval/execution engine introduced | `src/IM/domain/task_graphs.py:1`; `src/personal_assistant/tools/task_graph.py:69`; no calls from changed source to executor/scheduler APIs | Domain/API/bridge tests above, plus reviewed diff | source aligned |
| Gateway delta: true PA provenance, explicit allowlist, input-channel independence, honest unknown write outcome | `src/personal_assistant/gateway/task_graphs.py:39`; `src/personal_assistant/gateway/session_binder.py:745`; `src/personal_assistant/ws/im_connection.py:966` | `tests/unit/personal_assistant/test_task_graph_bridge.py:51`, `:122`; `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py:28` | source/test aligned |

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| D1/D2: containment, dependencies and derivation have distinct semantics | Yes | `src/IM/domain/task_graphs.py:171`, `:189`, `:201` |
| D3: records do not execute or propagate state | Yes | `src/IM/domain/task_graphs.py:232`; `src/personal_assistant/tools/task_graph.py:69` |
| D4/D5: tool provenance is separate from prompt channel; graph home is an existing IM conversation | Yes | `src/personal_assistant/gateway/task_graphs.py:24`, `:74`; `src/IM/application/task_graphs.py:123` |
| D6: IM is the only durable store | Yes | `src/IM/application/task_graphs.py:111`; `src/IM/infra/repositories/task_graphs.py:56` |
| D7/D8: one four-action tool, revisioned atomic writes and idempotent receipts | Yes | `src/personal_assistant/tools/task_graph.py:16`; `src/IM/application/task_graphs.py:142`; `src/IM/infra/repositories/task_graphs.py:84` |
| D9: Web browser is read-only and uses the existing app surface | Yes | `src/IM/api/routes/task_graphs.py:34`; `src/IM/frontend/src/features/tasks/task-graphs-page.tsx:161` |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| P1 navigation and Chat entry | R1 / W7 | shell, chat header and `/tasks` route | frontend component suite; live evidence belongs to product reviewer | source/test aligned |
| P2–P4 relationship layout and nesting | R2–R4 / W1 | `task-graph-layout.ts:8`, `task-graphs-page.tsx:83` | domain/API and frontend nested fixture tests | source/test aligned |
| P5 details and return-to-chat draft | R5 / W7 | `task-graphs-page.tsx:134`, `:195` | frontend test `:114` | source/test aligned |
| P6 loading/error/stale/ACL feedback | R6 / W7 | `task-graphs-api.ts:53`, `task-graphs-page.tsx:28` | frontend test `:99`; API ACL tests | source/test aligned |

## Issues

### CRITICAL

None.

### WARNING

None. The temporary `change_note` coverage warning was closed before this final report: `tests/im_service/integration/test_task_graph_api.py:163` proves persistence and re-read, and `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:97` proves detail rendering.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| IM delta, member-only list returns `total` for chat count/search/pagination | `src/IM/application/task_graphs.py:270`; `src/IM/infra/repositories/task_graphs.py:105`; `src/IM/frontend/src/features/tasks/task-graphs-page.tsx:20` | `tests/im_service/integration/test_task_graph_api.py:262`; `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:151` | aligned |
| IM delta, latest `change_note` is retained, required for reopening and displayed in detail | `src/IM/domain/task_graphs.py:331`, `:380`; `src/IM/frontend/src/features/tasks/task-graphs-page.tsx:147` | `tests/im_service/unit/test_task_graph_rules.py:78`; `tests/im_service/integration/test_task_graph_api.py:163`; `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:97` | aligned |

### Uncovered Observable Behavior

None in the corrected-delta scope. Live desktop/mobile rendering and all S01–S20 are covered by the separately running product-review task, rather than being claimed from static evidence here.

Outcome: **aligned**

## Round 2: targeted revalidation

> Revalidation mode: `targeted` · patch: `2126ccab0..21f79e3d8` · reviewed snapshot: `21f79e3d8`

### Retained evidence

Round 1's IM document, Gateway/PA tool, authorization, corrected-delta, and non-P5 browser-component conclusions remain valid: this patch changes only the frontend transition from same-origin task Markdown links to the existing Router. It adds no task-data mutation, API, schema, permission, tool, or delta-spec behavior.

### I1 / P5 verification

| Contract | Implementation evidence | Durable test evidence | Result |
|---|---|---|---|
| P5 / R5: visiting a same-origin task link from Agent Chat preserves the existing home-chat composer when Discuss returns | `src/IM/frontend/src/features/tasks/task-graph-link.tsx:5`; `src/IM/frontend/src/features/chat/components/message-pane.tsx:1830` | `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:117` visits the actual Agent Markdown link, returns through Discuss, and asserts draft text, mentions, pending attachment, appended reference, and no send | aligned |
| P5 / R5: the same Markdown transition in Agent Work stays within the application | `src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx:193` | `src/IM/frontend/src/features/settings/agents/agent-work-panel.test.tsx:28` asserts `/tasks/:id` plus query navigation from rendered Work prose | aligned |
| Existing ordinary/external Markdown behavior remains intact | `src/IM/frontend/src/features/tasks/task-graph-link.tsx:6`; `src/IM/frontend/src/features/chat/components/message-pane.tsx:1819` | `src/IM/frontend/src/features/chat/components/message-content-policy.test.ts` is included in the reported 140 focused passing tests | aligned |

The supplied focused command completed with **4 files / 140 tests passed** (`task-graphs`, `agent-work-panel`, `message-pane`, and `message-content-policy`); TypeScript/Vite build also passed. The independent product reviewer retains responsibility for the real-browser recheck of I1 and does not have its evidence pre-claimed here.

### Issues

CRITICAL: None.

WARNING: None.

SUGGESTION: None.

### Corrected Delta Reconciliation

No semantic delta changed in `2126ccab0..21f79e3d8`. Round 1's two corrected-delta outcomes remain **aligned**; the P5 navigation fix does not change their list-total or latest-`change_note` contracts.

Round 2 static verifier verdict: **PASS**. `requires_full_verification: false`.

## Round 3: targeted layout revalidation

> Revalidation mode: `targeted` · patch: `1ef600438..24bb6faad` · executed base: `2e9c83df9` · reviewed snapshot: `24bb6faad`

### Retained evidence

The layout-only frontend change introduces no IM/PA/API/schema/permission/tool behavior. Round 1's source/test-verifiable document, provenance, corrected-delta, and no-automatic-execution conclusions, plus Round 2's P5 router/draft-preservation conclusion, remain valid. The target requirement is now explicit in both the archived delta and canonical IM specification (`docs/changes/archive/feat-569-task-graphs-mvp/specs/im/task-graphs.md:27`; `docs/specs/im/task-graphs.md:27`): dependencies flow left to right at the earliest column whose prerequisites are satisfied; a same-column relation means it may be handled in parallel and neither starts work automatically nor waits for the entire preceding column.

### P2 layout and semantic verification

| Contract | Implementation evidence | Durable test evidence | Result |
|---|---|---|---|
| P2 / R2: direct DAG dependencies retain their recorded orientation while nodes occupy earliest prerequisite columns | Dagre receives only reversed *layout input* and route points are reversed back; returned edges retain `from`/`to` in `src/IM/frontend/src/features/tasks/task-graph-layout.ts:29` | `task-graphs.test.tsx:191` asserts increasing prerequisite columns and retains the `A → C` direct skip edge | aligned |
| P2 / R2: independent branches follow their connections rather than input-row ordering | Dagre calculates coordinates and edge corridors per scope in `task-graph-layout.ts:32` | `task-graphs.test.tsx:179` asserts shared source/sink columns, matching branch order, and the exact two direct edges | aligned |
| P2 / R2: the browser communicates layers/parallelism without changing execution semantics | DAG-only stage overlays in `task-graphs-page.tsx:106`; localized hint states that work does not auto-start | focused browser suite includes the Layer/Parallel assertions; the static copy/delta both retain no automatic execution | aligned |
| P3 / P4: exploration derivation and nested-scope isolation remain distinct | derivation still derives only scoped children and uses dashed render mode in `task-graph-layout.ts:29`, `task-graphs-page.tsx:91` | existing nested browser journey plus `task-graphs.test.tsx:191` excludes `Z1` from root scope | aligned |
| Dependency integrity | `package.json` declares `@dagrejs/dagre@^3.1.1`; lockfile resolves Dagre 3.1.1 and graphlib 4.0.5 | focused suite, TypeScript/Vite build, full frontend 84 files / 779 tests; critical audit exit 0 | aligned |

The archived design appends an as-built correction rather than changing historical Gate 2 rounds: the authorized Dagre choice replaces the prior hand layout while P2's edge semantics remain must-match and spacing/curves/order are may-adapt (`docs/changes/archive/feat-569-task-graphs-mvp/design.md:378`). This is coherent with the delta and does not reopen the approved design.

### Issues

CRITICAL: None.

WARNING: None.

SUGGESTION: None.

### Corrected Delta Reconciliation

The two earlier corrected-delta items (`total` and latest `change_note`) are untouched and remain **aligned**. The new layout sentence is implemented and covered as shown above: it preserves direct dependencies and nested-scope isolation, places prerequisites before dependents, identifies parallel columns, and explicitly retains no automatic execution.

Round 3 static verifier verdict: **PASS**. `requires_full_verification: false`. Actual desktop/mobile layout usability and the associated product journeys remain evidence for the independent product reviewer; this static report does not claim that review.

## Round 4: targeted short-ID revalidation

> Revalidation mode: `targeted` · patch: `4cb266658..5f667ba71` · executed base: `2e9c83df9` · reviewed snapshot: `5f667ba71`

### Retained Gate 2 assessment

The approved design requires service-generated node IDs, graph-local stable references, atomic batches, and the same four tool actions. Its `tn_*` example identifiers are explicitly proposed document shape/examples rather than an ID-format requirement. Therefore switching the generated representation to `n1…n500` does not change the approved product, authorization, storage ownership, or tool-action contract. The appended design decision correctly limits the approach to the current development state: no deletion/re-numbering operation, no migration, alias, or compatibility layer is claimed.

### Source and regression verification

| Contract | Implementation evidence | Durable test evidence | Result |
|---|---|---|---|
| Root and additions have short, graph-local stable IDs | create persists root `n1` in `src/IM/application/task_graphs.py:171`; add_task allocates by the current document cardinality in `src/IM/domain/task_graphs.py:282` | HTTP/WS test asserts root `n1` and n2–n7 client refs; multiple created graphs independently report `n1` | aligned |
| Cross-batch references and relations remain stable through ordinary changes | nodes are keyed by the persisted ID and all relationship operations resolve in the candidate document before validation | `test_short_node_ids_stay_stable_across_batches_and_reordering` retains n2/n3 relations while changing title/status/order and adds n4 | aligned |
| Same-batch references, replay, revision conflicts, and atomic write behavior retain their protection | `@client_ref` map stays request-local; existing receipt/revision sequence runs inside `BEGIN IMMEDIATE` before `repository.save` | existing HTTP/WS test replays the exact batch and asserts its complete n2–n7 map; existing integration conflict/rollback coverage remains in the reported focused suite | aligned |
| Tool guidance tells the Agent to reuse actual returned IDs | `src/personal_assistant/tools/task_graph.py:74` documents graph-local `n1` reuse and updates its operation example | tool surface remains unchanged; focused suite reports 30 passed | aligned |

The supplied focused validation (`tests/im_service/unit/test_task_graph_rules.py` and `tests/im_service/integration/test_task_graph_api.py`) completed with **30 passed**. No frontend source changed. The separately running service and full-suite work remains external evidence and is not claimed here.

### Corrected Delta Reconciliation

The new archived gateway delta is implemented: IDs returned by create/apply are short and stable within a graph, ordinary mutations do not renumber them, and no execution semantics change. However, this observable delta has not been copied to the current authoritative gateway specification: `docs/changes/archive/feat-569-task-graphs-mvp/specs/gateway/task-graphs.md:11` adds the clause, but the equivalent canonical scenario in `docs/specs/gateway/task-graphs.md:14` stops at line 17. This is a confirmed documentation reconciliation gap; it does not invalidate the source behavior or earlier corrected `total`/`change_note` outcomes.

### Issues

CRITICAL: None.

WARNING: Update the canonical gateway task-graphs specification with the same stable graph-local short-ID clause before final archive/contract closure.

SUGGESTION: None.

Round 4 static verifier verdict: **WARNING — implementation/source tests aligned, canonical gateway spec reconciliation incomplete.** `requires_full_verification: false`.

### Round 4 closure: canonical gateway contract

> Closure snapshot: `c23c19a53` · implementation retained: `5f667ba71`

`c23c19a53` changes only `docs/specs/gateway/task-graphs.md`, adding the same short stable graph-local ID sentence as the archived gateway delta. The canonical clause now covers `n1`/`n2` reads and updates, stability through title/order/status changes, and the removal of any UUID-passing expectation. It resolves the sole Round 4 WARNING without changing source, schema, API, tool actions, tests, or product behavior.

The supplied completion evidence is consistent with the retained targeted result: Python CI partitions report **1,986 passed** and **2,066 passed**; repository Ruff check/format reports **1,096** checks passing; docs validation reports **238 sources / 75 routes**. The reported isolated old-test-graph re-numbering is local test-data maintenance, with no committed migration, alias, or compatibility product path.

Round 4 static verifier verdict: **PASS**. `requires_full_verification: false`. The independent product reviewer remains responsible for live product-journey evidence.

## Round 5: targeted short graph-ID revalidation

> Revalidation mode: `targeted` · patch: `5f667ba71..7de35e397` · executed base: `2e9c83df9` · reviewed snapshot: `7de35e397`

### Retained evidence

Round 4's graph-local node IDs, all relation semantics, Agent/tool provenance, current-member authorization, atomic receipt behavior, and the independently reviewed node journeys remain valid. This patch changes only generated `graph_id` selection in the authorized IM create path; it changes no frontend, PA, schema, action, or permission code.

### Source and corrected-delta verification

| Contract | Implementation evidence | Durable test evidence | Result |
|---|---|---|---|
| A graph has one short stable ID used by tool result and Web route | `src/IM/application/task_graphs.py:171` generates `tg_` plus eight hex characters; existing summary derives `relative_url` from the same saved ID | collision test asserts each returned `relative_url` and its independent HTTP read | aligned |
| A shortened-ID collision cannot overwrite an existing graph | `repository.get` retries inside the existing `BEGIN IMMEDIATE` transaction before the existing upsert | forced shared-prefix UUIDs produce `tg_12345678` then `tg_abcdef01`; both first and second graph titles remain readable | aligned |
| Request replay remains idempotent and cannot allocate a replacement graph | receipt lookup precedes ID allocation at `src/IM/application/task_graphs.py:152` | collision test repeats the first create with the same key and asserts the exact original result | aligned |
| Short graph IDs do not widen access | actor and current membership validation precede receipt lookup and graph allocation | retained ACL/revoked-replay coverage; no access-path code changed | aligned |
| Corrected gateway delta is authoritative and reconciled | archived delta and canonical spec contain the same new graph-ID clause | direct line comparison; no canonical omission remains | aligned |

The supplied focused task-graph suite completed with **32 passed**. The remaining Python full suite is running separately and is not claimed as complete here; prior Agent/PA 1,986-pass and frontend 779-pass evidence remains unaffected.

### Issues

CRITICAL: None.

WARNING: None.

SUGGESTION: None.

Round 5 static verifier verdict: **PASS**. `requires_full_verification: false`. The separate product reviewer owns the added live short-graph-ID journey evidence.
