# M1 validation

## Frozen implementation and scope

- Base `08b06c57b` (Gate 2 closed); implementation `da1c2f3c1`, `4289f1896`, `ccf74c47c`; fixes `8aa3c8149`, `ba88c18bc`.
- After `ba88c18bc`, product source is unchanged; subsequent changes add targeted execution evidence and merge the independently aligned delta into canonical specs.
- Runtime build: `pnpm build` and `pnpm typecheck`, both pass. Logs `/tmp/feat615-build.log`, `/tmp/feat615-typecheck.log`. Frontend final source build `/tmp/feat615-ui-build.log` passed. Local Node 25.8.2; CI uses Node 24 backend / Node 20 frontend.
- Isolated final node started 2026-10-16 00:53:13 +08:00, PID57536, native DSH57540; gateway.log has ready/register. This load includes manual approval projection and complete-turn usage extraction. Independent reviewer then completed third-round Codex gamma→delta with persisted file and delivered reply, audit usage available. No production restart/deploy.

## Checks and retained evidence

| Check | Result | Local raw evidence |
|---|---|---|
| Full runtime/IM/Node Vitest (`pnpm exec vitest run --maxWorkers=2`) | 93 files / 346 tests pass | `/tmp/feat615-backend-serial.log` |
| Full frontend (`npm test`) | 96 files / 887 tests pass | `/tmp/feat615-frontend-tests.log` |
| Python (`pytest -m 'not e2e' -q`) | 56 pass, 31 deselected | `/tmp/feat615-python-tests.log` |
| Ruff check / format | pass, 83 files formatted | command output |
| Frontend dependency audit, critical threshold | 0 vulnerabilities | `/tmp/feat615-audit.log` |
| Documentation integrity | pass | `scripts/docs-check` |
| Final source-projection targeted test | 7 pass | `/tmp/feat615-static-source-closure.log` |
| Header save error targeted UI | 5 pass | `/tmp/feat615-ui-retest2.log` |
| Native guardian final scenarios | 1 composite test pass, 92.59s | `/tmp/feat615-native-final.log` |
| Native CC real symlink/outside/downstream constraints | 2 pass | `/tmp/feat615-native-paths.log` |
| Native manual approval while switching strategy | 6 pass | `/tmp/feat615-native-manual-switch-final.log` |

Full suite initially ran in parallel with frontend and produced 11 timeout failures; original output retained in `/tmp/feat615-backend-tests.log`. Reduced worker count full rerun passed. Subsequent final source changes were covered by the targeted tests above, not assumed valid merely from earlier full results. The 90-second deadline check uses the actual native DSH process: a read-only inspection occurs, the next model response stalls until its abort signal, and no late allow or effect survives; the reviewer is disposed before completion. The same test verifies out-of-order distinct allow/deny checks, full/delta/fork, invalid verdict, provider overflow rebuild, and parent cancellation.

Manual approval freeze test holds the native request unanswered, starts configuration.apply to Codex, proves it remains pending, answers the original request, verifies the original CC action/callId and human audit, then rejects a repeated late answer. First test draft attempted to rebind the persisted old session to a new preset during the separate cold-restart assertion; its failure is retained in `/tmp/feat615-native-manual-switch.log`. Corrected fixture keeps the immutable original binding; the pending approval checks are unchanged.

Usage assertion first used the provider key `inputTokens` for the native aggregate, whose public field is `uncachedInputTokens`. The first real 90-second run passed timeout/no-effect checks then failed this assertion; `/tmp/feat615-native-deadline.log` retained. Final assertion uses the published aggregate field and all checks pass.

## Evidence boundaries

Real-model A/B and user-visible effects are in [comparison.md](comparison.md). Independent visual/chat acceptance is [acceptance.md](../acceptance.md). Fixture-model native integration proves scheduling, dispatch, safety-tool constraints and failure handling; it is not a distributional quality claim. Context retention/admission and rewritten-history rebuild also have focused unit/lifecycle tests; an automatic native compaction transaction was not independently forced in this run. Provider overflow is directly forced through the real runtime and recovers with full parent evidence.

Main checkout dirty files were not staged or reset. Temporary config, credentials, logs, screenshots, DBs and runtime directories are excluded from commits. Isolated services were stopped using e2e-down; scoped sessions/audit/gateway log were copied to `/tmp/feat615-runtime-evidence` before checkout cleanup. Final typecheck `/tmp/feat615-final-typecheck.log` and documentation/ruff checks passed. Worktree-owned processes are stopped at delivery; evidence reports and reproducible synthetic drivers remain in the unit.
