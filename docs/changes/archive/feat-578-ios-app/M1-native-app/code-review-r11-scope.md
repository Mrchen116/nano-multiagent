# R11 bounded operation/feedback delta review

> Scope: `f8401b88a..ba202f5d32220070b97144ad5e1cbe61194d5dd6`, only the two fingerprint functions, associated cross-end regression, and AgentConfigView status scrolling with their direct canonical/apply/state context. No full source review, UI operation, implementation change or commit.

Result: `code-review-r11.json` is `[]`; no concrete surviving defect in this delta. Previous conclusions are retained where unaffected. This establishes static correction and regression coverage, not actual conflict/success feedback visibility or final product acceptance.

## Fingerprint and clear semantics

IM `candidate_fingerprint` first builds a fresh `gateway_candidate` projection; PA `agent_operation_fingerprint` first builds a fresh canonical operation projection. Each now maps canonical heartbeat_json `"{}"` to None only in that local hash input. Existing canonical JSON formatting happens before the comparison, so formatting whitespace/order does not create a second empty-object case. Neither function mutates the input candidate, the canonical/wire helper's return contract or the persistence/apply functions.

The runtime snapshot helper `_heartbeat_json_for_agent` returns None when every/active_hours are both absent. The observed persisted empty object and that snapshot therefore describe the same absent cadence, while nonempty cadence remains represented and hashed. Cross-end normalization makes the committed empty cadence comparable to the actual runtime default snapshot; it does not suppress differences in populated cadence or other fields. The reviewed coordinator still sends `gateway_candidate(candidate)` as its request payload; it is not sending the locally modified fingerprint projection.

Explicit `{}` still reaches the update/apply path as an empty object; None retains its existing separate handling. No new universal `{}`→None payload rewrite was added. The narrow fix does not change feature enablement, saved profile_version, operation ownership, previous-state checks, canonical persistence or the Gateway acknowledgment payload. It fixes state comparison, not an observed/desired-state UI status by assertion.

The new cross-end regression calls the actual IM and PA functions in both directions, proving `{}`/None fingerprint equality. It also proves populated `24h` differs and that `gateway_candidate(empty)` still emits `"{}"` on the wire. This is an observable protocol invariant, not a mirrored hashing implementation test. `/tmp/nano-feat578-heartbeat-empty-red.log` records the original unequal hashes; `/tmp/nano-feat578-heartbeat-empty-green.log` reports 50 passing configuration-operation/recovery/contract/integration tests after the fix. These focused results are reused; no full suite was rerun here.

## Native status feedback

`AgentConfigView` wraps the existing Form in ScrollViewReader, adds a stable ID to the already present status/recovery Section, and scrolls to it when error becomes non-nil or saved becomes true. The Section continues to contain the same error, saved, pending, conflict, reload, inspect/keep/replace, preview and busy controls. Existing toolbar-save guards, dirty draft handling, editor disablement, cancellation and save/reconcile methods are unchanged.

Thus a save rejection or confirmed result now requests a scroll to its existing feedback instead of creating a new status or silently treating pending as success. The same error message can still reappear after save clears error; saved=false reset is ignored and saved=true is handled. If initial loading fails before config exists, the existing top-level error path remains; the change does not remove that feedback or alter error recovery.

`/tmp/nano-feat578-functional-build-r6.log` ends with `** BUILD SUCCEEDED **`. Actual installation and independent native conflict/success/pending feedback retest are still required. Source-level scrollTo and compilation cannot prove the result is visibly placed after layout or that all keyboard/font states remain correct.

## Retained boundaries

No final verifier result is changed. P6 evidence for unchanged pages and R7–R10 conclusions remain scoped to their previous versions/evidence; the directly modified config feedback needs its new narrow UI evidence. The real operation_conflict and readback reports are not rewritten as passed before that rerun. Full product scenarios, physical phone, Mini/free signing/renewal/expiry and user final visual opinion remain open as previously recorded.
