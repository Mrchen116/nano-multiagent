# Verification Report: feat-515

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 4a11df1e5dcbd76c8eaedf6ae4ca2d1c4e1b045e`

## Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 3/4 spec requirements covered |
| Correctness | 6/7 top-level spec scenarios correct; one fixed-root scenario is violated |
| Coherence | Two blocking deviations, including one cross-machine architecture violation |

2 critical issue(s), 1 warning(s) found. Fix before PR.

## Completeness

- Tasks: the six M1 exit-criterion checkboxes are marked complete, but the claim that workspace root is fixed after creation is contradicted by the normal UI request shape; the second create of the same Agent can overwrite the first root (CRITICAL-1).
- Spec coverage:
  - `创建 Agent 时可选择默认目录或自定义路径`: implemented by the create page, Gateway creation boundary, and structured HTTP/WS outcome.
  - `采用已有目录前须提醒用户`: implemented as a side-effect-free first rejection and explicit confirmation retry.
  - `同节点 workspace root 只可归属一个 Agent`: implemented with Gateway-local canonical-root comparison; ownership is isolated per Gateway config.
  - `创建后 workspace root 固定`: not complete. Config PATCH and the detail page are read-only, but repeating the create request for the same ownerless Agent id replaces the persisted IM root and Gateway creation can replace the local Agent config (CRITICAL-1).
- Prototype / reference coverage: all four `must-match` rows are projected into `tasks.md`, implemented in the create page, and have durable desktop/390px/confirmation evidence under `M1-workspace-creation/evidence/`. The screenshots and acceptance report are repository-local and reproducible evidence, not `/tmp` references.
- Validation performed at the snapshot:
  - Focused Gateway/IM pytest owners: `86 passed`.
  - Focused changed-file Ruff: passed.
  - `git diff --check a5e64e4f..4a11df1e`: passed.
  - `scripts/docs-check`: passed (`221` maintained Markdown sources, `66` required routes).
  - Frontend Vitest could not be rerun in the detached verification worktree because it intentionally has no `node_modules`; M1's committed progress records targeted `28 passed`, full frontend `611 passed`, and a successful production build. The missing scenario coverage in WARNING-1 is established by source inspection, not by this environment limitation.

## Correctness

| Requirement / Scenario | Implementation location | Test coverage | Status |
|---|---|---|---|
| Default directory creation | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388`, `src/personal_assistant/gateway/agent_config_sync.py:172` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py:64`; create-page default payload test | covered |
| New custom workspace under usable parent | `src/personal_assistant/gateway/agent_config_sync.py:343`, `src/IM/api/routes/nodes.py:291` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py:64`; create-page custom test | covered |
| Missing/unusable parent or non-directory target | `src/personal_assistant/gateway/agent_config_sync.py:343`, `src/IM/api/routes/nodes.py:352`, `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:474` | Gateway unit coverage exists; HTTP 422 and UI field rendering are untested | covered implementation; WARNING-1 |
| Existing directory requires confirmation | `src/personal_assistant/gateway/agent_config_sync.py:388`, `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468` | Gateway unit, WS/HTTP conflict, UI retry, and real-stack evidence | covered |
| Same-node canonical root already assigned | `src/personal_assistant/gateway/agent_config_sync.py:185` | canonical symlink alias test and UI owner-message test | covered |
| Same string root on different nodes | `src/personal_assistant/gateway/agent_config_sync.py:336` | two independent Gateway-config unit test and durable dual-Gateway acceptance | covered |
| Existing Agent root is visible but immutable | Detail PATCH omits root at `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1303` and the field is disabled at `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1845`; create duplicate guard is insufficient at `src/IM/api/routes/nodes.py:246` | Existing PATCH immutability coverage does not exercise the normal UI's empty `owner_id` duplicate-create shape | violated; CRITICAL-1 |
| Gateway canonical root/provenance remains opaque through IM mirror/RPCs | `src/IM/application/config_service.py:222`; RPC callers use this accessor | `tests/im_service/contract/test_workspace_root_mirror_contract.py:13` covers config/live/capabilities/preview/cron/skill usage/heartbeat | covered for enumerated RPCs; architecture still violated by CRITICAL-2 |

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| Existing directory uses a second explicit-confirmation request with no first-request side effects | Yes | `src/personal_assistant/gateway/agent_config_sync.py:388`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468` |
| Default sends no root; custom root is resolved only on the target node | Yes | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388`; `src/personal_assistant/gateway/agent_config_sync.py:172`; `src/personal_assistant/gateway/agent_config_sync.py:297` |
| Same-node uniqueness uses canonical roots in Gateway-local config | Yes | `src/personal_assistant/gateway/agent_config_sync.py:185`; `src/personal_assistant/gateway/agent_config_sync.py:336` |
| Parent/target validation precedes initialization and persistence | Yes | `src/personal_assistant/gateway/agent_config_sync.py:193`; `src/personal_assistant/gateway/agent_config_sync.py:343` |
| Success alone creates IM mirror; stable failures map to 409/422 | Yes | `src/IM/api/routes/nodes.py:282`; `src/IM/api/routes/nodes.py:352` |
| A created Agent's workspace root is fixed | No | Duplicate normal-UI requests pass `src/IM/api/routes/nodes.py:246` and replace the profile through `src/IM/application/config_service.py:94`; see CRITICAL-1 |
| IM treats Gateway workspace paths as opaque and never reads the node filesystem | No | `src/IM/infra/repositories/conversations.py:683` treats persisted Gateway roots as IM-local paths and scans/opens them; see CRITICAL-2 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Workspace card between Identity and Behavior | M1 worker/reviewer #1 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:650`, `:741`, `:858` | `M1-workspace-creation/evidence/create-desktop-default.png` | covered |
| Default/custom exclusive choice; default selected | M1 worker/reviewer #1/#2 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:343`, `:754` | desktop and mobile screenshots plus acceptance report | covered |
| Custom copy identifies target node, parent rule, and field error | M1 worker/reviewer #2/#3 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:800`, `:818`; localized code mapping at `:474` | custom desktop/mobile screenshots and acceptance report | covered; automated scenario gap in WARNING-1 |
| Existing-directory warning, checkbox, retry | M1 worker/reviewer #3/#4 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:829` | `M1-workspace-creation/evidence/create-existing-confirmation.png` and acceptance report | covered |
| Colors, spacing, controls may adapt to existing Agent tokens | M1 visual evidence | `src/IM/frontend/src/styles/global.css` workspace selectors | desktop/390px screenshots | covered |

## Issues

### CRITICAL (must fix before PR)

- **CRITICAL-1 — The normal UI request can recreate the same Agent id and change its supposedly fixed workspace root.** The create-page draft hard-codes `owner_id: ""` (`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:83`), while both the route and service reject an existing Agent only when `existing.owner_id.strip()` is non-empty (`src/IM/api/routes/nodes.py:246`, `src/IM/application/config_service.py:94`). An isolated HTTP reproduction using the UI request shape returned 201 twice and changed the stored root from `/srv/agents/root-1` to `/srv/agents/root-2`. Gateway creation also replaces an existing local config with the same `agent_id` (`src/personal_assistant/gateway/agent_config_sync.py:738`) after initializing the new target. Fix the create boundary so ownership comes from the authenticated `user.owner_id`, reject any existing Agent id independently of client-supplied owner text, and prevent the Gateway handler from replacing an existing Agent id during create. Add a regression test using `owner_id: ""` that proves the second request is 409 and neither IM nor Gateway changes the first root; use an atomic/serialized uniqueness boundary so concurrent duplicate creates cannot bypass the pre-check.

- **CRITICAL-2 — IM still directly scans and opens a Gateway workspace, violating the cross-machine architecture boundary.** `ConversationRepository._resolve_source_jsonl_path()` reads the mirrored `workspace_root`, calls `Path(...).is_dir()`, recursively scans `*.jsonl`, and opens candidates (`src/IM/infra/repositories/conversations.py:683`). A custom root on a remote Gateway is therefore interpreted on the IM host, contrary to the design's opaque-root decision and the current contract that IM never directly reads Gateway workspace files. Move session-log discovery/read behind a target-Gateway RPC (or redesign the exposed distillation locator so IM never dereferences a node-local path), and replace the co-located filesystem tests in `tests/im_service/integration/test_users_conversations_api.py:11` and `tests/im_service/unit/test_repositories_user_conversation.py:177` with remote-node/RPC coverage.

### WARNING (must fix before PR)

- **WARNING-1 — The parent/target failure scenario lacks permanent HTTP and UI regression coverage.** Gateway unit tests verify that `workspace_parent_missing`, `workspace_parent_unusable`, `workspace_target_not_directory`, and `workspace_initialization_failed` are produced, but `tests/im_service/contract/test_agent_create_contract.py:128` covers only the confirmation 409, and `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx:104` covers only confirmation and assignment UI branches. Add parameterized IM route tests proving each validation code maps to 422 without creating a profile, plus create-page tests proving each code stays on the form, preserves the draft, and renders the localized reason beside Workspace Root. This directly covers the spec scenario rather than only testing its lowest-level producer.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.
