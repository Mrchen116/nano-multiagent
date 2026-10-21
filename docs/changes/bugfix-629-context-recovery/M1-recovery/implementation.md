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


## R3 user-directed revision (supersedes rc.2 recovery behavior)

- Design R3 approved; user requires native catalogs and original Notes/History, with no extra used-Skill restore and no interrupted_turn.
- Nano source c2a7d2a6c: when a workspace compaction owner is present, skip the entire nano-used-skills contribution. Summary fallback retains original full-body behavior. Usage tracking is unchanged.
- Plugin source 2c29b0b59581ff622923e3b92a0a4b6c68de1e9f: removes interruptedTurn/checkpoint/turn_id schema and filters; stable window contribution and on-demand references retained.
- Published immutable candidate v0.3.0-rc.3; downloaded and locally packed tarball SHA256 both 58aee15f347f2a2a26e02bb9bd0c8766e3a54e06ae294695d3aed1583c9c8f99. Nano dependency/lock commit 35fccff2f. Frozen install and build passed.
- Red evidence: /tmp/bugfix629-r3-nano-red.log (3 expected failures), /tmp/bugfix629-r3-plugin-red.log (2 expected failures). Green: /tmp/bugfix629-r3-nano-tests.log (5), /tmp/bugfix629-r3-plugin-tests.log (25), /tmp/bugfix629-r3-full-tests.log (484 / 107 files). Plugin typecheck/build passed. Full Nano suite ran with new Nano source and rc.2 plugin; final installed rc.3 narrow integration tests are recorded separately.
- Old candidate product evidence in regression.md is retained only as a baseline: it included interrupted_turn and cannot pass R3. A fresh isolated stack at /tmp/bugfix629-r3-runtime uses this worktree's built code and scripts, with independent ports/config/data/workspaces/identity to exclude the old protocol. No production writes or restarts. Product acceptance pending.

- Final installed rc.3 native model-policy matrix: 5 passed (/tmp/bugfix629-r3-installed-tests.log).
- Native request cost probes after reset, six consecutive small Notes/budget steps: both allowed-skill and workflow-only configurations have skillBodies=[0,0,0,0,0,0], usedIndexes=[0,0,0,0,0,0], runtimeSnapshots=[2,2,2,2,2,2]. Counts inspect message.content only, excluding duplicated attribution metadata. Evidence /tmp/bugfix629-r3-{allowed,restricted}-counts.json and matching probe logs. Scripted adapter verifies payload lifecycle only; not product task recovery. Probe runtimes shut down.

- Final installed rc.3 context/workspace integration: 6 passed in 2 files (`agent-context-default.test.ts`, `workspace-tools.test.ts`; /tmp/bugfix629-r3-installed-context-tests.log).

### R3 pressure distribution and failed recovery

Fresh session `534620fd-450e-4756-9b6d-04ba99d3276f` reproduces the original stale-Notes boundary. This is an intentionally large synthetic same-step batch, not normal diary workload sizing. Each of 25 native Skill outputs is about 42k characters, below the unchanged spill threshold. Results seq 93..141 total 1,058,668 characters and 264,885 estimated tokens including message framing (DSH fixed four-character heuristic). The previous seven Skill outputs total 60,557 characters including their wrappers.

The last provider request before the batch reports 20,096 cached input + 317 new input = 20,413 input tokens and 420 output tokens. All batch results arrive before the next model step. Default configured limits are C=258,400, output reserve O=32,768, input threshold H=225,632, work limit W=209,248 and reminder line W-R=203,104. The batch alone exceeds H, so the next pre-step pressure check replaces the window before sending these results to the model; there is no intermediate model step to observe a reminder and write fresh Notes. The 264,885 estimate is not provider-reported/billed input.

Compaction seq 143..146 records 283,827 estimated shadowed tokens for range 8..141; batch results account for 93.3% of that historical surface. This shadowed count is not the complete request including system/tools. The first post-reset provider request is 8,418 input tokens. Its checkpoint has the original Notes/History guidance and no interrupted-turn or used-Skill recovery contribution. The model reads stale preparation Notes, does not query History to recover the new Inbox task, and ends without the requested todo delivery. R3 therefore fails original incident recovery, despite passing request-growth and protocol-removal checks. No substitute hint, budget change or manual replay was introduced to turn this failure into a pass.

Evidence: /tmp/bugfix629-r3-e2e/534620fd-evidence.json and /Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_16-58-04_840_534620fd-450e-4756-9b6d-04ba99d3276f, including downstream message_delta usage for 17-00-38_638 and 17-00-53_146. Independent product report remains the final acceptance record.

## R4 native pressure pruning (supersedes rc.3 pressure path)

- User requested reconnecting DSH native pruning and replaying the same 25 documents. Gate 2 R4 approved with no critical/warning findings.
- Plugin `ce7d551ef90811191fb190a99f04ba74e961e14c`, candidate `0.3.0-rc.4`: calls the public optional `toolResultPruner.pruneSession` when the measured request reaches W, then measures the same request surface again before deciding H rollover. Public pressure compaction uses the same helper; overflow retains its existing forced reset after native pruning. Explicit model/manual reset behavior is unchanged. No separate truncator, interrupted-turn protocol, or used-Skill recovery hint was added.
- Native DSH per-result spill default is **12,500 estimated tokens**, not literally 50,000 characters. Its existing pressure pruner reduces large retained results. The previous custom engine bypassed that native BasicCompactionEngine call path. Offline replay through the installed native pruner reduced the original 25-result fixture from 264,885 to 32,450 estimated tokens; this is mechanism evidence only, not model task acceptance.
- Meaningful red: four new pressure-pruning expectations failed before implementation (`/tmp/bugfix629-r4-plugin-red.log`). Final plugin suite: 30 passed in 9 files; typecheck/build passed (`/tmp/bugfix629-r4-plugin-{tests,typecheck,build}.log`). Coverage includes native 25-result pruning without reset, residual pressure still resetting, below-W behavior, public pressure, overflow order and explicit model reset.
- Immutable release asset was downloaded and compared byte-for-byte: `https://github.com/Mrchen116/dsh-agent-context/releases/download/v0.3.0-rc.4/dsh-agent-context-0.3.0-rc.4.tgz`, SHA256 `6649b0da07c886a886a7a0e2a594df8d476951d6aca80a8bdc27b6a0b4cababa`. Nano dependency and lock pin it at `06c7aec52`; frozen installation and full build passed (`/tmp/bugfix629-r4-{install,nano-build}.log`).
- Fresh isolated runtime `/tmp/bugfix629-r4-runtime`, IM port 58043, PA `pa_003c76a7af96`; normal restart after configuration succeeded. The 25 journal Skill documents were copied from the failed R3 runtime and all SHA256 hashes match (`/tmp/bugfix629-r4-e2e/fixture-hashes.json`). Default budgets, model, Auto mode, tool restrictions and fixtures are retained. Independent model acceptance is recorded in regression.md; setup/restart alone does not count as acceptance.

- Final installed rc.4 Nano suite passed: 484 tests / 107 files (`/tmp/bugfix629-r4-nano-tests.log`); full typecheck passed (`/tmp/bugfix629-r4-nano-typecheck.log`); standalone helper and architecture suite 62 passed, 31 deselected (`/tmp/bugfix629-r4-pytests.log`). Frontend and Ruff evidence above remains valid because R3/R4 did not change their input trees.
- Final-sync fetch at 2026-10-21 17:43 Asia/Shanghai found no additional origin/main commits beyond this branch's base (HEAD ahead 10, behind 0). No integration code changed for sync. Final gate validity and documentation closure will record the effective tree after independent product/static reports.
