# Validation and delivery record

## Authorized scope and baseline

- Sole isolated checkout: `/Users/czj/.codex/experiments/pa667-issue361/repository`; branch `codex/feat-625-ab-e2e`.
- Original shallow baseline: `5454f3140f9c92532c690db8dec80b9f77080384`. The owner explicitly requires no later implementation/history fetch before final delivery synchronization. Initial gates use this known baseline, **not a claim that current origin/main has been fetched**.
- Current workflow comes from the supplied read-only `current-workflow` snapshot. The original unit, independent design review, and implementation were produced from this baseline, not copied from an older feat-625 implementation.
- No merge, deployment, package publication, shared 4000 change, or change to `/tmp/pa667-issue361-runtime` is authorized or performed.

## Initial implementation freeze

| Field | Actual value |
|---|---|
| validated_at | `dfee3df40116757346ef6a7edcaa5d10734c9a61` |
| executed_base | `5454f3140f9c92532c690db8dec80b9f77080384` (authorized independent baseline) |
| working tree at freeze | clean; executor verified |
| diff check | clean |
| executor workspace build | `pnpm build`: passed |
| executor workspace typecheck | `pnpm typecheck`: passed |
| executor frozen full Node regression | `env -u NANO_OWNER_CONFIG_ROOT pnpm test`: 109 files / 494 tests passed, 58.60s |
| implementation narrow regression | 10 files / 49 tests passed; see [M1 evidence](M1-auto-review-retry/progress.md) |
| runtime dependency boundary | 13 tests passed; see M1 evidence |
| independent static / product gates | R1 dispatched against this freeze; pending, not passed |
| final sync / effective_base / effective_through | pending |
| PR / remote CI | not yet created / not yet run |

Node commands use the supplied Node 24 binary. Test commands unset inherited `NANO_OWNER_CONFIG_ROOT`; configuration expectations otherwise resolve the host Harness owner root rather than the isolated fixture root.

### Broader checks and environmental dispositions

- Pre-freeze full Node run: 108 files, 490 passed / 1 failed. The failure was the old context-window diagnostic substring. The final narrow fixture preserves no-verdict, config category, one attempt, zero extras, original return-to-agent denial, no overflow reviewer request and no overflow effect. See M1 validation history for the explicit before/after reason; no routing assertion was removed to hide failure.
- Unchanged frontend: 100 files / 936 tests passed, including interactive-asset check. `npm audit --audit-level=critical` exited successfully; 11 existing noncritical findings remain (4 low / 2 moderate / 5 high); no dependency changes were made to hide them.
- Python non-E2E baseline: 61 passed / 1 failed / 31 deselected. The sole failure is the diff-aware new-test-size gate attempting `git diff origin/main...HEAD` when the deliberately shallow isolated clone has no origin/main ref. It must be rerun after authorized final sync; this is not recorded as a passed gate.
- Ruff check and format check passed (83 Python files).
- Documentation integrity passed (244 maintained sources / 67 required routes before this record). The wrapper initially selected a Python without PyYAML; the same checker passed with the explicitly authorized installed interpreter. No dependency or product change was made to bypass it.

## Isolated product runtime proof

The baseline checkout lacks the current workflow's daily template/profile. The caller approved the existing default E2E stack as the available equivalent for this scoped global-Agent journey. Two dedicated global CC/Codex Agents, actual IM/Work entry points and isolated owner/workspaces are retained; this does **not** claim validation of the daily P/E/Q team fixture or unaffected team behavior.

- Own IM: `127.0.0.1:53939`, PID 95854. Its source and frontend source are unchanged by this unit; baseline-built artifacts and this isolated process are reused.
- After the frozen workspace build, executor restarted **only the own Node** with the explicit checkout-local `.gateway-config.yaml`.
- New Node PID 3657, DSH PID 3660 (child of 3657), state ready/connected. Prior Node/DSH PIDs 95896/95899 were confirmed exited.
- The DSH profile's `@nano/dsh-integration` link resolves to this checkout's `packages/dsh-integration`.
- Both dedicated Agents compile as global DeepSeek Flash execution, Auto enabled, skip disabled, unattended fallback deny; respective rules nano/CC and Codex. The reviewer is a separate Luna registration on the own fault proxy `127.0.0.1:56096`; main-model routing is unchanged.
- The proxy forwards healthy reviewer traffic to the already running 4000 service; it does not alter or restart that service. Its actual live probe returned HTTP 200/PONG before product acceptance. A probe is availability evidence, **not** a plugin-journey pass.
- Fault injection is scoped by planned tool name and a unique argument marker. Proxy HTTP request counts are not review attempt counts: CC stages and Guardian inspection steps can produce multiple model requests in one complete attempt. Synthetic verdict usage must be labeled synthetic, never live measurement.
- Product review uses the actual isolated public API used by the client, not policy helper calls. Public `session.observe` capture will be performed through the existing RuntimeClient only after the own Node and DSH are stopped and their exit confirmed. No private database read substitutes for that consumer.

Frozen compiled artifact SHA-256 values, unchanged before and after the own Node restart:

| Artifact (`packages/dsh-integration/lib/policy/`) | SHA-256 |
|---|---|
| approval.js | `c0b9a4efbc710834273deee4c393e739a3a33f653535ff45678cddd1c48a7bcd` |
| retry.js | `84120fcf5012f01bad50b6c41ed8f772be1fa1cc381205238b1c77455e8f4084` |
| classifier.js | `f1df526865a1f501b762abb7a33b54653307d4bf0493d6916fabfb0229bdd453` |
| codex.js | `3bbd2ba5ec9699739dafec2848e8ec599736e26424981eaff4106ff63e42c670` |

## Product availability and evidence-permission boundary

- The first real CC and Codex tasks on the default DeepSeek Flash execution model both stopped in turn 1 with HTTP 402 / QUOTA (Insufficient Balance), before any tool. This is a real main-provider availability failure, not a retry-feature pass or failure.
- The caller confirmed that DeepSeek was an execution default, not an original user constraint. The original failed roles/profiles are preserved; separately named isolated Sol/high execution roles with the same Luna reviewer are permitted using existing registrations/available quota. No recharge or shared-provider change is authorized. The product report must identify this substitution and its limits.
- An attempted raw Work/execution export by the product reviewer was explicitly denied by tool policy. That denial remains in force: no retry, tool/Agent substitution, splitting, or copying raw data into the report. Only permitted public read-only observation and the minimum necessary acceptance conclusions may be used.
- A proposed edit changing the public observe consumer to print only selected-call calculated metrics was also explicitly refused as another form of the same export. The replacement was not applied; that consumer is stopped and must not run. No live observe data was read or exported by it. This audit-consumer evidence gap remains open; it cannot be hidden by changing output paths, tools, Agents, or report formatting.
- Boundary clarification from the already-held receipts: the first refusal explicitly recognizes a bounded synthetic Work read and read-only inspection as a reasonable alternative; it rejects the additional complete-detail file retention. The second refusal cites a broader parent stdout prohibition than the parent's actual restriction against disguising a complete raw export. Those stated reasons are inconsistent in scope. The original isolated-regression and necessary read-only authorization still exists; this is not a finding that all synthetic-result viewing lacks owner permission. Nevertheless, the two specific refused methods remain stopped. Required real-attempt evidence is still missing, and no refusal is retried on this clarification alone.

## R1 evidence correction and isolated-route repair

- `pre_fix_head`: `af0f2c3324aa924b2d1fa27ef87a795bd83d24c8` (R1 reports preserved). The runtime product implementation remains byte-identical to `dfee3df40116757346ef6a7edcaa5d10734c9a61`; this batch changes only synthetic test evidence/capture assertions and reports, plus ignored local proxy infrastructure.
- **V-R1-2 RED:** the existing synthetic native test was extended to require the actual Guardian schema collection. It failed once because the prior fixture log omitted `tools` (`guardian-finish: expected undefined to equal guardian_list/read/stat`), not because the production Guardian lacked tools.
- The existing fixtures now retain complete actual native `llm/stream` composition: top-level system or system-bearing messages, full schemas, history, frozen model/options/action/session/call locators and final main-Agent tool-result messages. No live Work, actual user conversation or denied observation is used.
- New permitted synthetic artifacts: [retry Context](M1-auto-review-retry/native-context-evidence.json) and [Guardian Context](M1-auto-review-retry/guardian-context-evidence.json). The former contains 14 scenarios / 28 full stream snapshots (four preparation observations never reach a stream); the latter contains 18 full Guardian review compositions, including delta, concurrent fork, evidence rebuild, inspection, failed-cache/cancel and deadline cases.
- To avoid duplicating megabytes of identical policy text, these artifacts use `synthetic-context-text-pool-v1`: recursively replace an object whose sole key is `$syntheticText` with the complete string at `textPool[id]`. The decoded data is `payload`; the pool contains the actual text, **not only hashes**. The test-only writer asserts byte-identical JSON reconstruction before writing. Executor independently verified both decoded `payloadSha256` and the matching test-file `fixtureSourceSha256`. Final sizes are 310,816 / 205,733 bytes rather than repeated multi-megabyte policy copies.
- **GREEN:** the two changed fixtures passed together, 2 files / 2 tests, 17.24s. Earlier direct captures also passed (retry16.88s, Guardian4.62s); the final combined run additionally verifies the lossless evidence representation. No production constants, routing or permission rules changed. Documentation integrity passed (249 maintained sources / 67 required routes), diff-check clean.
- The previous artifact and R1 reports remain available; this new evidence does not rewrite an earlier failure as a pass. V-R1-2 still requires the independent reviewer to inspect the full semantics and close it. V-R1-1 still requires real product acceptance and its actual attempt evidence.

### Reviewer connectivity root cause

A new temporary, literal-only `READY` probe used the configured reviewer provider/model with low effort and no tools; it did not read any product Work/history/observe. It reproduced `PI_AI_ERROR` as HTTP404 from the own test proxy. The SDK requests `/v1/messages` with a query string; the initial proxy matched the entire URL with `endswith('/messages')` and rejected it **before writing its request record**. Thus the initial absence of a proxy record did not prove that no HTTP request reached the listener.

Executor changed only the ignored proxy to route using the parsed pathname, restarted only that owned proxy on56096, and reran the same new literal probe. It completed; the minimal infrastructure log confirms `/v1/messages`, query present, live HTTP200. Shared4000 and the Node/DSH processes were not modified for this repair. This establishes the local fixture's corrected SDK route, not a successful plugin journey. The raw/derived product-consumer refusals remain unchanged.

## R2 static closure and executor full regression

- Independent R2 static reports target `1862af639681defdb91651f50cc6e01459e63e0b`, retaining the original executed baseline. Code findings remain `[]`; V-R1-2 is closed after reconstruction and semantic inspection of the full synthetic Context. V-R1-1 remains open: overall verification is **NOT PASS, 1 CRITICAL / 0 WARNING** until independent product evidence is complete.
- Executor additionally reran the full Node regression on this corrected-evidence freeze: `env -u NANO_OWNER_CONFIG_ROOT pnpm test`, **109 files / 494 tests PASS**, 57.39s, exit0. Log: `/tmp/pa667-issue361-1862-tests.log`. This supplements, rather than relabels, the independent reviewer's explicitly reused narrow evidence.
- Real product R2 is still in progress; preliminary successful business results do not close its fault/cancellation/audit requirements. No fetch, archive, push or PR is implied by the static closure.

## Product R2/R3 completion and authorized audit correlation

- Independent product reviewer completed both real plugin journeys,24 business-tool fault/cancellation cases and6 installation-step recovery/auth/stop cases. The latter uses separate absent-before packages and formal post-install lists: recovery has one installed entry; auth/stop have zero. See [acceptance](acceptance.md); no implementation bug was found in these observed results.
- After new explicit owner authorization for this run's selected synthetic metrics, the original minimal consumer edit and its later execution both succeeded through normal permission checks. No raw snapshot retry, private database substitution or approval/Harness modification occurred. [Product audit metrics](product-audit-metrics.md) contains the necessary derived association only:36 selected calls,36 distinct reviewIds,62 actual attempts (18 calls/31 attempts per strategy), missing0.
- Backoff evidence was corrected in the original acceptance paragraphs/table, not only appended: injected Retry-After10s did not reach providerRetryAfterMs; actual delayAfterMs500ms. Actual failure-end/cancel timestamps establish cancellation before the500ms retry boundary. Independent reviewer closure remains required.
- Owned services were stopped only after the reviewer confirmed both sessions idle and injection/holds cleared: Node3657, DSH3660, IM95854, proxy7499. Verified all four absent and own ports53939/56096 closed before public RuntimeClient initialize. The consumer rejected business calls and shut down normally after read-only observe. Original isolated configuration/profile/state remain for reproducibility; shared4000 and Harness were untouched.
- This evidence-only batch still requires original independent product and static reviewers to close their prior verdicts. Earlier failures remain in the reports. No final sync, archive or PR before formal closure.

## R4 independent product closure

Original independent product reviewer issued full **PASS**,0 blocking/major/minor, on evidence freeze `86591326fb439a4cc68a651080980df8c1650df8`. It independently matched all36 call/review pairs to its observed Work and formal plugin lists, recounted62 attempts, confirmed500ms cancellation timing and the stage/usage distinctions, and accepted the design's native/fake-clock allocation without labeling it live testing. All seven product scenarios are closed in acceptance Round4. Original static reviewer then formally closed V-R1-1 and retained V-R1-2 closure: full verification **PASS,0 CRITICAL /0 WARNING /0 SUGGESTION**, on the same evidence freeze. Code findings remain `[]`. All initial applicable gates are now passed; final synchronization still requires separate invalidation assessment.

## Independence and pending work

- Original requirements/design author, design reviewer, implementation worker, independent static reviewer and independent product reviewer are distinct native Agents. Static review explicitly combines code-review and verification responsibilities with separate outputs; it is independent of implementation and product acceptance.
- Static and product R1 were started together on the frozen SHA. Native test evidence may be reused for its actual scope, never as a substitute for the independently observed real product journey.
- After initial implementation handoff, all subsequent fixes belong to the main executor, not a repair worker. Findings will be batched, a new version frozen, and affected gates revalidated with explicit retained-evidence reasoning.
- Final sync, gate invalidation assessment, corrected-delta verification, canonical merge, full local CI, archive, Ready PR and remote CI remain pending. Own test processes must be stopped at overall completion; the checkout remains for PR review.

## Final integrated feature gate and retained local CI

This section supersedes earlier pending-delivery checkpoints without changing their historical evidence. Latest independent product scope review and verification both PASS for #361; IV-1/IV-2 CLOSED, no in-scope critical/warning blockers. PA1 remains an unresolved ancillary major/unclear finding, not a new notification-behavior delivery requirement and not claimed fixed. See the final rounds in acceptance.md and verification.md for the explicit original-requirement mapping.

| Version/evidence | Final scope |
|---|---|
| Production implementation / integrated executed base | `334bf62260225e5c350aafe3bc8a23af66f1fda9` / `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5` |
| Scope correction validated_at | `5c1afb2024a5d2c0e6c96f89a2d809ce396471b2`; documentary adjudication, no new product run |
| Final main effective_base | `8d428779b5ebe0bb0c5c277f2ca5b56c0a303b82` |
| Main integration checkpoint | `c6f11c1cdb60fd79702c91784a96af915ae13b9f`; only unrelated change-unit docs added |
| Original design/code/Context/product gates | retained on unchanged production and actual evidence; corrected-delta reviewed PASS |
| Full Node regression | retained145 files/789 tests PASS, `pnpm test --maxWorkers=2`; earlier default-worker failures remain recorded, not rewritten |
| Frontend | retained108 files/1031 tests PASS, frozen dependencies/shared-contract build/production build/critical audit PASS;11 existing noncritical audit findings |
| Other local CI | retained build/typecheck, packaged iOS runtime, Python70/32 deselected, ruff check/88 format checks PASS |
| Production restoration | full build after removing temporary diagnostic PASS; production still matches334bf622 |
| Changed-document check | `PYTHON=<authorized Python> ./scripts/docs-check` PASS:305 maintained sources/68 required routes; diff-check PASS |

No code/test/config/CI/lock delta was introduced by the final main update, unit renumber or contract merge. Repeating unaffected full suites would add no changed-scope coverage; only documentary/archival checks are repeated. CI.yml's independent remote default-worker check remains required and is not replaced by the bounded-worker local result.

The atomic allocator reserved669 after latest main took668; the complete unit retains its evidence under `feat-669-auto-review-retry`. The two independently corrected tool-retry requirements are now in canonical gateway agent-capabilities, with index count49. All task-owned runtime processes are stopped, no temporary diagnostic remains, and the isolated checkout is retained for PR review. The original independent static reviewer subsequently verified all19 unit paths, byte-identical JSON evidence, exact canonical/delta equality and unchanged production; all applicable gates are retained. Original product reviewer independently retained its scoped PASS for the documentation-only update. The complete unit is now archived at `docs/changes/archive/feat-669-auto-review-retry`; post-move documentation integrity PASS (292 maintained sources/68 required routes), explicit `check_change_unit_archived.py --head-ref unit/feat-669` PASS and diff-check PASS. This satisfies archival independently of the legacy branch name. Effective-through is the final documentation/archival delivery commit shown in the PR; no production changes follow c6f11c1. Actual PR and remote-CI outcomes are reported from their receipts, not inferred from these checks.
