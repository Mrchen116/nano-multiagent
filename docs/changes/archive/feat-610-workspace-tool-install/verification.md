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

Current corrected delta: `specs/gateway/agent-capabilities.md` and `specs/im/agents-nodes.md` within this unit, relative to the canonical baseline at `89c47478b`. Older rounds below preserve their historical conclusions. The standard-plugin reconciliation at `df579de5e8fb7c09626e132a28fd23f5663dae18` is retained. Round 7 verifies `48ecbfec267343bf6df6f2d577c21fb1a8ea7733..084b4ac18123db3b504e02e8c4a739dfc55577a6`, including the identical new third-party host-dependency/workspace-configuration scenario in the canonical Gateway spec and unit delta. Offline receipts retain the existing recovery contract rather than adding a new user behavior.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway standard workspace plugin Requirement; retained installation/failure/restart/permission scenarios | same native manager/Include profile; original allowlist gate retained | original native lifecycle regression remains green at current snapshot | aligned |
| Gateway non-tool contribution and whole-plugin withdrawal | native group/isolate, public leakedServices, Include update and old fiber drain | native prompt A/peer/B and cleanup fixture; Round 6 real prompt enabled/disabled/reenabled and actual stopped-tool result inspected | aligned |
| Gateway trusted web/chat management and busy queries | owner profile → Node Agent validation → runtime preset → same workspace owner; list bypass/maintenance gate | owner/scope HTTP regression and native pending/cleanup/input tests | aligned |
| Gateway disabled choice preserved on package update | native result.bundle now reconciles prior disabled state before refresh/early return; explicit enabled remains authoritative | real named package spec red→green, followed by restart remaining disabled and explicit web re-enable; R4-P2 closed | aligned |
| IM independent plugin page and retained unrelated-save behavior | new tab, zero-tool directory and immediate mutation; static draft serialization unchanged; old cards removed | UI/HTTP tests and Round 6 actual desktop/390-width plugin-page comparison | aligned |
| IM web management remains available with Agent management tool disabled | trusted web path has no plugin_manager tool-allowlist dependency; package state is separate from tool use | control identity test and source audit | aligned |
| IM pending, error, offline and confirmation semantics | native snapshots/pending/error; poll and refresh; per-card confirmation and no optimistic state change | native/HTTP/UI regressions plus actual pending, empty, failed-detail and confirmation screenshots; final product offline/restart work remains independent | aligned |
| Workspace host dependencies and resolution withdrawal | public native resolver per workspace; mappings retained through old fiber drain; serial first owner creation and reverse close | host Cordis/LLM imports and Context identity in native lifecycle; concurrent-disposal red/control and fixed restored:true evidence | aligned |
| Scoped preset compaction, workspace isolation and default fallback | public serviceFor selects current preset backend; automatic triggers yield; manual command invokes compactNow; absent backend keeps default focused summarizer | trigger/forwarding regression plus real DSH installed-engine command/summary/marker, B isolation and disable assertions; existing default-focus subprocess coverage retained | aligned |
| Offline recovery and delayed Web completion receipts | main.ts unchanged; GlobalAgent delays only offline completed Web receipts without confirmation, preserving external recovery | real InboxStore/NodeStore public recover red/green: external completes offline, Web stays pending, repeated reconnect delivers Web once | aligned |
| Gateway third-party host-dependency/workspace-configuration Scenario | canonical `agent-capabilities.md:658-661` and unit delta match; public resolver, user overlay, preset engine delegation, disable fallback and workspace isolation implement each clause | host-dependency native lifecycle, pressure/overflow branch regression, real installed preset summarize marker/B isolation/disable test; final targeted 3 files / 35 tests pass | aligned |

### Uncovered Observable Behavior

No omitted target behavior found in the reviewed unit delta, including Round 7's bounded fixes. The independently merged bugfix-611 is excluded. Registry replacement's native restart-required limitation remains documented, but does not excuse reversing a saved disabled choice (R4-P2). Multi-workspace Worker compatibility remains outside the approved main-thread fix. Third-party real-model rollover use is pending independent product acceptance; imports and native fixtures do not replace that journey.

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

## Round 4 — Standard-plugin scope verification

- verification_mode: full for the new plugin scope, including corrected-delta
- scope_delta: `89c47478b054b8d788022752213ff6d494b5f9d9..3e43f7649f21bc01c41241c3bb27d743142a9b77`
- executed_base: merged `origin/main` `4a1485d43d33c02fb3635a8c26b4b9a343a8680a`
- validated_at: `3e43f7649f21bc01c41241c3bb27d743142a9b77`
- verdict: issues-found
- corrected-delta outcome: implementation-mismatch
- issues: 0 CRITICAL / 1 WARNING / 0 SUGGESTION
- requires_full_verification: false; the expanded scope was reviewed in this round, not implicitly retained from tool-only acceptance.
- report_commit: caller-owned worktree; reviewer did not commit.

### Completeness and coherence

New implementation includes package directory, owner-only HTTP API, trusted Node/stdio forwarding, preset lifetime retention, per-workspace maintenance reservation, isolated service labels/leak detection, old-fiber drain, independent zero-tool-capable Plugins page and manual. No runtime fork, private DSH import, second Agent Loop or mirrored plugin database was introduced. The public native maintenance implementation was checked: it synchronously occupies idle, defers inbox wake and releases in finally. Scope attachments consult the workspace gate before registration. Pending list reads do not await the workspace mutation queue.

Source and runtime evidence cover new prompt-only contributions, A/peer sharing and B isolation; root services fail with repair guidance, scoped group services succeed; web disable waits a live turn, original displayed state persists, A's new input waits through asynchronous cleanup while B continues, old files are readable until cleanup and remove completes afterward. The source uses native bundle selection for disable and separate package removal, preserving author source/work files. New UI controls are separate from Agent draft/save and static tool permission selection. The one incomplete correctness condition is R4-P2 below.

### Test evidence

Inspected caller logs: `/tmp/feat610-plugins-native.log` **1 file / 1 test pass**; `/tmp/feat610-plugins-tests.log` **2 files / 2 tests pass**; `/tmp/feat610-plugins-ui.log` **2 files / 4 tests pass**. Caller reports typecheck/Web build pass and ongoing full build/tests. Independently ran architecture dependency contract **13 passed** and checked frozen range whitespace. These tests execute the real native package/scope/fiber seam; the UI tests use mocked HTTP and therefore do not prove a real browser/LLM plugin journey.

### WARNING — R4-P2: Disabled registry package selection is not preserved on versioned update

- Contract: `spec.md:46-49`, `design.md:101`; corrected Gateway delta's “停用状态在更新时保留”.
- Actual: `workspace-tools.ts:267-269` only matches prior packages by local staged name or exact target. For `report-style@1.1.0`, an installed disabled `report-style` is missed. Native install defaults to enabled and selects the package before its existing-dependency restart-required return. The workspace's persisted stop choice becomes enabled.
- Fix: use the actual result.bundle and previous native list to restore disabled choice in the controlled install transaction before refresh/early return; retain explicit enabled:true behavior. Add a versioned-registry adapter regression. Local-directory update protection alone is insufficient.
- Status: CONFIRMED at validated_at; accepted author fix in progress is not closure evidence.

### New prototype/reference contract

Actually inspected `design-assets/plugins-states.png` and the text corrections: named Plugins entry, shared scope hint before cards, tool/non-tool cards together, one target's pending feedback, secondary details/uninstall, per-card confirmation and mobile single-column intent. Source implements these explicit state/entry decisions; UI tests check zero-tool, pending, error/offline and confirm behavior. The image is a design board, not a product rendering; old workspace-tool cards are superseded.

Real comparison is **pending** the next independent product review: desktop/390-width independent Plugins page, working switch without Save, waiting/terminal behavior, readable failed/empty/offline states and confirmed removal. That evidence is needed before final frontend/product gate closure. The earlier 7/7 tool journey and old read-only-card screenshots are retained only for unchanged installation/static-selection/history behavior, and are not accepted as proof of standard non-tool plugins or the new page.

The unique Corrected Delta Reconciliation section above now reflects the current plugin delta. Outcome: **implementation-mismatch** until R4-P2 is independently closed. No source/test/config/design changes were made by this reviewer.

## Round 5 — Update-choice closure and remaining reference evidence

- verification_mode: targeted-closure plus corrected-delta update
- fix_delta_range: `3e43f7649f21bc01c41241c3bb27d743142a9b77..df579de5e8fb7c09626e132a28fd23f5663dae18`
- validated_at: `df579de5e8fb7c09626e132a28fd23f5663dae18`
- executed_base: `4a1485d43d33c02fb3635a8c26b4b9a343a8680a`
- validated_issues: R4-P2 closed
- implementation / corrected-delta outcome: aligned
- verdict: implementation verified; final reference-evidence closure pending
- issues: 0 CRITICAL / 1 WARNING (R5-W1, evidence only) / 0 SUGGESTION
- requires_full_verification: false
- report_commit: not committed by reviewer.

R4-P2 is independently closed: result.bundle is the public native authority for the installed package name; the previous disabled choice is restored under the existing transaction before refresh or restart-required return, only when enabled was omitted. Source diff preserves explicit enable behavior and propagates restoration failures. The real `workspace-echo@file:<source>` regression exercises target≠package-name without an invented resolver or package-manager mock. `/tmp/feat610-update-red.log` directly shows the prior persisted selection true; `/tmp/feat610-update-green.log` passes the complete native lifecycle after the fix, including post-update restart remaining disabled and explicit re-enable. Frozen fix diff whitespace passes.

Retained whole-scope results: 85 files / 315 backend tests, 96 files / 885 frontend tests, 56 Python tests / 31 deselected, inspected in `/tmp/feat610-all-native.log`, `/tmp/feat610-all-web.log`, `/tmp/feat610-python.log`. The whole-scope test runs began before this narrow correction; its direct post-fix native lifecycle result is the closure evidence. No broader repeat is needed for the unchanged UI/HTTP/maintenance code. Caller reports build/typecheck/docs/Ruff/audit gates passed.

### WARNING — R5-W1: New independent Plugins page still needs real reference comparison

- Contract: design's must-match matrix covers independent entry/shared scope, actual switch pending/terminal behavior, error/empty/offline and uninstall confirmation in desktop/390-width product views. The verifier skill requires inspectable real frontend comparison.
- Current evidence: actual design-board pixels and implementation/component/runtime tests have been inspected; a real implementation comparison for this new page has not yet been provided. The earlier read-only tool-card screenshots are obsolete for this contract. The independently assigned product reviewer is preparing this evidence, so this is an outstanding gate rather than a code defect or a request for redesign.
- Closure: inspect that report's actual page/state comparison and durable screenshots, plus real non-tool behavior/management results at an applicable revision. Update this issue without reopening the unchanged code review or repeating old tool-only journeys. Until then, do not label final frontend/product verification complete.

The corrected delta itself is **aligned** and no observable implementation behavior is omitted. R4-P2 is closed; the remaining warning is solely the new must-match evidence gate. No product source/test/config/design was changed and no commit was created by this reviewer.

## Round 6 — R5-W1 frontend reference-evidence closure

- verification_mode: targeted-closure (reference evidence only)
- validated_at: unchanged `df579de5e8fb7c09626e132a28fd23f5663dae18`
- executed_base: `4a1485d43d33c02fb3635a8c26b4b9a343a8680a`
- completed_at: 2026-10-15T01:57:00+08:00
- focus_issue: R5-W1 closed
- verdict: pass
- corrected-delta outcome: aligned
- issues: 0 CRITICAL / 0 WARNING / 0 SUGGESTION
- requires_full_verification: false
- report_commit: not committed by reviewer.

This round does not repeat code review or claim the independent product reviewer has completed final acceptance. Actual screenshots produced by that reviewer were opened with the image viewer and compared against the approved state board, its text corrections and the design must-match matrix. Only this report was changed in this closure.

| Must-match / reference | Actual evidence inspected | Reconciliation |
|---|---|---|
| Independent entry, zero-tool package and shared scope ahead of cards | `/tmp/feat610-review/r3/desktop-list.png` | Plugins is a separate selected tab; the zero-tool expense-report-style package is present beside tool packages; a visible shared-workspace panel explains whole-package disable and separate tool permissions; Refresh and Open chat remain available; no Save control appears |
| Waiting preserves original state and identifies only the target | `/tmp/feat610-review/r3/pending.png` | expense-summary remains visibly Enabled with dimmed checked switch and “Waiting for this workspace to become idle. Current work continues.”; other cards show their prior state with dimmed controls and no duplicate waiting label |
| Details and concrete uninstall confirmation | `/tmp/feat610-review/r3/uninstall-confirm.png` | Details identify orchid610-bundle and version/entry; inline confirmation names the specific package, all Agents sharing the workspace and source-file retention; confirm/cancel are distinct; the dangerous action is secondary within Details |
| Desktop/390-width hierarchy and wrapping | `/tmp/feat610-review/r3/mobile390.png` | Existing mobile identity/navigation retained; tabs wrap; shared scope/path, description and single-column cards fit; name/status/switch remain in the same card. Reviewer reports CSS viewport 390×844 and scrollWidth=390; screenshot pixels support the intended layout. This is a product screenshot, not a rendering of prototype.html |
| Genuine empty collection | `/tmp/feat610-review/r3/empty.png` | Peer workspace has an explicit No plugins yet state and natural-language creation suggestion, under its own scope path; no failure wording is replaced by emptiness |
| Failed package remains manageable and diagnostic visible | `/tmp/feat610-review/r3/failed-plugin.png` | Installed orchid610-repair-bundle remains listed as Needs attention, with package/version/entry and expanded native never-started diagnostic; Uninstall remains available and other cards remain visible |

The comparison satisfies the inspectable frontend reference contract that R5-W1 lacked. Implementation follows the design's explicit corrections rather than copying non-contract decoration from the concept board: only the target gets pending text; uninstall is in Details; real header/navigation is retained. No new implementation mismatch was found in this bounded evidence review.

Additional direct evidence inspected: `prompt-enabled.txt` and `prompt-reenabled.txt` contain the report-format section; `prompt-e2e-disabled.txt` omits it. `tool-disabled.out` includes an actual expense_summary tool call and native ToolNotFoundError/UNKNOWN_TOOL after disable, not merely model self-report. These support the new non-tool/whole-plugin behavior without treating the old tool-only 7/7 report as proof of new functionality. Caller relayed the independent reviewer's confirmation that orchid610 removal completed and its original source tool.mjs remained; final product report will retain that journey's detailed result.

Offline/restart, repaired-source update remaining disabled and the final product verdict were still being completed by the independent reviewer at this point. Their component/HTTP/native regression evidence was already reviewed; this closure does not declare those live acceptance steps passed or supersede the forthcoming acceptance report. Engineering verifier's sole missing real-reference evidence is now supplied, so R5-W1 is closed and the verifier verdict is **pass**, with corrected delta **aligned**.

## Test-only validity extension

- source validated_at remains `df579de5e8fb7c09626e132a28fd23f5663dae18`; effective_through `c4ba8d5ead802dbfaa911e0cd7ff5c0e6dd1198a`.
- Inspected the exact delta: one native lifecycle test file, 7 insertions / 1 replacement, no product source change. Prior code review and verifier pass remain valid; corrected delta remains aligned; no full re-review or whole-suite repeat is needed.
- New assertions exercise declared public behavior: while A is genuinely busy and a web mutation is pending, a same-workspace peer's plugin-manager mutation returns busy instead of joining a self-waiting queue. A second real busy turn accepts web enable as pending, then only the fixture's temporary DSH subprocess is SIGKILLed; restoring persisted bindings shows pending absent and the previously disabled tool still unavailable. These protect concurrent-management and interrupted-unapplied-state contracts through native dispatch/profile/restart, rather than asserting internal scheduling details.
- Inspected `/tmp/feat610-pending-restart.log`: complete native lifecycle **1 file / 1 test passed**, 14.05s. This evidence extends the earlier lifecycle regression; it does not claim a production or shared product service was killed. Product final acceptance and its offline/restore evidence remain owned by the independent reviewer.
- Verdict retained: **pass**, 0 CRITICAL / 0 WARNING / 0 SUGGESTION; requires_full_verification=false. This update changes only verification.md and is not committed by reviewer.

## Round 7 — Host resolution, preset compaction and offline receipt closure

- verification_mode: targeted-closure and corrected-delta.
- executed_base: `48ecbfec267343bf6df6f2d577c21fb1a8ea7733`.
- validated_at: `084b4ac18123db3b504e02e8c4a739dfc55577a6`; the caller committed the reviewed implementation while reports were being prepared; final committed text delta was checked.
- validated_issues: resolver disposal-order P2 closed; provisional offline GlobalAgent recovery guard P2 closed; real preset-compaction integration evidence warning closed.
- verdict: engineering pass; corrected-delta outcome: aligned.
- issues: 0 CRITICAL / 0 WARNING / 0 SUGGESTION.
- requires_full_verification: false.
- report_commit: caller-owned worktree; reviewer did not commit.

### Completeness and correctness

| Contract / decision | Implementation evidence | Validation inspected | Outcome |
|---|---|---|---|
| Public host dependencies with workspace scope | workspace-tools.ts imports public root app-boot exports, initializes native resolution for each actual profile/home, and isolates pluginPackages from manager auto-refresh | fixture imports host Cordis/LLM and verifies shared Context identity before real tool invocation; initial red/green and subsequent lifecycle green logs | covered |
| Keep dependencies available through cleanup and release native resolver stack | retained mappings precede Include update; old fiber inertia precedes latest table; creating serializes initial owner registration before reverse close | independent serial/concurrent resolver-control logs show the old failure; disposal-fixed.log reports concurrent restored:true; order-green.log passes | covered |
| Preset owns automatic and manual compaction; unrelated workspace and default path preserved | compaction.ts uses public serviceFor, returns null for both host automatic trigger paths when owned, and forwards manual compactNow; otherwise retains focused default path | model-policy branch regression and existing real default-focus command; installed native engine marker and compaction/summary, B isolation and disable assertions in workspace-tools.test.ts:184-207 | covered |
| Offline recovery proceeds while Web completed receipts wait for reconnect | main.ts restored; global-agent.ts:324-326 skips only not-ready non-external receipts and does not confirm them | receipt-red.log reproduces exception; receipt-green.log passes 32 tests; public recover with real stores proves external offline completion, durable Web pending state and one reconnect delivery | covered |
| Explicit third-party dependency/configuration scenario and Agent guidance | canonical Gateway spec :658-661 matches unit delta; description/manual explain existing-row user overlay, preset compaction, host yielding/manual routing and first-activation behavior | source/spec/manual reconciliation plus final2-targeted.log, 3 files / 35 tests passed, 19.98s; final2-typecheck.log all participating packages completed | aligned |

Evidence logs are under `/tmp/rollover-plugin-1015/`. `engine-integration.log` passes the complete extended native lifecycle in 20.53s; `combined-green.log` previously passed 2 files / 3 tests in 18.44s. Tests were inspected and reused rather than duplicated. The narrow trigger test by itself did not satisfy the integration requirement; the real installed-engine subprocess regression supplies that seam. The default-focus subprocess regression remains applicable to the absent-backend path.

### Coherence and limits

Native replace rejection is preserved for unsupported path/version changes. No private DSH imports, dependency copies, runtime fork, second Agent Loop or Node-to-DSH import boundary expansion was introduced. Native Worker resolution remains process-wide and is not represented as multi-workspace compatible. Approved R11 assigns custom backends their own compaction semantics; the fallback preserves Nano's existing focused summarizer.

The unique Corrected Delta Reconciliation section above includes the new Gateway scenario and the affected recovery behavior; outcome is aligned with no omitted reviewed observable behavior. Existing frontend reference evidence is unchanged and retained. The third-party dsh-context-rollover real-model journey is still running separately and is not declared accepted by this engineering report. Import success and a fixture backend do not establish that plugin's actual rollover result, deployment or release.

Only code-review.md and verification.md were edited by this reviewer. No product file, existing service or full-suite run was changed or operated; final whitespace check passed.
