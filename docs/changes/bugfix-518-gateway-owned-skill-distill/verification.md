# Verification Report: bugfix-518-gateway-owned-skill-distill

> Validation snapshot: `ff27a30b4ab3759213ec148ae46f0a6a6d23a12a → 2a66d9d0dcc8fa443aecf6f20a62b4aab2dbf93d`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone complete |
| Correctness | 10/12 behaviour-and-scenario seams protected |
| Coherence | Followed |

## Completeness

- Tasks: 6/6 complete. `tasks.md:7-16` maps the scanner removal, short-lived
  control RPC, local resolver/readiness, node-pinned conversation, withdrawal of
  abandoned subsystems, and dual-Gateway acceptance to concrete implementation.
- Spec coverage:
  - IM source-node projection and same-Gateway selection are implemented by
    `src/IM/infra/repositories/conversations.py:581-698`,
    `src/IM/frontend/src/features/chat/components/distill-selection.ts:3-18`, and
    `src/IM/frontend/src/features/chat/components/conversation-sidebar.tsx:181-249`.
  - The owner-scoped prompt operation is implemented at
    `src/IM/api/routes/web_im.py:237-341`; it only accepts identities from the
    browser, verifies IM-owned facts, calls the selected node, and creates the
    execution conversation only after a usable prompt returns.
  - Gateway-local binding/path/readiness work is isolated in
    `src/personal_assistant/gateway/distill_prompt.py:21-116`, with the
    request/result connected through `src/personal_assistant/ws/im_connection.py:1140-1156`
    and `src/IM/ws/gateway/control.py:364-447`.
  - The execution pin is persisted and made server-authoritative by
    `src/IM/infra/db.py:35-51,492-493`,
    `src/IM/infra/repositories/conversations.py:45-185`, and
    `src/IM/api/routes/messages.py:405-450`.
- Prototype / reference coverage: `prototype.html:83-122` has four explicit
  must-match claims. The mode-only UI, unavailable labels, same-Gateway selection,
  returned current-format prompt, and ordinary-send handoff are covered by
  `conversation-sidebar.tsx:106-249`, `chat-workspace-page.tsx:883-985`, and the
  focused Vitest journeys. Durable two-Gateway evidence is recorded in
  `M1-gateway-owned-distill/progress.md:3-18`; `design.md:130-147` supplies an
  executable isolated reviewer runbook. No permanent browser E2E was added.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| IM projects `source_node_id`, not a Gateway filesystem path | `conversations.py:616-698`; `web_im.py:157-192` | `test_users_conversations_api.py:9-65`; `test_repositories_user_conversation.py:167-206` | covered |
| First eligible source locks selection; running, missing source, and other-node rows are unavailable | `distill-selection.ts:3-18`; `conversation-sidebar.tsx:181-249`; `chat-workspace-page.tsx:425-439,883-899` | `conversation-sidebar.test.tsx:114-182`; `chat-workspace.integration.test.tsx:575-596` | covered |
| Browser submits identities only and IM creates a chat only after a local prompt | `chat-api.ts:102-132`; `web_im.py:242-341`; `chat-workspace-page.tsx:935-985` | `chat-api.test.ts:134-159`; `chat-workspace.integration.test.tsx:515-596`; `test_users_conversations_api.py:67-143` | covered |
| Correlated result accepts only the requested authenticated Gateway | `control.py:364-447`; `runtime.py:24-51,146-187`; `sessions.py:347-391` | `test_gateway_handler.py:461-504`; `test_gateway_im_connection_behavior.py:276-339` | covered |
| Local normal binding produces the exact existing ordinary-chat prompt without IM transcript work | `distill_prompt.py:59-97,119-138` | `test_gateway_distill_prompt_resolver.py:78-100` | covered |
| Missing local source or readiness returns no partial prompt and creates no chat | `distill_prompt.py:43-89,102-116`; `web_im.py:316-338` | `test_gateway_distill_prompt_resolver.py:103-152`; `test_users_conversations_api.py:101-143`; `chat-workspace.integration.test.tsx:598-610` | covered |
| External shadow uses the existing external binding only after a missing `web_relay` binding | `distill_prompt.py:59-80` | `test_gateway_distill_prompt_resolver.py:155-182` proves fallback, but not normal-binding precedence when both bindings exist | warning (V1-W2) |
| A successful prompt pins its direct conversation and ignores later client node hints | `db.py:35-51,492-493`; `conversations.py:45-185`; `messages.py:405-450` | `test_users_conversations_api.py:92-99`; `test_messages_api.py:54-98` | covered |
| Distiller or `skill_view` preflight failure preserves the dialog and does not navigate/create | `chat-workspace-page.tsx:917-985` | `chat-workspace.integration.test.tsx:598-610` and the following `skill_view` / prompt-failure journeys | covered |
| Gateway timeout/error leaves no execution conversation or relay task | `web_im.py:310-338`; `chat-workspace-page.tsx:958-983` | `test_users_conversations_api.py:101-143`; `chat-workspace.integration.test.tsx` prompt-error journey | covered |
| Direct API callers cannot bypass same-Gateway source/execution validation | `web_im.py:252-307` performs the check | The focused API test covers only the same-node happy path and Gateway-return error (`test_users_conversations_api.py:67-143`) | warning (V1-W1) |
| No new ordinary relay metadata, recovery state, transcript transfer, or IM→agent dependency | `web_im.py:242-341`; `messages.py:405-450`; `distill_prompt.py:21-99`; no new IM imports from `agent` | `tests/contract` (148 passed) plus diff inspection | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1: IM owns selection/node projection only, never the Gateway filesystem | 是 | `conversations.py:685-698` projects only `agent_profiles.node_id`; `src/IM` has no JSONL/session scanner in the unit diff. |
| D2: one identity-only, short-lived correlated control request; Gateway has final local readiness | 是 | `web_im.py:252-315`; `control.py:364-447`; `distill_prompt.py:43-49,102-116`. |
| D3: return the existing editable prompt, then use the existing ordinary relay with a server pin | 是 | `chat-workspace-page.tsx:958-985`; `messages.py:415-451`; `test_messages_api.py:54-98`. |
| D4: failed resolution occurs before an empty execution chat, model run, session, or skill write | 是 | `web_im.py:316-338`; `distill_prompt.py:51-97`; `test_users_conversations_api.py:101-143`. |
| v5.3 external-shadow compatibility stays private to IM→Gateway control | 是 | `web_im.py:283-294`; `distill_prompt.py:67-80`; browser DTO `chat-api.ts:102-132` has no external identity. |

The unit preserves the repository boundary: IM uses HTTP/WS only and does not
import `agent`; personal_assistant imports no `agent.core`/`agent.platform` module.
The local resolver is a single narrow owner for binding-to-path conversion rather
than a second transcript or recovery subsystem. Public handlers have contract
docstrings, the internal pin remains absent from `ConversationResponse`, and the
test layout follows `docs/development/testing.md` (one new semantic owner test,
otherwise extensions of existing API/control/frontend seams).

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Selection-only checkboxes and understandable unavailable states | `design.md:119-125`; `tasks.md:7-16` | `conversation-sidebar.tsx:106-249` | `conversation-sidebar.test.tsx:99-213` | covered |
| Same-Gateway source lock and execution picker | `design.md:122-124` | `chat-workspace-page.tsx:425-439,883-914` | `chat-workspace.integration.test.tsx:575-596`; `progress.md:9-13` | covered |
| Returned current-format prompt is editable and sent through ordinary chat | `design.md:20-28,76-91` | `chat-workspace-page.tsx:958-985`; `messages.py:405-479` | `chat-workspace.integration.test.tsx:515-596`; `progress.md:7-11` | covered |
| Two isolated Gateways, with cleanup and no permanent E2E suite | `design.md:127-147`; `tasks.md:31-32` | N/A (one-time runtime evidence) | `M1-gateway-owned-distill/progress.md:3-18` | covered |

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

- **[V1-W1] The IM-owned same-Gateway guard has no direct-API regression test.**
  `src/IM/api/routes/web_im.py:252-307` correctly rejects a source or execution
  Agent that does not belong to the selected node, but
  `tests/im_service/integration/test_users_conversations_api.py:67-143` exercises
  only the same-node success path. The frontend-disabled state at
  `src/IM/frontend/src/features/chat/components/conversation-sidebar.tsx:185-196`
  cannot protect a stale or direct HTTP caller. Extend the existing integration
  test (do not create a new test file) with a source/execution node mismatch and
  assert `409`, no Gateway control invocation, and no increment in conversations.
  This is the stable server boundary required by the delta scenario at
  `specs/im/web-chat-ux.md:14-24`.

- **[V1-W2] The external-shadow test does not prove normal `web_relay` binding wins
  when both bindings exist.** `src/personal_assistant/gateway/distill_prompt.py:59-80`
  implements the right normal-first lookup, yet
  `tests/unit/personal_assistant/test_gateway_distill_prompt_resolver.py:155-182`
  creates only an external binding. It would also pass if a future change consulted
  the external binding first and returned the wrong source transcript. Extend that
  existing test with distinct normal and external bindings/JSONL paths and assert
  the returned prompt contains the normal binding path. This directly protects the
  v5.3 contract at `specs/gateway/relay-protocol.md:11-13,32-36` without adding a
  parallel test layer.

### SUGGESTION（可以修）

None.

0 critical issue(s), 2 warning(s) found. Fix before PR.

---

## Round 2 — Targeted Closure

> Validation snapshot: `fbf855db1690452c388ea0ac0bd0501c316aa984 → 1ae49f87bfa3967b33f5c702ffbce288873ffc6e`

Mode: targeted closure
Delta range: `fbf855db..1ae49f87b`
Focus issues: V1-W1, V1-W2
requires_full_verification: false

| Previous issue | Closure evidence | Result |
|---|---|---|
| V1-W1 — direct callers could bypass the UI without a server-boundary regression test | `tests/im_service/integration/test_users_conversations_api.py:145-192` creates a second execution Agent on `node-2`, replaces control RPC with a fail-fast stub, submits the source on `node-1`, and asserts `409` plus an unchanged conversation count. The stub's successful absence proves rejection occurs before the control request. | resolved |
| V1-W2 — external fallback test did not establish normal-binding precedence | `tests/unit/personal_assistant/test_gateway_distill_prompt_resolver.py:156-214` first proves external fallback, then binds a distinct normal `web_relay` session and asserts the returned prompt contains the normal session path. A reversed lookup would return the external path and fail. | resolved |

### Targeted validation

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/im_service/integration/test_users_conversations_api.py tests/unit/personal_assistant/test_gateway_distill_prompt_resolver.py` — **7 passed**.
- `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check tests/im_service/integration/test_users_conversations_api.py tests/unit/personal_assistant/test_gateway_distill_prompt_resolver.py` — **passed**.
- `git diff --check fbf855db1690452c388ea0ac0bd0501c316aa984..1ae49f87bfa3967b33f5c702ffbce288873ffc6e` — **passed**.

The candidate changes only the two existing regression seams identified in Round 1;
they add no production behavior, public API, architecture, or document-contract
delta. Both warnings are closed, and the prior full-verification evidence remains
applicable. No full re-verification is required.

Verdict: **pass** — 0 critical issue(s), 0 warning(s), 0 suggestion(s).
