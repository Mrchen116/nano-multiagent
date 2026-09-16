# Code review — refactor-564

## Full review and closure

- Scope: origin/main through integrated feat-563 plus refactor implementation, including the uncommitted tree frozen as `6ee83e2e3`.
- Independent finder: `/root/code_finder_564`; independent candidate/closure verifier: `/root/code_verify_564`. Neither implemented the reviewed changes.
- Three confirmed findings were fixed: ordinary group input arriving during preparation lacked a final guard; manual permission waiting blocked its own approval-card events; protocol silence was treated as an unconfirmed send.
- Closure: **PASS, no surviving findings (`[]`)**. The verifier independently ran 15 focused tests, replayed its stale-input composed probe, and checked real composed `NO_REPLY`/`HEARTBEAT_OK` event chains.
- Final mechanisms: actual pending-input IDs fence group candidates until the matching consumption receipt; a permission-only event subscriber presents and deduplicates approval process events; visibility decisions precede any resource or channel operation.
- Evidence: `/private/tmp/refactor564-code-candidates.md`, `/private/tmp/refactor564-probe.py`, `/tmp/verify_564_stale.py`; permanent regressions are `test_pa_delivery_manual_permission.py`, `test_pa_delivery_input_admission.py`, `test_pa_reply_delivery.py`, and `test_candidate_observer.py`.

Product acceptance and implementation verification remain separate gates.

## Background correction patch

- review_mode: patch; diff_range: `6ee83e2e3..c2d8c1422`; executed_base: `c4ba604625001290f0191be06ae7ad741c9b4626`.
- Independent finder `/root/code_finder_564` returned `[]`, with 24 focused tests passed. No candidate required a separate confirmation round.
- Covered all background adoption, USER-origin feedback successors on the persistent subscriber, original provider/shadow routes, deletion of the raw publication path, and complete-round sidecar retention.
- Earlier three closed findings retain validity; the shared permission/new-input paths were exercised again by implementation verification (36 tests plus the final two provider-route cases).

## Host permission context patch

- review_mode: patch; diff_range: `c2d8c1422..150fbe30d`; executed_base unchanged.
- Independent finder `/root/code_finder_564` returned `[]`; 12 SDK/PA tests passed.
- Verified that SDK-provided operation description travels through a separate typed HookContext field, cannot be set by model arguments/session metadata, retains tool policy/full action, and does not bypass explicit deny/ask.
- This closes the implementation mechanism behind product P1; actual classifier behavior remains subject to product revalidation.

## Background return projection patch

- review_mode: patch; diff_range: `150fbe30d..d4a59af21`; executed_base unchanged.
- Independent finder `/root/code_finder_564` returned `[]`; the three new strict-protocol/Bash/manual-approval regressions passed independently.
- The observer copies the input event and projects only the IM-supported subagent/workflow return cards. Kernel notification content and ordinary text remain intact, and both initial-run and consumed-input entry points retain supported cards.
