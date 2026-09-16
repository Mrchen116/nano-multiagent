# M1 implementation and evidence

## Implementation

- `c8586a429`: shared Runtime context, authenticated IM public URL, ordinary model-round callback, permission reuse, descriptor-bound snapshots, private failure recovery, explicit image preparation and receipts.
- `23a1c39bc`: durable replay consumer, shadow manifest aliases, same-text unresolved identities, provider replay deadline, lifecycle reply bookkeeping, and integration coverage.
- `27de0ec4c`: permission/preparation for external replies before an IM shadow anchor exists.
- `270677318`: bounded diagnostic source data and escaped reminder delimiters.
- `8b99f43eb`: recovered offline image shadows finish with the correct completed footer while preserving kernel pending/partial receipts.
- No production deployment or persistent user configuration change.

## Red-to-green evidence

- Runtime/address regression tests failed before the new context/registration fields and passed after wiring.
- Core callback tests established failure before same-run continuation; exact prior new-input reminder remains protected.
- Ordinary owner tests first failed on the missing delivery module; source failure, permission denial, stale-after-upload and descriptor replacement now pass.
- Real composed pipeline reproduced empty final lifecycle text after successfully managed image delivery; regression now requires the actual reply and absence of `empty_visible_reply`.
- Real Feishu acceptance reproduced a failed footer after successful offline shadow recovery; both anchored and unanchored regressions failed before the correction and passed afterward (16 related tests).
- Independent verifier reproduced the missing-anchor offline bypass; both anchored/unanchored cases now perform one permission decision, one external delivery, and source-independent shadow catch-up.

## Verification evidence

- Final non-E2E Python suite on `8b99f43eb`: **3952 passed, 31 warnings in 110.21s**.
- Final focused integration/recovery batch: 19 passed; anchored/unanchored offline cases: 2 passed.
- Frontend: 83 files / 770 tests passed; build passed; critical-level dependency audit passed (no dependency changes).
- Ruff lint/format and diff whitespace checks passed; documentation integrity is rechecked after canonical merge/archive.
- Independent [verification](../verification.md): Round 4 PASS, corrected-delta aligned, no remaining critical/warning.
- Independent [code review](../code-review.md): PASS, no surviving candidates.
- Real product results and per-scenario evidence are owned by [acceptance](../acceptance.md).

## Runtime isolation

Primary fixture uses the unit worktree, unique IM ports/node/config/workspaces and dedicated test Feishu profile. Second fixture uses `/private/tmp/feat563-second-node` with separate IM/Gateway/node/workspaces and global/denied-image agents. Runtime files, credentials, screenshots, dependencies and databases are not deliverables. Owners clean their fixture processes after acceptance.

## Final validation scope

- `validated_at: 8b99f43eb` (final source); `executed_base: 0014ee0b0`; `effective_base: 0014ee0b0`.
- Final sync found unchanged origin/main. Later report/canonical/archive edits change documentation only; source validation remains effective through the delivery commit.
- Independent implementation verification and delta code review PASS; corrected-delta reconciliation aligned. Product evidence remains in the independent acceptance report.
