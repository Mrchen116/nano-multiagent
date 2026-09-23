# Verification Report: refactor-570

> Validation snapshot: `2e9c83df99ba1b9313dbea7c449ed43635e7ee59 → a3c6e819c1b0147baf60ca8c13f6a76ede6749a4`
>
> validation_mode: `full`
>
> validated_at: `2026-09-22T17:35:00+08:00`
>
> executed_base: `2e9c83df99ba1b9313dbea7c449ed43635e7ee59`

## Summary

| Dimension | Result |
|---|---|
| Completeness | 1/1 milestone implemented; 1 required composition regression guard missing |
| Correctness | 3/3 motivation scenarios implemented; focused regression evidence passed |
| Coherence | Followed, except the M1 production-composition test exit criterion is not evidenced |

**Verdict: warning.** The implementation follows the approved design and has no
spec delta, but M1 explicitly requires a production composition check that the
current fixture does not perform. Add that guard before the verifier gate passes.

## Completeness

- **M1 `boundary`: implemented.** The unit diff contains the concrete publisher,
  delivery boundary, typed sync handoff, shared composition store, and adapted
  existing tests. The worker record reports the frozen implementation narrow
  suite as 54 passed and records its pre-refactor 43-pass baseline.
- **Current-spec coverage:** no spec delta. The diff does not change
  `docs/specs/`; its external synchronization, offline recovery, image snapshot,
  and cancellation behavior remains governed by
  `docs/specs/gateway/external-channels.md` and
  `docs/specs/gateway/routing-delivery.md`.
- **Prototype/reference contract:** N/A. This unit has no frontend reference.
- **Outstanding guard:** `design.md` M1 requires the real composition to share
  the saga store and runtime admission/release hooks. The test fixture builds a
  separate publisher itself, so it cannot detect a production wiring regression.

## Correctness

| Requirement / Scenario | Implementation evidence | Regression evidence | Status |
|---|---|---|---|
| Reply/body, tool state, and updates remain in one shadow conversation without duplicate bubbles | `shadow_reply_publisher.py:61-111,113-186` preserves the former POST/PUT identifiers and receipts; `message_delivery.py:731-789` projects then records delivery; `shadow_sync.py:327-352,397-451` resolves the durable saga before delegation | Existing shadow-sync and relay tests in the recorded 54-pass suite exercise HTTP payloads, idempotency, rich snapshots, and recovery | covered |
| Accepted text and frozen images retry after temporary IM failure without rereading a source or duplicating the reply | `message_delivery.py:716-728` remains the sole frozen-snapshot projection; failures leave publisher receipts pending until `shadow_sync.py:397-451` replay | `tests/integration/test_shadow_reply_images.py:151-268` covers failed upload, recovery, source deletion, and revoked delivery; recorded focused suite passed | covered |
| A cancelled/invalid run cannot publish an old body; accepted attempts always release | `shadow_reply_publisher.py:85-104,153-177` retains admission before each request, discard-without-release on denial, and `finally` release after admission; composition injects `_admit_shadow`/`_release_shadow` at `composition.py:648-654` | `tests/integration/test_shadow_reply_images.py:228-268` retains revoked/no-write assertions; recorded focused suite passed | covered |

Reusable implementation evidence from `M1-boundary/progress.md` is versioned to
this exact commit: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_shadow_auth.py tests/integration/test_shadow_reply_images.py tests/unit/personal_assistant/test_gateway_build_runtime.py` reported **54 passed**. It also records Ruff on affected files and `git diff --check` as passed. Those checks are reused rather than rerun.

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| Concrete publisher owns outbound HTTP and saga publication receipts | Yes | `shadow_reply_publisher.py:21-186`; no IM write/receipt code remains in `message_delivery.py` or `shadow_sync.py` |
| Delivery owns frozen projection and its ledger | Yes | `message_delivery.py:716-789`; publisher accepts already-projected content and has no `ReplyImages`/ledger dependency |
| Sync owns anchor/preparation/recovery and does not expose private state to delivery | Yes | `shadow_sync.py:259-352,397-451`; type-only `MessageDelivery` import at `shadow_sync.py:36-38` |
| Composition shares one store and supplies admission/release hooks | Implementation: yes; permanent regression guard: no | Production wiring is explicit at `composition.py:645-670,763-777`; see WARNING-1 for the unprotected test seam |
| No contract delta | Yes | `git diff 2e9c83df9..a3c6e819c -- docs/specs` is empty; no external HTTP payload, recovery identity, or visible delivery behavior changed |

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

- **WARNING-1 — M1's production composition injection is not protected by a test.**
  `composition.py:645-670,763-777` correctly creates one
  `ExternalShadowSagaStore`, injects it into both sync and publisher, and passes
  the publisher into `MessageDelivery`. But
  `tests/helpers/message_delivery.py:34-53` constructs a publisher directly,
  while the only nearby IM-enabled composition test,
  `tests/unit/personal_assistant/test_gateway_build_runtime.py:238-308`, asserts
  skill/notice wiring and never captures the publisher/store/hooks. A later
  composition reorder or omitted `shadow_publisher=` would leave all rewritten
  protocol fixtures green while production shadow publication fails at runtime.
  Extend that existing composition test (or an adjacent focused test) to capture
  `ShadowReplyPublisher`, `IMShadowConversationSync`, and `MessageDelivery`, then
  assert publisher and sync receive the identical store and the publisher retains
  the composed admission/release hooks. This directly fulfills the M1 exit
  criterion without adding a parallel protocol suite.

### SUGGESTION (optional)

None.

## No Spec Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway / IM no spec delta | All observable POST/PUT payloads, receipt updates, image projection, and admission/release sequencing are retained in the new owner boundary | Recorded 54-pass focused suite covers existing protocol, recovery, auth, and image behavior | no spec delta |

Outcome: implementation-mismatch for the M1 test-coverage exit criterion only; no current-spec mismatch found.

---

## Round 2 — existing production-fixture coverage reconciliation

> validation_mode: `targeted-closure`
>
> validated_at: `2026-09-22T17:38:16+08:00`
>
> executed_base: `2e9c83df99ba1b9313dbea7c449ed43635e7ee59`
>
> validated_at commit: `a3c6e819c1b0147baf60ca8c13f6a76ede6749a4`

### R1 WARNING-1 — REFUTED

`tests/integration/test_pa_offline_image_shadow.py:55-143` is the existing
production-composition guard that R1 did not locate. It obtains its runtime from
`tests/integration/test_pa_candidate_delivery.py:70-158`, whose `build()` calls
`compose_gateway(config)` with an IM service and a real kernel/pipeline, rather
than using `tests/helpers/message_delivery.py`.

The test drives an external ingress through the assembled runtime, persists and
reads the real sync-owned saga store, deletes the original image source, then
calls `sync.recover_pending()` after IM recovery. It observes the IM PUT's
completed state and frozen-image URL while proving that the source path is not
re-read (`test_pa_offline_image_shadow.py:106-142`). This reaches the real
`IMShadowConversationSync → MessageDelivery → ShadowReplyPublisher` chain.

That behavior is sufficient to guard the R1 risk:

- omitting `shadow_publisher=` from production `MessageDelivery` makes recovery
  fail at `message_delivery.py:769-778` instead of producing the observed PUT;
- wiring publisher to a different saga store makes `acknowledge()` fail because
  its update finds no ready bubble (`shadow_saga.py:683-701`), so
  `recover_pending()` cannot complete;
- it therefore protects the same-store injection and real publication boundary
  without asserting private constructor wiring.

The report at `/tmp/refactor570-tests-remaining.log` records the remaining
suite, including this integration test, as **2045 passed in 153.66s** on this
commit. This evidence supersedes R1 WARNING-1. A future focused assertion may
add direct live admission/release accounting if a concrete lifecycle regression
is identified, but no additional test is required for the already-covered
composition risk.

### Round 2 verdict

All verifier findings are closed. No current-spec delta found.

**Verdict: pass. Ready for PR.**
