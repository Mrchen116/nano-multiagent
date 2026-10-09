# Verification Report: feat-578 bottom visibility delta

Validation snapshot: `f77b34633 → 5de8ffdb4d8c47c2645080c5bf4a3143c716099b`.

Mode: bounded delta code review + implementation verification of bottom visibility only. Necessary scrolling context, independent `acceptance-r12.md` / newly written `acceptance-r13.md`, progress and build/sample evidence were read; no full source audit, UI/service operation or tests were performed by this reviewer. `requires_full_verification: false`. No surviving concrete code finding (`code-review-r19.json` is `[]`). This bounded delta is aligned and its affected narrow journeys have independent product closure. **Overall verification remains not_pass** because wider product/device exits remain incomplete.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Bottom state now comes from scroll geometry instead of lazy-row lifecycle; independent R13 J52 send/background and J53 history/Latest impact checks are recorded |
| Correctness | Same near-bottom Boolean consumers and scroll target preserved; changed source introduces no new send/read/API/merge behavior |
| Coherence | Aligned with S6/S7 and existing near-bottom following vs history-preservation semantics; real rendering remains independently verified |

## Bounded implementation review

Only functional source delta is `ConversationView.swift:53–61`: retain the bottom target ID, remove its `.onAppear/.onDisappear` writes to bottomVisible, and attach `.onScrollGeometryChange(for: Bool.self)` to the containing ScrollView. The transform compares `visibleRect.maxY` with `contentSize.height - 24`; the action writes the transformed Boolean. This describes whether the viewport reaches within24 points of the content bottom, including fitting short content, without using lazy-row construction/recycling as a proxy. Apple's [ScrollGeometry documentation](https://developer.apple.com/documentation/swiftui/scrollgeometry) defines the viewport/content geometry, and [visibleRect](https://developer.apple.com/documentation/swiftui/scrollgeometry/visiblerect) is derived from content offset, insets and container size. The existing iOS26 minimum and successful build support this API use.

Direct consumers remain unchanged at `ConversationView.swift:62–68`: show Latest while not near bottom; count changes scroll on first load or near bottom; last-message content updates follow only while near bottom. Explicit Latest still calls the same non-animated scrollTo bottom target. Older-history loading/restoration at lines33–36 still restores the previous anchor. The geometry action itself performs no scroll, read acknowledgement or network mutation. Composer, sending, draft clearing, message merge, message `.onAppear` read callbacks and authorization are untouched. No new concrete safety/correctness defect is evidenced by this bounded change.

## Contracts and evidence

| Contract / observed issue | Evidence / conclusion | Status |
|---|---|---|
| `spec.md:84–86` S6: actual seen content governs reads; history not pulled down by arrivals | Boolean now tests actual scroll geometry. Existing message-read callback is unchanged; geometry change does not itself acknowledge a message | static alignment; no new blanket visible-read acceptance |
| `spec.md:88–90` S7; current `docs/specs/IM/web-chat-ux.md:36–69`: preserve history and follow when near bottom | ScrollTo/restore conditions and anchor IDs unchanged, with24-point near-bottom threshold; independent R13 J53 reaches early02/03 then Latest11/12, with body AX and Back responsive | no concrete static regression; affected long-history check recorded |
| R12-01: sent multiline tool request leaves UI frozen despite server completion | Independent `acceptance-r12.md:59–65` records one real send, old viewport/composer spinner/AX loss, authoritative completed reply and99% CPU | actual old-binary major, not explained away by API success |
| Layout-busy sample | `/tmp/nano-feat578-native-send-sample-r12.txt` has1267 main-thread samples and1257 under GraphHost.flushTransactions | supports transaction/layout busy; does not independently prove the bottom callbacks were sole root cause |
| Candidate compilation | `/tmp/nano-feat578-send-scroll-build-r13b.log` ends `** BUILD SUCCEEDED **` | reused actual build success |

The27 native tests and source/test scope from R18 remain unchanged, with the actual prior PASS retained; they are not presented as testing SwiftUI viewport geometry. No full test rerun or a test mirroring the simple view predicate is needed to establish this bounded static conclusion.

## Product closure status

Independent `acceptance-r13.md` J52 records the actual installed-candidate observation (native PID4396): one same-class multiline request clears composer; Latest shows running process at0:09–0:10; real Simulator Home and launch from the App icon restore the unique completed500500 reply with17.1s elapsed; one bash invocation took13,383ms and exited0; Back remains responsive. Caller then measured CPU0.0%. These are **independent recorded UI observations**, not this verifier's own operation and not deductions from source or sample. They close the observed R12-01 trigger within that journey. Do not reinterpret earlier R12 failure as a pass.

Independent `acceptance-r13.md` J53 also records the affected long-history check on5de8: semantic navigation reaches02 full19 lines/03 top, Latest remains available, and explicit Latest immediately shows10 full19 lines plus11/12 complete content with normal body AX and responsive Back. No history was added. The pre-existing no-pull historical-arrival/unread1 observation is retained from R10; this run does not claim a new incoming-message or exhaustive visible-read test. API unread0 alone remains insufficient to prove a message was visible. No repeated fixture or speculative full audit is requested.

R11-01 is now separately **closed by independent R12 evidence** for both existing M2 and the new real M3 late boundary before their corresponding requests; this supersedes R18's pending native closure only. R10-01's earlier Latest closure, R16 upload lifecycle source evidence, R8/R9 media/account evidence and all unaffected accepted scopes remain retained. Pending reminder/replay/other S1–S30 branches and physical phone/Mini signing/renewal retain their recorded limits.

## Remaining exit

The affected R12-01 and history/Latest checks are complete within independent R13's stated scope. No new bounded code issue or missing affected-delta evidence remains. **Overall product exits remain incomplete**, as the latest independent S1–S30 table records: remaining S12 metric/background branches, S27 reminder jump/replay scopes and other named scenarios still require their own evidence; physical phone and Mini renewal remain separately scheduled gates. These known exits are not additional code defects in this delta. No broader root-cause certainty or complete S12/S27 pass follows from the one tool journey. No design/current-spec correction is required, and no final verifier pass is granted.

Only reports were written. No implementation change or commit by this reviewer.
