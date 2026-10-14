# Code Review: feat-600-computer-page-experience

## Round 1

- Review mode: `patch`.
- Diff range: `bbc487e6da9cd69cfc5868906b2ce17ddbff3b6e..4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`.
- `validated_at`: `4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`.
- `executed_base`: `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`.
- Branch/worktree: `codex/feat-596-node-update`, `/Users/czj/.codex/worktrees/feat-596-node-update/nano-multiagent`.
- Verdict: **pass**. No confirmed or plausible actionable code defect remains in this patch.
- Focus findings: none. `requires_full_review: false`.

## Surviving findings

```json
[]
```

## Scope and evidence

Independently reviewed the complete patch: page/query and modal ownership, details and rename, installation/recovery instructions, update projection, local styles, both locales, changed regressions and unit evidence. Read this unit's spec/design/delta, current IM node contracts, `SPEC.md` and testing guidance. This is code review; independent real-product acceptance remains a separate gate.

- **Update authorization and asynchronous results:** `node-update-panel.tsx:36-48` retains the original request ID across an uncertain start response and clears it after a successful response or observed terminal lifecycle. `onSettled` invalidates the owned queries; it does not replace newer WS-derived state with a POST snapshot. The page keeps the one panel mounted per list item while details are open, rather than creating a second update mutation in the drawer.
- **Lifecycle precedence:** `node-update-panel.tsx:49-70` retains recovery before active state, active before ordinary availability, a newly available release before historical success, and actual current release before historical failure. Only requested/downloading/installing/waiting can cancel; switching/verifying/rollback cannot. Offline alone is not interpreted as evidence of a new release and does not expose an inert update action.
- **Live fields and drafts:** `nodes-page.tsx:40-56` updates only live connection fields in the existing query and invalidates when a new node appears. `node-details.tsx:21-42` owns only the alias draft and retains it through heartbeat/offline/error changes. Alias cache changes only after successful saving; list/chat/contact query invalidation remains explicit (`nodes-page.tsx:30-37`).
- **Availability and instructions:** recovery and switch states override transport status (`node-display.tsx:26-33`) and disable rename/creation (`node-details.tsx:25`). Connection instructions consume the existing authenticated onboarding response; recovery consumes the specific node's service-provided command. Missing installer/query failure and clipboard refusal have visible next actions. Legacy/recovery guidance retains the finish-current-tasks and preserve-data constraints in both locales.
- **Regression coverage:** the existing status/update files were updated around their original behavior seams; the page file adds coherent rename-failure and clipboard-risk protection. Tests assert user-visible outcomes and API payloads rather than new private helpers. Removed layout assertions concerned the intentionally replaced permanent form/KPI/heartbeat presentation.
- **Architecture:** independently confirmed `git diff --quiet <patch-base>..<validated_at> -- apps packages` passes. No runtime, DSH, backend, protocol, installer or chat implementation changed. The unchanged conclusions of [feat-596 code review](../archive/feat-596-node-update/code-review.md) remain applicable to those specific parts; this report does not re-review all PR #349.

Independently ran from `src/IM/frontend`:

```sh
npm test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/nodes/nodes-page-ws.test.tsx src/features/settings/nodes/nodes-page-status.test.tsx src/features/settings/nodes/node-update-panel.test.tsx
```

Result: **4 files / 12 tests passed**, 2026-10-14 08:39 local time. Checked the handed-off full-suite/build log tails: Web **93 files / 870 tests**, backend **79 files / 294 tests**, final build **passed**. Later localized copy/time/diagnostic changes have the final narrow tests and build recorded in [M1 evidence](M1/evidence.md).

## Mechanical delivery follow-up

The frozen committed patch's `git diff --check bbc487e6d..4068b2cfd` reports `node-display.tsx:35: new blank line at EOF`. An empty working-tree diff check cannot establish cleanliness of committed changes. Caller was notified to remove that final blank line and rerun the range check before delivery. This whitespace-only issue is not a behavioral code finding and does not require reopening the reviewed product scope.

No source, tests, configuration, design, runtime data or acceptance processes were modified during this review. Only this report and [verification.md](verification.md) were authored; the concurrent reviewer's untracked `output/` remains untouched.
