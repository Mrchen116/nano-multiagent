# Code Review: feat-569-task-graphs-mvp / M1-task-graphs

> Review mode: `full` · reviewed range: `499774a56..cb45a06a5` · implementation snapshot: `f6062432f` · retained through: `cb45a06a5`

## Findings

```json
[]
```

The full implementation adds IM-owned, revisioned task documents; PA's provenance-checked native tool and correlated Gateway transport; and a read-only Web IM browser. The review checked atomic mutation/replay, current conversation membership before every read or write, Agent allowlist/provenance, channel-independent target mapping, and the frontend's stale/revoked-cache handling. It does not substitute for the separate real-product review.

## Closure

One warning identified during this review was closed in `cb45a06a5`: the corrected delta required a persisted and visible latest `change_note`, while the original tests only enforced a note for a done-to-doing transition. The closure extends the existing IM integration test to assert the post-apply HTTP document value at `tests/im_service/integration/test_task_graph_api.py:163`, and the existing task-browser test to assert the detail label/value at `src/IM/frontend/src/features/tasks/task-graphs.test.tsx:97`. The reported narrow IM and frontend task suites pass.

Verdict: **PASS — no remaining confirmed or plausible code-review findings.**

## Round 2: targeted revalidation

> Review mode: `targeted` · patch: `2126ccab0..21f79e3d8` · reviewed snapshot: `21f79e3d8`

### Findings

```json
[]
```

This round verifies the product-review I1 correction only. `TaskGraphLink` converts same-origin `/tasks` and `/tasks/*` Markdown URLs to React Router navigation, preserving the in-memory composer store. It is used by Chat message Markdown (`src/IM/frontend/src/features/chat/components/message-pane.tsx:1830`), Agent Work Markdown (`src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx:193`), and task-detail Markdown/ordinary evidence links (`src/IM/frontend/src/features/tasks/task-graphs-page.tsx:146`). The component deliberately falls back to an ordinary anchor for malformed, non-task, and cross-origin links; Chat's established protected-resource, `mailto`, unsupported-link, and external-new-tab policies remain upstream of it.

The revised Chat path starts from an actual Agent Markdown link, visits the graph, uses Discuss, and verifies draft text, mentions, pending attachment, appended task reference, and no send (`src/IM/frontend/src/features/tasks/task-graphs.test.tsx:117`). The Work route assertion covers its real Markdown consumer (`src/IM/frontend/src/features/settings/agents/agent-work-panel.test.tsx:28`). Credible supplied validation is 140 focused frontend tests and the TypeScript/Vite build, both passing. Earlier static evidence remains valid because this patch changes only the affected frontend navigation boundary and its tests.

Verdict: **PASS — no remaining confirmed or plausible targeted code-review findings.**

## Round 3: targeted layout revalidation

> Review mode: `targeted` · patch: `1ef600438..24bb6faad` · executed base: `2e9c83df9` · reviewed snapshot: `24bb6faad`

### Findings

```json
[]
```

This round covers the user-requested DAG layout correction. `layoutTaskScope` gives Dagre only reversed layout edges under `rankdir: "RL"` and `ranker: "longest-path"`; it reverses the routed points back before rendering and retains each stored `from`/`to` pair (`src/IM/frontend/src/features/tasks/task-graph-layout.ts:29`). Thus neither the displayed arrow direction nor the graph's direct-dependency data is reversed. The canvas renders the derived-mode relationship separately, keeps its dashed styling, and leaves cards and interaction unchanged (`src/IM/frontend/src/features/tasks/task-graphs-page.tsx:90`).

The regression coverage first demonstrates the old independent-branch crossing, then asserts stable branch order, left-to-right prerequisites, direct skip-edge retention, nested-scope exclusion, and unchanged task records (`src/IM/frontend/src/features/tasks/task-graphs.test.tsx:178`). Layer/parallel labels are limited to DAG scopes and the accompanying copy explicitly says that parallelism does not automatically start work (`src/IM/frontend/src/features/tasks/task-graphs-page.tsx:106`; `src/IM/frontend/src/i18n/en.json:999`). `@dagrejs/dagre@3.1.1` is a declared runtime dependency with its exact package-lock resolution; the library was expressly authorized for this correction.

Supplied evidence shows the focused task-graph suite (8 tests), TypeScript/Vite build, full frontend suite (84 files / 779 tests), docs-check, and diff-check passing. `npm audit --audit-level=critical` exits successfully; its seven reported low/moderate/high advisories predate this two-package addition. The separate product reviewer remains responsible for actual UI evaluation.

Verdict: **PASS — no remaining confirmed or plausible targeted code-review findings.**

## Round 4: targeted short-ID revalidation

> Review mode: `targeted` · patch: `4cb266658..5f667ba71` · executed base: `2e9c83df9` · reviewed snapshot: `5f667ba71`

### Findings

```json
[
  {
    "file": "docs/specs/gateway/task-graphs.md",
    "line": 17,
    "summary": "Current gateway specification omits the new short node-ID contract",
    "failure_scenario": "After this archived unit is merged, a tool consumer consulting the canonical gateway specification is not told that IDs are graph-local stable n1/n2 values and may still assume the prior unspecified long-ID behavior.",
    "review_mode": "targeted",
    "status": "CONFIRMED"
  }
]
```

The implementation itself is coherent in the stated development-only scope. Creation persists `n1` (`src/IM/application/task_graphs.py:171`); each atomic add allocates `n{len(nodes)+1}` after copying the one graph document, then validates all relationship references before save (`src/IM/domain/task_graphs.py:282`). The existing `BEGIN IMMEDIATE` transaction continues to serialize receipt lookup, revision validation, document mutation and receipt save (`src/IM/application/task_graphs.py:111`). Thus same-batch `@client_ref`, later-batch concrete IDs, retry receipts, and separate graphs that each start at `n1` retain their original scoping/atomicity behavior. No deleted-node or imported-document fallback is required by the authorized scope.

The new domain and HTTP/WS assertions cover n1 roots, n2–n7 references, exact replay, cross-batch relationships, reordering without renumbering, and multiple graphs independently rooted at n1 (`tests/im_service/unit/test_task_graph_rules.py:44`; `tests/im_service/integration/test_task_graph_api.py:80`). The supplied focused command passes 30 tests. The original Gate 2 contract requires service-generated IDs and stable returned references but does not constrain a UUID format, so the as-built design correction is a permitted implementation choice.

The remaining finding is documentary: the archived gateway delta adds the observable short-ID requirement (`docs/changes/archive/feat-569-task-graphs-mvp/specs/gateway/task-graphs.md:11`), while the canonical gateway spec ends the corresponding scenario at its prior no-scheduling clause (`docs/specs/gateway/task-graphs.md:17`). The current spec needs that same one-line requirement before archival reconciliation is complete.

Verdict: **WARNING — source implementation passes targeted review; canonical gateway-contract reconciliation remains open.**

### Round 4 closure: canonical gateway contract

> Closure snapshot: `c23c19a53` · implementation retained: `5f667ba71`

```json
[]
```

`c23c19a53` adds only the missing canonical clause at `docs/specs/gateway/task-graphs.md:18`. It is textually the same short, graph-local stable-ID requirement already present in the archived gateway delta (`docs/changes/archive/feat-569-task-graphs-mvp/specs/gateway/task-graphs.md:11`), including the no-renumbering and no-UUID-passing semantics. The confirmed Round 4 documentation finding is closed; no implementation behavior changed, so the earlier source review remains retained.

Supplementary supplied evidence is clean: equivalent Python CI partitions report 1,986 and 2,066 passed; repository Ruff check/format report 1,096 checks passing; and docs validation reports 238 sources / 75 routes. This closure does not claim the separate product review.

Verdict: **PASS — Round 4 implementation and canonical gateway-contract reconciliation are complete.**

## Round 5: targeted short graph-ID revalidation

> Review mode: `targeted` · patch: `5f667ba71..7de35e397` · executed base: `2e9c83df9` · reviewed snapshot: `7de35e397`

### Findings

```json
[]
```

Creation now chooses `tg_` plus the first eight hexadecimal characters from the existing UUID source, then checks the authoritative `task_graphs` key and retries while a row exists (`src/IM/application/task_graphs.py:171`). That check and the later upsert live under the pre-existing `BEGIN IMMEDIATE` reservation. A pre-existing graph therefore cannot be overwritten by a shortened-ID collision, and concurrent creates cannot pass the check simultaneously. Receipt lookup remains before generation, so an exact same-key retry returns its original graph without consuming or replacing an ID (`src/IM/application/task_graphs.py:152`). The global collision check is reached only after the original Agent identity and home-conversation membership checks; it exposes no graph data and introduces no access path.

The HTTP/WS regression forces two full UUIDs with the same eight-character prefix. It verifies that the second create retries to a different `tg_` ID, both returned links resolve to their own graph, and the same create request replays its original receipt (`tests/im_service/integration/test_task_graph_api.py:210`). The supplied focused task-graph command passes 32 tests. Node-ID source, frontend, PA tool shape, authorization and prior product evidence are unchanged by this one application-level generation change.

The new requirement is identical in the archived gateway delta and current gateway specification (`docs/changes/archive/feat-569-task-graphs-mvp/specs/gateway/task-graphs.md:12`; `docs/specs/gateway/task-graphs.md:19`). It accurately states stable short graph references, collision non-overwrite, and the shared tool/Web link ID.

Verdict: **PASS — no remaining confirmed or plausible targeted code-review findings.**
