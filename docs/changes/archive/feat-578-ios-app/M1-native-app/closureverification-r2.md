# Verification Closure: feat-578-ios-app — Round 2

> Mode: targeted-closure. Prior report: `verification-r1.md`. Finding origin: native `b970e20a60c0d1e18bc10d1d734b75d3d11cf4d6`. Fixed reviewed head: `1708bdd74f6798a2013171958b29a8e3314a1710`. Fixes: `8b30e2361` (chat metrics and uncertain-send regression), `1708bdd74` (photo presenter). Code review covers only these post-verification native changes, not a new full review.

## Summary

The inspected metric omission is corrected in source, and the uncertain-send regression gap is closed by a meaningful HTTPTransport test. The photo presentation fix uses a stable presenter outside the menu. No concrete new code defect was found in this scope; `code-review-r4.json` is `[]`.

Full verification remains **not_pass**: C-01 known unfinished exits remains open; W-01 is now pending presentation evidence rather than a surviving source omission; W-02's send portion is closed while configuration conflict/pending evidence remains open. This round does not grant product/device acceptance or close the photo journey before UI retest. No scope expansion requires a new full code review.

## Focus findings

| Prior item / fix | Code closure | Evidence closure | Overall status |
|---|---|---|---|
| W-01 / C09 metrics | **closed**: Agent-only running timer, authoritative final elapsed_ms, collapsed inline usage, cache quantity/rate including no hit | Native visual checks of timer progression, completed freeze/user-hidden state, expanded layout and cache/no-hit rows are not yet recorded; no new focused metric presentation regression in the 22 tests | **still_open — evidence only** |
| W-02 / uncertain send | **closed**: no sending implementation change was needed | HTTPTransport lost-response test proves no automatic POST after recovery/normal send, stable explicit retry key and one canonical history row; portable and actual simulator runs pass | **closed — send portion** |
| W-02 / configuration conflict/pending | No configuration source change in this delta; prior inspection of preserved draft/reload/choice remains applicable | Independent `acceptance-r1.md` J3 now records actual 409/draft/reload/version choice and explicit save, with `output/feat578/reviewer-config-conflict.png` evidence. `config_apply_pending`/delayed authoritative confirmation and the required lasting regression evidence remain unclosed | **still_open — configuration portion**, 409 journey established |
| C-01 / incomplete M1 exits | Outside fix scope | Independent product review, native multi-width/IME/DT/system media evidence and final physical phone/Mini signing/renewal/expiry/HTTPS-WSS gates remain pending; remote CI/current merge remain open | **still_open — known exits** |
| Photo menu failure found in product review | **corrected in source**: root presenter survives menu dismissal | Earlier b970 menu failure was observed twice by product reviewer; fixed head has not been UI retested because the Mac was locked | **pending UI closure**, not a new speculative code finding |

## Source and contract checks

### Chat metrics

`src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift:44–65,92–114` now follows the concrete mechanisms required by `docs/specs/im/response-metrics.md` and C09:

- The whole statistics row is gated on `sender_type == "agent"`; user messages do not receive an elapsed/timer display even if a field is present.
- A server-reported elapsed_ms takes precedence and renders the fixed final wall-clock value. Without that value, only `delivery_status == "running"` uses SwiftUI's date timer. `startedAt` supports ISO timestamps with and without fractional seconds, matching the UTC ISO format produced by `src/IM/infra/_timestamps.py` and forwarded by message/history DTOs. It uses the actual message creation time rather than a locally restarted receipt timer.
- `ChatUsageView` has a default-collapsed DisclosureGroup with inline layout and a shallow background; no overlay obscures following messages. It exposes output, total, context used/window, cache hit count and rate.
- Cache rate uses the server's full-turn `cache_read_tokens / cache_total_input_tokens`; positive denominator is guarded and the row stays present as `0 (0%)` without hits. The server TokenUsage contract gives the cache fields zero defaults, so this is the actual no-hit contract rather than invented accounting. Other absent count fields show “Unreported”.
- Context utilization uses the reported window and a bounded progress value. Existing process/permission behavior is unchanged by this delta.

This establishes source consistency. Compilation does not show a live timer ticking, freeze after the completed event, disclosure placement under narrow/Dynamic Type layouts or VoiceOver behavior. Those presentation checks remain part of W-01 and the independent product evidence; no pass is inferred from implementation alone.

### Uncertain message send

`src/IM/ios/Tests/ChatStateTests.swift:69–113` adds `testLostSendResponseRequiresExplicitRetryWithSameKeyAndNoDuplicateHistory`. Its HTTPTransport handles the actual Session/IMClient/ChatAPI/ChatStore boundary: the first POST records the Idempotency-Key then throws a connection-lost error; an authoritative history GET returns the already persisted message; explicit retry returns that same canonical message.

Assertions prove that pending/error state remains, recovered history contains one ID, another history recovery and normal send leave the POST count at one, and explicit retry sends the same nonempty key. Completion clears pending/draft and retains one history row. The test does not mirror private state-machine implementation or assert only DTO encoding. `ChatStore.swift:175–204` and `ChatAPI.swift` still use the PendingSend caller key and require `retry: true` while a pending send exists. No automatic transport retry was introduced.

The simulated loss is a protocol-seam regression, not a real network interruption acceptance claim. It closes the lasting regression gap raised for uncertain send; server idempotency semantics remain authoritative.

### Photo presenter

`src/IM/ios/NanoIM/Features/Chat/ConversationView.swift:8,80–81,98–100` replaces a PhotosPicker nested inside Menu with a menu Button toggling `pickingPhoto`. The `.photosPicker(isPresented:selection:matching:)` modifier is attached to the stable conversation root alongside the file importer. It retains image matching, the existing selection/upload path and its `nil` cancellation guard; the menu action itself does not send or upload.

The change directly addresses the observed presenter lifetime failure. Source/build success is sufficient for a no-finding code review of this bounded fix, but the actual Photos UI opening, cancel behavior and select/upload/send path still require product retest. The failed old behavior is not erased by marking the source corrected.

## Reused execution evidence

- `/tmp/nano-feat578-xctest-r5.log`: actual simulator run passed **22** cases (12 XCTest, 10 Swift Testing), `** TEST SUCCEEDED **`; the added lost-response case explicitly passed. Result bundle `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_02-18-15-+0800.xcresult`.
- `/tmp/nano-feat578-unconfirmed-send.log`: portable focused HTTPTransport regression passed, including the uncertain-send case and the three existing ChatState cases. This independently confirms the test seam can exercise actual source without UI.
- `/tmp/nano-feat578-build-r5.log`: `** BUILD SUCCEEDED **`. No simulator/UI operations were performed by this reviewer.
- `acceptance-r1.md` appeared before report handoff and was inspected for this scope: J3 records the actual two-client v1→v2 conflict, retained draft, authoritative reload, explicit choice and final save; its S18 result remains inconclusive for delayed node confirmation/nonowner behavior. The native config code is unchanged by the reviewed delta, so this narrow 409 evidence remains applicable. J5/R1-01 records the older photo failure and requires retest; it does not certify the fixed presenter. The metrics screenshot likewise predates the metric fix and cannot close W-01.
- `/tmp/nano-feat578-archive-r5.log`: archive had completed by report inspection, `** ARCHIVE SUCCEEDED **`; packaged executable reported Mach-O arm64. Independently read `/tmp/nano-ios-build/NanoIM-unsigned.ipa` SHA256: `e168bafe3d7e2373e7f9177985485a6198f38c62e02f8e3d785476bf8426ab0b`. This is still an unsigned IPA and establishes no physical signing/renewal result. The prior b970 artifact hash must not be treated as the fixed-head IPA hash.

No old test outcome was mechanically invalidated: the fixes touch exactly ChatMessageView, ConversationView and ChatStateTests. Session isolation, history/membership, Agent/Settings payload and CI conclusions remain scoped to their earlier evidence and the new full simulator regression run.

## Remaining actions and handoff

1. After the user's manual unlock, independently retest photo presentation/cancel/select, live/final/user metrics and the collapsed/expanded usage/cache layout. Record fixed revision and native artifacts; then close the affected product/evidence rows.
2. Preserve the independent J3 configuration 409 evidence and complete delayed `config_apply_pending`/authoritative confirmation evidence and M1-W1 lasting behavior protection at an appropriate simple seam. Do not count profile_version payload assertions as conflict recovery.
3. Keep the remaining product and physical phone/Mini gates in their agreed sequence. Neither this no-finding code review nor 22 unit tests closes M1-R1/W2/W3.

- `unit_id`: feat-578-ios-app
- `review_round`: 2
- `verification_mode`: targeted-closure
- `prior_verification_path`: `M1-native-app/verification-r1.md`
- `fix_delta_range`: `b970e20a6..1708bdd74`
- `focus_issues`: W-01, W-02; associated photo presenter fix
- `verdict`: not_pass (remaining evidence/gates)
- `issues`: critical=1 inherited unfinished exits; warning=2 residual evidence areas; suggestion=0; no new code defect
- `validated_issues`: W-01 source correction, W-02 uncertain-send closure; remaining configuration/visual/physical gates retained
- `requires_full_verification`: false
- `report_path`: `docs/changes/feat-578-ios-app/M1-native-app/closureverification-r2.md`
- `report_commit`: caller-owned; no implementation change or commit by reviewer
