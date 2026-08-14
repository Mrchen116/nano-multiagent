# M1-fix Tasks

## Scope

- Fix only `OutboundRouter`'s concurrent external-final-reply dedupe race and the async ownership needed by its two existing final call sites.
- Preserve observer bubble mirroring, terminal fallback, bounded completed-key cache, retry after provider failure, and IM/shadow behavior.
- Do not change canonical specs or unrelated delivery paths.

## Exit criteria

- Concurrent observer-final and terminal-final contexts with intersecting semantic keys cause exactly one provider send.
- Terminal fallback waits for an overlapping owner outcome: owner success suppresses the fallback, while owner failure transfers the reservation and the fallback sends.
- Cancelling an overlapping fallback leaves no worker that can wake and late-send after old-run suppression.
- An overlapping waiter consumes the owner's explicit result, independent of completed-cache eviction.
- A provider send exception releases the reservation so a later explicit retry can also send.
- Existing completed-key eviction behavior remains covered.
- Narrow and nearby automated tests plus Python lint/format pass.
- Perform the dedicated isolated Feishu E2E validation and prove exactly one user-visible final reply.

## Test strategy

- Protected regression risk and observable seam: two public `OutboundRouter.send_text_async()` calls can concurrently invoke the channel adapter twice, lose the fallback after owner failure, or let a cancelled fallback late-send; assert the final observable provider outcome for owner success, owner failure, waiter cancellation, and completed-cache pressure.
- Existing protection and disposition: `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_outbound_router_dedupes_external_final_reply_across_paths` (keep) covers sequential cross-path semantic dedupe; the same semantic owner contains deterministic overlapping-send success and owner-failure cases because sequential execution cannot expose either race.
- Layer/directory/marker: `tests/unit/personal_assistant/`, marker none; router-to-adapter boundary is the lowest layer that exposes the concurrent provider-send defect.
- File ownership: extend `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`; it already owns router dedupe and bounded-cache behavior.
- Optional dependency `importorskip`: none.
- One-time acceptance evidence: dedicated isolated Feishu E2E attempt only; record in `progress.md`, not in the permanent test suite.

### Affected existing-test disposition

| Risk / behavior | Existing test | Disposition | Rationale and retained/replacement protection | Verification |
|---|---|---|---|---|
| Sequential final-path semantic dedupe | `test_gateway_web_relay_adapter.py::test_outbound_router_dedupes_external_final_reply_across_paths` | keep | Still protects a distinct non-concurrent semantic dedupe behavior. | Narrow test file |
| Concurrent owner failure transfers to terminal fallback | `test_gateway_web_relay_adapter.py::test_outbound_router_fallback_sends_after_inflight_final_send_fails` | keep | Protects the review-confirmed final-loss order that a later explicit retry does not cover. | Narrow test file |
| Cancelled overlapping fallback does not late-send | No pre-existing test (review round 2 exact reproduction) | keep new | `test_outbound_router_cancelled_fallback_never_sends_after_owner_failure` protects reset/shutdown cancellation at the lowest Router-to-provider seam. | Narrow test file |
| Overlapping owner success survives completed-cache eviction | No pre-existing test (review round 2 exact reproduction) | keep new | `test_outbound_router_waiter_observes_success_after_completed_key_eviction` separates active result handoff from bounded completed history. | Narrow test file |
| Bounded completed-key cache | `test_gateway_web_relay_adapter.py::test_outbound_router_bounds_dedupe_key_memory` | keep | Reservation storage is separate and must not weaken completed-key eviction semantics. | Narrow test file |

## Roadpoints

- [DONE] R1: Add deterministic concurrent final-path RED regression and failure-retry regression.
- [DONE] R2: Add atomic multi-key reservation, success commit, and exception rollback in `OutboundRouter`.
- [DONE] R3: Prove a single real Feishu final reply through the dedicated isolated E2E chain and clean every script-owned runtime resource.
- [DONE] R4: Close the review-confirmed owner-failure gap by waiting for the in-flight result, then rerun automated and real Feishu validation.
- [DONE] R5: Replace the condition worker wait and cache-based result handoff with a cancellation-owned async flight outcome; rerun automated and real Feishu validation.
- [DONE] R6: Close independent code review, merge the observable contract into the canonical spec, and pass final delivery gates.
