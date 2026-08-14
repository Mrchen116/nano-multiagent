# M1-fix Tasks

## Scope

- Fix only `OutboundRouter.send_text()`'s concurrent external-final-reply dedupe race.
- Preserve observer bubble mirroring, terminal fallback, bounded completed-key cache, retry after provider failure, and IM/shadow behavior.
- Do not change canonical specs or unrelated delivery paths.

## Exit criteria

- Concurrent observer-final and terminal-final contexts with intersecting semantic keys cause exactly one provider send.
- Terminal fallback waits for an overlapping owner outcome: owner success suppresses the fallback, while owner failure transfers the reservation and the fallback sends.
- A provider send exception releases the reservation so a later explicit retry can also send.
- Existing completed-key eviction behavior remains covered.
- Narrow and nearby automated tests plus Python lint/format pass.
- Perform the dedicated isolated Feishu E2E validation and prove exactly one user-visible final reply.

## Test strategy

- Protected regression risk and observable seam: two worker-thread calls to public `OutboundRouter.send_text()` can concurrently invoke the channel adapter twice for one final assistant text, or suppress the fallback before an in-flight owner later fails; assert the final observable provider outcome for both owner success and failure.
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
| Bounded completed-key cache | `test_gateway_web_relay_adapter.py::test_outbound_router_bounds_dedupe_key_memory` | keep | Reservation storage is separate and must not weaken completed-key eviction semantics. | Narrow test file |

## Roadpoints

- [DONE] R1: Add deterministic concurrent final-path RED regression and failure-retry regression.
- [DONE] R2: Add atomic multi-key reservation, success commit, and exception rollback in `OutboundRouter`.
- [DONE] R3: Prove a single real Feishu final reply through the dedicated isolated E2E chain and clean every script-owned runtime resource.
- [DONE] R4: Close the review-confirmed owner-failure gap by waiting for the in-flight result, then rerun automated and real Feishu validation.
