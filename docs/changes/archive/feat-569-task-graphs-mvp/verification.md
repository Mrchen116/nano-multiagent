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
