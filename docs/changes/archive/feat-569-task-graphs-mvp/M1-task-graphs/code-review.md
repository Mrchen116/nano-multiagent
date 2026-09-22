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
