# Verification Report: feat-578 attachment failure delta

Validation snapshot: `b8f9a9bc6 → 8488f8adf081fc9f5bd6f723b4db02fd840a389b`.

Mode: delta + targeted closure of the known S11 fixed-limit/failed-file recovery gap. Only the four attachment source/test files and necessary direct contracts/lifecycle were reviewed. `requires_full_verification: false`. Overall status: **not_pass**. Static recovery has one WARNING; S11 product exit remains incomplete. Prior unaffected reviews and verification conclusions are retained, including the limited P6 visual evidence; this is not a final verifier pass.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Policy delegation and foreground failed-file actions implemented; scene-stop recovery has a concrete gap; new S11 UI evidence pending |
| Correctness | Text-only retention, explicit retries/cooldown and clear isolation have passing state/transport evidence; retained in-flight upload after scene stop does not recover |
| Coherence | Existing raw upload, conversation authorization, per-conversation drafts and explicit user actions retained; one deviation from background draft continuation |

## Completeness and correctness

| Contract | Fixed-head implementation / evidence | Result |
|---|---|---|
| `spec.md:106–108` S11; `coverage.md:13` C07; current `docs/specs/IM/conversations-messages.md:472–475`: per-file failure, remove/appropriate retry | `ChatModels.swift:34–43`, `ChatStore.swift:176–223`, `ConversationView.swift:99–126`; error mapping agrees with existing `attachment_upload.py` (413 size, 429 Retry-After, 507 generic capacity) and upload route 415 | Implemented; actual failure UI pending |
| Same contracts: text-only choice retains every unsent attachment and successful send clears only submitted items | `ChatStore.swift:225–245`, `ConversationView.swift:125–127,154`; `testFailedUploadBlocksNormalSendAndTextOnlyKeepsEveryAttachment` checks no normal message POST, text-only empty attachment payload, both draft kinds retained, explicit retry with original bytes | Covered by meaningful HTTPTransport/state test; actual UI pending |
| Same contracts: obey Retry-After | `ChatStore.swift:220–222`, `ConversationView.swift:111–116`; `testUploadRetryWaitsForRetryAfterThenKeepsFileUntilSuccess` uses API 429 with 20-second header, verifies no early second upload, then success after deadline | Covered at transport/state boundary; displayed countdown/action pending UI |
| Current upload policy is server-owned, not hardcoded 10 MiB | `ConversationView.swift:169–181` removes client size veto; unchanged `ChatAPI.swift:20–23` uses raw bytes + file_name/conversation_id + Content-Type; server `messages.py:create_upload` reauthorizes and applies existing storage policy | Aligned. Actual 16 MiB rejection and legal files above old threshold still require product evidence |
| S4/S11 clear/revoke isolation | `ChatStore.swift:38–40,128–135,165,197–206`; new `testUploadFinishedAfterStoreClearCannotRestorePrivateDraft` gates the actual transport, clears, releases response and checks no old attachment/draft/list restoration; existing membership test now checks failed data removed | Clear and revoke code aligned; clear test passes. No new claim of live account-switch/late-response acceptance |
| `design.md:90`: background closes stream/polling while retaining process-local drafts, active resumes useful work | `NanoIMApp.swift:168–170` calls `stop`, `ChatStore.swift:34–36` changes epoch; retained uploads still mark uploading at `192`, and return at `197/202` without settling | **WARNING A-W1**: retained row becomes permanently non-actionable |

The bounded delta introduces no new API, role or attachment access bypass. 403/404 discard protected draft/cache and reload authoritative conversation access; non-member upload/download authorization and same-origin resource restrictions remain existing server/client responsibilities. Download/export behavior was not modified or re-reviewed.

## Evidence

`/tmp/nano-feat578-attachment-tests-r10.log` records `xcodebuild -project .../src/IM/ios/NanoIM.xcodeproj -scheme NanoIM -destination platform=iOS Simulator,id=1CE31893-672F-495A-B2B5-3ACF39A7A257 -derivedDataPath /tmp/nano-ios-build test`, 15 XCTest and 10 Swift Testing successes, no failures, and `** TEST SUCCEEDED **`. Result bundle: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_14-00-20-+0800.xcresult`. The three new tests demonstrate failure/send retention, cooldown and late-clear isolation rather than merely mirroring view state. They do not cover stop-with-retained-upload. Caller reports diff/docs checks passed (270 sources / 75 routes); those checks do not replace behavior evidence. This verifier ran no UI, service or tests and changed reports only.

Independent `acceptance-r7.md:75–81,104` documents native file selection, 83-byte synthetic TXT plus text send and correct Quick Look content on the previous binary. It explicitly leaves S11 inconclusive: 16 MiB was not operated before Mac lock, and the new failed-file UI has not been installed/verified. Authentication wording has its own completed narrow evidence and is outside this delta.

## Issues and remaining exit

**WARNING A-W1 — Recover uploads retained across scene suspension.** See `code-review-r15.json`, `ChatStore.swift:197` (also catch at 202). Upload → inactive/background → response leaves uploading true because stop invalidates its epoch without removing the row. Every explicit recovery/send action remains blocked. Distinguish stream stop from account/cache invalidation, or otherwise settle the retained upload safely. Add a gated transport regression for stop rather than clear, covering eventual success/failure and a usable draft on return; keep existing clear/revoke isolation evidence intact. This is a direct deterministic code finding, not a newly claimed UI observation.

**CRITICAL A-C1 — S11 product exit still incomplete (known evidence gate, not a code defect caused by lock).** After the lifecycle fix and safe installation, independent product review must exercise actual server size rejection, failed upload/removal/explicit retry, visible cooldown, and text-only send retaining every unsent file. Preserve the wider previously pending download failure/export/external credential and account-switch evidence scopes. `acceptance-r7.md:104` remains inconclusive until those required observations exist. A locked Mac and unscheduled physical-phone/Mini signing are pending resources, not implementation findings; no UI, physical device, renewal, full S1–S30 or overall delivery pass is granted here.

No design/current-spec correction is needed for this delta: existing S11, C07 and current IM failed-file contract already require the behavior. No new speculative issues or full implementation audit are requested.
