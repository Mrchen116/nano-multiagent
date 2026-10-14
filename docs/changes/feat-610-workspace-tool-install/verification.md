# Verification Report: feat-610

> Validation snapshot: `9182699fca58d42fbf166f3de7445c635dcb3527 → 33ef0d76d342a10c411ccbc0828f82d0d564e810`

## Summary

- reviewer: independent agent `workspace_tools_static_review`
- verification_mode: full, including corrected-delta
- verdict: pass
- corrected-delta outcome: aligned
- requires_full_verification: false
- issues: 0 CRITICAL / 0 WARNING / 0 SUGGESTION
- report_commit: caller-owned shared worktree; not committed by reviewer.

| Dimension | Result |
|---|---|
| Completeness | M1 implementation and worker runtime exits covered; product reviewer exit remains a separate Gate 4 |
| Correctness | All changed requirements/scenarios have implementation and applicable evidence |
| Coherence | Follows approved design and published runtime boundary |

Engineering verification passes. This report does not substitute native runtime fixtures for the separate real-IM product journey, deployment or release acceptance.

## Completeness

- M1 implementation is complete: scoped management service, trusted workspace identity, native installation/loader integration, dynamic selection, persistent generations, product manual and native process regression.
- Spec covers self-install, immediate use, same-workspace sharing, cross-workspace denial, restart, preserved choices, truthful failure/retry and disable/remove. The implementation mapping is below.
- UI prototype/reference: N/A; this unit adds no frontend surface.
- Reused validated implementation evidence: `pnpm build` and `pnpm typecheck` pass (caller reports built source/lib matched the validated revision); `pnpm test` 84 files / 313 tests pass, confirmed from `/tmp/nano-feat610-tests.log`. Caller also reports non-E2E pytest 56 pass / 31 deselected (`/tmp/nano-feat610-pytest.log`), frontend 94 files / 881 tests pass (`/tmp/nano-feat610-frontend.log`), and Ruff check/format pass.
- Independent architecture check: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py` — 13 passed; branch diff whitespace check passed.
- Documentation closeout: caller is correcting the delta's `task-graphs.md` relative link and will complete docs-check. This is a navigation-path correction without requirement changes; final docs gate belongs to caller closeout.

## Correctness

Paths below are relative to `packages/dsh-integration/` unless otherwise stated.

| Requirement / Scenario | Implementation evidence | Test / validation evidence | Status |
|---|---|---|---|
| Self-create, install and invoke in existing chat | `src/workspace-tools.ts:48-64,149-208` | `tests/workspace-tools.test.ts:62-69`: failed evaluation, corrected source, reinstall, actual same-turn result | covered |
| Same-workspace chats share additions | `src/workspace-tools.ts:45-47,60-68,116-145` | test `70-75`: existing second chat sees and executes tool | covered |
| Other workspace cannot discover or execute | `src/workspace-tools.ts:44-47,80-86`; preset scope parenting retained | test `73,76,91`: schema absence and actual denied dispatch | covered |
| Restart preserves installed tool and history binding | `src/workspace-tools.ts:79-109`; existing `prepareProfile` does not rewrite nested profiles | test `85-91`: normal shutdown, boot preparation, restored bindings, actual result | covered |
| Static disabled tools and empty selections stay disabled | `src/workspace-tools.ts:56,144`; `src/capabilities.ts:24-29,47-59` | test `61,71,74`; existing `capabilities.test.ts` retains selection and dispatch coverage | covered |
| Management-disabled Agent gains no implicit additions | `src/capabilities.ts:27-29` | source-level effective collection check; existing tool restriction regression retained | covered |
| Subtasks retain inherited/role restrictions | `src/capabilities.ts:47-59`; existing workflow `toolFilter` and native child composition | locked native tools view intersects all ancestor layers; existing workflow/approval tests remain green | covered |
| Failed install/load is truthful and recoverable | `src/workspace-tools.ts:111-147,198-207`; immutable generation source `149-164` | test `62-69,79-84`: diagnostics, unavailable failed tool, fixed retry, good tool survives unrelated failure | covered |
| Disable/remove revoke now and persist | `src/workspace-tools.ts:185-208` | test `92-101`: actual denied call after disable, disabled state after restart, re-enable actual result, removal schema withdrawal | covered |
| Capability selection matches callable collection | `src/agent-config.ts:39`; `src/index.ts:318`; `src/capabilities.ts:24-29` | test `77-78`; node's existing catalog projection marks management tool default-on | covered |

## Coherence

| Design decision | Evidence | Result |
|---|---|---|
| Native package management confined to trusted workspace | `workspace-tools.ts:42-54,79-94,166-209` | followed |
| Native Include/HMR own execution lifecycle | `workspace-tools.ts:24-27,58-64,124-142,193-202` | followed |
| Local generation execution URLs anchored to real persisted source | `workspace-tools.ts:96-109,149-164`; real failure-to-success regression | followed; closes design-review R1-W2/R2-W1 |
| Installation does not silently widen static permissions | `workspace-tools.ts:56,144`; `capabilities.ts:24-29,47-59` | followed; matches corrected R1-W1 delta |
| Existing Nano pre-execute approval retained | tools registered/executed through native tools; existing `src/policy/approval.ts:30,101-145` applies to new names | followed |
| No second runtime / private DSH dependency | installed package exports and independent 13-test contract check | followed |
| Product manual explains usage and evidence limits | `packages/personal-assistant/assets/skills/nanoassistant-docs/references/skills-tools-memory.md:52` | followed |

### Prototype / Reference Contract

N/A. The pinned DSH 0.2.1-alpha.1 published packages are runtime API evidence; upstream source `5badb15009` is a reference, not a new repository contract.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

Delta: `specs/gateway/agent-capabilities.md` within this unit; canonical destination: `docs/specs/gateway/agent-capabilities.md`.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| MODIFIED whitelist Requirement and preserved scenarios (`3-35`) | static allowlist plus conditional workspace additions in `capabilities.ts:24-29`; baseline collision exclusion in `workspace-tools.ts:56,144`; empty/feature restrictions retained | `workspace-tools.test.ts:61,70-78`; existing capabilities/communication regression | aligned |
| ADDED workspace management and immediate scoped use (`40-46`) | workspace owner/mount sets; trusted workspace tool closure; native manager/Include | test `62-78`: actual install/use, another chat, B refusal | aligned |
| Truthful failed installation/loading (`48-50`) | native error propagation plus Loader/fiber audit and actual application result | test `62-69,79-84`: failed source, distinct fixed generation and unaffected good tool | aligned |
| Restart and revocation (`52-54`) | persistent native profile/file dependencies; disable-before-remove and scope refresh | test `85-101`: restart, disable across restart, re-enable/remove | aligned |
| Preserve unrelated choices (`56-59`) | baseline names excluded from automatic additions; management/empty selection gate | test `61,71,74` and retained native restrictions | aligned |

### Uncovered Observable Behavior

None. Ordinary external package replacement retains native `restart-required`, as explicitly documented in design and the product manual; local authored bundles use the approved generation path. Package build approval remains part of native management and existing Nano execution approval.

Outcome: aligned

## Round 2 — Package invocation delta verification

- verification_mode: delta
- fix_delta_range: `c4822c94f6c388fc4807a2bc88a199b581f42e03..d7265f0a3a11a3467d9acb421ad6e45ec4721fbd`
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`
- validated_at: `d7265f0a3a11a3467d9acb421ad6e45ec4721fbd`
- prior_verification: Round 1 above, validated at `33ef0d76d342a10c411ccbc0828f82d0d564e810`
- completed_at: 2026-10-15T00:20:00+08:00
- verdict: pass
- issues / validated_issues: none; 0 CRITICAL / 0 WARNING / 0 SUGGESTION
- requires_full_verification: false
- report_commit: caller-owned shared worktree; not committed by reviewer.

| Affected contract | Actual implementation / evidence | Result |
|---|---|---|
| Managed installations can self-install without global pnpm | `apps/node/src/release.ts:40-43` uses the installer's private pnpm path and absolute Node; installer `apps/im-server/assets/install.sh:43-46,65` and updater `apps/node/src/update-worker.ts:22,34-35` confirm that layout | aligned |
| Package manager is trusted startup data, outside model/Agent scope arguments | Node main initializer → `index.ts:251` → `agent-config.ts:41` → workspace owner's native `ProfileContext.packageManager`; assigned before configured preset registration | aligned |
| Public DSH runtime boundary remains intact | Type exported by locked `@deepseek-ai/dsh-app-boot`; no DSH import from Node; independent architecture suite **13 passed** at this snapshot | aligned |
| Source and workspace execution semantics remain valid | Source release returns undefined and owner preserves native default; only package command changes; scope, allowlist, generations, load audit and management operations unchanged | aligned |
| Real no-global-pnpm failure has regression protection | Red log contains `spawn pnpm ENOENT`; green log has **2 files / 4 tests passed**. Runtime PATH is hidden during the full native install/repair/isolation/restart/revocation test; updater fixture executes the resolved private CLI path | covered |

Commands/results reused at this snapshot: caller's `pnpm build` and `pnpm typecheck` passed; `pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts apps/node/tests/node-updater.test.ts` passed, confirmed from `/tmp/feat610-pinned-pnpm-green.log`. Independently reran `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py` (**13 passed**) and `git diff --check c4822c94f..d7265f0a3` (passed). Earlier full-suite evidence remains applicable to unchanged paths.

Corrected delta remains **aligned**: its consumer requirements and scenarios are unchanged in this patch; the design addition makes the existing self-install promise work with the installer-owned package manager. No omitted new user behavior was found. The unique Corrected Delta Reconciliation section above retains its outcome; this round extends its installation evidence.

The independent `acceptance.md` reports real IM → Node → DSH → real LLM **7/7** at `33ef0d76d`. Those product results remain valid: the patch changes only the managed package execution command, and the new real native regression validates the affected seam with global pnpm unavailable. Full product verification is not required again; this conclusion does not expand that acceptance to published installer execution or production deployment. Independent design-review R4 passed with 0 CRITICAL / 0 WARNING; it remains a separate design gate. Caller confirmed isolated product services were cleaned.

Final snapshot evidence inspected: `pnpm test` **84 files / 313 tests passed** (`/tmp/feat610-final-tests.log`); non-E2E pytest **56 passed / 31 deselected** (`/tmp/feat610-final-pytest.log`). These supersede the earlier retained whole-suite evidence for the final implementation version.
