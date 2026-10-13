# Verification Report: feat-588 M1

## Round 1 — full

> Validation snapshot: main `6275f271d` (included with PR #337 in implementation base `e2e7aae53bd33a3257f33616d0311f1070d1e97a`) → `eff9d6daf0b44cd6d1297e08500697e97561fa69`.

- Date: 2026-10-13.
- Branch/worktree: `codex/feat-588-model-services`, `/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`.
- `verification_mode`: `full`; `review_round`: 1; `requires_full_verification`: false (this round is already full).
- The reviewer is independent of implementation. Current Gate 2 is R4 Approved. The rejected old UI judgment is not retained. This report verifies implementation and explicit contracts; independent product acceptance and remaining delivery CI are separate gates.

## Summary

| Dimension | Result |
|---|---|
| Completeness | S1–S9 have implementation and regression seams; M1 A–G mapped below. Separate product acceptance / delivery CI are not claimed complete. |
| Correctness | 7 scenarios aligned at the inspected implementation/test seams; S7/S8 have one confirmed cross-service credential deviation. |
| Coherence | Package/DSH responsibility boundaries followed; surviving legacy credential binding is not preserved during removal. |
| Issues | 0 CRITICAL / 1 WARNING / 0 SUGGESTION |
| Verdict | **FAIL — fix WARNING W1 before PR.** |

## Completeness

This is the simplified implementation flow, so a separate worker `tasks.md` is not required. Actual work and test ownership are recorded in `progress.md`. The single M1 implementation covers all named areas; the following table distinguishes implemented evidence from external gate outcomes.

| M1 exit criterion | Implementation / evidence | Result and boundary |
|---|---|---|
| A: permanent entry, computer/service identity, three widths | Router/menu/Me; `models-page.tsx:19–29`, `model-services-panel.tsx:123–157`, `models.css`; `evidence/ui-redesign.md` | Explicit layout and context contract covered; inspected current 1440/390/768 artifacts. Aesthetic/product verdict belongs to product reviewer. |
| B: API first, catalog/custom, multiple and same-ID models, edit to same assistant reply | `onboarding-page.tsx:113–121`, common editor, `model-setup.ts:77–137`, `configuration.ts:46–76`; relevant Node/DSH/Web tests and author real-reply artifacts | Implementation and regression seams present. Independent full browser journey is separately dispatched. |
| C: failure/cancel/conflict/dependency/offline recovery | `model-services-panel.tsx:39–79`, `:125–145`; `model-setup.ts:69–165`; configuration shared queue | Covered for tested operation failures and reference protection; W1 breaks the “other services unaffected” removal guarantee. |
| D: public exports, roundtrip/wire ID, write queue, rollback, no-secret, probe cleanup | Contract suite; `configuration.test.ts:64–105`, `model-setup.test.ts:31–115`, `model-probe.test.ts:7–42`, integration setup test | Relevant checks passed in shared evidence; independent real HTTP reproduction identifies a missing legacy-credential case (W1). |
| E: prototype/product comparison, inference/restart, installation evidence, independent gates/CI | `evidence/ui-redesign.md`, `evidence/release-distribution.md`, author screenshots/reply artifacts, test logs | Evidence chain exists. This static gate fails W1; independent product acceptance and final CI are not represented as passed here. |
| F: fixed IM version, direct package download and failure preservation | `install.ts:11–62`, `install.sh:47–68`, installer/onboarding tests | Implemented and isolated fixture-covered. Actual released asset / binding / production rollback not established. |
| G: manifest SHA/hash, old-path redirect, bad-hash protection and publish order | Build/publish scripts, `node-release.yml`, release tests; `evidence/release-distribution.md` | Candidate and deployable manifest are separate; promotion follows anonymous hash check. Actual publication/download evidence is deferred to the authorized release operation exactly as design permits. |

## Correctness

| Requirement / Scenario | Implementation seam | Regression / evidence | Status |
|---|---|---|---|
| S1 API-first first run; optional subscription | `onboarding-page.tsx:113`; `model-services-panel.tsx:60`, `:159`; editor `:36–48` | Onboarding tests and models tests; author API-to-assistant evidence | aligned at implementation seam; product acceptance separate |
| S2 permanent own-computer management; offline/missing clarity | Router/menu/Me; `models-page.tsx:19–29`; `onboarding.ts:27–55` | IM owner/transfer tests; models tests for missing/offline state | aligned |
| S3 runtime built-in provider/model catalog | integration `model-setup.ts:41–45`; Node `:47–64`; editor `:18–23`, `:40–55` | Locked-runtime setup test queries real catalog; models catalog/metadata tests | aligned; not a claim that every paid vendor key was tested |
| S4 custom service, multiple models, same wire ID | Node `model-setup.ts:83–112`; config `:46–76`; capability display names | Node setup test `:31`; configuration test `:64`; frontend selection normalization | aligned |
| S5 stable edit and blank credential retention | Node `model-setup.ts:102–106`, `:129–145`; editor `:11–14`, `:47` | Setup edit and legacy-inline-key migration tests; real DSH credential stage/rollback and next-session request | aligned for edited service |
| S6 failure/cancel/offline/conflict with explicit retry | Node setup `:51–56`, `:69`, `:137–165`; Web panel `:39–79`, `:125–139` | Node failed probe/cancel/busy/stale/YAML/child recovery tests; Web conflict/recovery/cancellation tests | aligned for tested failure boundaries |
| S7 prevent in-use removal; others unaffected | Configuration `:115–124`, `:134`; setup `:109–145`; Web panel `:143–145` | Shared Agent/model write-queue test and dependency UI tests; independent same-session HTTP reproduction | **deviation W1: remaining legacy service sends removed service's key** |
| S8 refresh/restart consistency | Persisted revision, safe snapshot, common editor; cold initialization from YAML | Configuration roundtrip, real DSH cold restart, author UI refresh/restart evidence | **deviation W1: successful removal changes B's live credentials until full node restart** |
| S9 pinned direct distribution and safe failures | IM install routes, shell, build/publish scripts, workflow | Installer/onboarding/bootstrap/release fixtures, local candidate build | aligned within explicitly documented pre-release validation boundary |

Gateway delta scenarios map to S4/S5/S6/S7/S8; IM delta scenarios map to S1/S2/S5/S6/S7/S9. No additional unit-diff observable behavior was found outside those deltas. Model label/metadata changes support the existing selection contract; `credential_stored` is the concrete boolean used for the design's safe has-credential projection.

## Coherence

| Design decision | Result | Code evidence |
|---|---|---|
| One editor for onboarding and daily settings | followed | Common `ModelServicesPanel` imported by both entrypoints; `ModelServiceEditor` owns shared fields. |
| Runtime API catalog; fixed provider identity; separate OAuth | followed | integration `model-setup.ts:41`; Node `:78–85`; editor `:40`; panel `:159`. |
| Stable product reference vs wire ID | followed | Node `:102–103`; configuration primary/fallback/approval conversion; capability metadata. |
| Probe outside live process; queue stage/YAML/rollback | followed for current credential-store routes; W1 affects surviving legacy env bindings | `model-probe.ts:7–25`; setup `:137–157`; configuration `:134–146`; integration `:23–65`. |
| Agent/model writes share final reference/revision check | followed | `configuration.ts:105–146`; existing queue regression asserts both orderings. |
| Preserve old model fields and API credential/OAuth semantics | followed for edited route; W1 blocks complete cross-service preservation | Model spread `model-setup.ts:103`; local credential read/stage/restore; OAuth removal message and preserve path. |
| Fixed GitHub distribution, manifest promotion and coordinated deployment | followed | IM manifest validation / redirect; `publish-node-release.mjs:18–46`; workflow; release evidence handoff. |
| Only integration imports declared public DSH exports; no second loop or HTTP kernel | followed | Inspected imports and `SPEC.md:39–50`; retained public dependency contract results. |

### Prototype / Reference Contract

The reviewer directly viewed the current author prototype desktop/mobile images and current real desktop/mobile/tablet images under the external artifact root recorded in `evidence/ui-redesign.md`. This establishes a concrete comparison of explicit layout contracts, not independent product acceptance. Old rejected UI artifacts were not used to approve the new layout.

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Compact computer context; name/type/models hierarchy; inline mobile actions | M1 A | `models-page.tsx:21–29`; panel `:146–155`; CSS context/row rules | `evidence/ui-redesign.md` links current `ui-after-desktop.png` / `ui-after-mobile.png`; compare current prototype images | covered for inspected explicit contract; full product states separate |
| One editor, compact mode switch, grouped fields; natural ending submit; fixed existing provider | M1 B | editor `:35–64`; panel `:125–139`; computer select `disabled={editing}` | Current `ui-after-add-tablet.png`, `ui-after-editor-mobile.png`, `ui-after-focus-click-mobile.png`; R4 focus evidence | covered; mobile submit is not sticky/floating |
| API feedback by form; Codex feedback in subscription section; recoverable draft comparison | M1 C | panel `:106–119`, `:131–139`, `:159–164`; Web tests for offline/conflict/cancel | `evidence/ui-redesign.md` authorization walk-through and current authorization image locator | explicit structure covered; product reviewer verifies full live error journeys |

## Evidence Reuse and Independent Verification

- Shared backend: `pnpm exec vitest run --fileParallelism=false` / `native-tests-serial.log`: 67 files / 205 tests passed. Python contract run: 54 passed, 31 e2e deselected. Frontend full run: 89 files / 842 tests passed. Tests were read alongside their results; these broad passes do not cover W1.
- UI redo after backend freeze: `/tmp/nano588-ui-tests.log`: 4 files / 22 tests passed; `/tmp/nano588-ui-final-test.log`: models 8 tests passed; final TypeScript + Vite build passed. Backend conclusions were reused because the intervening changes are Web layout/feedback only.
- Installation scope/results and pre-release limits are preserved in `evidence/release-distribution.md`; fixture commands do not prove a public Release or deployment.
- Independent critical mechanism check: real isolated DSH + OS-assigned HTTP port, two fake legacy inline keys, remove earlier service, submit to the same remaining-service session. **Failed**, directly observing `Bearer fixture-key-B` before vs `Bearer fixture-key-A` after, while removal reported `succeeded`. Complete trigger, call chain and output are preserved in [code-review.md](code-review.md#direct-evidence-for-the-finding).
- `git diff --check e2e7aae..eff9d6daf` passed. No user service/runtime or source/config/test/design was changed. Only this review's temporary DSH process/server/home were created and cleaned; `.runtime/` and `output/` remain untouched.

## Issues

### CRITICAL

None.

### WARNING

**W1 — surviving legacy service credentials change after removing an earlier service.** Contract: `spec.md:68–74` requires other services to remain unaffected and configuration to stay consistent; design decisions 3/4/6 preserve old references and connection behavior. Actual evidence: `apps/node/src/model-setup.ts:145` stages a newly indexed full provider map; `providers.ts:69` / `:85` select positional env bindings, while `main.ts:29` / `:46` retain the initial child env. A real same-session HTTP reproduction used key B before removal and key A afterward, with a successful operation result. This affects supported existing YAML inline-key configurations; the current legacy migration test only edits one service and cannot expose a remaining service's binding change.

Recommendation: preserve surviving credentials when recomputing live routes, then protect this exact two-service removal through the lowest real credential-resolution seam. Rerun affected model setup/profile/integration tests and the same-session reproduction; independently reverify W1 and any changed transaction/restart boundary. Do not change the spec to permit cross-service disruption.

### SUGGESTION

None.

One WARNING remains. This frozen implementation is not ready for PR until W1 is fixed and the separately required product acceptance / final CI gates are complete.

## Round 2 — targeted closure and corrected delta

- Date: 2026-10-13; same independent static reviewer as R1.
- `validated_at`: `c4e2517b96d22f7c1a38df22ac8259ec5ab96f68`.
- `executed_base`: `b7e367cc08a642133dea28e372816cd79038818d`.
- `verification_mode`: `targeted-closure`, plus `corrected-delta`; `fix_delta_range`: `eff9d6daf0b44cd6d1297e08500697e97561fa69..c4e2517b96d22f7c1a38df22ac8259ec5ab96f68`.
- `focus_issues`: W1; `requires_full_verification`: false.
- Verdict: **PASS for static verification — 0 CRITICAL / 0 WARNING / 0 SUGGESTION. Corrected delta outcome: aligned.** Independent product acceptance, canonical merge, final CI and actual release/deployment remain their respective owners' work.

### W1 closure

The fix replaces the positional env name with the full UTF-8 hex of immutable service ID (`apps/node/src/providers.ts:70`). It changes no profile fields, credential store format, probe or commit/rollback mechanism. Startup, live stage and recovery all recompute profiles through this same function, so removing A does not change B's key reference. `main.ts:29` / `:48` are the actual initial env capture and supervisor assembly locations (the R1 shorthand `:46` was imprecise).

Independently reran the R1 real DSH/HTTP reproduction at the frozen head, then rebuilt the child using the original startup env and current remaining profiles. The same B session sent `Bearer fixture-key-B` on all three requests: before removal, after successful A removal, and after child rebuild. Initial/live profile binding was identically `NANO_PROVIDER_6C65676163792D62_KEY`. Full durable output and command are appended in [code-review Round 2](code-review.md#round-2--closure). This closes the S7/S8 deviation; all nine scenario implementation mappings now align within their documented evidence boundaries.

Reviewed permanent regression `apps/node/tests/providers.test.ts:11–77`: two real inline-key providers, actual `ModelSetup.remove`, same-session completed requests, and actual Authorization header assertion. Shared red log proves the old B→A failure; shared green log records 4 files / 15 tests passed across providers/model-setup/configuration/integration setup. These logs and source were inspected; no unrelated full suite was rerun. Child-rebuild evidence validates env/profile consistency, not a whole-node lifecycle or full browser acceptance.

### Retained conclusions and base impact

R1 completeness, architecture, unaffected correctness, explicit prototype comparison and installation evidence boundaries remain valid. Compared the complete fix delta and main increment: only the env-name implementation and its regression changed; main added two unrelated feat-589 requirement documents. No Web, IM source, installer/publisher, model probe/transaction, spec, design or prototype changed. Current Gate 2 R4 remains applicable; the old rejected UI judgment remains invalid. Product reviewer continues separately on the eff9 build; this static pass does not issue a product verdict.

`git diff --check eff9d6daf..c4e2517b9` passed. Only assigned reports were edited. Independent fixture resources were cleaned; existing `.runtime/`, `output/`, user service 52267 and shared model fixtures were preserved.

## Corrected Delta Reconciliation

Scope: read both complete delta files at the frozen head, the canonical target for the modified IM requirement, their R1 implementation/test mappings, and the whole implementation delta for uncovered observable behavior. The IM MODIFIED item completes the canonical replacement of the old discovered-connection wording; it does not expand or weaken the accepted feature scope. The R1 statement that no behavior was omitted is refined here: the already-implemented removal of developer-proxy autodiscovery is now explicitly represented as MODIFIED, avoiding contradictory canonical wording after merge.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| IM MODIFIED `页面完成模型连接` / 验证与失败恢复 (`specs/im/agents-nodes.md:5–11`) | API-first common panel at `onboarding-page.tsx:113`; catalog/custom switches and optional subscription; Node setup no longer imports/scans local proxy configuration | Existing onboarding + models component tests, Node setup real-request probe and failure/cancel tests, R1 author evidence | aligned; replaces the exact current requirement at `docs/specs/im/agents-nodes.md:733` with a complete modified entry |
| IM ADDED / 首次 API 接入 (`:17–19`) | Common panel initial API draft; subscription separated | Onboarding tests; models catalog selection test | aligned |
| IM ADDED / 日常新增和编辑 (`:21–24`) | Permanent route/menu/Me, computer scope, safe fields; owner check before/after relay | Models edit/blank-key/missing/offline tests; IM owner-transfer/safe projection tests | aligned |
| IM ADDED / 未完成保存保留草稿 (`:26–28`) | Revision-bound local draft; conflict comparison/reapply; explicit pending/cancel terminal feedback | Models conflict/offline/cancel tests; Node failed probe/stale revision tests | aligned |
| IM ADDED / 依赖保护 (`:30–32`) | Shared final Agent/reference check, dependency names and confirmation UI | Configuration interleaving tests; models dependency test; W1 actual header regression now preserves remaining services | aligned |
| IM ADDED / 安装当前服务配套版本 (`:36–38`) | Fixed full SHA manifest and GitHub URL; script direct download; origin-bound setup | Onboarding manifest/redirect tests, installer/bootstrap tests, release fixture | aligned within design's pre-publication boundary |
| IM ADDED / 下载失败保留原安装 (`:40–42`) | Hash before promotion; failure cleanup and previous install/config preserved | Installer malformed manifest/download/hash tests; publication failure manifest preservation tests | aligned |
| Gateway ADDED / 同名上游模型分属不同服务 (`specs/gateway/agent-capabilities.md:7–9`) | Stable product model reference and provider-qualified wire ID resolution | Node setup duplicate IDs; configuration primary/fallback/approval wire-ID test | aligned |
| Gateway ADDED / 成功编辑与失败恢复 (`:11–14`) | Isolated candidate probe, shared queue apply/rollback, persisted revision | Node setup edit/cancel/YAML/child recovery tests; real DSH stage/rollback/cold restart; new remaining-service live request regression | aligned |
| Gateway ADDED / 拒绝旧版本与在用引用移除 (`:16–18`) | Preflight/final revision/reference check; Agent save re-resolves inside same queue | Configuration both-order interleaving and stale writes; Node dependency tests | aligned |
| Gateway ADDED / 凭据限于执行电脑 (`:20–22`) | Local stdio credential record; API key excluded from YAML and nested IM response projection; blank retains record | Node blank-key/migration tests; IM nested safe projection; real credential stage/rollback | aligned |

### Uncovered Observable Behavior

None remaining. The env-name fix is internal and restores the existing S7/S8 guarantee; it does not add a new user-facing contract. Model display labels and metadata support service-qualified selection already in the deltas. The corrected IM MODIFIED requirement explicitly covers the retired developer-proxy discovery path. Native iOS model management, automatic publication/deployment and comprehensive paid-vendor acceptance remain outside the accepted scope.

Outcome: **aligned**. Canonical documents are still current baseline documents at this validation snapshot; their subsequent merge must apply the listed MODIFIED replacement and ADDED entries together, without retaining the obsolete discovery sentence.

## Round 3 — targeted closure: built-in catalog identity

- Date: 2026-10-13; same independent verifier.
- `validated_at`: `6309714219ba8cc1432e5e1752a94b50a7d8ad35`.
- `executed_base`: `b7e367cc08a642133dea28e372816cd79038818d`.
- `verification_mode`: `targeted-closure`; `fix_delta_range`: `310c63f85b8ce82a2f4ebea5171717388248f876..6309714219ba8cc1432e5e1752a94b50a7d8ad35`.
- `focus_issues`: Product-R1 built-in directory identity after service rename/cold initialization; retained W1 closure.
- `requires_full_verification`: false.
- Verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION.** Independent targeted product acceptance remains separate.

| Contract / focus | Implementation and evidence | Alignment |
|---|---|---|
| S3 built-in provider directory; design decision 2's fixed provider identity | Native profile no longer overrides the DSH provider `displayName` (`providers.ts:60–66`). Real DSH cold initialization compares the empty-profile catalog with a renamed configured DeepSeek service (`providers.test.ts:11–33`); shared red evidence reproduced `deepseek` → `My Research API`, green evidence passes. | Product-R1 defect closed at the implementation/test seam. Cached catalog has the same correct built-in identity from initialization, including after service removal. |
| S5 editable service name; design decision 3's stable service ID | Node keeps `display_name` in YAML, status and Agent capability labels (`model-setup.ts:62`, `:105`; `capabilities.ts:52`); native runtime profile no longer owns this product label. Custom runtime `displayName` remains (`providers.ts:79`). | aligned; independent source exercise confirms native product label and custom profile label remain intact. |
| S7/S8 surviving credentials; W1 | Stable provider-name hex env binding (`providers.ts:70`) is unchanged. Same-session HTTP regression remains and is part of the green provider-file run. Independent profile exercise confirms removing the other service leaves B's key name unchanged. | W1 remains closed; R2 real HTTP/rebuilt-child evidence retained. |

Inspected `/tmp/nano588-catalog-red.log` and `/tmp/nano588-catalog-green.log`, the actual regression source and the full patch. Green result: 4 files / 11 tests passed across providers/model-setup/capabilities/integration setup; node typecheck pass is provided by the author handoff. Reused these relevant results without an unrelated full-suite rerun. No implementation, tests, configuration or design were changed by the reviewer.

The fix restores accepted identity/catalog behavior without changing the design or public API, so no design revision is needed. Both complete delta files are unchanged; Round 2's corrected-delta outcome **aligned** remains effective through this validation head. All unaffected R2 completeness/correctness/coherence and explicit reference-contract findings are retained. Browser acceptance and the separately documented test-upstream terminal failures are not decided by this static closure.

`git diff --check c4e2517b9..630971421` passed. No runtime was started or restarted, no service data was modified, and no new fixture resources require cleanup. Existing user service 52267, shared model fixtures, `.runtime/` and `output/` were preserved.
