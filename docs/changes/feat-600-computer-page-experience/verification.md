# Verification Report: feat-600-computer-page-experience

> Validation snapshot: `290652ada2bf5fafbd4ac9f27a1514680ff78ca9 → 4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`.

## Round 1 — Full

- `unit_id`: `feat-600-computer-page-experience`; `review_round`: `1`; `verification_mode`: `full`.
- Branch/worktree: `codex/feat-596-node-update`, `/Users/czj/.codex/worktrees/feat-596-node-update/nano-multiagent`.
- `validated_at`: `4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`; `executed_base`: `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`.
- Product patch inspected: `bbc487e6da9cd69cfc5868906b2ce17ddbff3b6e..4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`.
- Verdict: **pass for implementation and contract verification**; **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. `requires_full_verification: false`.
- Delta alignment, checked within this full round: **aligned**. No delta repair or omitted stable public behavior found.

This report covers all four Requirements/eight Scenarios, design decisions, M1 A–D and the entire IM delta. M1's independent product-experience judgments are being performed in parallel and are **pending at this report's snapshot**; this static verdict does not declare that acceptance gate complete or the unit ready to deliver. The caller must combine the independent acceptance report with these results.

## Summary

| Dimension | Result |
|---|---|
| Completeness | 4/4 Requirements and 8/8 Scenarios have implementation; all four M1 worker/evidence projections mapped |
| Correctness | No implementation/contract mismatch found; focused regressions independently 12/12 pass |
| Coherence | Existing lifecycle/query ownership preserved; local UI structure and approved information hierarchy followed |
| Product acceptance | Separate independent reviewer pending; no visual or real-process acceptance inferred from tests |

## Completeness and Correctness

Paths below are relative to `src/IM/frontend/src/features/settings/nodes/` unless otherwise stated.

| Requirement / Scenario | Implementation evidence | Validation evidence | Result |
|---|---|---|---|
| Browsing, S1: identity, availability, present version and one useful action | `nodes-page.tsx:64-89`; `node-display.tsx:6-33`; `node-update-panel.tsx:49-70` removes current/inert update panels and preserves active/recovery priority | Status/update regressions; author final 1440/820/390/360 screenshots and M1 S1/S2 record | covered; overall density/readability is reviewer-owned |
| Browsing, S2: mobile, long names, full detail, return | `nodes-page.css:24-27,58-65,78-85`; `node-surface.tsx:29-42`; `node-details.tsx:28` | Four actual viewports and long-name/detail media in M1; inspected actual 1440/390 screenshots against the design images | explicit contract/evidence chain covered; live journey judgment pending |
| On-demand editing, S3: successful save, cancel, empty value, failed save, offline | `node-details.tsx:21-42` preserves draft and gates submission; `nodes-page.tsx:26-38,93` changes cached alias after success and invalidates other name owners | `nodes-page.test.tsx` save/empty/failure flow; `nodes-page-ws.test.tsx` actual WS frame retains draft and disables save; M1 detail recording | covered |
| On-demand diagnosis, S4: last connection and reconnect guidance; identifiers/errors below disclosure | `nodes-page.tsx:87`; `node-details.tsx:44,51-56`; `node-display.tsx:17-23` | `nodes-page-status.test.tsx` verifies hidden raw errors until diagnosis opens; author detail evidence | covered |
| Updating, S5: genuine stages, cancellation before switch, success/current version, retry after cancel | `node-update-panel.tsx:7-19,36-71`; `node-display.tsx:11-13`; no simulated completion timer | Existing update tests plus M1 actual waiting/cancel/switch/success operation IDs and media; POST results only invalidate instead of replacing newer WS state | covered; end-to-end experience remains reviewer-owned |
| Recovery, S6: old version available versus not recovered, appropriate retry or recovery, non-updateable reasons | `node-update-panel.tsx:49-70`; `node-connect-guide.tsx:18-40`; `node-details.tsx:25,42-43` | Update tests cover offline, relay-gated recovery link, next release, obsolete failure; M1 rollback/real-process preparation record; unchanged feat-596 process evidence retained only for underlying lifecycle | covered; complete new-page failure/recovery experience pending independent review |
| Connection, S7: existing/first computer entry, current-service instructions, return, unpublished installer | `nodes-page.tsx:69,73,92-95`; `node-connect-guide.tsx:13-41` | Page clipboard success/refusal and empty-to-connected regressions; M1 real service command and copy evidence | covered; missing-installer real screen included in parallel review scope |
| Reading, S8: initial loading/error retry and stale existing content | `nodes-page.tsx:65,71-76`; onboarding errors remain local to details/guide | `nodes-page-status.test.tsx` preserves existing list and warns after failed refetch; initial-query conditional inspected; M1 delegates complete real-browser abnormal states to reviewer | covered; real-browser abnormal-state judgment pending |

## Coherence

| Design decision | Evidence | Result |
|---|---|---|
| Page owns selected computer and authoritative live list; only alias is draft state | `nodes-page.tsx:21-56,93`; `node-details.tsx:21-25` | followed |
| Single update operation/mutation; retain uncertainty, query invalidation and WS/POST order | `node-update-panel.tsx:36-48`; no operation object is copied from POST; panel remains in the list only | followed |
| Recovery before ordinary offline; no timer-driven success or invented task/progress data | `node-display.tsx:26-33`; `node-update-panel.tsx:49-66` | followed |
| Desktop drawer/mobile full-screen, return context and keyboard focus | Existing Radix Dialog in `node-surface.tsx:29-42`; local CSS desktop/mobile rules; detail key uses node identity | followed; physical keyboard/mobile experience is not implied by build |
| Installation and assistant data reuse current authenticated API only when a sub-surface opens | `node-connect-guide.tsx:13-18`; `node-details.tsx:18-26`; existing create route at `:49` | followed |
| Local styling and both locales; no architecture/runtime change | `nodes-page.css`, `i18n/en.json`, `i18n/zh.json`; no changes to `apps/` or `packages/` | followed |

The design's reference to an existing alias API length limit does not introduce a missing validator: the actual current PATCH route (`apps/im-server/src/control.ts:584-604`) declares no such limit. Empty/trim behavior is implemented as specified. No hypothetical validation or backend change is requested.

## Prototype / Reference Contract

The reference contract in `design.md:94-104` has four must-match rows, all projected into M1 (`design.md:133`). Checked actual author artifacts against the prototype's daily desktop/mobile images for the explicit hierarchy and layout relationship; this is evidence-chain verification, not an independent aesthetic or full interaction acceptance.

| Reference contract | M1 projection | Implementation | Durable evidence | Status |
|---|---|---|---|---|
| Header summary, compact cards, single update action | A / S1–S2 | Page hierarchy and list; local responsive CSS; current/available projection | `/Users/czj/Movies/Nano-Computer-Page-20261014/author/author-{1440,820,390,360}.png`; M1 evidence version/build and viewport record | worker evidence covered; reviewer pending |
| Detail / inline rename / diagnosis | B / S3–S4 | Drawer, live selected record, alias form, diagnostics disclosure | `author-desktop-details.png`, `author-mobile-empty-name.png`, `author-mobile-save-failure.png`, `author-details.webm`; direct regressions | worker evidence covered; reviewer pending |
| Update stages, cancellation, failure/recovery | C / S5–S6 | Existing lifecycle and request-ID ownership, new presentation and guide | `author-mobile-{waiting,cancelled,switching,succeeded}.png`, `author-update.webm`; M1 real operation/PID record and underlying feat-596 evidence | worker evidence covered; expanded failure/recovery review pending |
| Empty/read-failure/connection guide | D / S7–S8 | Distinct page query branches and current-service connection guide | `author-mobile-connect.png`, `author-mobile-copy-failed.png`; empty/stale/copy regressions | implementation covered; complete abnormal-state/English real screens pending reviewer |

Media exist at the stated durable paths. Videos are genuine browser recordings whose encoded frame size is not a claim about the product viewport; M1 records viewport coverage separately. May-adapt icon/token details and out-of-scope global navigation, next-page creation, installation execution, toast and physical iPhone are not reclassified as missing work.

## Validation

- Independently ran the four direct nodes test files at the frozen HEAD: **4 files / 12 tests passed**, 2026-10-14 08:39 local time. The command and reviewed risk seams are in [code-review.md](code-review.md).
- Inspected version-scoped handed-off log results: `/tmp/computer600-frontend-all.log` **93 files / 870 passed**, `/tmp/computer600-backend-all.log` **79 files / 294 passed**, `/tmp/computer600-tests.log` final **12 passed**, `/tmp/computer600-build.log` final build **passed**, with `index-D9js0oX-.js` / `index-CYZZh8ip.css` matching M1. Reused the narrow/build rerun after localized copy/time/diagnostic changes; did not redundantly rerun whole suites.
- Caller additionally reports same-product-HEAD typecheck passed, non-E2E pytest **56 passed / 31 deselected**, Ruff check/format passed, docs-check **236 maintained sources / 64 routes** passed, npm audit **0 vulnerabilities** and architecture contract **13 passed**. These are attributed handoff evidence, not independently re-executed here.
- Independently confirmed no `apps/` or `packages/` patch. [Prior feat-596 verification](../archive/feat-596-node-update/verification.md), [code review](../archive/feat-596-node-update/code-review.md) and [acceptance](../archive/feat-596-node-update/acceptance.md) remain valid for the unchanged backend/chat/installer/runtime portions. New-page experience is owned by this unit's independent product review.
- Mechanical follow-up: committed-range diff check finds one extra EOF blank line at `node-display.tsx:35`, unlike the clean working-tree-only check in M1. Caller was notified to remove it and rerun the range check before delivery. This is outside the behavior/architecture findings; no scope expansion or functional retest is needed for deleting that line.

## Issues

- CRITICAL: none.
- WARNING: none.
- SUGGESTION: none.

Independent product acceptance is a pending parallel delivery gate, not an inferred implementation defect. This verifier neither operated its services nor changed its configuration/data/processes. The caller owns runtime cleanup and final gate integration.

## Delta Reconciliation Within Full Verification

This section records the complete delta alignment conclusion for later canonical merge. It does not change `verification_mode=full` or pretend the canonical merge has already happened.

| Delta item | Implementation and regression evidence | Outcome |
|---|---|---|
| `specs/im/agents-nodes.md:5-10`, identity/actual availability and progressive management | Page list name/status/version/action hierarchy, on-demand detail/diagnostics, neutral ordinary offline; update action absence is directly asserted | aligned |
| `specs/im/agents-nodes.md:12-14`, failed/live editing retains input and only success changes the list | Alias-only state; mutation success cache update; rejected-save and WS offline regressions | aligned |
| `specs/im/agents-nodes.md:16-20`, current-service connect/install/bind guide with unavailable-installer handling and return | Existing onboarding query and node-specific recovery command; no fabricated URL; absent command omits copy UI; real clipboard/error and empty-to-connected tests | aligned |
| `specs/im/agents-nodes.md:22-24`, retry first failure and retain/warn on stale loaded content | Query distinguishes undefined initial data from existing rows; stale test observes preserved card plus alert after refetch rejection | aligned |

### Uncovered Observable Behavior

None found requiring an additional canonical requirement. Responsive drawer/keyboard/diagnostic details refine the page's progressive-management promise in the implementation design; creation remains on its existing route. Clipboard fallback and local sub-surface query failures support the connection-guidance promise. Update/cancel/recovery semantics are already represented in the canonical feat-596 update lifecycle requirements and are deliberately not duplicated by this delta. No runtime/public endpoint, authorization, installer policy, global navigation or native iOS change was added.

Outcome: **aligned**. Canonical merge may retain these conclusions for this exact delta and unchanged product snapshot; no delta text was modified to fit an incorrect implementation. Final independent product acceptance and the mechanical range-check cleanup must still be integrated by the caller before delivery.
