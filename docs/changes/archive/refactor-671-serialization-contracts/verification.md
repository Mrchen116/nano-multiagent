# Verification Report: refactor-671-serialization-contracts

> Validation snapshot: `ff326c351d104447028f4b185740ab6d6be55de6 → 8289e5634b64c64c18d421eff58801b2a2c745b1`

## Metadata

- Independent verifier, same assignment as the independent code reviewer; no participation in implementation.
- Initial verification mode: `full`, including corrected-delta / no-spec-delta reconciliation; review round 1.
- Latest verification mode: `targeted-closure`, review round 2; focus issue `V1` only. No product or full-suite test was rerun by this closure reviewer.
- Branch/worktree: `codex/serialization-contracts`, `/Users/czj/.codex/worktrees/serialization-contracts/nano-multiagent`.
- Frozen HEAD matched `validated_at`; capture baseline is `a34af8473c15f1145d6a1dbbc036bc320560f351`.
- Inputs: `motivation.md`, approved R2 `design.md` / `design-review.md`, `M1-serialization/implementation.md`, complete frozen diff, `SPEC.md`, applicable current specs and testing/Context rules.
- `requires_full_verification: false`; full verification is already the requested scope. No implementation/design mismatch found.
- Report commit: none; shared worktree reports are handed uncommitted to the caller.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All M1 exit criteria covered; V1 closed by completed full-suite evidence |
| Correctness | All scoped byte/crypto/persistence invariants covered; no mismatch found |
| Coherence | Follows approved design and package boundaries |
| Final verdict | **pass** — 0 open CRITICAL / 0 WARNING / 0 SUGGESTION; ready for PR |

## Completeness

The single M1 is implemented and all exit criteria now pass. Round 1 correctly remained pending because the necessary backend CI evidence was incomplete; round 2 closes that evidence gap without changing the frozen source or the original review findings.

| M1 exit standard (`design.md:86`) | Direct evidence | Status |
|---|---|---|
| Zero user surface; no product reviewer | Frozen diff only changes pure serialization ownership, imports/names and regression tests; no HTTP/WS/storage/auth flow change. Product reviewer N/A per approved design. | pass |
| Task no longer exports a generic serializer | `apps/im-server/src/task-graphs.ts:1`; original definition removed; no remaining source `canonicalJson` references. | pass |
| Every live caller uses the intended encoding | Complete changed-caller trace and original root-export resolution; map in `code-review.md`. | pass |
| Unicode/nested fixed bytes | Contracts tests at `serialization.test.ts:5,11`; identity at `identity.test.ts:449`; old-function comparison metadata with 12 inputs/four encoders. | pass |
| Configuration and idempotency digests unchanged | `approval-configuration.test.ts:67`, `message-attempts.test.ts:58`, existing PA configuration fixed SHA/recovery tests, historic Workflow key replay at `workflow-control.test.ts:121`. | pass |
| Historic envelopes and IM→ChannelKey interoperability | `channel-credentials.test.ts:22`, fixture baseline metadata and `control.test.ts:516`; independent decryption also pins actual AAD/plaintext bytes. | pass |
| Crypto stays with each owner and is unchanged | Frozen production diff changes only encoder references/names; key derivation, versions, contexts, salt/nonce, auth tag and AAD projections unchanged. | pass |
| Necessary CI passes | Prior successful checks retained; the same complete root Vitest suite passed at `--maxWorkers=2`, exit 0, 144 files / 780 tests, on the unchanged frozen source. | pass |

Prototype/reference: N/A. No UI prototype, real product journey or frontend must-match contract is introduced by this refactor.

## Correctness

| Requirement / scenario | Implementation / test evidence | Status |
|---|---|---|
| Motivation: maintain wire bytes and persistent fingerprints without migration | `serialization.ts:12,33`; `configuration.ts:30,50`; fixed fingerprints and historic receipt recovery; no migration/schema diff. | covered |
| Motivation: meaningful Unicode and nested-input compatibility | Exact original-body comparison plus fixed test vectors cover UTF-16 ordering, numeric-key JS enumeration, recursive/array semantics, boundary escaping and original traversal differences. | covered |
| Motivation: preserve credential envelopes, AAD and shallow semantics | IM Channels uses unchanged UTF-8 replacer; ChannelKey/Node retain shallow encoder; fixed pre-change IM/node envelopes and independent-byte interop tests. | covered |
| Motivation: preserve Task recovery and Workflow durable call keys | `task-graphs.ts:514,627,819,1011`, migration comparisons and `workflow/control.ts:128-157` keep their original data projections; fixed old Workflow completion is selected without a new child. | covered |
| Current IM config durable receipt semantics (`docs/specs/im/agents-nodes.md:105`) | Fingerprint algorithm and normalization unchanged; current PA recovery tests retained and passed. | covered |
| Current device binding ownership/proof semantics (`docs/specs/im/agents-nodes.md`, “设备绑定把节点归属到当前用户”) | `identity.ts:96,647,761,792,809` retains DEL encoding and proof/snapshot projections; existing identity proof/transfer tests plus historic bytes passed. | covered |
| Current managed channel encrypted cache/restart semantics (`docs/specs/gateway/external-channels.md:424-438`) | No lifecycle/cache changes; fixed envelopes open after key reload; altered owner/revision rejected. | covered |
| Current persistent Task facts (`docs/specs/im/task-graphs.md:37-45`) | Only equal encoding replacement; no mutation, storage or transaction changes. Existing Task/migration protections retained in the complete passing 144-file / 780-test suite. | covered |

## Coherence

| Approved design decision | Evidence | Result |
|---|---|---|
| Two pure, explicit, option-free shared functions | `serialization.ts` has exactly `sortedJsonUtf8` and `sortedJsonAscii`, no imports or crypto; public subpath declared at `package.json:23`. | followed |
| Retain DEL and native/pre-traversal differences | Shared UTF-8/ASCII bodies preserve original algorithms; candidate owner retains DEL regex and identity adds only DEL; direct comparison/test vectors pass. | followed |
| Keep shallow encoders local | `packages/channels/src/channel-credentials.ts:65`, `apps/node/src/device-binding.ts:44` only rename original bodies. | followed |
| Remove Task ownership and unused ambiguous interactive encoder | Live imports moved to declared contracts subpath; old generic exports removed; no remaining live canonicalJson callsite. | followed |
| No unrelated Row/ImContext, Gateway split or runtime boundary change | Full diff is limited to scoped ownership/encoding references/tests and docs; independent dependency contract 13 passed. | followed |
| Test at meaningful seams; preserve existing protections | New shared pure seam has fixed vectors, existing owner tests extended, real cross-owner interop covered, no meaningful regression test deleted. | followed |

The limited Context applicability analysis is reused from `code-review.md`: PA Inbox/publication and Workflow replay keep the same projections, bytes and selection/timing. No Context delta or model-behavior claim.

## Validation evidence

All paths below are ignored local evidence under `output/refactor-671/`; fixed vectors and synthetic historical envelope fixtures are committed tests. Logs are evidence for this frozen source tree, not a substitute for their reported completion status.

| Command / method | Result | Locator |
|---|---|---|
| Independent old-Git-body vs built-new-function comparison | pass; 12 inputs × 4 encoders; 5 captured byte values checked against original functions | `reviewer-equivalence.json` (records both SHAs and method) |
| Independent `pnpm exec vitest run` for contracts serialization, Channels credential, IM approval/control/identity/message-attempt, Workflow control and PA configuration files, `--reporter=dot` | 8 files / 56 passed, Node 24.22.1 | `reviewer-narrow.log` |
| Independent `.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q` | 13 passed | reviewer tool result; 1.77 seconds |
| `pnpm build` | pass; built installer candidate explicitly identifies frozen SHA | `build.log` |
| `pnpm typecheck` | pass | `typecheck.log` |
| `pnpm check:ios-runtime` | pass, per caller completed command; log contains command only | `ios-runtime.log` |
| Frontend `npm test` (with interactive asset pretest) | 108 files / 1029 passed | `frontend-tests.log` |
| Frontend audit at critical threshold | gate passes per caller; 11 vulnerabilities remain (5 high, no critical). No dependency/lockfile diff. | `frontend-audit.log` |
| Python non-E2E | 100 passed / 28 deselected | `python-tests.log` |
| Docs check using existing `.venv`; two ruff checks | pass per caller's completed command report; no direct logs supplied to this reviewer | caller handoff |
| `git diff --check` on frozen range | pass | independent reviewer tool result |
| Default-concurrency root `pnpm test` | Native-integration timeouts occurred; caller stopped run with SIGINT, exit 130. This run did not pass and is retained as initial evidence. | `backend-tests.log`; caller exit-status handoff |
| Four earliest failing files: `pnpm exec vitest run <four files> --maxWorkers=1` | 4 files / 22 tests passed, 110.50s; exit 0 per caller | `isolation-tests.log` |
| Complete root suite: `pnpm exec vitest run --maxWorkers=2` | **144 files / 780 tests passed**, 369.22s; exit 0 per caller | `backend-controlled.log`; final summary inspected by closure reviewer |

The baseline scripts `capture.ts` and `workflow-capture.ts` import original owners and describe pre-change generation; fixed values are not generated by the new encoder during tests. Original baseline Git objects remain readable, and there is no difference in their four relevant original function source files between capture baseline and executed base. The fixture private key is synthetic offline test material, never an account/service key.

## Issues

### CRITICAL

None open. Initial V1 is closed in round 2; its original pending state and closure evidence are preserved below.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `design.md:59`: no spec delta | Full diff introduces an explicit private-package API and replaces internal names/imports; existing wire fields, persistent encodings/projections, crypto, storage, authorization and model Context semantics stay unchanged. Current SPEC dependency directions are retained. | Original-body comparison, fixed hashes/bytes, historic envelopes, historic replay and dependency contract above. | aligned — no spec delta |

### Uncovered Observable Behavior

None found in the frozen unit diff. Removal of unused/ambiguous private-package exports is the intended internal API refactor, not an omitted product behavior delta. No current spec change is needed to legitimize this implementation. The initial full-CI evidence gap was closed in round 2 and does not alter the no-spec-delta conclusion.

Outcome: **aligned**. Overall full-verification verdict after targeted closure: **pass**.


## Review record and V1 targeted closure

### Round 1 — full verification

- Snapshot: `ff326c351d104447028f4b185740ab6d6be55de6 → 8289e5634b64c64c18d421eff58801b2a2c745b1`.
- Initial verdict: **pending**, with one CRITICAL evidence item, V1, because `design.md:68,86` requires necessary CI and the default concurrent backend run had no passing final summary.
- Initial finding: “Necessary backend CI is not yet established.” It was an incomplete exit criterion, not a confirmed serialization defect. The original default-concurrency failures remain recorded in `backend-tests.log`; no later passing run retroactively changes that result.

### Round 2 — targeted-closure of V1

- Verification mode: `targeted-closure`; focus issues: `[V1]`; prior report: this report's round 1 record.
- Executed base remains `ff326c351d104447028f4b185740ab6d6be55de6`; validated/finding-origin head remains `8289e5634b64c64c18d421eff58801b2a2c745b1`; actual checkout HEAD was independently rechecked and matches.
- Fix delta: none in product source, tests, thresholds or design. Closure delta consists only of completed execution evidence and this report update. Source freeze validity extends to the original frozen tree; later documentation archival and PR `effective_through` decisions belong to the caller.
- Method: read `backend-controlled.log`, `isolation-tests.log` and retained `backend-tests.log`; reuse unchanged earlier check evidence. No product execution or full implementation re-review performed.
- Evidence: the same complete suite with `pnpm exec vitest run --maxWorkers=2` passed 144 files / 780 tests in 369.22 seconds, exit 0 per caller. Earlier four-file isolation passed 4 files / 22 tests in 110.50 seconds with `--maxWorkers=1`, exit 0 per caller. The complete passing run, rather than the four-file subset alone, fulfills the exit criterion.
- Limits: concurrent local work and caller-observed load sample 49.85 are consistent with resource contention, but are not proof of a unique root cause for the original native timeouts. This closure makes no such root-cause claim and does not claim the original default-concurrency run passed.
- V1 status: **closed**. `requires_full_verification: false`; no shared-boundary change or new mismatch invalidates the prior static/compatibility verification.
- Final result: **pass**, 0 open CRITICAL / 0 WARNING / 0 SUGGESTION. All checks passed. Ready for PR.
