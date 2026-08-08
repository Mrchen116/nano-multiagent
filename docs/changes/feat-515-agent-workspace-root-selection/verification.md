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

# Round 2

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 2a35a4c4f3afcf31248c55ad09dc1cf24ca2b764`

## Summary

Mode: full
Delta range: `e813c45f10fc11a33f0e75358c810e1a0fe1aa5e..2a35a4c4f3afcf31248c55ad09dc1cf24ca2b764`
Focus issues: round-1 CRITICAL-1 / CRITICAL-2 / WARNING-1 plus duplicate-ID, lost-response retry, Gateway immutability, invalid preview, ownerless provenance, and remote session-log corrections
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 spec requirements covered |
| Correctness | 7/7 top-level spec scenarios implemented and permanently covered |
| Coherence | One blocking provenance deviation remains |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Round-1 Closure

| Prior issue / review candidate | Result | Evidence |
|---|---|---|
| CRITICAL-1 / UI-shaped duplicate ID could replace the fixed root | closed | The route uses authenticated `user.owner_id`, holds the app-scoped create lock across precheck, Gateway dispatch, and insert, and rejects any existing ID at `src/IM/api/routes/nodes.py:240-380`; the repository insert-only boundary is `src/IM/infra/repositories/agents.py:233-299`. UI-shaped and concurrent HTTP regressions pass in `tests/im_service/contract/test_agent_create_immutability_contract.py:69-237`. |
| Lost Gateway success before IM mirror write was not safely retriable | closed | Gateway returns the persisted success only for the same canonical root and provenance at `src/personal_assistant/gateway/agent_config_sync.py:194-210`; HTTP recovery is covered at `tests/im_service/contract/test_agent_create_immutability_contract.py:125-179`. |
| Gateway could replace an existing Agent ID or race divergent creates | closed | The check-and-publish operation is serialized at `src/personal_assistant/gateway/agent_config_sync.py:166-218`; divergent-root, same-root retry, and concurrent-create regressions pass in `tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py:13-118`. |
| CRITICAL-2 / IM dereferenced a Gateway-local workspace for session lookup | closed | Repository projection now returns no local path at `src/IM/infra/repositories/conversations.py:635-657`; the API asks the owning node at `src/IM/api/routes/web_im.py:175-194`, and only Gateway scans/opens its local sessions at `src/personal_assistant/ws/im_connection.py:1068-1097,2024-2051`. Remote-root HTTP/RPC coverage is in `tests/im_service/integration/test_users_conversations_api.py:10-89` and Gateway-local resolver coverage is in `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py:219-291`. |
| WARNING-1 / parent-target failures lacked HTTP and UI regressions | closed | All four stable codes have 422/no-profile/no-user coverage at `tests/im_service/contract/test_agent_create_immutability_contract.py:17-66`; the UI preserves identity, mode, and root while rendering localized field errors at `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx:205-229`. |
| Invalid custom prompt preview disconnected the Gateway receive loop | closed | Resolver `ValueError` becomes a correlated workspace result and returns without invoking the provider at `src/personal_assistant/ws/im_connection.py:1218-1260`; protocol and HTTP mapping tests pass at `tests/unit/personal_assistant/test_gateway_workspace_creation_protocol.py:139-202` and `tests/im_service/contract/test_agent_config_contract.py`. |
| Ownerless provenance correction | behavior present; coherence warning | Ownerless re-registration now forcibly refreshes non-null provenance at `src/IM/infra/gateway_persistence.py:166-204` and the integration regression proves it. This conflicts with the approved non-overwrite contract; see WARNING-1. |

## Completeness

- Tasks: all six M1 exit criteria and all round-1 correction checklist items have corresponding implementation and durable evidence. The round-1 duplicate-root, remote-path, and path-error gaps are closed.
- Spec coverage:
  - `创建 Agent 时可选择默认目录或自定义路径`: covered by the create page, node-local creation authority, and structured HTTP/WS result.
  - `采用已有目录前须提醒用户`: covered by side-effect-free confirmation rejection and confirmed retry.
  - `同节点 workspace root 只可归属一个 Agent`: covered by canonical Gateway-local comparison and per-node configs.
  - `创建后 workspace root 固定`: covered by read-only detail/update behavior plus IM and Gateway duplicate-ID immutability boundaries.
- Prototype / reference coverage: all four `must-match` rows remain projected into M1 tasks, implementation, repository-local desktop/mobile/confirmation screenshots, and `M1-workspace-creation/evidence/acceptance.md`.
- Validation at this snapshot:
  - Focused round-1 correction and feature owners: `110 passed`.
  - Full non-E2E Python suite: `3049 passed, 24 deselected`.
  - Changed-file Ruff: passed.
  - `scripts/docs-check`: passed (`224` maintained Markdown sources, `66` required routes).
  - `git diff --check`: passed after this round-2 report removed the three pre-existing trailing-space markers in the round-1 summary.
  - Frontend Vitest could not be rerun directly from the read-only detached worktree because it has no local `node_modules`; attempts using the main checkout dependency tree failed package resolution before collection. The committed correction evidence records targeted `22 passed` and a successful build; source inspection confirms the four-code table asserts draft preservation and localized field placement.

## Correctness

| Requirement / Scenario | Implementation location | Test coverage | Status |
|---|---|---|---|
| Default directory creation | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388-395`; `src/personal_assistant/gateway/agent_config_sync.py:181-227` | Gateway creation, HTTP success, frontend default payload, and real-stack evidence | covered |
| New custom workspace under usable parent | `src/personal_assistant/gateway/agent_config_sync.py:181-243,377-432` | Gateway filesystem, HTTP, frontend custom payload, and real-stack evidence | covered |
| Missing/unusable parent or non-directory target | `src/personal_assistant/gateway/agent_config_sync.py:377-426`; `src/IM/api/routes/nodes.py:314-410`; UI mapping at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:459-487` | Gateway producer plus permanent four-code HTTP/UI coverage | covered |
| Existing directory requires confirmation | `src/personal_assistant/gateway/agent_config_sync.py:427-432`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468-486,829-849` | Gateway, protocol, HTTP, UI retry, and real-stack evidence | covered |
| Same-node canonical root already assigned | `src/personal_assistant/gateway/agent_config_sync.py:212-218,370-375` | canonical alias, UI owner message, and real-stack evidence | covered |
| Same string root on different nodes | ownership is derived only from `self._config_snapshot().agents` at `src/personal_assistant/gateway/agent_config_sync.py:370-375` | independent Gateway-config test and dual-Gateway acceptance evidence | covered |
| Existing Agent root is visible and immutable | create rejection at `src/IM/api/routes/nodes.py:266-290`; insert-only profile at `src/IM/infra/repositories/agents.py:233-299`; Gateway guard at `src/personal_assistant/gateway/agent_config_sync.py:194-210`; detail/update remains read-only | UI-shaped duplicate, concurrent HTTP/Gateway, lost-response retry, PATCH immutability, and detail tests | covered |

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| Existing directory uses explicit confirmation retry with no first-request side effects | Yes | `src/personal_assistant/gateway/agent_config_sync.py:377-432`; create page confirmation at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468-486,829-849` |
| Default delegates to node; custom paths are resolved only on the target node | Yes | request projection at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388-395`; node resolver at `src/personal_assistant/gateway/agent_config_sync.py:331-368` |
| Same-node ownership uses canonical roots in Gateway-local config | Yes | `src/personal_assistant/gateway/agent_config_sync.py:212-218,370-375` |
| Parent/target validation precedes initialization and persistence | Yes | `src/personal_assistant/gateway/agent_config_sync.py:220-243,377-432` |
| Success alone creates the IM mirror and typed failures map to 409/422 | Yes | `src/IM/api/routes/nodes.py:305-381,384-410` |
| A created Agent's root remains immutable while a lost success is recoverable | Yes | IM/Gateway serialized duplicate boundaries cited in Round-1 Closure |
| IM never dereferences Gateway-local workspace/session files | Yes | API-to-Gateway session lookup cited in Round-1 Closure; IM repository returns `source_jsonl_path=None` |
| Register only fills missing provenance and never overwrites recorded true/false | No | `src/IM/infra/gateway_persistence.py:177-204` and `src/IM/infra/repositories/agents.py:188-194` deliberately replace any ownerless non-null value; see WARNING-1 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Workspace card between Identity and Behavior | M1 worker/reviewer #1 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:650-858` | desktop default/custom screenshots | covered |
| Default/custom exclusive choice; default selected | M1 worker/reviewer #1/#2 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:343,754-798` | desktop and 390px screenshots | covered |
| Target-node copy, parent rule, and field errors | M1 worker/reviewer #2/#3 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:800-826`; stable code mapping at `:474-487` | custom/mobile screenshots plus acceptance report | covered |
| Existing-directory warning, checkbox, and retry | M1 worker/reviewer #3/#4 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:829-849` | existing-confirmation screenshot plus acceptance report | covered |
| Colors, spacing, and controls may adapt to existing tokens | M1 visual evidence | `src/IM/frontend/src/styles/global.css` workspace selectors | desktop/390px screenshots | covered |

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — Ownerless re-registration overwrites an already recorded provenance value, contradicting the approved root/provenance contract and allowing the pair to become inconsistent.** The design says `workspace_root` and `workspace_is_default` are inseparable and that register may only fill a NULL provenance, never overwrite recorded true/false (`docs/changes/feat-515-agent-workspace-root-selection/design.md:182-195`); the current spec likewise says existing profile fields survive re-registration (`docs/specs/im/agents-nodes.md:181-193`). The correction instead sets `replace_workspace_provenance=true` for every ownerless existing profile with a seed (`src/IM/infra/gateway_persistence.py:166-204`), and repository SQL replaces non-null provenance (`src/IM/infra/repositories/agents.py:188-194`) while retaining the existing root (`src/IM/infra/gateway_persistence.py:173-180`). A later ownerless frame can therefore pair old root P with provenance for the Gateway's current root Q. Either restore the approved fill-NULL-only behavior and adjust the ownerless regression, or explicitly amend the design/current spec and atomically refresh both root and provenance for the narrowly authorized ownerless state; add a test where both incoming root and provenance change and assert the resulting pair is coherent.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 3

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 22be44246870caf59920e593976667c5a7fd7c9b`

## Summary

Mode: full
Delta range: `6b6d550353f6a0b18dd8be474fe762b1aa45fa99..22be44246870caf59920e593976667c5a7fd7c9b`
Focus issues: round-2 WARNING-1 plus provenance pair fill-NULL-only, cross-OS opaque roots, seeded lost-response recovery, one-node distillation, and bounded background session-log lookup
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 spec requirements and 6/6 M1 exit criteria covered |
| Correctness | 7/7 top-level spec scenarios covered; one adjacent recovery case remains incorrect |
| Coherence | Two blocking design/implementation deviations remain |

0 critical issue(s), 2 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / required boundary | Result | Evidence |
|---|---|---|
| Round-2 WARNING-1 / registration could split root and non-NULL provenance | closed | Existing profiles retain both the stored root and any non-NULL provenance at `src/IM/infra/gateway_persistence.py:166-195`; repository conflict handling only fills a NULL provenance at `src/IM/infra/repositories/agents.py:177-191`. A changed-root/changed-provenance re-registration retains the first pair at `tests/im_service/integration/test_gateway_im_registration.py:39-117`. |
| Cross-OS target roots must remain opaque outside the Gateway | closed | IM accepts and persists any non-blank Gateway root at `src/IM/api/routes/nodes.py:330-339` and `src/IM/application/config_service.py:303-316`; the create page forwards Windows syntax at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:563-580`. HTTP and component regressions are at `tests/im_service/contract/test_agent_create_immutability_contract.py:240-275` and `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx:152-172`. The stale design wording is separately reported as WARNING-2. |
| Lost `agent.created` recovery may claim only the matching ownerless registration seed | partially closed | The app create lock contains seed detection, Gateway dispatch, and claim at `src/IM/api/routes/nodes.py:265-293,365-393`; the repository claim atomically requires ownerless + same node/root/provenance and never updates the pair at `src/IM/infra/repositories/agents.py:229-290`. The seeded HTTP regression rejects changed literal root/name and accepts an exact canonical string at `tests/im_service/contract/test_agent_create_immutability_contract.py:278-348`. A valid non-canonical alias of that same root is still rejected; see WARNING-1. |
| Distillation must not combine transcript paths from different Gateway nodes | closed | Conversation list/sync returns `source_node_id` with the Gateway-resolved path at `src/IM/api/routes/web_im.py:182-196`; eligibility and selection require one source node at `src/IM/frontend/src/features/chat/components/distill-selection.ts:3-27` and `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:445-457,925-988`. HTTP projection and disabled-other-node UI coverage are at `tests/im_service/integration/test_users_conversations_api.py:10-91` and `src/IM/frontend/src/features/chat/components/conversation-sidebar.test.tsx:191-217`. |
| Session-log lookup must not block the Gateway receive owner and must bound filesystem scans | closed | Resolve frames schedule background tasks at `src/personal_assistant/ws/im_connection.py:1081-1092,1470-1482`; scans run through `asyncio.to_thread` under a four-slot semaphore at `src/personal_assistant/ws/im_connection.py:38-39,364-373,1484-1504`, and close cancels outstanding tasks at `src/personal_assistant/ws/im_connection.py:450-482`. `tests/unit/personal_assistant/test_gateway_session_log_resolution.py:17-107` proves a second resolve reaches the receive owner while the first scan is blocked. |

## Completeness

- Tasks: all 6 M1 exit criteria and all 6 round-2 correction checklist items have implementation and durable evidence.
- Spec coverage:
  - `创建 Agent 时可选择默认目录或自定义路径`: covered by the default/custom create UI, target-Gateway path authority, and structured HTTP/WS outcome.
  - `采用已有目录前须提醒用户`: covered by side-effect-free confirmation rejection and the explicit confirmed retry.
  - `同节点 workspace root 只可归属一个 Agent`: covered by canonical Gateway-local comparison; different Gateway configs do not share an ownership index.
  - `创建后 workspace root 固定`: covered by duplicate-ID serialization/insert-only storage, Gateway immutability, and the read-only detail page.
- Prototype / reference coverage: all four `must-match` rows remain projected into M1 exit criteria, code, repository-local desktop/mobile/confirmation screenshots, and `M1-workspace-creation/evidence/acceptance.md`.
- Independent validation at this snapshot:
  - Affected Python feature/contract/integration/unit owners: `179 passed, 8 warnings`.
  - Focused core seam subset: `71 passed, 8 warnings`.
  - Changed Python files Ruff: passed.
  - `PYTHON=.venv/bin/python scripts/docs-check`: passed (`225` maintained Markdown sources, `66` required routes).
  - `git diff --check a5e64e4f..HEAD`: passed.
  - The orchestrator-reported full non-E2E Python gate is `3052 passed, 24 deselected`; this verifier did not duplicate that complete run.
  - Frontend Vitest/build could not be independently rerun without writing a dependency link into this read-only worktree: it has no local `node_modules`, while the main checkout dependency tree is outside the worktree's normal module-resolution ancestry. The committed correction evidence records `69 passed` and a successful production build; this verifier inspected the relevant assertions directly.

## Correctness

| Requirement / Scenario | Implementation location | Permanent test / evidence | Status |
|---|---|---|---|
| Default directory creation | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388-396`; `src/personal_assistant/gateway/agent_config_sync.py:181-227` | Gateway create, HTTP success, default payload, and real-stack evidence | covered |
| New custom workspace under usable parent | `src/personal_assistant/gateway/agent_config_sync.py:181-243,377-432` | canonical custom-root unit test, HTTP/UI coverage, real-stack evidence | covered |
| Missing/unusable parent or non-directory target | `src/personal_assistant/gateway/agent_config_sync.py:377-426`; `src/IM/api/routes/nodes.py:321-328,424-449`; UI mapping at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:459-487` | producer plus four-code HTTP/no-write and UI/draft-preservation coverage | covered |
| Existing directory requires confirmation | `src/personal_assistant/gateway/agent_config_sync.py:427-432`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:825-845` | Gateway, HTTP/WS, UI retry, and real-stack evidence | covered |
| Same-node canonical root already assigned | `src/personal_assistant/gateway/agent_config_sync.py:212-218,370-375` | canonical symlink alias and owning-Agent UI coverage | covered |
| Same string root on different nodes | ownership reads only the active Gateway config at `src/personal_assistant/gateway/agent_config_sync.py:370-375` | independent-config unit test and dual-Gateway acceptance | covered |
| Existing Agent root visible and immutable | IM create serialization at `src/IM/api/routes/nodes.py:265-297`; repository insert/claim boundaries at `src/IM/infra/repositories/agents.py:229-352`; Gateway duplicate guard at `src/personal_assistant/gateway/agent_config_sync.py:194-210`; detail root is omitted from PATCH and disabled at `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1303-1316,1845-1858` | UI-shaped/concurrent duplicates, Gateway divergent roots, PATCH/detail, and real browser evidence | covered |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Existing directory uses an explicit second request with no first-request side effects | Yes | `src/personal_assistant/gateway/agent_config_sync.py:377-432`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:825-845` |
| Default delegates to the node and custom roots are interpreted only by the target node | Yes in implementation | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:388-396,563-580`; `src/personal_assistant/gateway/agent_config_sync.py:181-192`; stale local-validation prose remains in WARNING-2 |
| Same-node uniqueness uses canonical roots in Gateway-local config | Yes | `src/personal_assistant/gateway/agent_config_sync.py:212-218,370-375` |
| Parent/target validation precedes initialization and persistence | Yes | `src/personal_assistant/gateway/agent_config_sync.py:220-243,377-432` |
| Success alone creates the IM mirror and stable failures map to 409/422 | Yes | `src/IM/api/routes/nodes.py:312-328,394-421,424-449` |
| Root/provenance is an inseparable opaque mirror; registration fills provenance only when NULL | Yes | `src/IM/infra/gateway_persistence.py:145-195`; `src/IM/infra/repositories/agents.py:177-191` |
| A lost response is safely retriable only for the same canonical workspace decision | No for aliased custom input | Gateway canonicalizes it, but IM compares raw request text at `src/IM/api/routes/nodes.py:368-375`; see WARNING-1 |
| IM never dereferences Gateway-local transcript files | Yes | `src/IM/infra/repositories/conversations.py:635-657`; `src/IM/api/routes/web_im.py:182-196`; Gateway resolver at `src/personal_assistant/ws/im_connection.py:1484-1519` |
| Package dependency and cross-machine boundaries | Yes | IM communicates with `personal_assistant` only through HTTP/WS; no new prohibited cross-package imports are present in the unit diff |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Workspace card between Identity and Behavior | M1 worker/reviewer #1 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:646-852` | desktop default/custom screenshots | covered |
| Default/custom exclusive choice; default selected | M1 worker/reviewer #1/#2 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:343,750-794` | desktop and 390px screenshots | covered |
| Target-node copy, parent rule, and field errors | M1 worker/reviewer #2/#3 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:796-822`; stable error mapping at `:474-487` | custom/mobile screenshots and acceptance report | covered |
| Existing-directory warning, checkbox, and retry | M1 worker/reviewer #3/#4 | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:825-845` | existing-confirmation screenshot and acceptance report | covered |
| Colors, spacing, and controls may adapt to existing tokens | M1 visual evidence | `src/IM/frontend/src/styles/global.css` workspace selectors | desktop/390px screenshots | covered |

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — A lost-response retry for a valid custom-path alias cannot claim its matching canonical registration seed.** The target Gateway intentionally canonicalizes `..`, `~`, and symlink aliases before persistence (`src/personal_assistant/gateway/agent_config_sync.py:181-190`), and the ownerless seed and `agent.created` result therefore both contain canonical P. IM correctly proves that pair matches the seed, but then additionally requires the browser's raw `payload.workspace_root` string to equal canonical P (`src/IM/api/routes/nodes.py:368-375`). An independent HTTP + real `node.register` reproduction submitted `/x/staging/../seed-agent`, received canonical `/x/seed-agent` from the Gateway stub, and was rejected with 409 `agent_id already exists`. This leaves the lost-response recovery incomplete for a path form explicitly supported by the approved design. Remove the IM-host literal comparison and rely on the already-correlated Gateway result plus the atomic node/root/provenance seed claim, or have the Gateway return an opaque request identity that proves the retry; add a seeded HTTP regression using `..` or a symlink alias and assert the owner claim succeeds without changing the stored canonical pair.

- **WARNING-2 — The approved design still requires IM/frontend host absolute-path checks that the cross-OS correction correctly removed.** `docs/changes/feat-515-agent-workspace-root-selection/design.md:108-111` says a non-absolute custom input is an immediate local form error, and `docs/changes/feat-515-agent-workspace-root-selection/design.md:152-154` says IM applies an absolute-path format guard. The round-2 implementation instead treats any non-blank target root as opaque and delegates syntax to the selected Gateway (`src/IM/application/config_service.py:303-316`; `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:563-580`), which is necessary for Windows Gateway roots and matches the correction checklist. Amend those design statements to say only blank values are rejected outside the Gateway and that target-node validation decides absoluteness; retain the cross-OS HTTP/UI regressions so the documentation correction cannot reintroduce POSIX-only behavior.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 4

Validated at: `101f72f583729c5b90a6c824162b02135d0061c8`

## Summary

Mode: full
Delta range: `c5ec433576d6a24854dca243471dbda28c2cc6c2..101f72f583729c5b90a6c824162b02135d0061c8`
Focus issues: all Round 1-3 findings, especially registration-seed migration/exact claims, canonical aliases, bounded session-log resolution, draft-root classification, and design/delta/Runbook corrections
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 spec requirements and 6/6 M1 exit criteria implemented; one required permanent-test boundary remains incomplete |
| Correctness | 7/7 top-level spec scenarios implemented; one adjacent recovery/migration coverage gap remains |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / required boundary | Result | Evidence |
|---|---|---|
| Round-1 duplicate create/fixed-root violations | closed | The create lock, insert-only profile path, and Gateway same-root/provenance retry guard remain in place; duplicate/concurrency regressions passed. |
| Round-1 IM dereferenced Gateway-local transcripts | closed | IM delegates lookup to the owning Gateway; the resolver at `src/personal_assistant/ws/im_connection.py:1480-1587` passed its cross-machine owners. |
| Round-1 parent/target error coverage | closed | Four stable 422/no-write mappings and draft-preserving UI assertions remain present. |
| Round-2 split root/provenance refresh | closed | Register retains the root and non-NULL provenance and only fills NULL provenance. |
| Round-2 cross-OS opaque roots | closed | Browser/IM reject only blank custom values; revised design/delta and code delegate syntax to Gateway. |
| Round-2 canonical-alias seed recovery | closed in implementation | IM removed raw browser-text equality. The positive alias regression passes and the atomic claim matches the persisted decision; permanent negatives are incomplete under WARNING-1. |
| Round-2 one-node distillation | closed | Source-node projection and one-node-only selection remain covered. |
| Round-2/3 session-log bounds | closed | Fixed slots, per-key coalescing, 4.5-second expiry, and immediate overload null response are at `src/personal_assistant/ws/im_connection.py:1480-1562`; focused tests passed. |
| Round-3 draft-root classification | closed | Create no longer passes a draft root to `SkillSourceSelector`; see `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx:174-199`. |
| Round-3 design/delta and Runbook | closed | Opaque forwarding is documented and the second Gateway uses one isolated config-adjacent runtime directory. |

## Completeness and Correctness

- All M1 checkboxes, six exit criteria, four spec requirements, seven top-level scenarios, and five prototype/reference rows have implementation/evidence.
- Root immutability remains enforced at IM create, atomic profile insert/claim, Gateway local config, and the read-only detail UI. No prohibited import or IM-host workspace dereference appears in the diff.
- Independent validation:
  - focused registration/create/mirror/session-log/workspace matrix: `55 passed, 7 warnings`;
  - architecture contract suite: `148 passed`;
  - Ruff, docs check (`226` sources/`66` routes), and `git diff --check a5e64e4f..HEAD`: passed;
  - temporary legacy-schema probe restored the removed `registration_seed` column, retained owner/root/provenance, and assigned the legacy row marker `0`.
- This verifier did not rerun the complete Python or frontend suites. The detached worktree has no local frontend dependencies, so frontend source/tests were inspected without linking dependencies into it.

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Side-effect-free existing-directory check and confirmed retry | Yes | Gateway validates before initialization/persistence. |
| Custom input opaque outside target Gateway | Yes | Revised design/delta, Windows-root regression, and alias path agree. |
| Canonical Gateway-local uniqueness | Yes | No IM/global path index was introduced. |
| Inseparable root/provenance mirror | Yes | Register fills only NULL provenance; creation/claim never rewrites the pair independently. |
| One marked same-owner/node/root/provenance/display seed claim | Yes in implementation | API checks are at `src/IM/api/routes/nodes.py:287-397`; atomic conditions/clear are at `src/IM/infra/repositories/agents.py:232-309`. |
| Gateway-local bounded session-log work | Yes | `src/personal_assistant/ws/im_connection.py:1480-1587`. |

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — The durable registration-seed migration and exact claim boundary lack permanent negative regression coverage.** The upgrade adds `registration_seed INTEGER NOT NULL DEFAULT 0` at `src/IM/infra/db.py:661-664`, but no schema test removes/omits that column and proves an existing row upgrades with owner/root/provenance unchanged and a non-claimable marker; `tests/im_service/unit/test_repositories_schema.py:8-61` initializes the current schema first, so it never executes this `ALTER TABLE`. The HTTP contract at `tests/im_service/contract/test_agent_registration_seed_recovery.py:11-113` proves a positive same-owner alias claim and one-shot clearing, but its changed-root/name requests occur after the successful claim cleared the marker, and it never drives owner or provenance mismatch through a still-marked claim. The implementation and temporary probe behaved correctly, but M1 explicitly requires SQLite migration coverage. Add an old-schema migration test asserting marker `0` without owner/root/provenance changes, plus pre-claim negatives for wrong owner, canonical root, provenance, and Gateway display; each must return 409 and leave the row/marker unchanged, then retain the positive alias/one-shot case.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 5

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 91bf97d94a5c5c64a76a9c993aebdc3a5041a23d`

## Summary

Mode: full
Delta range: `bb9cb43e0457c9c67beb1eed7e81da607b988634..91bf97d94a5c5c64a76a9c993aebdc3a5041a23d`
Focus issues: Round-4 WARNING-1 plus durable operation correlation, all negative claims, transcript state/one-node selection, remote-filesystem ownership, and cancellation/overload semantics
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 requirements and 6/6 M1 exit criteria implemented; one permanent recovery-test boundary remains incomplete |
| Correctness | 7/7 top-level scenarios implemented; exact-operation negative coverage is incomplete |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / boundary | Result | Evidence |
|---|---|---|
| Round-4 legacy-schema migration | closed | `tests/im_service/unit/test_db_init.py:65-128` runs the real migration and preserves owner/node/root/provenance/profile version while adding non-claimable markers. |
| Arbitrary registration | closed | A registration marker requires an existing IM reservation for the same node/Agent (`src/IM/infra/gateway_persistence.py:201-210`); `tests/im_service/contract/test_agent_registration_seed_recovery.py:63-91` rejects an arbitrary advertisement. |
| Wrong owner/root/provenance/display and completed operation | closed | Pending detection and atomic claim require owner/node/Agent/operation and the stored root/provenance pair (`src/IM/infra/repositories/agents.py:299-419`); pre-claim negatives and one-shot retirement pass at `tests/im_service/contract/test_agent_registration_seed_recovery.py:94-231`. |
| Profile PATCH | closed in implementation | Normal update clears the pending marker at `src/IM/infra/repositories/agents.py:582-615`; repository coverage is `tests/im_service/unit/test_repositories_agent_profile.py:288-331`. |
| Durable reconnect recovery | closed | Gateway persists/advertises the operation (`src/personal_assistant/gateway/agent_config_sync.py:296-343`; `src/personal_assistant/reporter/upstream_reporter.py:250-262`); real HTTP/WS reconnect succeeds once at `tests/im_service/contract/test_agent_registration_seed_recovery.py:234-308`. |
| Transcript states and one-node selection | closed | IM projects owning node/path/status (`src/IM/api/routes/web_im.py:177-202`); selection and submission retain one node (`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:445-457,925-988`), and `unavailable` differs from `missing` (`src/IM/frontend/src/features/chat/components/distill-selection.ts:13-26`). |
| No remote filesystem dereference in IM | closed | Exact path derivation/file existence lives only on Gateway at `src/personal_assistant/gateway/session_binder.py:897-930`; IM routes the opaque result. |
| Cancellation/overload | closed | Per-key coalescing, independent pending lookups without capacity false-negatives, close cancellation, and `unavailable` provider failure are covered by `src/personal_assistant/ws/im_connection.py:375-378,481-486,1475-1523` and `tests/unit/personal_assistant/test_gateway_session_log_resolution.py:34-155`. |

## Completeness and Correctness

- All six exit criteria, five roadpoints, four requirements, seven scenarios, and five prototype/reference rows have implementation and evidence. Round-4's claim that every negative operation boundary has permanent coverage remains incomplete under WARNING-1.
- The create flow still covers default/custom roots, parent/target failures, explicit existing-directory confirmation, canonical same-node uniqueness, cross-node independence, opaque root/provenance mirroring, and fixed roots.
- Durable create recovery is implemented as an IM SQLite reservation/fingerprint (`src/IM/api/routes/nodes.py:302-343`), Gateway YAML operation (`src/personal_assistant/gateway/agent_config_sync.py:181-220,296-343`), operation-correlated registration, atomic claim, and retirement (`src/IM/infra/repositories/agents.py:234-431`).
- Independent validation: recovery/migration/profile/session matrix `98 passed, 2 warnings`; create/mirror/reconnect/transcript matrix `45 passed, 7 warnings`; architecture contracts `148 passed`; changed-file Ruff passed; docs check passed (`227` sources / `66` routes); `git diff --check a5e64e4f..HEAD` passed.
- The committed correction evidence records full non-E2E Python `3060 passed, 24 deselected`, focused frontend `60 passed`, and a successful production build. This detached worktree has no frontend dependencies, so Vitest/build were inspected but not independently rerun.

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Side-effect-free existing-directory check and confirmed retry | Yes | Gateway validates before initialization/persistence. |
| Custom input opaque outside target Gateway | Yes | Browser/IM reject only blank input; Gateway resolves/canonicalizes it. |
| Canonical Gateway-local uniqueness and immutable root | Yes | No IM-global root index or root-update path was introduced. |
| Inseparable opaque root/provenance mirror | Yes | Registration fills only NULL provenance; IM does not resolve non-empty Gateway roots. |
| Only one request-correlated durable operation may recover | Yes in implementation | Reservation, YAML echo, pending registration, atomic claim, and retirement form one persisted chain. |
| Exact-binding transcript lookup is Gateway-local, coalesced, cancellable, and status-bearing | Yes | No recursive scan or IM-host file read remains. |
| Package/deployment boundaries | Yes | HTTP/WS remains the IM↔Gateway boundary; architecture contracts passed. |

### Prototype / Reference Contract

All four `must-match` rows (card order, mode choice, target-node/path error presentation, existing-directory confirmation) and the one `may-adapt` token/layout row remain covered by the implementation, repository-local desktop/390px screenshots, and acceptance evidence.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — The exact create-operation contract still lacks permanent tests for a different HTTP request and a wrong echoed operation while the pending marker is live.** The implementation fingerprints the effective outbound payload and rejects a non-matching retry before dispatch (`src/IM/api/routes/nodes.py:302-342`), and rejects an otherwise matching result whose `create_operation_id` differs (`src/IM/api/routes/nodes.py:400-410`). But `tests/im_service/contract/test_agent_registration_seed_recovery.py:94-231` always retries the original HTTP payload and always echoes the operation received from IM; the wrong-operation Gateway unit at `tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py:68-104` does not exercise IM pending-profile claim. Extend the HTTP contract before its positive claim with (1) a changed effective request field that returns 409 without Gateway dispatch and leaves the operation/profile marker unchanged, and (2) a same-root/provenance/display response carrying another operation id with the same unchanged-state assertions. Retain the positive reconnect and one-shot checks.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 6

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 85d4f98948526b3316344e515c74ffc0e41408ec`

## Summary

Mode: full
Delta range: `2bd4af837e232ec2c6b1978968df9e4d82a4caf1..85d4f98948526b3316344e515c74ffc0e41408ec`
Focus issues: Round-5 WARNING-1; Gateway no-ID/different-ID replay rejection; absent/unroutable source projection; exact pending-operation HTTP negatives; all prior issue closures
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 original requirements and 6/6 M1 exit criteria implemented; one required permanent recovery assertion remains incomplete |
| Correctness | 7/7 original top-level scenarios implemented; the exact rejected-recovery state contract is not fully protected |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / boundary | Result | Evidence |
|---|---|---|
| Round-1 duplicate create and fixed-root violations | closed | Authenticated-owner create serialization, insert/claim boundaries, Gateway-local immutability, and duplicate/concurrent regressions remain present and passed. |
| Round-1 remote workspace dereference and parent/target HTTP/UI coverage | closed | IM routes transcript and workspace RPCs to Gateway; four stable 422/no-write paths and draft-preserving UI owners remain present. |
| Round-2 root/provenance split, opaque cross-OS roots, canonical aliases, and one-node distillation | closed | Register remains fill-NULL-only, nonblank roots stay opaque outside Gateway, alias recovery passes, and source-node selection remains enforced. |
| Round-3 registration marker, transcript bounds, draft-root classification, and design/delta/Runbook coherence | closed | Durable operation correlation replaced the generic marker; exact binding lookup is Gateway-local/cancellable/status-bearing; documentation and selector behavior remain aligned. |
| Round-4 migration and operation-correlated recovery negatives | closed in implementation | Migration, arbitrary/prehosted registration, wrong owner/root/provenance/display, PATCH, reconnect, one-shot retirement, and transcript status/cancellation owners all passed. |
| Round-5 Gateway no-ID/different-ID replay | closed | Existing Gateway Agents replay only when the incoming operation is nonempty and exactly equals the persisted operation (`src/personal_assistant/gateway/agent_config_sync.py:181-218`). Permanent no-ID legacy, missing-ID persisted-operation, and different-ID regressions are in `tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py:43-112`. |
| Round-5 absent/null-node Agent source | closed | IM projects `source_jsonl_status="unavailable"` without invoking Gateway resolution (`src/IM/api/routes/web_im.py:177-202`), and UI status precedence is enforced at `src/IM/frontend/src/features/chat/components/distill-selection.ts:13-26`; Python and sidebar owners cover absent and null-node cases. |
| Round-5 exact HTTP pending-operation negatives | partially closed | A changed effective request is rejected before dispatch and a wrong echoed operation is rejected before claim; both immediate snapshots preserve the operation row and the root/provenance/pending-id subset. The required exact profile-state assertion remains incomplete under WARNING-1. |

## Completeness and Correctness

- All six M1 exit criteria, five roadpoints, four original requirements, seven original top-level scenarios, and all five prototype/reference rows still have implementation and durable evidence.
- Gateway default/custom creation, parent and target failures, existing-directory confirmation, canonical node-local uniqueness, cross-node independence, immutable root/provenance mirroring, and read-only existing-Agent UX remain covered.
- Durable recovery remains a single IM-reserved request fingerprint, Gateway-persisted and echoed operation, operation-correlated registration marker, atomic immutable-result claim, and one-shot retirement (`src/IM/api/routes/nodes.py:277-457`; `src/IM/infra/repositories/agents.py:234-431`).
- Transcript resolution remains Gateway-local and distinguishes `ready`, `missing`, and `unavailable`; absent or unroutable Agent profiles now use the temporary-unavailable projection rather than the permanent missing state.
- Independent validation:
  - expanded Gateway/IM/create/recovery/transcript/architecture matrix: `285 passed, 8 warnings`;
  - full non-E2E Python suite: `3062 passed, 24 deselected, 22 warnings`;
  - changed Python Ruff, `git diff --check a5e64e4f..HEAD`, and docs check (`228` maintained sources / `66` required routes): passed.
- This detached verifier worktree has no frontend dependency tree, so Vitest/build were source-inspected rather than independently rerun. The committed Round-5 evidence records full frontend/build success and a real isolated unavailable-source browser journey.

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Side-effect-free existing-directory check and confirmed retry | Yes | Gateway validates before initialization and persistence. |
| Custom input remains opaque outside the target Gateway | Yes | Browser/IM reject only blank input; Gateway alone resolves and canonicalizes it. |
| Canonical Gateway-local uniqueness and immutable workspace root | Yes | No IM-global root index or root-update path exists. |
| Root/provenance is an inseparable opaque mirror | Yes | Registration fills only NULL provenance and IM does not resolve nonempty Gateway roots. |
| Only the exact persisted create operation may replay or recover | Yes in implementation | Gateway rejects absent/different operation ids; IM fingerprints the effective request and verifies the echoed operation before atomic claim. |
| Transcript lookup is Gateway-local, exact-binding, cancellable, and status-bearing | Yes | IM holds only routing/projection responsibility and unavailable state is not collapsed into missing. |
| Package and deployment boundaries | Yes | IM and Gateway communicate only over HTTP/WS; architecture contracts passed. |

### Prototype / Reference Contract

All four `must-match` rows (card order, default/custom mode, target-node/path error presentation, and existing-directory confirmation) plus the one `may-adapt` layout row remain covered by implementation, repository-local desktop/390px screenshots, and acceptance evidence.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — The new pending-operation HTTP negatives do not assert that the complete profile and operation records remain unchanged.** The current spec requires invalid recovery attempts to leave owner, root, provenance, and display fields unchanged (`docs/specs/im/agents-nodes.md:177-180`), and the approved recovery decision additionally binds node, operation, and immutable display identity. However, `pending_state`, `state_after_different_request`, and `state_after_wrong_operation` select only `workspace_root`, `workspace_is_default`, and `pending_create_operation_id` from the profile and omit `created_at` from the operation (`tests/im_service/contract/test_agent_registration_seed_recovery.py:115-188`). A regression that writes display/description/config fields, bumps profile metadata, or rewrites an omitted operation column before returning 409 can therefore pass these immediate equality assertions; later requests and the successful claim can overwrite or mask that mutation. Snapshot the complete `agent_profiles` and `agent_create_operations` rows before the two negatives and compare the complete rows immediately after each rejection (or explicitly include every immutable/profile-version/timestamp column). Retain the no-dispatch assertion for the different request, the wrong-operation Gateway response, and the subsequent valid one-shot claim.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 7

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 2bbaa6e77887dce9a17d7e1a29c3461e5df8da8d`

## Summary

Mode: full
Delta range: `b6ffab941bb7c420b58916c45cafe854a7bca764..2bbaa6e77887dce9a17d7e1a29c3461e5df8da8d`
Focus issues: Round-6 WARNING-1; synchronous Gateway receive-path filesystem work; transcript `ready` / `missing` / `unavailable`; selection purge and one-node stability; complete durable-row negative assertions; all prior closures
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 original requirements and 6/6 M1 exit criteria remain implemented; 1 added transcript non-blocking requirement is incomplete |
| Correctness | 7/7 original top-level scenarios remain correct; 1/3 Round-6 correction boundaries is not correct in production composition |
| Coherence | One blocking deviation from the approved async Gateway design |

1 critical issue(s), 0 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / requested boundary | Result | Evidence |
|---|---|---|
| Round-6 WARNING-1 / complete profile and operation snapshots | closed | `_pending_rows()` selects every column from both durable tables (`tests/im_service/contract/test_agent_registration_seed_recovery.py:63-79`), and both the divergent-request and wrong-operation paths compare their immediate complete snapshots with the pre-rejection state (`tests/im_service/contract/test_agent_registration_seed_recovery.py:134-164,258-263`). |
| Transcript status semantics | closed | A durable binding projects the exact address without probing the JSONL (`src/personal_assistant/gateway/session_binder.py:897-931`); the resolution owner maps a nonempty projection to `ready`, no binding to `missing`, and provider failure to `unavailable` (`src/personal_assistant/ws/im_connection.py:1492-1523`). IM preserves those states (`src/IM/api/routes/web_im.py:177-201`), and the selector gives `unavailable` its distinct message before missing checks (`src/IM/frontend/src/features/chat/components/distill-selection.ts:13-26`). |
| Ineligible selection purge and no cross-node switch | closed | The query-data effect removes every selected id that is no longer eligible (`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:311-322`); selected rows are then restricted to the first selected node (`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:459-471`). The refresh regression proves unavailable A is purged, B can be selected, and a later ready/reordered A stays disabled while B stays checked (`src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx:536-587`). |
| No synchronous filesystem work in the Gateway receive flow | still open | The removed `Path.is_file()` / `Path.resolve()` calls do not eliminate the production synchronous SQLite read. See CRITICAL-1. |
| Rounds 1-5 implementation closures | closed | Authenticated serialized creation, immutable Agent id/root, node-local canonical ownership, opaque IM root/provenance, exact durable operation recovery, negative claim guards, legacy migration, and unavailable-source projection remain present and passed their permanent owner suites. |

## Completeness

- Tasks: the six original M1 exit criteria and the Round-6 selection/snapshot corrections are implemented. The new task claiming that durable transcript projection cannot stall Gateway control handling is contradicted by production composition and is incomplete under CRITICAL-1.
- Original spec coverage remains complete:
  - default/custom creation and node-side validation are implemented at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:343-396` and `src/personal_assistant/gateway/agent_config_sync.py:181-248,383-447`;
  - existing-directory confirmation and typed errors remain mapped at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468-485`;
  - canonical same-node uniqueness remains enforced at `src/personal_assistant/gateway/agent_config_sync.py:203-225`;
  - immutable creation/recovery remains serialized at `src/IM/api/routes/nodes.py:266-430` and persisted through the repository claim/create boundaries at `src/IM/infra/repositories/agents.py:234-431`.
- Prototype/reference coverage remains unchanged and complete: the four `must-match` rows and one adaptive layout row still have code, repository-local desktop/mobile screenshots, and durable browser evidence under `M1-workspace-creation/evidence/`.
- Independent validation at this snapshot:
  - focused transcript/recovery owner suite: `35 passed, 2 warnings`;
  - architecture/create/mirror seam: `19 passed, 5 warnings`;
  - full non-E2E Python: `3063 passed, 24 deselected, 22 warnings`;
  - changed Python Ruff: passed;
  - `scripts/docs-check`: passed (`229` maintained Markdown sources, `66` required routes);
  - `git diff --check a5e64e4f..HEAD`: passed.
- This detached verifier worktree has no frontend dependency tree. Targeted frontend behavior was source-inspected; the committed Round-6 evidence records `49 passed`, full frontend/build success, and isolated Chromium acceptance.

## Correctness

| Requirement / Scenario | Implementation and test evidence | Status |
|---|---|---|
| Default directory creation | Default mode emits no custom root (`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:343-396`); Gateway default factory/persistence owners passed. | covered |
| New custom root below a usable parent | Node-local validation and initialization remain at `src/personal_assistant/gateway/agent_config_sync.py:383-447`; Gateway and HTTP owners passed. | covered |
| Missing/unusable parent or invalid target | Stable producer codes at `src/personal_assistant/gateway/agent_config_sync.py:400-436` map to localized field errors at `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:475-485`; permanent HTTP/UI coverage remains. | covered |
| Existing directory requires explicit confirmation | First rejection and confirmation retry remain at `src/personal_assistant/gateway/agent_config_sync.py:436-447` and `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:468-485`. | covered |
| Same-node root uniqueness and cross-node independence | Ownership checks only the target Gateway config (`src/personal_assistant/gateway/agent_config_sync.py:203-225`); canonical alias and independent-node owners remain. | covered |
| Created root remains visible and immutable | The detail root remains read-only (`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1856`); IM/Gateway duplicate and claim boundaries passed. | covered |
| Exact-operation lost-response recovery | Reservation, echoed operation, atomic claim, retirement, and complete negative snapshots remain covered at `src/IM/api/routes/nodes.py:307-430` and `tests/im_service/contract/test_agent_registration_seed_recovery.py:113-286`. | covered |
| Binding projection returns `ready` / `missing` / `unavailable` accurately | Projection and status mapping at `src/personal_assistant/gateway/session_binder.py:897-931` and `src/personal_assistant/ws/im_connection.py:1492-1523` match the delta contract. | covered |
| Slow/unavailable durable binding lookup does not block Gateway control frames | Production uses SQLite-backed bindings (`src/personal_assistant/gateway/composition.py:242-253`); the lookup synchronously executes SQLite on the event loop (`src/personal_assistant/gateway/session_keys.py:695-736`). The current fake-provider test does not exercise this seam. | missing implementation and test; CRITICAL-1 |
| Ineligible source purge and one-node selection | Effect, node filter, and refresh regression at `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:311-322,459-471` and `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx:536-587`. | covered |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Side-effect-free existing-directory check and confirmed retry | Yes | Gateway validation precedes initialization and persistence. |
| Custom roots are interpreted only on the target Gateway | Yes | Browser/IM treat the input as opaque; Gateway alone resolves it. |
| Canonical node-local uniqueness and immutable root/provenance | Yes | No IM-global root index or root-update path was introduced. |
| Only the exact persisted create operation may recover | Yes | Request fingerprint, operation echo, pending claim, and retirement remain a single durable chain. |
| Transcript status distinguishes ready, missing, and unavailable | Yes | Binding-derived address and explicit wire status are preserved end to end. |
| Transcript binding lookup is cancellable and cannot stall Gateway receive/control handling | No | `asyncio.create_task()` moves ownership out of `_listen_once`, but its synchronous provider still performs the production SQLite lookup on the same event-loop thread. Cancellation cannot preempt that call. |
| Package and deployment boundaries | Yes | IM and Gateway communicate over HTTP/WS; architecture seam tests passed. |

### Prototype / Reference Contract

All four `must-match` rows (card order, default/custom mode, target-node/path-error presentation, and existing-directory confirmation) plus the adaptive layout row remain covered by implementation, repository-local desktop/390px screenshots, and acceptance evidence.

## Issues

### CRITICAL (must fix before PR)

- **CRITICAL-1 — The production durable-binding projection still performs synchronous SQLite filesystem I/O on the Gateway event loop, so a slow binding read can stall later control frames.** The runtime composes `GatewaySessionBinder` with `PersistentSessionBindingStore` (`src/personal_assistant/gateway/composition.py:242-253`). A `session.log.resolve` schedules `_resolve_session_log()` (`src/personal_assistant/ws/im_connection.py:1475-1490`), but that coroutine immediately calls the synchronous provider before its first await (`src/personal_assistant/ws/im_connection.py:1492-1504`). The provider calls `capture_binding_provenance()` (`src/personal_assistant/gateway/session_binder.py:912-920`), which calls repository `get()` under its lock (`src/personal_assistant/gateway/session_binder.py:661-675`); the production `get()` executes SQLite synchronously (`src/personal_assistant/gateway/session_keys.py:695-736`). `asyncio.create_task()` therefore does not move the I/O off the event-loop thread, and cancelling the task cannot interrupt a blocked SQLite call. The new control-progress regression uses an immediate in-memory fake that raises before any await (`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py:301-369`), so it stays green even if the production seam blocks. Make the production binding capture non-blocking (for example, expose an async projection that offloads the persistent read away from the receive event loop, or maintain an authoritative in-memory binding snapshot), then add a regression around the real production composition/store whose binding read is held until after a heartbeat/control frame is observed; also assert close cancellation does not wait on that held read.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 8

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 891aa54fd3a0ed68e1060552a4122d3dc3659151`

## Summary

Mode: full
Delta range: `657a39c55..891aa54fd`
Focus issues: Round-7 CRITICAL-1; copy-on-write startup hydration; receive/close independence from a held persistent lookup; projection consistency after every durable binding transition; all prior closures
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 original requirements and 6/6 M1 exit criteria remain implemented; 1 added transcript projection transition is incomplete |
| Correctness | 7/7 original top-level scenarios remain correct; the Round-7 event-loop blocker is closed, but one durable-write path returns stale `missing` state |
| Coherence | One blocking deviation from the approved copy-on-write consistency design |

1 critical issue(s), 0 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Prior issue / requested boundary | Result | Evidence |
|---|---|---|
| Round-7 CRITICAL-1 / production SQLite lookup could block Gateway receive and close | closed | `GatewaySessionBinder` hydrates persistent rows before the receiver exists and publishes immutable mapping replacements (`src/personal_assistant/gateway/session_binder.py:249-263,764-778`); the provider reads only that projection (`src/personal_assistant/gateway/session_binder.py:935-965`). The real `PersistentSessionBindingStore` regression holds `get()` in another thread while heartbeat and `close()` complete and the prewarmed binding still resolves `ready` (`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py:305-425`). |
| Round-6 complete durable-row negative assertions | closed | The complete pending profile/operation snapshots and immediate rejected-state comparisons remain present and passed in the full non-E2E suite. |
| Rounds 1-5 implementation closures | closed | Authenticated serialized creation, immutable Agent id/root, node-local canonical ownership, opaque root/provenance mirroring, exact durable-operation recovery, negative claim guards, migration, and unavailable-source projection remain present; their permanent owners passed in the full non-E2E suite. |
| Original workspace-root user contract | unchanged and closed | The Round-7 delta changes only binder projection code, its Gateway delta/design, and focused tests/evidence. Default/custom creation, existing-directory confirmation, same-node uniqueness, and immutable detail behavior were not changed; the full non-E2E suite passed. |

## Completeness

- The original four workspace-root requirements, seven user scenarios, six M1 exit criteria, and prototype/reference contract remain implemented and unchanged by this internal delta.
- Startup hydration, lock-free projection reads, and the real persistent-store receive/close regression close the exact Round-7 production-composition blocker.
- The approved design and Gateway delta additionally require every later durable binding update to publish the affected projection entry (`docs/changes/feat-515-agent-workspace-root-selection/design.md:255-264`; `docs/changes/feat-515-agent-workspace-root-selection/specs/gateway/service-lifecycle.md:61-83`). The semantic conversation bind path persists a row without publishing it; therefore that added requirement is incomplete under CRITICAL-1.
- Independent validation:
  - binder/IM/persistent-store/session-fork focused suite: `61 passed, 2 warnings`;
  - full non-E2E Python suite: `3063 passed, 24 deselected, 22 warnings`;
  - changed-file Ruff: passed;
  - `scripts/docs-check`: passed (`230` maintained Markdown sources, `66` required routes);
  - `git diff --check a5e64e4f..HEAD` and `git diff --check 657a39c55..HEAD`: passed before this report.
- This delta does not modify frontend sources, so no additional browser or frontend rerun was required to determine its internal projection verdict.

## Correctness

| Requirement / Scenario | Implementation and test evidence | Status |
|---|---|---|
| Default/custom workspace creation, parent validation, existing-directory confirmation, same-node uniqueness, and immutable root display | No production path for the original user contract changed in `657a39c55..891aa54fd`; all permanent Python owners passed. | covered |
| Startup-hydrated projection avoids binder lock and SQLite on `session.log.resolve` | Construction hydrates `bindings_for_agent()` before IM receive (`src/personal_assistant/gateway/session_binder.py:249-263`); reads use `capture_session_log_projection()` (`src/personal_assistant/gateway/session_binder.py:702-715,950-965`). | covered |
| Held production persistence lookup does not block heartbeat or close | Persistent-store regression holds `get()` at `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py:305-343`, then proves heartbeat and close finish before release at `:385-425`. | covered |
| Every later durable binding update publishes the exact projection | Ordinary resolve, reset publication, and runtime update paths call `_record_provenance()` (`src/personal_assistant/gateway/session_binder.py:297-328,391-428,501-566`). `bind_conversation()` instead writes the durable row and updates three legacy maps only (`src/personal_assistant/gateway/session_binder.py:613-651`), leaving `_session_log_projections` unchanged. | missing implementation and test; CRITICAL-1 |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Hydrate committed bindings before IM receive starts | Yes | Binder construction reads `bindings_for_agent()` and records each row before composition creates the IM connection. |
| Session-log receive/close never waits on binder lock or SQLite | Yes | Provider uses the immutable projection; the held persistent-lookup regression proves control and close progress. |
| Every later durable binding write replaces the affected projection entry | No | `bind_conversation()` persists a canonical conversation binding without calling `_record_provenance()` or otherwise replacing the projection entry. |
| Original workspace-root architecture and user contract | Yes | The delta remains inside Gateway binder projection and does not alter cross-package dependencies or workspace creation behavior. |

### Prototype / Reference Contract

The four workspace-create `must-match` rows and one adaptive layout row are unchanged by this internal Gateway delta; prior repository-local browser evidence remains applicable.

## Issues

### CRITICAL (must fix before PR)

- **CRITICAL-1 — `bind_conversation()` commits a durable conversation binding without publishing its copy-on-write transcript projection, so a newly forked/semantic conversation is falsely reported as `missing` until another update or Gateway restart.** The approved design says every later durable binding write replaces the affected projection entry (`docs/changes/feat-515-agent-workspace-root-selection/design.md:255-264`), and the Gateway delta requires publishing a new entry after every durable binding update (`docs/changes/feat-515-agent-workspace-root-selection/specs/gateway/service-lifecycle.md:61-83`). The ordinary resolve, reset, and runtime-write paths converge on `_record_provenance()` (`src/personal_assistant/gateway/session_binder.py:297-328,391-428,501-566`), but `bind_conversation()` directly calls repository `bind()` and updates `_binding_revisions`, `_binding_agents`, and `_session_agents` without updating `_session_log_projections` (`src/personal_assistant/gateway/session_binder.py:613-651`). Independent reproduction in this snapshot produced `bind_status=bound`, a present durable row from `binder.lookup()`, and `projected_log_path=None`. Route the successful semantic bind through the same projection publication helper after the durable write, and add a permanent regression that constructs the binder before the bind, calls `bind_conversation()`, and immediately asserts `build_session_log_path_provider()` returns the new kernel session's exact JSONL address; include rebinding the same conversation to a second kernel session so copy-on-write replacement, not only insertion, is protected.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 9

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 4ad4a02d653ef5fe2b885524d6bb3f7810758db4`

## Summary

Mode: targeted-closure
Delta range: `a3ac7d5fc..4ad4a02d6`
Focus issues: Round-8 CRITICAL-1; persistence-before-publication, immediate fork projection, error atomicity/no stale projection, and unchanged original workspace contract
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | Round-8 implementation gap closed; 4/4 original requirements and 6/6 M1 exit criteria remain implemented |
| Correctness | Focus behavior is correct; replacement/error atomicity lack permanent provider-seam coverage |
| Coherence | Followed |

0 critical issue(s), 1 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Boundary | Result | Evidence |
|---|---|---|
| Round-8 CRITICAL-1 / successful semantic bind omitted COW publication | closed in implementation | Durable `bind()` precedes `_record_provenance(..., persist_binding=True)` at `src/personal_assistant/gateway/session_binder.py:625-650`; the helper replaces the immutable-map entry at `:763-777`. |
| Immediate provider result on the fork path | closed | The binder exists before the fork, then the permanent regression immediately observes the exact fork-session JSONL path at `tests/unit/personal_assistant/test_session_fork_handler.py:67-116`. |
| Error atomicity / no stale projection | correct; permanent coverage incomplete | Stale guards exit before persistence/publication at `src/personal_assistant/gateway/session_binder.py:625-631`; repository exceptions occur before publication at `:632-645`. An independent read-only probe proved insertion, same-key A→B replacement, and an injected C persistence failure retaining durable/projection B. Existing error/race tests assert no durable destination at `tests/unit/personal_assistant/test_session_fork_handler.py:190-240,243-319`, but not the provider; see WARNING-1. |
| Original workspace-root contract | unchanged | The delta changes one internal Gateway binder call plus focused test/docs/evidence; no IM/frontend/create/ownership/root implementation changed, and the full non-E2E suite passed. |

## Completeness

- The missing semantic-bind publisher is present and converges on the established COW publisher.
- Original default/custom selection, target-node validation, existing-directory confirmation, same-node uniqueness, immutable-root display, and opaque cross-machine root behavior are untouched.
- Evidence: focused owners `46 passed, 2 warnings`; independent insertion/rebind/failure probe passed; full non-E2E Python `3063 passed, 24 deselected, 22 warnings`; changed-file Ruff passed; docs-check passed (`231` maintained sources, `66` routes); delta `git diff --check` passed.

## Correctness

| Requirement / Scenario | Evidence | Status |
|---|---|---|
| Publish only after successful durable bind | `src/personal_assistant/gateway/session_binder.py:632-645` | covered implementation; WARNING-1 test gap |
| Successful fork immediately resolves its exact JSONL address | `src/personal_assistant/gateway/session_binder.py:1029-1048,934-968`; `tests/unit/personal_assistant/test_session_fork_handler.py:67-116` | covered |
| Same-conversation rebind replaces the old projection | map replacement at `src/personal_assistant/gateway/session_binder.py:763-777`; independent A→B probe | covered implementation; WARNING-1 test gap |
| Kernel/stale/persistence errors publish no destination or stale projection | exits at `src/personal_assistant/gateway/session_binder.py:625-645,1021-1043`; durable-store tests and independent failure probe | covered implementation; WARNING-1 provider gap |
| Original workspace-root scenarios | no original-contract production path changed; full suite green | covered / unchanged |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Every successful durable binding update replaces the affected projection | Yes | `bind_conversation()` converges on `_record_provenance()` at `src/personal_assistant/gateway/session_binder.py:632-645`. |
| Receive reads remain lock-free and SQLite-free | Yes | Provider reads only the immutable projection at `src/personal_assistant/gateway/session_binder.py:934-968`. |
| Original package/deployment/workspace boundaries | Yes | Production delta is confined to the Gateway binder. |

### Prototype / Reference Contract

Unchanged; prior repository-local workspace-create browser evidence remains applicable.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — Permanent coverage proves first insertion only, not COW replacement or persistence-failure atomicity at the provider seam.** The new assertion at `tests/unit/personal_assistant/test_session_fork_handler.py:67-116` observes only absent→present; error/race owners at `:190-240,243-319` never query the provider. Add one lowest-layer regression in `tests/unit/personal_assistant/test_gateway_session_binder.py` that binds the same conversation to session A and asserts provider A, rebinds to B and asserts provider B, then injects a repository `bind()` failure for C and asserts both durable row and provider remain B. Add provider-absence assertions to fork failure owners only if needed for their distinct handler wiring; do not duplicate binder state-transition coverage.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for targeted-closure verification.

# Round 12

> Validation snapshot: `ff665108fd61d19c5af7b9c39bd61566c67b43c8 -> 9dd0d2dadfba1bb99aa7f9c905542cade9e4c43f`

## Summary

Mode: targeted-closure
Delta range: `ff665108f..9dd0d2dad`
Focus issues: Round-11 CRITICAL-1 — invalid model or reasoning input must not create or initialize a default or custom workspace
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | The two create paths now validate candidate model/reasoning before their respective workspace setup; the Round-11 missing boundary is closed. |
| Correctness | Direct and durable create reject invalid model/reasoning before default/custom initialization; rejected operations are stable and cannot be repurposed. |
| Coherence | Followed: the Gateway remains the sole node-local filesystem authority, and the fix adds no IM-side path handling or new cross-package dependency. |

0 critical issue(s), 0 warning(s) found. All checks passed. Ready for PR.

## Prior-Issue Closure

| Boundary | Result | Evidence |
|---|---|---|
| Direct `agent.create` must reject invalid model/reasoning before default or custom workspace initialization | closed | `IMAgentConfigSync._handle_agent_create()` normalizes and validates the pair at `src/personal_assistant/gateway/agent_config_sync.py:318-325`, before either default `ensure_workspace_defaults()` at `:327-334` or custom preparation/initialization at `:335-349`. The permanent custom-root regression is `tests/unit/personal_assistant/test_gateway_workspace_creation.py:124-143`; an isolated probe covered both direct default/invalid-model and direct custom/invalid-reasoning cases. |
| Durable create operation must establish a terminal rejected receipt without resolving/initializing a target when its model/reasoning is invalid | closed | `handle_agent_config_operation()` validates at `src/personal_assistant/gateway/agent_config_sync.py:511-542` before `_resolve_operation_workspace()` at `:543-548`, whose default/custom mutation points are at `:663-690`. The persistent custom-root regression is `tests/unit/personal_assistant/test_gateway_config_operation_validation.py:86-137`; the isolated probe covers default and custom targets plus invalid model and invalid reasoning. |
| Rejected operation remains idempotent and its id cannot name a changed intent | closed | `ConfigApplyReceiptStore.prepare()` rejects a different `(kind, fingerprint, expected state)` for the same ID at `src/personal_assistant/gateway/config_apply_receipts.py:78-102`; terminal rejects are returned unchanged by `finish()` at `:104-131`. `tests/unit/personal_assistant/test_gateway_config_operation_validation.py:31-83` covers reuse after invalid reasoning, and the isolated custom-root probe verifies exact retry remains `invalid_agent_config`, changed intent is `operation_id_reused`, and the durable receipt remains rejected. |
| An existing approved user directory remains protected by the confirmation boundary and retains user content | remains correct | `_prepare_custom_workspace()` remains before initialization only for a valid candidate (`src/personal_assistant/gateway/agent_config_sync.py:673-690`); `tests/unit/personal_assistant/test_gateway_workspace_creation.py:199-235` preserves `README.md` through confirmation. The isolated probe repeated the valid-confirm path and verified user content intact before and after initialization. |

## Completeness

- Round 11 identified one incomplete failure ordering. The P1 delta moves the direct create validation ahead of the two workspace branches and establishes the same ordering in the durable create operation before `_resolve_operation_workspace()`.
- The delta does not change the approved Workspace Root UI, root ownership/immutability, confirmation copy, default/custom request shape, or Gateway-local canonicalization; the original M1 completion and browser evidence therefore remain applicable.
- Validation at this snapshot (all Python commands explicitly set `PYTHONPATH=src` so imports resolve to this detached candidate tree):
  - focused direct and durable Gateway owners: `14 passed`;
  - affected Gateway/IM contract and integration owners: `54 passed, 7 warnings` (dependency/deprecation warnings only);
  - independent `TemporaryDirectory` probe: default/custom × direct/durable invalid candidates leave no target or config, exact rejected retries are stable, changed reuse is rejected, and confirmed existing user content is retained;
  - changed-file Ruff and `git diff --check origin/main...HEAD`: passed.
- The orchestrator's final full non-E2E run on this same candidate reports `3101 passed`; this targeted verifier did not rerun that broader suite.

## Correctness

| Requirement / closure scenario | Implementation | Permanent and independent evidence | Status |
|---|---|---|---|
| Invalid model cannot initialize a missing custom target via the direct create entry point | validation at `agent_config_sync.py:318-325` precedes `:335-349` | `test_custom_workspace_is_untouched_when_candidate_model_is_invalid` at `test_gateway_workspace_creation.py:124-143`; focused suite passed | covered |
| Invalid reasoning/model cannot initialize a default or custom target via durable create | validation at `agent_config_sync.py:511-542` precedes resolver mutation at `:663-690` | `test_create_operation_rejects_invalid_model_before_custom_workspace_setup` at `test_gateway_config_operation_validation.py:86-137`; independent four-mode probe passed | covered |
| Exact retry of an invalid operation returns its durable terminal rejection, not a new attempt | receipt lookup plus terminal receipt return at `agent_config_sync.py:511-551,581-584` | independent probe observes two `invalid_agent_config` results and a persisted `rejected` receipt | covered |
| Same operation ID cannot become a valid/default or custom create by changing the candidate | fingerprint/intent comparison at `config_apply_receipts.py:78-102` | `test_config_operation_rejects_invalid_effort_and_operation_id_reuse` at `test_gateway_config_operation_validation.py:31-83`; independent custom and default probes assert `operation_id_reused` and no target | covered |
| Confirmed existing user directory remains adopted without overwriting user content | valid custom branch unchanged at `agent_config_sync.py:673-690` | `test_existing_workspace_requires_confirmation_then_preserves_files` at `test_gateway_workspace_creation.py:199-235`; independent probe passed | covered |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Validate a candidate before any workspace mutation | Yes | Both create entry points now call the same Gateway-local reasoning catalog before their default/custom initialization branches at `src/personal_assistant/gateway/agent_config_sync.py:318-349,511-548`. |
| Existing directories require explicit confirmation and preserve pre-existing content | Yes | The validation move does not bypass `_prepare_custom_workspace()` or alter `ensure_workspace_defaults()` timing for a valid confirmed request at `src/personal_assistant/gateway/agent_config_sync.py:673-690`. |
| Gateway alone interprets and mutates node-local workspace paths | Yes | This delta is confined to Gateway candidate validation, receipt handling, and Gateway unit tests; it introduces no IM filesystem access or package dependency. |

### Prototype / Reference Contract

Unchanged. This P1 delta has no create-page or style change; the repository-local desktop, mobile, custom, and existing-directory acceptance evidence from M1 remains applicable.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for targeted-closure verification.

# Round 11

> Validation snapshot: `f18b345c61d94bfa202ea693a539102044d49052 -> 307baeba36e93406008cc6a2545afb1e8a2aacfc`

## Summary

Mode: full
Delta range: `f18b345c..307baeba3`
Focus issues: final rebase on current `origin/main` and the final Agent-create frontend fixture alignment
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 4/4 original requirements and 6/6 M1 exit criteria are present, but one creation-failure boundary is incomplete |
| Correctness | Original user scenarios, create-recovery guards, opaque root/provenance propagation, and transcript projection additions are covered; invalid create candidates can leave workspace side effects |
| Coherence | One blocking ordering deviation |

1 critical issue(s), 0 warning(s) found. Fix before PR.

## Prior-Issue Closure

| Boundary | Result | Evidence |
|---|---|---|
| Round-10 COW replacement and failed-write atomicity | remains closed after rebase | `tests/unit/personal_assistant/test_gateway_session_binder.py:261-315` passed in the focused and full suites; `GatewaySessionBinder.bind_conversation()` persists before publishing the replacement projection (`src/personal_assistant/gateway/session_binder.py:632-645`). |
| Original workspace-root contract | reopen: invalid candidate no-side-effect boundary | The final rebase preserves the Gateway-local create authority, IM structured forwarding/mirror, and create-page flow; independent code review found model/reasoning validation occurs after custom workspace initialization. |

## Completeness

- M1's checked task record remains complete: the Workspace card, canonical default/custom outcomes, no-write rejections, confirmed existing-directory adoption, node-local ownership, opaque IM mirror, permanent tests, build/static gates, and isolated browser evidence are recorded in `docs/changes/feat-515-agent-workspace-root-selection/M1-workspace-creation/tasks.md:9-67` and `progress.md`.
- The approved prototype's four must-match rows have durable desktop/mobile/confirmation evidence and a passing product acceptance record in `M1-workspace-creation/evidence/` and `acceptance.md`; this rebase does not alter the create-page component or its styles.
- Re-executed final gates at this exact snapshot:
  - focused Gateway/IM/recovery/transcript suite: `169 passed, 7 warnings`;
  - full Python non-E2E suite: `3099 passed, 24 deselected, 22 warnings in 143.01s`;
  - final-create frontend owners: `25 passed` across `agent-create-workspace.test.tsx` and `im-agent-config-api.test.ts`;
  - `ruff check src/IM src/personal_assistant tests/im_service tests/unit/personal_assistant`, `git diff --check origin/main...HEAD`, and `scripts/docs-check`: passed (`229` maintained Markdown sources, `66` required routes).
- The existing permanent tests do not exercise an invalid `default_model` or `reasoning_effort` with a missing custom target, so they do not protect the ordering of candidate validation and filesystem initialization.

## Correctness

| Requirement / Scenario | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| Default directory is selected at creation and the node returns its root/provenance | `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:798-842`; `src/personal_assistant/gateway/agent_config_sync.py:278-321` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py`; `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx` | covered |
| A missing custom target is created only under an existing usable parent | `src/personal_assistant/gateway/agent_config_sync.py:842-900` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py`; `tests/im_service/contract/test_agent_create_immutability_contract.py:17-75` | covered |
| Invalid/unusable parent or non-directory target is a field-presentable 422 with no IM profile | `src/IM/api/routes/nodes.py:361-402`; `src/IM/application/agent_config_operations.py:18-55` | `tests/im_service/contract/test_agent_create_immutability_contract.py:17-75`; `tests/im_service/integration/test_agent_create_workspace_error_flow.py` | covered |
| Existing directory requires an explicit second submission and preserves existing contents | `src/personal_assistant/gateway/agent_config_sync.py:901-919`; `src/IM/application/agent_config_operations.py:524-559` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py`; `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx` | covered |
| Invalid model/reasoning input has no custom-workspace side effect | `src/personal_assistant/gateway/agent_config_sync.py:321-341` initializes a valid custom target before `_reasoning_catalog.validate()` at `:367-373` | missing | **CRITICAL-1** |
| Canonical root is unique only in the target Gateway config; another node may use the same string | `src/personal_assistant/gateway/agent_config_sync.py:300-317,842-879` | `tests/unit/personal_assistant/test_gateway_workspace_creation.py:211-271`; recorded two-Gateway acceptance evidence | covered |
| Existing Agent root remains immutable | `src/IM/api/routes/agents.py:63-66`; `src/IM/application/config_service.py:383-423`; existing detail API only reads the stored mirror | `tests/im_service/contract/test_agent_create_immutability_contract.py`; `tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py` | covered |
| Lost successful create is recoverable only through the exact durable operation; ordinary registration cannot be claimed | `src/IM/application/agent_config_operations.py:71-145,291-410`; `src/IM/infra/repositories/agents.py:400-489` | `tests/im_service/contract/test_agent_registration_seed_recovery.py`; `tests/im_service/contract/test_agent_create_immutability_contract.py:139-198,306-372` | covered |
| IM keeps a successful Gateway root opaque and returns/routs the same provenance | `src/IM/application/config_service.py:425-448`; `src/IM/api/routes/agents.py:225-235,419-446` | `tests/im_service/contract/test_workspace_root_mirror_contract.py` | covered |
| Binding-derived transcript resolution remains lock-free and truthful | `src/personal_assistant/gateway/session_binder.py:632-645,934-968`; `src/personal_assistant/ws/im_connection.py` | `tests/unit/personal_assistant/test_gateway_session_binder.py`; `test_gateway_session_binder_concurrency.py`; `test_gateway_session_log_resolution.py` | covered |

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| Gateway alone interprets node-local filesystem paths; IM mirrors a nonblank successful root | Yes | Local `Path` validation is in `src/personal_assistant/gateway/agent_config_sync.py:278-329,842-919`; IM's one accessor returns the stored value without path interpretation at `src/IM/application/config_service.py:425-448`. |
| Root/provenance are creation facts and cannot be overwritten by a profile edit or normal registration | Yes | `ConfigService.update_profile()` has no workspace parameter (`src/IM/application/config_service.py:383-423`); claim predicates require exact root/provenance/operation (`src/IM/infra/repositories/agents.py:400-489`). |
| Recovery must not turn a prehosted or ordinary registered Agent into a create result | Yes | Gateway persists and re-advertises the operation; IM only accepts the exact pending operation in `src/IM/application/agent_config_operations.py:71-145,339-393`, with permanent negative contracts. |
| IM must not access a Gateway workspace directly, and Gateway control receive must not block on SQLite | Yes | Workspace RPCs use the Gateway control boundary, while the session provider reads the COW projection; no new cross-product import or IM-side workspace filesystem access is introduced by this unit diff. |
| Validate all candidate model/reasoning inputs before filesystem mutation | No | Custom `ensure_workspace_defaults()` runs at `src/personal_assistant/gateway/agent_config_sync.py:321-341`, while candidate model/reasoning validation is deferred until `:367-373`. |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Workspace card is between Identity and Behavior | M1 reviewer/worker exit criteria | `agent-create-page.tsx:785-865` | `M1-workspace-creation/evidence/create-desktop-default.png`; `acceptance.md` | covered |
| Default/custom chooser and custom target-node guidance | M1 reviewer/worker exit criteria | `agent-create-page.tsx:798-850` | `create-desktop-custom.png`; `create-mobile-custom.png`; frontend owner tests | covered |
| Existing-directory alert and confirmed retry | M1 reviewer/worker exit criteria | `agent-create-page.tsx:503-528,844-900` | `create-existing-confirmation.png`; frontend owner tests | covered |
| Narrow layout remains a single-column card flow | M1 reviewer/worker exit criteria | `src/IM/frontend/src/styles/global.css` | `create-mobile-workspace.png`; acceptance report | covered |

## Issues

### CRITICAL (must fix before PR)

- **CRITICAL-1 — invalid `default_model` or `reasoning_effort` can initialize a new custom workspace before the Gateway rejects the candidate.** `AgentConfigSync._handle_agent_create()` prepares and initializes a non-existing custom target at `src/personal_assistant/gateway/agent_config_sync.py:321-341`; it validates the model/reasoning pair only at `:367-373`. Thus an invalid candidate can create the target and `.nanoassistant` content even though no Agent config/profile is committed, violating the design's expected-failure-before-initialization boundary. Move `_reasoning_catalog.validate(default_model, reasoning_effort)` ahead of `_prepare_custom_workspace()` / `ensure_workspace_defaults()` while retaining the existing payload normalization. Add a lowest-layer regression in `tests/unit/personal_assistant/test_gateway_workspace_creation.py` that submits a missing custom target with an invalid model or reasoning effort and asserts the target, `.nanoassistant`, local Agent config, and returned successful payload are all absent.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for full verification.

# Round 10

> Validation snapshot: `a5e64e4fa0565179417ed96056838ce40a69ebc6 -> 1ffc6d819a518420ba3984feb4ef821e96f21487`

## Summary

Mode: targeted-closure
Delta range: `a3ac7d5fc..1ffc6d819`
Focus issues: Round-9 WARNING-1; same-conversation COW provider replacement; persistence-failure atomicity; preservation of coverage while splitting Binder concurrency tests
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | Round-9 permanent-regression gap closed; original requirements and M1 exit criteria remain unchanged |
| Correctness | 3/3 focused closure boundaries are permanently covered |
| Coherence | Followed |

0 critical issue(s), 0 warning(s) found. All checks passed. Ready for PR.

## Prior-Issue Closure

| Boundary | Result | Evidence |
|---|---|---|
| Same-conversation COW replacement is immediately visible at the production provider seam | closed | `test_conversation_bind_publishes_only_successful_projection_replacements` creates the binder/provider before any bind, binds `conv-projection` to session A and then B, and immediately observes A's and B's exact JSONL addresses (`tests/unit/personal_assistant/test_gateway_session_binder.py:261-295`). |
| Persistence error leaves durable state, provider projection, and provenance maps unmodified | closed | The same test injects `PersistentSessionBindingStore.bind()` failure for session C, then proves the durable row and provider remain B, B provenance remains present, and C provenance is absent (`tests/unit/personal_assistant/test_gateway_session_binder.py:297-315`). Because `bind_conversation()` calls the repository before `_record_provenance()`, the failure cannot publish C (`src/personal_assistant/gateway/session_binder.py:632-645`). |
| Test split preserves all former coverage | closed | The old-binding reuse race moved intact to the dedicated concurrency owner (`tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py:50-76,192-237`). An independent AST test-id comparison across both files found no removed tests and exactly one added regression; the files are 347 and 264 lines. |

## Completeness

- Round-9 WARNING-1 requested one lowest-layer Binder regression covering A-to-B provider replacement and failed-C atomicity. That exact regression is present in the permanent Binder owner.
- The test-only delta does not change the original workspace-root behavior, architecture boundaries, or prototype/reference contract.
- Independent validation:
  - focused Binder/fork/provider owners: `50 passed, 2 warnings`;
  - changed-file Ruff: passed;
  - `scripts/docs-check`: passed (`232` maintained Markdown sources, `66` required routes);
  - `git diff --check a3ac7d5fc..1ffc6d819`: passed;
  - old/new test-id comparison across the Binder and Binder-concurrency owners: no removals, one addition.

## Correctness

| Requirement / Scenario | Evidence | Status |
|---|---|---|
| Same conversation rebind replaces A with B in the already-created provider | `tests/unit/personal_assistant/test_gateway_session_binder.py:261-295` | covered |
| Failed persistence of C leaves maps and provider at B | `tests/unit/personal_assistant/test_gateway_session_binder.py:297-315`; write-before-publication ordering at `src/personal_assistant/gateway/session_binder.py:632-645` | covered |
| Moving the old-binding reuse race does not drop its original assertions | `tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py:192-237`; no removed test ids across the split | covered |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Observe COW behavior through the public production provider, not private projection internals | Yes | The regression builds and calls `build_session_log_path_provider()` at `tests/unit/personal_assistant/test_gateway_session_binder.py:269-295,304-307`. |
| Publish only after a successful durable binding write | Yes | Persistence occurs before `_record_provenance()` at `src/personal_assistant/gateway/session_binder.py:632-645`, and the failure regression protects that ordering. |
| Keep concurrency behavior in its dedicated owner without reducing coverage | Yes | The moved blocking-store helper and reuse race are co-located in `test_gateway_session_binder_concurrency.py`; all prior test ids remain collected. |

### Prototype / Reference Contract

Unchanged; this targeted delta changes only permanent Gateway Binder test coverage and its unit evidence.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

## Corrected Delta Reconciliation

N/A for targeted-closure verification.
