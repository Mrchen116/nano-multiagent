# Verification Report: feat-578 attachment lifecycle closure

Validation snapshot: `8488f8adf → 2505c9772420f8910b9a82789dc2703d5ca6fbc9`; finding origin `8488f8adf`.

Mode: targeted-closure of R15 P2 / attachment verification A-W1 only. `requires_full_verification: false`. **Overall status: not_pass**: A-W1 is closed, but known A-C1 S11 product exit remains incomplete. Earlier unaffected implementation, contract, visual and verification scopes remain retained; no full implementation scan or final acceptance is performed.

## Summary

| Dimension | Closure result |
|---|---|
| Completeness | Both eventual-success and eventual-failure retained uploads recover after realtime stop; required new UI evidence remains pending |
| Correctness | Same upload UUID settles independently of stream epoch; clear/revoke removal continues to block late restoration |
| Coherence | Aligned with `design.md:90` background stream suspension retaining process-local drafts and `spec.md:106–108` / current `docs/specs/IM/conversations-messages.md:472–475` actionable failed-file recovery |

## Finding closure and direct evidence

| Item | Fixed implementation / evidence | Status |
|---|---|---|
| R15 P2 / A-W1: scene stop leaves upload permanently uploading | `ChatStore.swift:186–222` removes stream epoch dependency only. Successful response checks same row UUID and still-authorized conversation, removes upload row and appends pending attachment; failure finds same UUID and clears uploading before setting reason/deadline. `ChatStateTests.swift:155–171` gates upload, calls stop, then releases both 200 and 503 responses. | **closed** |
| Clear/revoke isolation retained | `ChatStore.swift:38–40,127–136,197–205`: clear/reconcile/denial remove upload rows; late success and catch return if original UUID is absent. Existing `testUploadFinishedAfterStoreClearCannotRestorePrivateDraft` passes in the green run; access-reconciliation implementation and prior membership coverage are retained. | aligned; no new live account-switch claim |
| Foreground failure/normal-send blocking/text-only retention/cooldown | Not changed by this fix. Existing R15 meaningful tests remain passing in the full green run. | earlier conclusions retained |

## Evidence

Caller supplied red run `/tmp/nano-feat578-upload-background-red.log` against pre-fix `8488f8adf`: xcodebuild selected `NanoIMTests/ChatStateTests/testUploadCompletesWhenRealtimeStopsForBackground`, and four assertions fail—no success conversion and retained uploading=true/no failure reason. The final status is `** TEST FAILED **`. This matches the independently reported mechanism.

Green `/tmp/nano-feat578-upload-background-green.log` records the same background test passing, existing late-clear isolation passing, 16 XCTest tests without failures, 10 Swift Testing tests passing and `** TEST SUCCEEDED **`. Result bundle: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_14-09-50-+0800.xcresult`. This is reusable actual execution evidence; the verifier ran no UI/services/tests. Caller reports docs-check 272 sources / 75 routes and diff-check passed.

No new concrete source problem remains in this closure. The minimal fix distinguishes realtime suspension from lifetime of an upload draft without weakening removal on clear/revoke. No design/current-spec correction is required.

## Remaining exit

**CRITICAL A-C1 retained — S11 product evidence pending, not an additional code defect.** `verification-attachments-r1.md` and independent `acceptance-r7.md:75–81,104` remain authoritative for prior scope: native 83-byte TXT send/Quick Look is proved, while the new size rejection/failed upload/removal/retry/visible cooldown/text-only UI has not yet been installed and independently operated. Retain download failure/export/external credential and live account-switch evidence limits. After safe installation, continue those specific independent journeys; do not substitute this green state regression for S11 acceptance.

No physical phone, Mini renewal, full S1–S30, complete product acceptance or overall verifier pass is granted. Mac lock and unscheduled device/signing steps remain resource/evidence gates. Reports only were written; no implementation edit or commit.
