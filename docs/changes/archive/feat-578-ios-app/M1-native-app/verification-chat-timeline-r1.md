# Verification Report: feat-578 late configuration boundary delta

Validation snapshot: `33b6e64f4 → f77b346337d6191e6cb61cc33005122ddbbce128`.

Mode: delta implementation verification of R11-01, limited to TimelineMerge, ConversationView's anchored display filter and the changed TimelineTests/ChatStateTests fixture. Relevant API/Web contracts and actual logs were read as direct context. `requires_full_verification: false`. No surviving concrete code finding (`code-review-r18.json` is `[]`); static implementation is aligned with the required boundary placement. **Overall status: not_pass** because R11-01's new-binary product closure and remaining product/device exits are not yet complete.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Late boundary is anchored to cached request; replay identity retained; anchorless marker is retained but hidden; actual native R12 confirmation pending |
| Correctness | Incoming authoritative entries replace matching IDs, discarded IDs are filtered, messages are sorted consistently by created_at/id, and each marker is placed immediately before its request |
| Coherence | Existing typed timeline, message-counted pagination cursor and native non-message presentation retained; direct boundary behavior agrees with API and Web |

## Contract and implementation

| Requirement / contract | Fixed implementation / relevant regression | Status |
|---|---|---|
| `spec.md:88–90` S7: history, configuration boundary and realtime replies consistent; `docs/specs/IM/conversations-messages.md:82–106` marker explains its anchored request and remains stable when late | `ChatModels.swift:124–136` replaces ID values from incoming page, groups marker by before_message_id and inserts before matching message regardless of marker applied_at. `TimelineTests.swift:16–25` starts with M2 cached, then supplies boundary and final reply, asserting M1 reply/boundary/M2 request/M2 reply | Source corrected; red/green regression proves the observed merge mechanism |
| Replay/refresh does not duplicate a message or marker | Same dictionary identity merge and repeated-page assertion in the new test; pre-existing overlapping-page test verifies replacement of partial content and discarded messages | covered |
| Marker remains tied to anchor rather than appearing alone on wrong page | `ConversationView.swift:18–22` hides non-message entries unless their before_message_id exists among loaded messages. `TimelineMerge` keeps unanchored entries in memory for a later merge. Current Web reducer and MessagePane use the same keep/hide/anchor approach | aligned; no claim of new UI or anchor-arrival acceptance |
| Message chronology and cross-page recovery remain stable | `ChatModels.swift:127–129` sorts by created_at/id rather than page arrival direction; existing ChatStateTests121-message recovery still asserts complete order, two requests and retained older cursor | covered after fixture corrected to actual increasing timestamps |
| Boundaries are non-message explanatory content | Existing ConversationView rendering remains a label without message menu; upload/auth/account/API/permission handling is untouched | earlier conclusions retained |

Direct API evidence: `WebIMService.list_timeline` inserts boundaries immediately before each page's anchor; `ConfigBoundaryRepository.list_for_message_ids` selects only included anchors; `messages.py:list_messages` counts messages and derives next_before_message_id from messages only. Storage page order/cursors remain server-controlled and were not changed by this client delta. Web `mergeTimelineItems` sorts messages using its timestamp/id comparator and separately groups boundaries by anchor, retaining unknown anchors in memory; MessagePane hides them until their anchor is loaded. Native now follows that same boundary mechanism with its canonical UTC string DTO ordering. This report does not assert that backend storage itself changed to a new sort order.

The retained `older` argument no longer changes merge ordering because authoritative chronology now determines the combined timeline; all existing call paths continue to supply the same message cursor. Direct ChatStore loadChat recovery and send merge callers were read solely to check this change's impact. No new mutation, data access, ownership or identity boundary is introduced.

## Test evidence and fixture correction

- `/tmp/nano-feat578-timeline-red-r12.log`: selected new late-boundary test fails on old code with actual order M1 reply/M2 request/boundary/M2 reply instead of the expected anchor-before-request order.
- `/tmp/nano-feat578-timeline-green-r12.log`: first full run is **not** a pass. Boundary test passes, but the121-message test uses identical created_at values and expects numeric m1…m121 order, conflicting with the timestamp/id sort's lexical tie ordering. This failed run is preserved.
- Fixed fixture changes only helper timestamp generation to genuinely increasing ISO8601 dates. It retains121 messages, overlapping recovery pages, complete numeric expectation, original m1 older cursor and requested cursors `[nil, m62]`. This models actual chronological test input rather than weakening the assertions.
- `/tmp/nano-feat578-timeline-green-r12b.log`: actual xcodebuild test on Simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257`,17 XCTest without failures +10 Swift Testing successes, `** TEST SUCCEEDED **`. Both boundary/replay and cross-page recovery tests pass. Result bundle: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_15-55-51-+0800.xcresult`.

These are meaningful model/transport regressions reused from actual execution. This verifier did not run tests, operate UI/services, change implementation or commit. No new test mirroring the simple visibility filter is required for this bounded change.

## Product evidence and remaining exit

Independent `acceptance-r11.md` J49/R11-01 records two actual native observations on the prior candidate: M2 request before the boundary, while API before_message_id=M2 and authoritative page order put the marker before M2. Valid native mention targeting and both real Gateway/LLM replies remain proved, but that report correctly marks S7 fail. The new merge regression explains and corrects this source mechanism; it does not establish new rendered ordering.

**CRITICAL TL-C1 retained — R11-01 major awaits independent product closure.** After safe installation of f77b candidate, revisit the existing M2 conversation and verify M1 reply/boundary/M2 request/M2 reply on screen, including reentry. Then perform the bounded next-round late-boundary check if required by the product reviewer, with real adoption and cleanup rather than relying on duplicate fixtures. Verify only one divider stays before its anchor and earlier history remains readable. Until those observations are recorded, R11-01 and the affected S7 product gate remain open despite green tests and no surviving static finding.

R10-01 is separately **closed by independent R11 J47 evidence**: same long-history fixture02→Latest actually shows11 with responsive controls/return/reentry. This supersedes only its prior pending UI closure; no new scroll code or repeat audit is performed here. R8/R9 attachment/account evidence, R16 core lifecycle review and all earlier unaffected accepted scopes remain retained. S12/S27 remaining branches and other overall/physical phone/Mini renewal gates remain as the latest product report records. No full S1–S30, device, signing, product or final verifier pass is granted.

No design/current-spec correction is required: S7 and the existing typed-timeline boundary contract already cover this behavior. Stop after this bounded source/test review; no new speculative issue or full re-audit is requested.
