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

## Round 6: targeted task-graph feature-switch revalidation

> Review mode: `targeted` · patch: `46238f91f..a34bb2bd3` · reviewed snapshot: `a34bb2bd3`

### Findings

```json
[]
```

This round covers only the new per-Agent task-graph feature. `resolve_enabled_tools` remains the single effective-tool resolver for the session runtime, prompt preview, and task-graph Bridge. It treats an absent `features.task_graph` value as enabled, never adds `task_graph` when the explicit allowlist omits it, and removes it when the feature is explicitly false (`src/personal_assistant/product.py:434`). The capability projection advertises the feature as default-on with `requires_tool="task_graph"`, while the existing Agent create/edit linkage adds that required tool when the user explicitly enables the feature (`src/personal_assistant/reporter/capability_projection.py:67`; `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1747`).

Runtime and preview both call the same resolver, so disabled task graphs are neither offered to the model nor represented in preview. The Bridge authorizes against the session's applied snapshot, not a newer catalog publication (`src/personal_assistant/gateway/task_graphs.py:55`). `ensure_agent_runtime` writes new provenance only after the Kernel accepts the updated runtime; an idle-only global reconfiguration rejected for a busy session returns before that write (`src/personal_assistant/gateway/kernel_client.py:201`). The global resolver also preserves an existing session snapshot during address resolution. Thus a save affects the next admitted reply while an in-flight global turn continues with the already-adopted capability set.

The supplied targeted evidence is `40 passed` in `/tmp/feat569-feature-green.log`; the supplied red phase records the expected eight failures before implementation. This review did not rerun those tests or claim the separate real-product feature-switch journey. Earlier DAG layout, graph/node short-ID, persistence, authorization, channel-neutral tool, and no-automatic-execution evidence is unchanged by this configuration-only patch.

The archived task-graphs delta adds S21 and the new agent-capabilities delta makes the limited effective-tool exception explicit. They match the existing canonical next-turn full-runtime rule and are semantically ready for corrected-delta reconciliation. `git diff --check` reported only the final blank line in `specs/gateway/agent-capabilities.md`; its mechanical cleanup is owned by the integrator and does not change this verdict.

Verdict: **PASS — no remaining confirmed or plausible targeted code-review findings.**

## Round 7: targeted account-ownership and per-node-chat revalidation

> Review mode: `targeted` · patch: `4058e38ad..b94e157c7` · reviewed snapshot: `b94e157c7`

### Findings

```json
[
  {
    "file": "src/IM/domain/task_graphs.py",
    "line": 72,
    "summary": "Root creation drops the supplied last-update chat",
    "failure_scenario": "An Agent creates a graph from an accessible chat. TaskGraphService passes that conversation to new_node, but new_node writes last_chat_id=None after expanding fields. The root has no return-to-chat button or update-chat title until a later apply happens to modify it, contrary to S23's requirement that creation records the current chat.",
    "review_mode": "targeted",
    "status": "CONFIRMED"
  }
]
```

The account boundary itself is correctly derived from the authenticated user or registered non-stale Agent profile. Owner-scoped list/get/write and receipt replay all compare the current trusted `owner_id`; no model argument can select an owner. Same-account enabled Agents therefore share graphs without an Agent-assignment path, while a different account cannot obtain a graph or an old receipt merely through source-chat membership. Optional source validation remains a separate current-conversation membership check, and read projection independently clears inaccessible/deleted node chat IDs and titles.

The Bridge carries the trusted `ToolContext.run_id`; for a single-thread write without explicit target it consults the shared `RunDeliveryContextStore` and verifies both Agent and Kernel session before using that run's canonical chat. Global and missing/mismatched-context paths retain no inferred source. `conversation_id` is removed from the receipt hash and a matching replay returns before source validation or node mutation, preserving the initial update source.

However, `TaskGraphService.create` passes `last_chat_id=conversation_id` to `new_node` (`src/IM/application/task_graphs.py:194`), while `new_node` assigns its default `last_chat_id` after `**fields` (`src/IM/domain/task_graphs.py:72`). Python therefore overwrites the supplied chat with `None`. The existing ownership test exercises a source create only through a peer that cannot read the source, and later changes the root through apply, so it misses the creation case. Move the default before `**fields` (or otherwise preserve a supplied value) and add an owner HTTP/WS assertion that create with `conversation_id` returns the root's ID/title; retain the existing no-source null assertion.

Supplied narrow evidence is Python `33 passed`, UI `11 passed`, plus build and Ruff. This review did not rerun those commands or claim the separate product journey. Earlier DAG, compact-ID, S21, persistence, provenance, and no-automatic-execution conclusions remain valid outside the failed root-source write.

Verdict: **WARNING — S22 owner sharing and most S23 paths align, but source-chat creation of the root is incorrect.**

### Round 7 closure: root creation source retention

> Closure snapshot: `44af01688` · targeted repair range: `b94e157c7..44af01688`

### Findings

```json
[]
```

`new_node` now establishes its `last_chat_id` default before expanding caller fields (`src/IM/domain/task_graphs.py:72`). The explicit source passed by graph creation therefore persists on the root. The focused owner HTTP read now asserts both the root `last_chat_id` and the independently ACL-projected `last_chat_title` immediately after source-backed creation (`tests/im_service/integration/test_task_graph_ownership.py:59`).

The supplied red phase records the original failure in both global and single-thread cases (`2 failed`); the repair phase reports `27 passed` in `/tmp/feat569-create-source-green.log`. This was a static targeted revalidation; it does not claim the separate product journey or rerun the parallel full suites. The mechanical S21 wording update from Web-membership language to account access is consistent with the implemented owner boundary and changes no behavior.

Verdict: **PASS — the confirmed Round 7 root-source finding is closed; no remaining targeted code-review finding.**

## Round 8: targeted real-Agent principal repair

> Review mode: `targeted` · repair snapshot: `a4bd167de` · repair range: `44af01688..a4bd167de`

### Findings

```json
[]
```

The removed `u.owner_id=p.owner_id` predicate was an identity-model error: `ConfigService.ensure_agent_user` creates the unique synthetic `agent:<agent_id>` chat user with its own `owner_id`, while the authoritative human account is the registered, non-stale profile owner. The retained profile-to-node owner join establishes that account before any graph or receipt lookup; the synthetic `users` join now supplies only the real participant ID required for source-chat membership. The `users.username` uniqueness constraint keeps this correspondence singular.

The integration fixture now creates profiles through `ConfigService`, then resolves the synthetic participant through `UserRepository`, matching the production construction path. Its existing transfer regression intentionally changes only profile/node ownership and still denies the old receipt, which proves authorization does not accidentally fall back to the synthetic user's self-owner value.

The supplied red phase has the expected four actual-Agent command failures; the focused API, owner, and domain repair phase reports `27 passed` in `/tmp/feat569-agent-principal-green.log`. This review did not rerun full suites or claim the independent product revalidation. The only implementation change is this principal-resolution repair; all earlier DAG, short-ID, feature-gate, source-chat, persistence, provenance, and no-automatic-execution conclusions remain retained.

Verdict: **PASS — real registered Agents resolve to their profile/node human owner without weakening cross-account isolation.**

## Round 9: targeted redundant chat-header task entry removal

> Review mode: `targeted` · patch: `6cec792e7..d248135e2` · reviewed snapshot: `d248135e2`

### Findings

```json
[]
```

`ConversationTasksLink` was the only removed behavior: it independently queried the same account-wide task list and routed the chat header to `/tasks`. The desktop shell navigation and mobile bottom navigation still route to `/tasks` (`src/IM/frontend/src/app/shell/app-shell.tsx`), while message Markdown still routes same-origin task URLs through `TaskGraphLink` (`src/IM/frontend/src/features/chat/components/message-pane.tsx`, `src/IM/frontend/src/features/tasks/task-graph-link.tsx`). Thus the removed duplicate does not remove the account-level browsing entry or a direct graph-link path that preserves composer snapshots.

The deleted assertions covered only the removed header link and its no-conversation-filter fetch. The retained message-link journey verifies the actual direct-link and draft-preservation behavior. Removing the component also removes its isolated list-count query; no live task-page query, graph rendering, node discussion, or access path is changed. The supplied targeted UI/shell result is `15 passed`, with TypeScript/Vite build, docs-check, Ruff, and diff checks passing; this review did not rerun the in-progress full frontend suite.

Verdict: **PASS — no targeted code-review finding; prior implementation, authorization, DAG, compact-ID, feature-gate, and source-chat gates remain valid.**

Round 9 targeted closure: `headerActions` had no remaining frontend caller after the duplicate task entry was removed; `e820450d9` deletes only that unused prop, destructure, and JSX slot. The Round 9 PASS is validated at and effective through `e820450d9`.
