# M1-recovery implementation evidence

## Scope and versions

- Nano implementation: `2ee87df7becb22f5d2576c192dbbee3018a3a07f`, based on `164352839cd8717748d4621a5d731780beb44b7e`.
- Plugin implementation: `51eb236`, based on `621278d`; candidate `dsh-agent-context@0.3.0-rc.2`.
- Candidate tgz SHA256: `5aa290fb5634cccccb6ed8f11b96acccac587fc708a420b80ecf29d2b2bf3461`. The same bytes were published at `https://github.com/Mrchen116/dsh-agent-context/releases/download/v0.3.0-rc.2/dsh-agent-context-0.3.0-rc.2.tgz`, downloaded and compared byte-for-byte. Nano dependency and lock now pin this URL with SHA512 integrity `x5kdNY6JaJliFp9U5S2FHk+anSQz+a9Ps1Zqc62ittJ08xFz7sVW8wnPNZnB3bxcQ39VStzZ/zgNPl969UZngA==`. No Nano application release was published.

## Changes and coverage

Plugin ordinary prompt contribution now contains stable window identity only. Current item references remain queryable through `get_context_remaining`, and the exhausted-window fallback retains its bounded reference snapshot. Notes writes no longer change the runtime contribution. Native compaction/environment reconstruction remains unchanged.

History adds session-local `turn_id` from the native `turn/start` event seq and an exact archive-only filter. Before replacement, the transaction emits bounded, body-free navigation for the current open turn when selected ordinary records belong to it. Recovery instructions require original input and prior delivery recovery before continuing or concluding; stale Notes cannot by themselves establish completion. Idle manual reset creates no interrupted task.

Nano restores used Skills as name/path navigation when the scoped `skill` tool is callable. Configurations that allow explicit `/skill:name` without `skill/read` retain full-body restoration. Only successful compaction brackets activate this recovery; existing Skill restrictions still apply.

Existing owner tests were extended, with no parallel milestone-specific suite: plugin engine/safety/history tests cover prompt growth, pressure/overflow and multi-window turn navigation; Nano model-policy test is parameterized across plugin enabled/disabled and skill callable/unavailable. Existing provenance, pairing, scopes, fallback, empty business allowlist and preset ownership tests remain.

## Reproduction and automated verification

All commands ran in the isolated implementation checkout on 2026-10-21. Raw logs are local evidence, not committed runtime data.

| Evidence | Result | Locator |
|---|---|---|
| Plugin red: engine/safety | 3 intended failures: progressive full context copies and missing interrupted-turn marker | `/tmp/bugfix629-plugin-red.log` |
| Nano red: callable Skill branch across both engines | 2 intended failures; 3 existing cases pass | `/tmp/bugfix629-nano-red.log` |
| Plugin typecheck/build/full tests | 26 passed | `/tmp/bugfix629-plugin-all.log` |
| Nano narrow native model-policy matrix | 5 passed | `/tmp/bugfix629-nano-green.log` |
| Nano build/typecheck/full native and IM suite | 484 tests in 107 files passed | `/tmp/bugfix629-build.log`, `/tmp/bugfix629-nano-typecheck.log`, `/tmp/bugfix629-nano-full-tests.log` |
| Python non-E2E helper/architecture suite | 62 passed, 31 deselected | `/tmp/bugfix629-pytests.log` |
| Frontend CI-equivalent tests/audit | 936 tests passed; critical audit gate passed (5 low, 1 high existing findings) | `/tmp/bugfix629-frontend-tests.log`, `/tmp/bugfix629-frontend-audit.log` |
| Documentation and Ruff | passed | `/tmp/bugfix629-docs-check.log`, `/tmp/bugfix629-ruff.log` |

## Actual native request comparison (scripted provider)

Baseline and fixed probes load a ~55k character Skill, perform native manual compaction, then run ordinary Notes/budget operations. Count only `messages[].content`, excluding duplicated provenance metadata in `source.sections`. Six post-reset requests:

| Variant | Full Skill body copies | Runtime snapshots | Visible request characters |
|---|---|---|---|
| Baseline rc.1 | 1,2,3,4,5,6 | 2,3,4,5,6,7 | 66,689 → 369,913 |
| Fixed, callable skill | 0,0,0,0,0,0 | 2,2,2,2,2,2 | 9,763 → 13,442 |
| Fixed, restricted workflow only | 1,1,1,1,1,1 | 2,2,2,2,2,2 | 67,974 → 71,403 |

Locators: `/tmp/bugfix629-baseline-counts.json`, `/tmp/bugfix629-fixed-counts.json`, `/tmp/bugfix629-restricted-counts.json`; each names its native capture home with `requests.jsonl`. Baseline raw rows counted serialized provenance twice; the table is corrected from actual message content and independently verified by static reviewer. These probes prove native request composition, not model task recovery. Real-model recovery/actual delivery belongs to the independent regression report.

## Isolated real-model fixture

Worktree-local IM and Node own separate ports/config/workspaces/identity/data. The PA uses default budgets, codexOAuth:gpt-6-astra medium, Auto off, disabled autonomous features. Seven synthetic Skills total 58,373 characters. A readonly journal fixture contains three pending tasks, one completed action and a large archive appendix; its actual output forces pressure before the model can save fresh Notes. Setup first encountered unknown Skill paths, corrected to `.nanoassistant/skills`; all seven were subsequently successfully loaded. Auto off correctly rejected both installation and execution of the custom fixture; its safe-tool set has no public custom-tool exemption. Environment setup preinstalled it, but the acceptance source was then exposed as the native readonly `skill` tool through `journal-archive/SKILL.md`, retaining the same journal data and default budget. The giant native Skill was spilled to ~50k characters and did not trigger pressure, so it also cannot count as pressure acceptance. A subsequent batch fixture uses 25 native Skill results of ~42k characters each (under the unchanged per-result cap), with three new pending tasks distributed across volumes 01/13/25; a real same-step batch can cross H before any model Notes write. No permission or spill policy was changed. These setup failures are not counted as product recovery passes.

Final package provenance, final sync and independent product outcomes are recorded during closure. No production state has been cleared or rewritten by this unit.
