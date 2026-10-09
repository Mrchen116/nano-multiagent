# Verification Report: feat-578 task reference and scope details delta

Validation snapshot: `5de8ffdb4 → 107290abecbef5c1605cc769284f3053017df12d`.

Mode: bounded delta review/verification of R15-01 and R15-02 only, covering `TasksView.swift` changes and direct task-detail/callback/permission context. This report's evidence closure update reads independent R16 without re-reviewing source. `requires_full_verification: false`. No surviving concrete source finding (`code-review-r20.json` remains `[]`). **S14 delta aligned/pass**: independent R16 closes both failures and the invalid-association branch. **Overall verification remains not_pass** because other precise product/device exits remain separately open.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Full-sheet reference and root Details now have independent R16 J59 evidence; invalid-association/retained-subgraph branch has J60 evidence |
| Correctness | Nested views propagate the same callback; one action appends one reference via the existing caller; root fields reuse existing detail rendering |
| Coherence | Existing company-wide task visibility, authorized last-chat projection, read-only client and draft-without-auto-send contract retained |

## Contract and bounded implementation

| Contract / finding | Fixed implementation and direct context | Status |
|---|---|---|
| `spec.md:122–124` S14; `coverage.md:17–18` C11/C12; current `docs/specs/IM/task-graphs.md:77–97`: reference returns to the appropriate chat and appends to draft without auto-send | `TasksView.swift:121–126` wraps the node sheet callback with selected=nil before forwarding. `TaskNodeView:179` no longer performs local dismiss after reference; relationship descendants at187 and nested subgraphs at175 preserve the forwarded callback | R15-01 **closed** by independent R16 J59: one deepest Check action closes sheet, reaches correct group and leaves only one editable Check reference without send |
| S14 selected candidate/reason/result/change note readable for root as well as children | Header `TasksView.swift:80–85` now sets selected=scope through Details for every current scope. Existing TaskNodeView displays result166, change_note167, selection_reason168, selected candidate173, prerequisites/successors/derived/children170–175 | R15-02 **closed** by independent R16 J59: root todo/result/change_note/selected A/reason and child links directly visible |
| Existing reference preserves user draft and does not execute/send tasks | `NanoIMApp.swift:178–180` and group callback `ChatInfoView.swift:42–45` append reference and navigate. No sendMessage/task-write call added. URL/text generation `TasksView.swift:150–153` unchanged | aligned; no automatic send or task execution |
| Inaccessible/expired last-chat association does not provide jump | Existing server `TaskGraphService._project_chats` (`src/IM/application/task_graphs.py:417–450`) resolves member_conversation and emits last_chat_id/title only when authorized; node button remains conditional on non-null last_chat_id. Graph403/404 load still clears selected and graph at146 | **closed within R16 J60**: after actual group deletion/reload, B/A show unlinked explanation without Reference, while graph/subgraph/dependencies remain |

The changed closure moves ownership from each pushed TaskNodeView's environment dismiss to the actual `.sheet(item: $selected)` owner. Deeper related nodes continue to call the same closure, so no extra local pop is required before opening chat. A nested TaskGraph sheet forwards through its parent callback; each enclosing sheet owner clears its own selection before the original reference callback. The original callback receives exactly one chatID/text pair per action; no repeated reference append is added by this patch. The separate Done dismissal remains unchanged.

The new header entry selects the existing scope object and opens its existing TaskNodeView; it neither invents task fields nor changes models, APIs, authorization, task mutation or execution. Existing graph/list and child-node selection remain. The current graph fetch continues to use `view=all`, allowing already-existing detail relations to resolve. Direct callback/server projection context was read solely for this delta; no broader task/client audit was performed.

## Actual evidence and validation bounds

Independent `acceptance-r15.md` J57 documents actual new graph `tg_b839513e` / group `c_82otvgr8`: nested Check reference pops to Prepare, then further references pop through A/B before finally returning to chat, accumulating four draft references without sending. It separately documents root explore with children displaying only title/child graph/list and no root detail entry. These are retained as **actual failures on the prior version**, not erased by the source candidate.

`/tmp/nano-feat578-task-reference-build-r16.log` ends `** BUILD SUCCEEDED **`. The previously running `/tmp/nano-feat578-task-reference-tests-r16.log` has now completed: xcodebuild test for the existing Simulator destination,17 XCTest with0 failures +10 Swift Testing passes and `** TEST SUCCEEDED **`. Result bundle: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_17-05-48-+0800.xcresult`. Existing native test code is unchanged; these27 tests protect prior state/transport/model contracts and do not prove modal navigation or root field visibility.

Prior5de8 Python4120/Web808 and unaffected native source/test evidence remain reusable within their prior scopes. No repeat full-suite run by this reviewer. The applicable testing policy rejects tests that merely mirror private view state or SwiftUI behavior; this minimal callback/entry wiring needs meaningful rendered journey evidence rather than a selected=nil source assertion. Independent R16 now supplies that specific journey.

## Independent product evidence closure and remaining exit

**TR-C1 closed; S14 delta aligned/pass.** Independent [acceptance-r16.md](acceptance-r16.md) explicitly identifies installed107290abe,390/native10990 and the same real graph/group. J59 directly opens root Details and sees todo, result578 comparison record, the expected change_note, selected Candidate A and selection reason. B→A→Prepare→Check then one Reference closes the entire sheet and enters the correct group with only Check/node=n5 editable draft, no automatic send. Reviewer clears the draft using the real keyboard and confirms Send disabled. This closes R15-01 and R15-02 through actual UI rather than source/tests.

J60 records safe handoff before caller deletes only the new group c_82otvgr8 (HTTP204); auxiliary API confirms tg_b839513e revision2/five nodes preserved and all last_chat_id null. Reviewer independently reloads list/graph: B and A show the unlinked explanation and no Reference entrance. A's subgraph still shows Prepare done→Check todo and its dependency, with responsive return. Direct UI plus authorized deletion response closes this invalid-association branch. These synthetic done/result records do not prove real task execution; no additional message or automatic task execution is claimed. J59 started from the safe empty draft; it proves one current reference without accumulation, not a newly executed pre-existing-text retention test.

Original R15 failures remain historical evidence above. R20 code[] and existing27-test record are unchanged. The UI belongs to the independent product reviewer; this evidence closure update performs no source re-review, UI/service operation or tests. Other accepted management/media/account/scroll/timeline scopes remain retained. Current precise remaining product states are linked in [acceptance-r17.md](acceptance-r17.md)'s latest S1–S30 table; its source was not re-verified here. Remaining overall scenarios and S29/S30 keep their recorded limits. No completed path is reopened because physical phone/Mini gates are scheduled later, and no overall product/device/final verifier pass is granted.

No design/current-spec correction is required: S14, P2 and existing task-reference contract already cover these behaviors. Only reports were written; no implementation edit or commit.
