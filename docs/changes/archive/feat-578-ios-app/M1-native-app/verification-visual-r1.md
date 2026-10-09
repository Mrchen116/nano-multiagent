# Visual Delta Implementation Verification — Round 1

> Unit: feat-578-ios-app. Mode: delta. Frozen reviewed head: `c8eafc360c4854154a1729fb377675674dda89e4`. Visual implementation base: `28ba862fc70eb7c558ea4bb5a4db914f4b3e52a3`; additionally reviewed that base commit's previously unreviewed invalid-credentials localization. Approved design delta: `c3587b9a3`, `design-review-visual-r3.md`. Existing R5 review and earlier implementation evidence are retained where unaffected.

## Summary

| Dimension | Result |
|---|---|
| Completeness | New visual structure is projected across Auth, four roots, conversation, Agent/profile/config and management titles; P6 evidence remains incomplete. |
| Correctness | One confirmed search-submit regression (V-W1/P2); no other concrete lost action/field/permission/draft/pending/conflict behavior found in the inspected delta. |
| Coherence | Native system controls, semantic light/dark colors, current API/store boundaries and agreed install sequencing preserved. |
| Verdict | **not_pass**: 1 CRITICAL known P6 evidence gate, 1 WARNING actual submit regression, 0 suggestions in this delta. No overall product/device acceptance. |

This review was limited to the actual native diff plus necessary previous handlers and current auth/SwiftUI contracts. It did not operate Simulator/browser/production, edit implementation or run full suites. Native screenshots were read from existing local files; no screenshots were captured by this verifier. Historical findings and pending gates are not mechanically invalidated or silently closed by visual restyling.

## Implementation and behavior projection

Locations are under `src/IM/ios/NanoIM/` unless otherwise stated.

| Delta area | Static consistency check | Result / evidence limit |
|---|---|---|
| Auth brand, persistent field labels, primary button, language and secondary connection controls | `Features/Auth/AuthView.swift:13–76`: same username/password/display-name/server/locale bindings; same authenticate, register toggle, recovery and local sign-out actions; same busy/empty/register/cooldown guards and countdown task. Connection disclosure changes presentation, not origin behavior. Password still clears only after authentication returns a user. | Retained semantics. Real login screenshot shows fields/main action; register, expanded connection/error/cooldown, keyboard and large-font states pending. |
| Invalid-credentials localization from base commit | `Client/CommonModels.swift:43–45`; current server `src/IM/api/routes/auth.py:203` emits the exact `invalid credentials` detail. Localization changes LocalizedError text while keeping original detail/status/code/retryAfter for handler logic. App authenticate uses localizedDescription. | Narrow contract aligns; no broad error rewriting or credential handling change. Historical actual feedback evidence from installed base remains useful; restyled error placement needs new rendered check. |
| Theme and shared root/search/avatar/time presentation | `UI/CommonViews.swift:26–108`, named color assets and `App/NanoIMApp.swift:19`: semantic colors have light/dark variants, root title uses system typography, TextField keeps bound values and a labeled clear action, timestamp derives from real ISO fields. | Source projection aligns with P6. Search submit trigger differs from searchable (V-W1 below). No dark/Dynamic Type/VoiceOver acceptance inferred. |
| Chat list/filter/search/preferences/navigation | `Features/Chat/ChatListView.swift:16–69`: filters and local search calculation unchanged; open, new-chat, distill, pin/mute and refresh handlers retained. Names/summary/time/unread use actual conversation fields; avatar kind is derived from actual type/category. | Native screenshot has continuous white list, title/time/summary/badges and more than five visible rows. This one simulator view does not prove both required widths or all states. |
| Conversation/composer/message cards | ConversationView background/padding/border/text color changes; same safeAreaInset, upload/pending/send/access guards, draft binding, UITextView/marked text behavior, menu and Photos/file presenter. ChatMessageView adds asymmetric spacing/border while retaining body/attachment/process/permission/statistics paths. | No new send/store/authorization behavior change. Media aspect-ratio and Photos presenter fixes remain in source. Actual revised conversation, keyboard, metrics expansion and media layout pending. |
| Tasks search/list/graph | `Features/Tasks/TasksView.swift:15–57`: same query binding, load/more/preservePages cursors and active-visible polling; title/status/mode/time come from server. Graph now uses top-leading frame and alignment anchor; relation, alternative list, node and reference callbacks unchanged. | Top alignment source projection retained; task-list screenshot is partial evidence. Immediate submitted search is regressed (V-W1); populated graph/paging/reference layouts need UI checks. |
| Agent root/profile/create | `Features/Agents/AgentsView.swift`: local search predicate, creation sheet, refresh and openChat handlers retained. `owned` still gates config/channels/Skills management; global Work remains separate. Name/ID/owner/mode/device come from contacts, not prototype fixtures. AgentCreate changes only title mode; cancellation/draft protection is unchanged. | Concrete native grouping exists; fresh Agent/profile/create screenshots and role journeys pending. |
| Config save/dirty/pending/conflict | `Features/Agents/AgentConfigView.swift:22–87`: toolbar save calls the same save handler and explicitly disables when no config, busy, pending, conflicted, unchanged or blank name. Editors retain pending/busy/conflicted disable; conflict reload/inspect/keep-vs-replace and pending reconciliation are still available. Back confirmation remains based on dirty/pending. | Source preserves existing version/draft lifecycle. The action is moved, not duplicated. Prior 409 behavior evidence remains relevant to handlers, but updated toolbar/disclosures need actual native interaction evidence. |
| Config complete field set and default selections | `AgentConfigView.swift:128–237`: model/effort/fallback ordering/group policy unchanged; custom prompt, tools, Skills, feature controls moved into disclosures. Existing skills selection-mode/default-discovery/explicit-empty distinctions, unavailable stored values and global fixed tools retained. Name/description remain bound. The primary-model onChange is restored to outer Section and still resets effort/removes matching fallback. | No field or binding deletion in diff. Collapse does not replace AgentDraft. Real expanded selection/preview/save/reopen evidence pending; source is not user-journey acceptance. |
| Me and management details | Me uses real user identity/admin information with existing account/device/company/policy/help/logout callbacks. Node, company, policy, binding, channels, cron, Work and chat-details changes are primarily inline navigation titles. Existing owner/admin guards, role failures, secret lifecycle, confirmation actions, paging and polling handlers are unchanged. | Existing behavioral evidence remains scoped to unchanged handlers. Revised representative management screens/long labels need P6 evidence. |

API/client/store/payload models and tests are unchanged in `28ba862fc..c8eafc360`; the deliberate earlier base-commit APIError localization is the only separately included client change. No new endpoint, mock product data, Web container or privilege path was introduced. New conversation examples are runtime fixtures in the isolated server, not native hard-coded design data.

## Evidence reviewed

- `design-review-visual-r3.md` records **Approved**, zero critical/warnings for the frozen design delta, including the actual 390/430 prototype save-label closure. Its own scope explicitly excludes SwiftUI acceptance. This is the design basis, not an App result.
- Independently opened existing `output/feat578/native-visual-login.png`, `native-visual-chats.png` and `native-visual-tasks.png`. They show actual Simulator chrome and the limited views described above. They are single iPhone 17 Pro screenshots with chrome, not a 390/430 evidence matrix or a Dynamic Type run. They do not establish the remaining P6 pages, register/keyboard/error states, dark mode, contrast across all controls, scrolling interaction or user acceptance.
- `/tmp/nano-feat578-visual-tests-r1.log`: `** TEST SUCCEEDED **`, 12 XCTest + 10 Swift Testing cases; xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_11-03-48-+0800.xcresult`. Existing tests protect Session/history/commands/uncertain sends and payload distinctions; they do not cover this ordinary TextField submit trigger or native layout. They precede the final onChange closure-position cleanup; final archive below covers its compilation. Do not label the test log as a separate final-head UI run.
- `/tmp/nano-feat578-visual-archive-r1.log`: final `c8eafc360` Release archive completed, `** ARCHIVE SUCCEEDED **`, actual packaged executable Mach-O arm64. `/tmp/nano-ios-build/NanoIM-unsigned.ipa` SHA256 independently read as `b6f0fc4ae4693c2f6254920c091933472f5f02392e0c57ed4596409e4cc955fa`. This covers final syntax/package compilation and establishes no physical install or free-signing result.
- `progress.md` explicitly states the last installed visual-build-r2 screenshots are partial and the revised Agent/config, conversation, graph, management representatives, 390/430 and Dynamic Type remain pending. Mac lock is an environment interruption, not a product code defect; no automatic unlocking was attempted here.

## P6 / reference projection

| Contract | Implementation projection | Evidence status |
|---|---|---|
| Compact root titles, neutral text, bounded page rhythm and real density | Shared root title/list/theme/search components; per-row actual fields | Three root/login captures inspectable; no full-page/viewport/font matrix |
| Login persistent labels/main action/secondary connection with all previous recovery controls | ScrollView+TextField/SecureField+disclosure; retained guards/actions | One login capture; register, keyboard, errors and large type pending |
| Conversation reading hierarchy and reachable safe-area composer | Card spacing, neutral surfaces/borders and UITextView composer retained | Actual revised conversation/keyboard/process/media layouts pending |
| Tasks relations top-aligned and existing semantics | Real list fields and top-leading graph frame/scroll alignment | Task-list screenshot only; graph/reference and submitted-query closure pending |
| Agent overview/message/Work/owned management order | Native profile Sections and unchanged owned/global guards | New revised native list/detail and nonowner cases pending |
| Complete grouped config with visible primary save and folded long capabilities | Toolbar save and retained bound field disclosures/confirmation paths | Updated 390/430 and large type, actual selections/conflict/pending pending |
| Me and representative long management/role/error screens | Real identity and inline system navigation, unchanged controls | New native evidence pending |

System material/font metrics may adapt as approved; source projection does not waive hierarchy, density, action reachability or the user's prior visual rejection. P6 is **not passed**.

## Issues

### CRITICAL — V-C1: new P6 exit evidence is incomplete (known gate)

Contract: `design.md` P6 and visual-quality paragraph; `design-review-visual-r3.md` preserves nine-page actual native comparison and ordinary/large type at representative 390/430 widths. Existing three screenshots and source/build checks do not complete it. The user's old visual rejection has not been closed by independent actual new App review. **Action:** after the user restores the operating environment, capture and independently review remaining native pages/states and both widths/large type, then resume remaining functional journeys. This is a known evidence gate, not a new code defect, and physical/Mini stages remain in the authorized later sequence.

### WARNING — V-W1: Tasks keyboard search no longer submits a query

Location: `src/IM/ios/NanoIM/Features/Tasks/TasksView.swift:35`, associated with the replacement at lines 16–17 and `UI/CommonViews.swift` NanoSearchField. Before the delta, searchable supplied a `.search` submission. Now the control is a regular TextField with `submitLabel(.search)`, while the view still listens only to `.search` triggers. [Apple's SubmitTriggers contract](https://developer.apple.com/documentation/swiftui/submittriggers) distinguishes regular text-control submissions from searchable submissions; the keyboard label does not change the control's trigger category. Typing and tapping “搜索” therefore does not call load(). The unchanged three-second poll can later load the query, which masks rather than preserves immediate submission. **Action:** use the default/`.text` onSubmit for this field, or explicitly forward its submit action, and verify pressing Search produces an immediate query without waiting for polling. Caller accepted the finding; no fix is included in this frozen report. `code-review-r6.json` records P2 CONFIRMED.

### SUGGESTION

None. No speculative abstraction, compatibility or extra design changes proposed.

## Retained evidence and handoff

R5 image-axis correction and prior API/session/uncertain-send/command/membership/payload conclusions remain applicable to unchanged mechanisms. Previous native semantic journeys support those particular behaviors, but do not certify the new layouts; previously open conflict-pending/media/Work/role/physical/signing branches stay open unless a separate direct result closes them. This delta does not reopen untouched modules or change final S1–S30 scope.

- `unit_id`: feat-578-ios-app
- `review_round`: visual-1
- `verification_mode`: delta
- `fix_delta_range`: `28ba862fc..c8eafc360`, plus base commit's APIError localization
- `verdict`: not_pass
- `issues`: critical=1 known P6 gate; warning=1 confirmed submit regression; suggestion=0
- `validated_issues`: V-W1 static mechanism/current Apple contract; V-C1 documented incomplete native evidence
- `requires_full_verification`: false — bounded delta reviewed; unaffected previous conclusions retained
- `report_path`: `docs/changes/feat-578-ios-app/M1-native-app/verification-visual-r1.md`
- `report_commit`: caller-owned; not committed by reviewer
- `top_concern`: restore the ordinary-field submit action, then obtain actual native P6 evidence without calling source/style changes visual acceptance.
