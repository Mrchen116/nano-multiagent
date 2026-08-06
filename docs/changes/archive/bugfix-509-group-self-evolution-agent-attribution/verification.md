# Verification Report: bugfix-509

> Validation snapshot: `97474256889f3654760ef4178041707126fb88b1`
> Executed base: `d7600ca913b040250e68acc46ba170093b46bbe7`
> Mode: full, round 1

## Summary

- **Mode:** full
- **Delta:** N/A
- **Focus:** N/A
- **requires_full_verification:** false

| Dimension | Result |
|---|---|
| Completeness | 2/2 milestones are implemented; 3/4 delta requirements are fully complete and the Gateway relay requirement is partial because an already-disconnected IM manager is silently skipped. |
| Correctness | 19/20 delta scenarios conform in code; the notification-failure scenario is partial. Two milestone exit matrices also lack durable coverage. |
| Coherence | Followed. The implementation reuses the existing subscription, authenticated Gateway relay, message repository/event, fork, reducer, i18n, and system-row seams without adding a parallel notification path. |

**Finding counts:** 0 critical, 3 warnings, 0 suggestions.
**Verdict:** FAIL — warnings require fixes before PR.

## Completeness

### Milestones and requirements

| Scope | Status | Implementation and durable evidence |
|---|---|---|
| M1 reliable structured notice | Implemented with one contract gap | The subscription preserves request-time Agent/session identity; the delivery callback builds the canonical targets and stable key and awaits the business ACK; IM validates attribution, snapshots the profile name, persists the nullable sidecar, emits one canonical `message.created`, projects it through REST/live history, deduplicates retries, and copies it on fork. Focused backend tests passed. The already-disconnected callback path is incomplete; see W1. |
| M2 localized Agent attribution | Implemented with an exit-coverage gap | The frontend preserves the sidecar in live state, chooses direct/group and skills/memory/both complete-sentence keys, renders in the existing system row, and falls back for unknown/old records. Real-stack evidence covers group attribution, zh/en switching, direct fork, desktop/mobile, and reload. The required 12-cell component matrix and full P2 evidence are incomplete; see W2. |
| Gateway relay delta requirement | Partial | Source Agent id, targets, stable identity, awaited ACK, and non-fatal caught delivery failures are implemented in `src/personal_assistant/gateway/runtime_delivery/background.py:40-123`. An absent/disconnected manager returns before event identification or logging at lines 46-48, contradicting the diagnosable-disconnection scenario. |
| IM gateway relay delta requirement | Implemented; validation gap | Authenticated node/profile/current display/synthetic user/conversation membership validation is implemented in `src/IM/infra/gateway_persistence.py:316-344`; structured ingress, stable error ACK, snapshot persistence, first-insert event, and idempotent retry are implemented in `src/IM/ws/gateway/relay.py:392-492` and the message repository. Not every enumerated rejection cause is durably tested; see W3. |
| Conversations/messages modified requirement | Implemented | Direct fork passes the stored `system_notice` unchanged into each copied message (`src/IM/application/web_im_service.py:470`); `tests/im_service/unit/test_fork_conversation_edges.py:314-373` proves a new message id with an identical notice snapshot. Existing fork availability, history, context, and branch-isolation behavior remains on the established path. |
| Web chat UX delta requirement | Implemented; validation gap | `src/IM/frontend/src/features/chat/system-notice.ts:5-36` validates and formats the structured notice from its stored snapshot; `MessagePane` keeps the existing centered system-row presentation; zh/en provide all six complete-sentence keys. The implementation is correct by inspection, but the required cross-product regression/evidence is incomplete; see W2. |

### Prototype must-match contract

| Prototype item | Result | Evidence |
|---|---|---|
| P1 centered lightweight system row | Verified | The four committed screenshots show the existing centered low-emphasis row; `evidence/README.md:40-45` records no avatar, sender header, or message actions. |
| P2 direct/group × zh/en × skills/memory/both | Partial | Real-stack evidence shows group skills in zh/en and direct skills in zh; it records a combined persisted notice but does not render or capture the complete 12-cell matrix. Unit/component coverage is also incomplete (W2). |
| P3 desktop 1280×800 and mobile 390×844 without horizontal overflow | Verified for recorded journeys | Desktop group and mobile group/direct screenshots were visually inspected; `evidence/README.md:40-45` records the checked viewports and no overflow. |

## Correctness

### Delta-spec scenario mapping

| Specification scenario | Result | Implementation / verification |
|---|---|---|
| Gateway: group event retains source Agent | Pass | Request identity is captured by the subscription and emitted as `source_agent_id`; focused subscription/delivery tests cover the payload. |
| Gateway: direct chat uses the same structured path | Pass | Conversation resolution is channel-agnostic; the direct real-stack journey persisted and forked a structured notice. |
| Gateway: ACK-loss replay retains delivery identity | Pass | The key is `self-evolution-review:{session}:{sequence}` and repository retry returns the same id; `test_system_notice_roundtrip_event_and_retry_are_exactly_once` and the structured handler test prove one row/event. |
| Gateway: notification failure does not change task result | **Partial** | Await/negative-ACK exceptions are caught and warned without bubbling, but an already absent/disconnected manager is silently returned at `background.py:46-48` (W1). |
| IM: valid source persists and publishes live | Pass | Relay creates a system message with the profile snapshot and `emit_created_event=True`; repository and handler tests assert the stored sidecar and one event. |
| IM: refresh reads the same snapshot | Pass | Repository/API round-trip tests preserve the sidecar; real-stack reload kept the same two records and notice count. |
| IM: commit then ACK loss does not duplicate | Pass | Conversation-scoped caller idempotency returns the first message and emits no second event; backend tests assert identical ids, one row, and one event. |
| IM: invalid node/profile/name/member attribution is rejected | Pass by implementation; incomplete durable matrix | The resolver checks all enumerated authorities and the relay converts every `ValueError` to `invalid_system_message`; only node mismatch and participant mismatch are directly covered (W3). |
| IM: old system messages remain compatible | Pass | The sidecar is nullable; invalid/unknown sidecars project as absent, and frontend tests render stored content. |
| Fork: completed Agent reply copies bounded history | Pass | Existing service and fork-edge tests remain on the same path; the unit changes only add sidecar fidelity to message copying. |
| Fork: self-evolution semantics and snapshot survive | Pass | Fork test asserts a new message id with exactly equal `system_notice`; browser evidence shows the direct fork rendering. |
| Fork: Agent retains context through the fork point | Pass, unchanged path | No kernel-history mapping or request-fork behavior changed; focused fork tests passed. |
| Fork: source and branch remain independent | Pass, unchanged path | Copying creates new conversation/message ids and leaves source rows untouched; existing service boundary is preserved. |
| Fork: entry remains limited to completed direct Agent replies | Pass, unchanged path | No fork eligibility/UI action logic was modified. |
| Web: Chinese group shows source and target | Pass | Formatter/component assertions cover group zh memory; real-stack screenshots cover two separately attributed group skills notices. |
| Web: English group attributes different Agents | Pass | Real-stack English group screenshots show both Agent snapshots; formatter uses each notice snapshot. |
| Web: direct is localized without duplicate Agent name | Pass | Component test and direct-fork zh screenshot verify the direct key omits the name; all six keys exist. |
| Web: live, refresh, re-entry, and language switch retain semantics | Pass | Reducer preserves live sidecars, REST preserves history sidecars, the component reacts to language changes, and real-stack reload/re-entry did not duplicate. |
| Web: pre-fix history is not rewritten | Pass | Unknown/absent notice falls back to stored content; no backfill/migration rewrites old content. |
| Web: forked structured notice uses current locale | Pass | Fork preserves the sidecar and the formatter reads current i18n state; the direct fork was observed in the browser. |

### Verification executed at the validation snapshot

- 79 focused backend tests passed across subscription/delivery, Gateway attribution/idempotency, migration, repository/event, REST, and fork suites.
- 5 architecture contract tests passed for product `agent.sdk` and core/platform dependency boundaries.
- Ruff on all changed Python files, `git diff --check`, and `scripts/docs-check` passed (`235` maintained Markdown sources, `66` routes).
- The verification worktree intentionally had no frontend `node_modules`; an independent Vitest/build rerun was therefore unavailable without mutating the read-only checkout. The committed M2 progress records 579 passing frontend tests and a successful build at the same snapshot, while W2 identifies the missing assertions even in that committed suite.
- All four committed screenshots were inspected directly against P1/P2/P3.

## Coherence

| Design decision | Result |
|---|---|
| D1 optional structured sidecar on the existing system message | Followed. There is one nullable domain/SQLite/repository/API/live representation and fork copies it exactly. |
| D2 browser-localized complete sentences | Followed. Rendering chooses one of six direct/group × target keys from the current browser locale; stored English text remains compatibility fallback only. |
| D3 IM-authoritative attribution and display-name snapshot | Followed. Gateway sends only Agent id; IM authenticates node ownership and conversation membership and snapshots `AgentProfile.display_name`. |
| D4 stable in-process identity, awaited ACK, repository idempotency, canonical event | Followed except for W1's pre-send disconnected early return. No outbox or WS-only parallel authority was introduced. |
| D5 old/unknown fallback and CLI/kernel isolation | Followed. Old rows retain content; no `coding_cli` or Agent kernel implementation was changed; architecture contracts passed. |

The implementation respects the repository redlines: `personal_assistant` continues to consume the public Agent boundary, IM does not import Agent code, kernel dependency directions are unchanged, and the change stays within the approved existing seams.

## Issues

### Critical

None.

### Warnings

#### W1 — Already-disconnected IM delivery is silently discarded

`src/personal_assistant/gateway/runtime_delivery/background.py:46-48` obtains the manager and returns immediately when it is absent or disconnected, before checking whether the event is a self-evolution review or resolving its conversation/event identity. The delta spec requires disconnect, timeout, and rejection to be diagnosable while remaining non-fatal; the design additionally says a disconnect is retried with the same key. Because the session event has already reached this callback, this branch can consume a valid notice without a warning or enqueue/replay attempt.

**Required fix:** identify a valid self-evolution notice first, then route the disconnected state through the existing diagnosable non-fatal failure behavior (or the connection manager's same-key replay path). Add a caplog regression for both `None` and `connected=False`, plus a negative-ACK assertion that the callback logs identity and does not raise.

#### W2 — The required localization/prototype cross-product is not durably verified

The M2 exit criterion explicitly requires `group/direct × zh/en × skills/memory/both` component coverage and P2 real-browser evidence (`design.md:305`). `system-notice.test.ts:15-38` covers memory for four locale/chat combinations plus group zh both, but no skills assertion and no direct both assertion. `system-notice-message.test.tsx:72-91` exercises only memory. The real-stack artifacts show group skills zh/en and direct skills zh; `evidence/README.md:32-38` mentions a combined persisted notice but the screenshot renders the earlier skills-only row, and there is no memory rendering artifact.

**Required fix:** parameterize formatter/component tests over all 12 combinations, make the conversation participant's current name differ from the notice snapshot to prove history is not overwritten, and record sufficient P2 evidence to demonstrate all three target variants in group/direct and zh/en (a compact evidence matrix is acceptable; twelve screenshots are not required).

#### W3 — The trust-rejection scenario lacks its enumerated failure matrix

Production code rejects missing profile, wrong node, blank current profile display name, missing synthetic Agent user, missing conversation, and non-participant source (`src/IM/infra/gateway_persistence.py:316-344`). The persistence test only parameterizes wrong node and non-participant (`tests/im_service/unit/test_gateway_conversation_persistence.py:253-286`), and the handler test only checks a wrong-node error without explicitly proving no additional row/event (`tests/unit/personal_assistant/test_background_session_events.py:327-331`). M1's exit criterion requires the profile/node/conversation rejection behavior to have lowest-level durable regressions.

**Required fix:** extend the resolver test across every enumerated trust failure and add a handler-level assertion that each rejected payload returns stable `invalid_system_message`, persists no new row, and emits no live event.

### Suggestions

None.

0 critical issue(s), 3 warning(s) found. Fix before PR.

# Round 2

## Verification Report: bugfix-509

> Validation snapshot: `ac47fca08148ccc245eca956d253096b9394f8dd → ebaec0d71b9c5322b6042a5724b8015777ceb5e9`

### Summary

- **Mode:** targeted-closure
- **Delta range:** `ac47fca08148ccc245eca956d253096b9394f8dd..ebaec0d71b9c5322b6042a5724b8015777ceb5e9`
- **Focus issues:** W1 disconnected/failed delivery diagnostics; W2 localization matrix and P2 evidence; W3 trust-rejection matrix
- **requires_full_verification:** false

| Dimension | Result |
|---|---|
| Completeness | 3/3 focus issues closed |
| Correctness | 4/4 targeted checks passed, including the related direct-fork millisecond-order regression |
| Coherence | Followed |

**Finding counts:** 0 critical, 0 warnings, 0 suggestions.
**Verdict:** PASS.

## Targeted Closure

| Focus issue | Implementation evidence | Durable verification | Outcome |
|---|---|---|---|
| W1 — disconnected/failed IM delivery was not fully diagnosable | `src/personal_assistant/gateway/runtime_delivery/background.py:51-148` now identifies a valid notice before checking connectivity. A missing manager logs conversation/Agent/session/sequence; `connected=False` logs and still calls `send_json_await_ack`, whose existing queue retains business frames until reconnect (`src/personal_assistant/ws/im_connection.py:566-613`, `1398-1415`); rejected and missing/blank-message-id ACKs are caught and logged without escaping. The callback-local delivery incarnation keeps the key stable across same-process replay without colliding after restart. | `tests/unit/personal_assistant/test_external_visible_delivery.py:373-504` covers same-incarnation identity, disconnected queue handoff, manager absence, negative ACK, and two malformed ACK shapes. Focused tests passed. | **closed** |
| W2 — localization/prototype cross-product lacked durable coverage | Formatter and component matrices enumerate all 12 `group/direct × zh/en × skills/memory/both` cells (`src/IM/frontend/src/features/chat/system-notice.test.ts:15-40`, `components/system-notice-message.test.tsx:73-106`). The component participant is currently `Renamed Product` while the stored snapshot is `SpecLab Product`, and every case rejects the current participant name. Malformed live/persisted sidecars fall back to stored text rather than throwing. | Both focused frontend files passed 28 tests and the production build passed. The independent real-stack P2 matrix and durable artifact index are recorded in `regression.md:46-67` and `evidence/README.md:49-60`; the committed group/direct, zh/en, three-target, two-Agent, reload, and long-name screenshots were inspected. | **closed** |
| W3 — trust rejection lacked the complete durable matrix | The existing resolver still enforces profile, authenticated node, nonblank profile name, synthetic user, conversation, and participant membership. | `tests/im_service/unit/test_gateway_conversation_persistence.py:256-304` covers all six resolver failures. `tests/unit/personal_assistant/test_background_session_events.py:334-432` repeats all six through the handler and asserts stable `invalid_system_message`, zero message rows, zero `message.created` rows, and zero notifier emissions. Focused tests passed. | **closed** |

## Related Direct-Fork Order Check

The reviewer-discovered browser-order failure was checked only as the requested related closure, not as a new full review. `src/IM/application/web_im_service.py:444-485` assigns source-ordered timestamps one millisecond apart and ending at copy time, while continuing to copy `system_notice` exactly. `tests/im_service/unit/test_fork_conversation.py:179-251` creates mixed user/Agent/system history, forces the old repository clock collision, and proves both source content order and distinct sorted browser-millisecond timestamps. The design now explicitly records this timestamp contract and the Gateway delivery incarnation in `design.md:84-98`, `141-152`, and `251-255`; implementation and design are synchronized.

This implementation-level closure does not replace the product reviewer's requested round-2 browser rerun of the formerly failing fork journey.

## Validation

- 63 focused Python tests passed across W1, W3, message persistence, and direct-fork ordering; only two pre-existing dependency deprecation warnings were emitted.
- 28 focused Vitest cases passed (12 formatter cells, 12 component cells, and fallback checks), followed by a successful production frontend build; only the existing chunk-size warning was emitted.
- Ruff passed on all Python files changed in the fix range.
- `git diff --check` passed for the fix range.
- `scripts/docs-check` passed: 237 maintained Markdown sources and 66 required routes.
- All operations were read-only except this report.

## Issues

### Critical

None.

### Warnings

None.

### Suggestions

None.

All checks passed. Ready for PR.
