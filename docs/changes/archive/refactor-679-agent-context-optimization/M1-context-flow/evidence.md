# M1 implementation and validation evidence

This is the caller's actual implementation/validation record, not a reconstructed worker log. Product acceptance and independent static decisions remain in their own reports.

## Source and scope

- Baseline: `4b27d962c1cc09a27a567619bd5cabc3db2ee934`, migrated from current Memory `unit/feat-676` at `c2a7fe3c3727db2c557a28915fda6ccee5e4298e`.
- Inherited implementation saved without loss as `4dda5de90`; owner-workspace Memory and native request fixture fixes in `b610b02b5`.
- `36cef9604` fixes typed `task.context.sync.result` correlation across the real Channels transport.
- `6dc940cf6` fixes transactionally persisted Task deletion notices, PA source synchronization before native Memory assembly, and running Schedule repair at the next native step. Gate 2 Round 6 approves the assembly timing adjustment.
- `6881952b9` gives current members a locatable revocation message while retaining the same-ID minimal projection for the lost source. Gate 2 Round 7 clarifies that historical revocation does not override later verified access; restored access does not resume paused work.
- Final destination remains `unit/feat-676`. No production deployment or production testing is included.

## Actual checks

All Node commands used v24.22.1. Python tools used the main checkout's existing `.venv`. Log locators are ignored local files under `output/refactor-679/`; they are evidence, not committed runtime data.

| Check | Command/scope | Actual result and locator |
|---|---|---|
| Owner workspace | `memory-documents.test.ts`, `memory-workspace-native.test.ts` | 8 pass; `recovery-fix.log` (later wire failures in that mixed log are superseded below) |
| Provider request | `context-revalidation-provider.test.ts` | 2 pass; document/current window reset and explicit legacy/native summary, actual HTTP Anthropic requests; `recovery-wire.log` |
| Preserved provider capture | Temporary exact test copy with only a `finally` JSON write, removed after checking byte equivalence | 2 pass; `provider-capture.log`, `provider-wire-DOCUMENT.json` (3 requests), `provider-wire-LEGACY.json` (4 requests, including summary). Actual HTTP serialization with controlled responses; not a real upstream-model payload claim. |
| Initial runtime regression | `pnpm exec vitest run --maxWorkers=3` | 175 files / 938 tests pass; 6 tests fail under concurrent load; `full-tests.log`. This is not represented as an all-green run. |
| Final runtime regression | `pnpm exec vitest run --maxWorkers=2` | 180 files / 949 tests pass; the new visible-revocation red test was collected while its fix was being developed and was the sole failure; `final-runtime-tests.log`. Its final implementation is validated by the 53-test run below. |
| Failed-file recheck | `history.test.ts`, Node `lifecycle.test.ts`, `agent-context-default.test.ts`, `model-setup.test.ts`, `global-child-tools.test.ts`, `task-execution-limits.test.ts`, `--maxWorkers=1` | 5 files / 12 tests pass; one transient child diagnostic in `global-child-tools` instead of events; `full-timeout-recheck.log`. Both child cases pass in the subsequent focused run below. |
| Channels regression | `packages/channels/tests/web-relay.test.ts` | 16 pass; prior missing reply mapping failed its bounded response deadline; `task-sync-green.log` |
| Source/Task fixes | Exact command below | 8 files / 41 tests pass; `final-fix-focused.log` |
| Deletion notices red | IM `task-execution.test.ts -t 'publishes one original deletion'` | Root/subtree deletion persisted no notice before fix; `task-delete-red.log` |
| Running repair | `task-reminder-batch.test.ts`, `global-child-tools.test.ts`, `--maxWorkers=1` | 2 files / 4 tests pass; `repair-child-focus.log`. Running repair captures actual next native model input containing the stable repair ID, task title, reason and exactly one Task package. |
| Existing repair/stop/child matrix | `task-reminder-batch.test.ts`, `schedule-deletion-native.test.ts`, `task-execution.test.ts` | 18 pass plus the new fixture failed because its allowlist omitted Task; `running-repair-green.log`. Corrected fixture passes above; the file name does not imply the earlier run was all green. |
| Visible revocation | IM `task-context-revocations`, `task-context-live`, `task-context-migration`, `task-execution`, `identity`, `e2e/conversation-tasks`, `--maxWorkers=1` | 6 files / 53 tests pass; `visible-revocation-green.log`. The new test fails before the fix (`visible-revocation-red.log`) and proves current members see the affected Agent/Task, while the same-ID lost-source relay and sync contain only the minimal fact. |
| Revocation wording and ingestion | PA `inbox.test.ts`, `task-context.test.ts`, `--maxWorkers=1` | 2 files / 18 tests pass; `eligibility-tests.log`. Actual restored-access model behavior remains a product acceptance check. |
| TypeScript build/typecheck | `pnpm build`; `pnpm typecheck` | Passed at `6dc940cf6`; `final-build.log`, `final-typecheck.log` |
| Shared iOS runtime | `pnpm check:ios-runtime` | Passed; `ios-runtime.log`. No native iOS source change; full simulator/archive not required. |
| Web regression | `npm --prefix src/IM/frontend run test -- --maxWorkers=2` | 108 files / 1,031 tests pass; `frontend-tests.log` |
| Web dependency audit | `npm --prefix src/IM/frontend audit --audit-level=critical` | Exit 0, no critical finding; 11 existing lower-severity advisories (4 low, 2 moderate, 5 high); `frontend-audit.log` |
| Python architecture/helpers | `pytest -m 'not e2e' -q` | 127 pass, 28 deselected; `python-tests.log` |
| Python formatting | `ruff check .`; `ruff format --check .` | Passed, 97 files formatted; `ruff-check.log`, `ruff-format.log` |
| Documentation | `./scripts/docs-check` | 292 maintained sources / 68 required routes pass before final archive; `docs-check-current.log` |

The eight-file source/Task regression command was:

```sh
pnpm exec vitest run \
  apps/im-server/tests/task-execution.test.ts \
  apps/im-server/tests/task-notifications.test.ts \
  apps/node/tests/global-inbox-native.test.ts \
  packages/dsh-integration/tests/task-context-originals.test.ts \
  packages/dsh-integration/tests/task-context-sync.test.ts \
  packages/dsh-integration/tests/context-order-provider.test.ts \
  packages/dsh-integration/tests/context-revalidation-provider.test.ts \
  packages/dsh-integration/tests/memory-child-runtime.test.ts --maxWorkers=1
```

It covers same-step PA generation/invalidation with no unread messages, claimed-input revocation, outage/stop/restart recovery, environment/catalog ordering, real window/summary request serialization, and same-child source invalidation. It ran before the one-line running-repair adjustment; the latter has the focused evidence above. Tests use controlled model transport unless explicitly identified as real-model product acceptance.

## Real stack and behavior boundary

The fixed daily stack is `/tmp/nano-refactor679-daily/.e2e-daily.json`, `http://127.0.0.1:64012`, node `wt-nano-refactor679-daily-89152`. P/E/Q use `gpt-6.1-sol high`, PA uses `gpt-6-astra medium`, with the normal Codex review path. The managed Node and isolated IM were restarted at `6dc940cf6` and `6881952b9`, preserving identity/data; process and health evidence is in `daily-final-restart.log` and `daily-eligibility-restart.log`. Independent browser actions, real model requests, source exclusion, notices and fixed-chat deliveries are recorded in `../acceptance.md`.

Mechanism tests establish deterministic boundaries; they do not establish model reliability for every branch. The representative actual model scenarios and any unrun/failed branches must remain explicit in acceptance. No service-health result is substituted for product behavior.

## Final documentation and lifecycle closure

Independent code review is `[]`; verification and corrected-delta are PASS/aligned at `6881952b9`, with R1–R6 product PASS and all five observed findings closed. The destination was fetched again and remains `unit/feat-676` at `c2a7fe3c3`; no source sync was needed. The three audited deltas were merged by exact Requirement name, the Gateway index counts were refreshed, and the entire unit was moved to archive with relative links migrated. These documentation-only changes retain the frozen gates. Final `scripts/docs-check` passed (283 maintained Markdown sources / 68 required routes); `scripts/check_change_unit_archived.py --head-ref codex/refactor-679-on-memory` and staged/unstaged `git diff --check` passed. Exact comparison confirms all seven merged Requirement blocks match the audited deltas.

The isolated daily stack was stopped via `scripts/e2e-down.sh --wt /tmp/nano-refactor679-daily`; no listener remains on port 64012 and its IM/Node/runtime PIDs are gone (`daily-shutdown.log`). Ignored local evidence is preserved at `/tmp/nano-refactor679-daily/evidence/` before disposable worktree cleanup. No production process or data was changed.
