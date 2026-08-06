# bugfix-509: Code Review

## Review scope

- Review mode: `closure`
- Finding origin: `ac47fca08148ccc245eca956d253096b9394f8dd`
- Fix head: `ebaec0d71b9c5322b6042a5724b8015777ceb5e9`
- Fix range: `ac47fca08148ccc245eca956d253096b9394f8dd..ebaec0d71b9c5322b6042a5724b8015777ceb5e9`
- Focus: only the five confirmed full-review findings and direct regressions in their fix patch; no new finder round.

## Closure

| Finding | Status | Closure evidence | Required action |
|---|---|---|---|
| CR1 Gateway restart resets the process-local event sequence and can collide with a persisted notice key. | `closed` | `build_session_event_callback()` now captures one generated delivery incarnation and includes it in `self-evolution-review:{incarnation}:{session}:{sequence}`. Repeated delivery through one callback keeps the same key, while a reconstructed callback gets a different key; the focused identity test covers both states. | None. |
| CR2 A disconnected IM manager caused the callback to return after the subscriber had consumed the event. | `closed` | The callback no longer returns for `manager.connected == false`; it calls `send_json_await_ack()`. The connection manager's normal `PendingFrame` has `requeue_on_disconnect=True`, is retained while offline, and is flushed after reconnect. The disconnected callback regression and connection-manager queue/reconnect suite pass. | None. |
| CR3 A recognized malformed live sidecar reached `.trim()` before source identity type checks. | `closed` | `formatSystemNotice()` checks both source identity fields with `typeof ... === "string"` before either `.trim()`. Malformed null/numeric identities return `null`, so `MessagePane` uses stored content; formatter and component regressions pass. | None. |
| CR4 History decoding coerced null/non-string source identity into accepted strings. | `closed` | `_decode_system_notice()` now requires `kind`, `source_agent_id`, and `source_agent_display_name` to already be strings before constructing `SystemNotice`; malformed persisted null/numeric identities decode to `None`. Repository history regressions pass. | None. |
| CR5 A success ACK without a non-empty `message_id` was accepted as delivered. | `closed` | The callback now inspects the raw ACK, requires a non-blank string `message_id`, and routes missing/blank values through the existing non-fatal warning path. Negative, missing, and blank ACK regressions pass. | None. |

- Findings closed: 5 / 5
- Remaining findings: None
- Direct fix regressions: None found in the changed delivery, formatter, decoder, message timestamp, or fork-copy paths.
- Final result: Pass

## Verification

- `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_background_session_events.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_message.py` — 63 passed; 2 dependency deprecation warnings.
- `npm test -- --run src/features/chat/system-notice.test.ts src/features/chat/components/system-notice-message.test.tsx` from `src/IM/frontend` — 28 passed.
- `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/im_service/unit/test_fork_conversation.py tests/im_service/unit/test_fork_conversation_edges.py` — 18 passed.
- `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check` over the changed Python production and test files — passed.
- `git diff --check ac47fca08148ccc245eca956d253096b9394f8dd..ebaec0d71b9c5322b6042a5724b8015777ceb5e9` — passed.

```json
[]
```
