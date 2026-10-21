# Code Review: feat-627

## R1 — full

- Nano branch/worktree: `unit/feat-627`, `.worktrees/unit-feat-627`.
- Nano frozen range: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28...31e47aab36782a99c17d709b6496f344892c55a1`.
- Independent plugin branch/worktree: `codex/feat-627-agent-context`, `/Users/czj/Repos/opensource-hub/dsh-agent-context-worktree`.
- Plugin frozen range: `d74876a90968bd5498b5af0bcc2f327c3131f007...7f0a2b78ec530075edd48452c2cf5499548ca99c`.
- Review mode: `full`; both implementation ranges reviewed together. Both worktrees were clean and at the frozen implementation commits when inspected. Report-only advancement does not change this validation snapshot.
- Verdict: **PASS — no confirmed or plausible actionable code findings**.

## Coverage and evidence

Reviewed the plugin's entire production implementation, package/patch/build/CI changes and replacement tests, plus Nano's complete integration diff and its callers. The following boundaries have direct source and applicable regression evidence:

| Risk | Evidence |
|---|---|
| Kernel fork/private imports or a second runtime | The plugin imports published DSH exports; generated private-path/compat machinery was removed. `cordis.patch.yml` mounts only an isolated compaction owner. Nano resolves the fixed release as a package dependency; no DSH runtime version change or kernel patch is in either range. |
| Old conversation or Notes body surviving reset; loss of current runtime state or claimed input | Plugin `src/index.ts:123`, `src/index.ts:263`, `src/checkpoint.ts:16`, `src/rollover.ts:66`; real public AgentLoop request assertions in `tests/engine.spec.ts`, forced/overflow paths in `tests/safety.spec.ts`. Checkpoints are deterministic navigation/control state; no summarization call is made. The stale projected runtime candidate is removed only after a successful reset. |
| Unsafe tool-call/result split, false successful window or endless fixed-only overflow retry | Full paired surface selection and native start/summary/replacement/end transaction; strict token shrink and conversational-progress checks; `tests/rollover.spec.ts`, `tests/safety.spec.ts`. A failed/unclosed bracket is not counted as a new window. |
| Budget unavailable before first request, uncapped output, repeat reminders after restart | `src/budget.ts:8`, `src/index.ts:141`, `src/index.ts:233`, `src/tools.ts:53`; `tests/reminder-delivery.spec.ts` and `tests/tools.spec.ts`. Pending admission is estimated separately, an absent maxTokens uses a labeled policy reserve without changing provider options, and reminder state is read from durable events. |
| Missing original tool payload/provenance or inaccessible result tail | `src/history.ts:78` normalizes committed messages, full call arguments/result payloads and original source; active membership excludes current bodies from History. Unicode slices, stable seq/window IDs, paging, replay and cross-session rejection are covered by `tests/history.spec.ts` / `tests/tools.spec.ts`. |
| Notes traversal, destructive failed append, truncated long lines | `src/notes.ts:23`, `src/notes.ts:72`, `src/notes.ts:133`, `src/notes.ts:173`; the store enforces session paths, rejects symlinks, serializes same-file writes, atomically replaces, and returns Unicode continuation coordinates. `tests/notes.spec.ts` includes the retained unreadable-append regression. |
| Default activation changing user opt-out, business selection or approval | Nano `src/agent-context.ts:12`, `src/workspace-tools.ts:65`, `src/capabilities.ts:25`, `src/policy/approval.ts:103`; `tests/agent-context-default.test.ts` covers existing/new profiles, PA/Global/no-workspace scopes, native child dispatch under all three Auto-off rulesets, explicit downstream denial, empty business allowlists and persistent opt-out. Existing workspace lifecycle tests continue to cover ownership, disposal, activation failures and workspace isolation. |
| Prompt provenance being a self-referential golden assertion | Independently compared fixture originals to fixed Codex commit `464add49587a7cb6032d5ab04faa8a1585947853`: guidance/reminder/fallback exactly match `models[0].model_messages.token_budget` (`gpt-6-astra`, disabled reference configuration); all nine action descriptions match `tools.rs`. Adapted runtime strings match the approved prompt appendix and golden fixtures. |

Validation used:

- Independently executed in plugin at `7f0a2b78ec530075edd48452c2cf5499548ca99c`: `pnpm test` — **9 files / 22 tests passed**; `pnpm typecheck` — **passed**. This focused suite took under one second and directly exercises the reviewed native integration.
- Independently checked local candidate tarball SHA-256: `f8a26ca5c6558ef04a2ff2b7d93535993272f80cd05d138029c733aa391e4fb1`, equal to the published-download digest recorded by the implementation owner. Nano `package.json` and lock use the exact `v0.3.0-rc.1` Release URL and integrity, with no local path.
- Read the completed final Release-based logs: `/tmp/feat627-release-tests.log` — **107 files / 482 tests passed**; `/tmp/feat627-peers.log` — **no peer conflicts**; `/tmp/feat627-python-frozen.log` — **62 passed / 31 deselected**; `/tmp/feat627-docs-frozen.log` — **251 Markdown sources / 67 routes passed**. Reused the owner's successful build/typecheck and unchanged Web **936 passed** evidence recorded in `M1-agent-context/progress.md` / dispatch. No entire suite was needlessly repeated.
- `git diff --check` for the full Nano implementation range passed.

These tests and code review do not establish real model task quality, user receipt, restart continuation, or the required one-time external side effect. The independent product review is still pending and is tracked in `verification.md`; no product acceptance is claimed here.

## Findings

```json
[]
```

No implementation edits, runtime changes, commits or pushes were performed by this reviewer. Only the two authorized reports were written.

## R2 — patch and independent R1 attribution check

- Frozen Nano: `7fe9224fb3f566b1db2ed4964c4b0e4d09cedb00`; executed base remains `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`.
- Patch reviewed: `b09851c01cf39b6198edd6956914e66b52153c24...7fe9224fb3f566b1db2ed4964c4b0e4d09cedb00`.
- Plugin remains `7f0a2b78ec530075edd48452c2cf5499548ca99c`, same rc.1 asset/digest. R1 full static conclusions remain applicable outside the patch.
- Verdict: **PASS — no surviving actionable patch findings**. Original R1 product failure is retained in `acceptance.md`; this is not a claim that the wrong final report or prohibited attempts became correct.

### Inventory repair

The R1 product report identified a concrete introduced integration defect: model-facing `WorkspaceOwner.command(list_bundles)` included only `bundle.installed`, so the shipped default (not installed in the workspace) disappeared even while active. The patch at `packages/dsh-integration/src/workspace-tools.ts:259` now includes that single shipped bundle by name, matching the control-plane list. It does not broaden tool selection, approval, installation, or package ownership.

The added assertion at `packages/dsh-integration/tests/workspace-tools.test.ts:72` uses the existing scripted model → real native `plugin_manager` dispatch → returned tool result before installing other bundles. This protects the actual discrepant seam, rather than only rechecking the already-correct management RPC. Reviewed `/tmp/feat627-inventory-red.log`: the expected enabled default entry failed against `entries: []`; `/tmp/feat627-inventory-green.log`: the complete lifecycle test passed, **1 file / 1 test, 35.00s**. This scoped evidence is sufficient for the one-line fix; the unchanged R1 full-suite evidence is reused. `git diff --check` passed for the patch. R2 user-facing inventory confirmation and the missing identity matrix remain the product reviewer's work.

### Independent causal classification

Read the original `acceptance.md`, the new attribution note, native events `/tmp/feat627-acceptance/session-events.jsonl`, and the actual three request/response pairs in the R1 proxy directory. The request directory is recorded in `M1-agent-context/evidence/r1-attribution.md`; raw transport logs and full messages remain local.

| Original product finding | Independently observed evidence | Attribution / closure |
|---|---|---|
| R1-1: incorrect aggregate, repeated after restart | Request `2026-10-21_11-44-52_585-req-anthropic_messages.json` contains all 12 numeric rows in the restored Notes result. Independently extracted rows sum to **13482 / 13237 / 245** and equal all 12 delivered rows. Incorrect **14353 / 13308** are absent from that request and appear in its matched model response's `write` call `call_00_qfLNKrZT4iXHIBH6IK7O2234`. The original wrong final-report artifact is unchanged. | Confirmed model computation/verification error with correct data available. No demonstrated Notes/History/rollover value loss or mutation. **Not fixed, not a correct answer, and not established as a defect introduced by this unit.** Repeating a model-written incorrect note after restart does not itself prove storage corruption. |
| R1-2: two prohibited bash attempts | Request `2026-10-21_11-42-37_313-req-anthropic_messages.json`, messages 3 and 6, explicitly contains `不用 bash` from native Notes result 371 and progress result 377. Matched response calls `bash echo ok`, call ID matching native tool/call 382. Request `2026-10-21_11-44-34_432-req-anthropic_messages.json`, message 3, contains `禁用 bash` in the restored task heading plus the original constraint reference (Notes result 649); matched response calls the prohibited directory listing, matching native 654. Native results 386/658 are user-rejected errors. | Confirmed instruction-adherence failure despite prohibition present in actual model input; not an absence-of-input failure or bypass of approval. The second input is a Notes heading/reference, **not the full original user message**. **Not fixed or compliant; unit-specific causation is unestablished.** |
| R1-3: model inventory hides enabled default | Actual command filter, demonstrated red native-dispatch regression, and post-fix green lifecycle result above | **Source defect closed**, user-facing R2 confirmation pending. |

These observations support treating R1-1/R1-2 as model-behavior side findings for this feature's implementation review. They do not establish that rollover timing, instruction presentation or salience had zero causal influence: no matched baseline/counterfactual observation isolates those variables. Such additional comparison would be needed for that stronger causal statement. The latest explicit user clarification requires this distinction; it does not authorize erasing failed product observations. No speculative prompt rewrite, automatic tail retention, arithmetic oracle injection or general Agent behavior mechanism is required by the evidence or introduced by this patch.

### R2 findings

```json
[]
```

Only the two reports were updated. No tests needing real services were rerun, no runtime/configuration/source was changed, and no commit or push was performed.
