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
