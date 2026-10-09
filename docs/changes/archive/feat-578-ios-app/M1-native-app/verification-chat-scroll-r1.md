# Verification Report: feat-578 Latest scroll candidate

Validation snapshot: `ff866a80a → 33b6e64f4938260ce6fd2113f82c005ff9b9ccc0`.

Mode: delta review/verification of the one-line Latest action, with necessary direct scrolling context and independent `acceptance-r10.md`. Scope excludes a full source re-audit or product operation. `requires_full_verification: false`. Static code review finds no new concrete defect (`code-review-r17.json` is `[]`); **overall verification remains not_pass** because observed R10-01 is not yet product-closed.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Candidate removes explicit animation; actual latest-message reachability/responsiveness closure pending |
| Correctness | Same bottom target/anchor and action condition retained; no data/read/API change. Static source cannot establish actual scroll completion or fix the observed layout stall |
| Coherence | Candidate aligns with existing non-animated automatic-follow/pagination paths; S6 visible-read contract and S7 stable-history contract remain binding |

## Bounded code review

Only product delta is `ConversationView.swift:55`: `withAnimation { scroll.scrollTo("bottom", anchor: .bottom) }` becomes `scroll.scrollTo("bottom", anchor: .bottom)`. Same button, accessibility label, visibility condition, reader, bottom target ID and bottom anchor remain. The target is still defined at lines 49–51. Automatic following at lines 57–60 and older-history anchor restoration at lines 29–33 already call scrollTo without this explicit animation wrapper. Removing the wrapper does not change the destination or introduce new authorization, network, identity, draft or message mutation behavior.

The action still relies on the existing rendered bottom sentinel and message `.onAppear` read callbacks; it does not directly mark a requested destination read. These mechanisms are unchanged and were read solely as necessary context. There is no new actionable source finding in this bounded diff. This conclusion does not certify that SwiftUI now reaches the target or that the pre-existing onAppear/read behavior passes real visibility requirements.

## Contract and actual evidence

| Contract / observation | Evidence | Status |
|---|---|---|
| `spec.md:84–86` S6: unread advances only to actually seen content; new messages do not force history to bottom | Independent `acceptance-r10.md` J46: early02/03 retained when unique11 arrives, with authoritative unread1 | That bounded historical-position observation retained |
| S6 Latest operation must produce actual usable reading | R10-01: clicking Latest on old native2505c9772 leaves08/09,11 unseen; body AX unavailable; process near99% CPU; sample in SwiftUI/AttributeGraph/LazyStack. Authoritative unread0 is explicitly not visual proof | **not closed**; candidate requires same-data native retest |
| `spec.md:88–90` S7 history order/pagination position/live consistency | Candidate keeps all item IDs, page load/restore, merge/API, bottom-follow conditions unchanged | No static regression introduced; existing relevant evidence retained |
| Candidate compiles | `/tmp/nano-feat578-latest-scroll-build-r10.log` ends `** BUILD SUCCEEDED **` | Actual build evidence; not UI closure |

The sample supports a layout-busy observation; neither it nor source review proves explicit animation was the sole cause. This is a minimal A/B candidate. No new full native test run or view-wiring mirror test was requested: core26/sourceR16 and applicable R8/R9 attachment/account evidence remain valid within their recorded scope. A build and retained green source tests cannot replace this rendered scroll regression check.

## Remaining issue and exit

**CRITICAL SC-C1 — R10-01 major product finding remains pending actual closure.** Use the same dedicated synthetic long-history conversation, return to its early02 position, confirm latest11 is outside the visible region, then click Latest on installed33b6 candidate. Independently prove11 actually appears, the App and body AX remain responsive and subsequent navigation/scrolling works. Correlate actual visible result with the authoritative unread state; unread0 alone cannot close S6. If this minimal candidate does not resolve the observed behavior, root should continue the concrete layout diagnosis from that reproduced scene rather than declaring source closure.

S7/S12/S27 remaining branches were not executed in R10 and remain as that independent report records. Earlier unaffected static, scoped visual, management, attachment and account conclusions are retained; S11's later R8/R9 product evidence is not reopened. Physical installation/renewal and remaining overall gates remain separately pending, without repeating already-green source checks. No full S1–S30, physical device, Mini renewal or final verifier pass is granted.

This reviewer performed code/document/log review only, with no UI/service/test execution, implementation edit or commit.
