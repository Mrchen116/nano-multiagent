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
| ADDED IM workspace availability and unrelated-save / management-disabled scenarios (`specs/IM/agents-nodes.md:3-15`) | catalog metadata → Node/IM normalization → read-only workspace cards; saved static draft and creation defaults remain separate | native catalog enabled/disabled/repeated-preview regression; Node/IM projection tests; PillSelector normalized status/static-choice regression; actual settings screenshot inspected in Round 3 | aligned |

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

## Round 3 — Availability display and source-classification delta

- verification_mode: delta, including corrected-delta reconciliation
- fix_delta_range: `d8f3a6b0d0435ef6b33f24d5e0f063b073ec194a..4122379c8ef39fc110c553302ea23081830f595f`
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`
- validated_at: `4122379c8ef39fc110c553302ea23081830f595f`
- completed_at: 2026-10-15T00:40:00+08:00
- code / contract outcome: aligned
- verdict: pass
- issues: 0 CRITICAL / 0 WARNING / 0 SUGGESTION
- requires_full_verification: false
- report_commit: caller-owned shared worktree; not committed by reviewer.

| Affected contract | Implementation and direct evidence | Result |
|---|---|---|
| Workspace tools identified without broadening static tools | `workspace-tools.ts:118-122` extends baseline from current static names before updating Include; previous managed names are preserved as managed | aligned |
| Late Cron contributions remain static and unselected | repeated `configuration.catalog` native regression asserts only `workspace_echo` has workspace source and `schedule_create` remains unavailable; red log proves the original classification failure | covered |
| Page reports actual availability, including management disabled | `capabilities.ts:36-50` marks installed names using the same effective selection; native test checks management-enabled and empty Agent catalogs | aligned |
| Metadata preserved across Node/IM/frontend | `apps/node/src/capabilities.ts:60-65`; `apps/im-server/src/control.ts:499`; frontend API normalization `328-331`; projection and route regression | aligned |
| Read-only dynamic state does not mutate static selection | frontend `pill-selector.tsx:40-42,101-120` separates workspace state; detail payload remains draft-only; create defaults accept only default_on=true and Node marks managed tools false | aligned |
| New IM delta is the narrow consumer addition | `specs/IM/agents-nodes.md` adds availability/source, unrelated-save and management-disabled behavior, leaving configuration persistence/protocol unchanged | aligned |

Evidence inspected: `/tmp/feat610-late-tools-red.log` reproduces static scheduler misclassification; `/tmp/feat610-ui-native-tests.log` **3 files / 18 passed**; `/tmp/feat610-ui-frontend-tests.log` **3 files / 37 passed**; full native `/tmp/feat610-ui-full-tests.log` **84 files / 314 passed**; full frontend `/tmp/feat610-ui-full-frontend.log` **95 files / 882 passed**. Caller reports build/typecheck success. Independent runtime dependency contract **13 passed**, and `git diff --check d8f3a6b0d..4122379c8` passed.

### Reference Contract Coverage

The design now has a bounded reference contract; earlier rounds' N/A applied before this UI addition. `prototype.html` is explicitly an unrendered draft, so it cannot provide browser comparison evidence. The worker subsequently supplied an actual HTTP settings screenshot `/tmp/feat610-review/workspace-tools-settings.jpg`; this verifier inspected its pixels. It shows the original static Tool Allowlist with unchecked schedule tools, a distinct Workspace tools section, expense_summary Enabled, description and no-allowlist/chat-disable guidance, followed by the original model controls. This provides a real implementation comparison for the explicit content/hierarchy contract, without claiming the draft was rendered or replacing the independent product review.

| Must-match | Milestone projection | Implementation evidence | Durable real comparison | Status |
|---|---|---|---|---|
| Distinct workspace origin, actual state and no-check-needed guidance | M1 reviewer addition in design's configuration-page section | workspace cards and localized help; native metadata tests and component assertions | Actual desktop screenshot inspected; source/state also confirmed by native and IM tests | covered |
| Static choices editable and unrelated save does not append workspace names | same M1 addition | static buttons and existing draft serialization; default_on=false; component static-choice assertion | Actual screenshot separates static buttons and the read-only dynamic card; full browser save journey belongs to independent product review | covered at verifier seam |
| Existing settings hierarchy and narrow-screen wrapping | design may-adapt/real-page boundary | existing field/container retained; wrap/break classes on workspace rows | Actual desktop hierarchy inspected; narrow-screen product evaluation pending | desktop/reference contract covered; responsive product gate separate |

### Resolved evidence concern — R3-W1

- Contract: `design.md` configuration-page section requires actual browser walkthrough and unrelated-field save; verifier skill requires inspectable real comparison for frontend must-match.
- Initial evidence: the prototype is explicitly unrendered and tests alone do not establish a real frontend comparison.
- Closure: inspected the subsequently provided actual HTTP desktop screenshot above, and reconciled its explicit content/hierarchy with design and source. Combined with real native availability and metadata tests and existing form serialization, verifier contract evidence is sufficient. No implementation defect was found. The independent product reviewer still owns narrow-screen experience, actual unrelated-field save, management-disabled view and continued real call; this verification does not claim those actions have already occurred.

Retained evidence: the previous real-IM/real-LLM **7/7** continues to prove tool creation/use, sharing and other-workspace denial, restart, preserved choices, failure-source repair and revocation. The new read-only UI does not alter those operations. The baseline change is additionally covered by the full native lifecycle regression at this revision, so it does not require re-acceptance of unrelated core journeys.

Corrected-delta outcome remains **aligned**. The unique reconciliation table above includes the IM addition; no new observable behavior is omitted. Engineering verification passes with 0 CRITICAL / 0 WARNING. The next independent browser product gate remains separate and is not inferred from the older 7/7 report.
