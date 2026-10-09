# Verification Report: feat-578-ios-app — Round 1

> Mode: full. Executed base: `76fe1d7e7`. Native implementation validated at: `b970e20a60c0d1e18bc10d1d734b75d3d11cf4d6`. CI reviewed at: `723414c9f`. Repository HEAD observed while reporting: `7cdb515c9587451324e4d7e840c6b53140a6f0fe`; the merge adds Web viewport work and a manifest route, with no change under `src/IM/ios` or to the reviewed iOS CI job. Fixed-version conclusions do not certify subsequent native fixes.

## Summary

| Dimension | Result |
|---|---|
| Completeness | C01–C34 and R1–R12 all have implementation projections; M1 is not complete. C09 is partial; C34 has build/help but no physical installation/renewal evidence. |
| Correctness | One confirmed current-contract mismatch in C09; two required behavioral regression areas lack evidence. Existing 21 native tests and the Release archive remain valid. |
| Coherence | Native/client/server responsibilities, credential boundaries, typed models, workspace/mode constraints and no-APNs decision follow design. |
| Verdict | **not_pass**: 1 CRITICAL exit-standard blocker, 2 WARNINGs, 0 suggestions. The CRITICAL is a known incomplete delivery gate, not a newly discovered code defect. |

This verifier inspected source, server contracts, tests, requirement/design/coverage documents and recorded artifacts. It did not operate a simulator, phone, Mini, Bot or service, rerun already valid tests, or grant product/device acceptance. Independent simulator product review was still in progress at this snapshot. The user's sequence remains implementation and simulator first, then physical phone/Mini/free signing; no final S1–S30 scenario is waived.

## Evidence and its limits

- Native XCTest run at the fixed implementation: `/tmp/nano-feat578-xctest-r3.log`, `** TEST SUCCEEDED **`, 11 XCTest and 10 Swift Testing cases, zero failures; result bundle `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_01-56-09-+0800.xcresult`. Session tests cover refresh single-flight, bearer-only requests, late-response isolation, rotated-token logout, transient versus unauthorized refresh, and origin rejection. Chat tests cover cursor-free removal, authorized rename retaining drafts, a gap spanning more than one history page, canonical timeline merge/discard, and command/mention identity. Agent/Settings tests cover actual payload distinctions and Work replay/child data, not all management journeys.
- Review closure evidence remains applicable: `code-review-r1.json`, `closure-r2.md`, `closure-r3.md`; R3 has no surviving finding. Membership red and green logs prove failure before the fix and success after it. This does not expand closure into full product acceptance.
- Release build: `/tmp/nano-feat578-archive-r3.log`, `** ARCHIVE SUCCEEDED **`, device executable reported as Mach-O arm64. `/tmp/nano-ios-build/NanoIM-unsigned.ipa` SHA256 independently read as `c7652da3095a92843bb801c8f85137375a38b58e7837ecb9e1954546654439aa`. It is an unsigned archive for re-signing, not proof of installation or profile expiry.
- Actual DTO decode harness and responses are in `/tmp/nano-feat578-ios-api/`: sync, contacts, config, capabilities, account, conversation, messages, nodes, task graphs, policies and capacity. The harness uses actual Swift models. Empty messages/tasks responses prove envelopes, not task graphs, tool execution, pagination or mutations. Reusing this evidence does not imply that every endpoint was exercised.
- `progress.md:43–55` records the real native peer send/reply and rename, and local Python 4119/Web 804 tests. The peer screenshot is a local artifact, not this verifier's UI observation. The source/tests and build evidence are separately inspectable. Docs log reports 251 sources/75 routes; Ruff and formatting logs pass, with 1134 formatted files. Neither these suites nor typecheck proves native journeys.
- The HTML prototype's 390/430/600 rendering in `evidence/design-validation.md` validates the reference only. It cannot stand in for native layouts, IME, keyboard, Dynamic Type, VoiceOver, system media, foreground restoration, phone networking or signing.

## Completeness

M1 has one implementation milestone rather than a set of checked task boxes. All feature areas in `tasks.md` have source owners and native screens, and all 34 coverage rows below have an implementation projection. This is **not** a claim that 34/34 are accepted or that M1-R1/W1/W2/W3 are complete.

| Exit standard (`design.md:168`) | Established | Still open |
|---|---|---|
| M1-R1 | Independent code review/closures, actual App launch and narrow real chat evidence | Independent native product review for all S1–S30/C01–C34/P1–P5; management, task/Work, media and failure journeys need their own results. |
| M1-W1 | Native test execution, actual DTO envelopes, simulator build/test, current arm64 Release archive, fixed Markdown dependency | Required uncertain-write and version-conflict behavior evidence (W-02); C09 correction (W-01). Existing green tests do not cover these seams. |
| M1-W2 | Native source uses system layouts/controls and reference contract is explicitly projected | Native 390/430/600 and Dynamic Type durable comparison; actual IME/keyboard/permissions/foreground evidence, including the required physical-device boundary. |
| M1-W3 | Unsigned IPA and installation/recovery plan exist; static review closure is clear | Free signing/install, unplugged same-Wi-Fi refresh, genuine expiry/recovery, phone HTTPS/WSS/media access, Mini conditions, completed independent gates, current-spec merge and remote CI/PR. |

The pending physical-resource rows are the agreed later execution stage. They are recorded because a full verifier cannot close M1 without them, not because implementation should have waited for device access.

## Correctness: requirement and scenario mapping

Source locations below are relative to `src/IM/ios/NanoIM/` unless prefixed otherwise. “Projected” means a concrete code path exists and was inspected; it does not mean a native user journey passed. Existing tests are deliberately listed only where they prove the stated property.

| Requirement / scenarios | Implementation | Evidence / status |
|---|---|---|
| R1 / S1–S2: native navigation, input, accessibility | `App/NanoIMApp.swift:93`, `Features/Chat/ConversationView.swift:20`, UIKit composer and `UI/MarkdownView.swift:5` | Four native stacks and system input/selection exist. IME, long form, widths, Dynamic Type and VoiceOver remain product/device evidence. |
| R2 / S3–S4: auth, company eligibility, isolation | `Features/Auth/AuthView.swift:3,48`, `Client/Session.swift:4`, `Client/CredentialStore.swift:29`, root session identity | SessionTests establish key request/isolation behavior; actual login is recorded. Pending/suspended UI and A→B rendered journeys remain pending. |
| R3 / S5–S9: chat lifecycle, preferences, commands/history, uncertain send, fork/distill | ChatList/NewChat/Info/Conversation, `ChatStore.swift:175`, `ChatAPI.swift`, `ChatText.swift` | Command targeting, membership reconciliation and >one-page recovery have regression evidence. Management/fork/distill UI pending; uncertain-send seam is W-02. |
| R4 / S10–S11: system media, order, retry, permissions | `ConversationView.swift:79–80`, upload helpers, `UI/MediaViews.swift:4,35`, `Client/Transport.swift:8` | Raw upload, protected read, no authenticated external image load, QuickLook/share and scoped temp cleanup are projected. Origin test is valid; media/revoke/share native journeys pending. |
| R5 / S12–S13: process, metrics, permissions | `ChatMessageView.swift:24–52,85`, `AgentWorkView.swift:138,231,265` | Process and actual options/state are represented; Work replay/child usage tests exist. Chat metrics differ from inherited contract (W-01); real approval delays pending. |
| R6 / S14–S15: Tasks and main/child Work | `TasksView.swift:3,51,134,169`, `AgentWorkView.swift:4,89` | Native graph/list, relation and node details, nested navigation, draft reference, paged turns/items and child sessions projected. Work payload tests establish data handling; populated graph and permission-bound links need real runtime evidence. |
| R7 / S16–S19: create/config/preview/skills/heartbeat/cron | `AgentsView.swift:100`, `AgentConfigView.swift:3,115,225`, `AgentSkillsView.swift:4,89` | All intended forms, immutable mode/path, default discovery vs explicit empty, feature prerequisites and preview fields present; payload tests valid. Conflict/pending behavior lacks regression evidence (W-02); writes/Skills/cron UI pending. |
| R8 / S20–S21: channels, credentials, observed state/removal | `AgentChannelsView.swift:3,107`, `AgentChannelModels.swift` | Secure input, keep/replace, CAS, actual diagnostics and removal retry projected; removal DTO test valid. Dedicated real Bot lifecycle remains pending. |
| R9 / S22–S23: binding and nodes | `SettingsBindingView.swift:3`, `SettingsNodesView.swift:3,55` | Fragment-token same-origin parsing, waiting-local commit, inspect/accept/decline and owned-node forms projected; binding contract tests valid. Real two-ended binding/node writes pending. |
| R10 / S24–S26: account, membership, policy/capacity | `MeView.swift:64`, `SettingsCompanyView.swift:3`, `SettingsPoliciesView.swift:3` | `/me` explicit-null default device, member paging/admin guards, policy forms and admin capacity projected; actual response DTOs and null test valid. Actual role/mutation/failure journeys pending. |
| R11 / S27–S28: reminders/background truth | `NanoIMApp.swift:154–162`, ChatStore live/replay filtering, `MeView.swift:151` | Actionable optional banner and foreground reconfirmation exist; no APNs entitlement or false push state. Real live/replay/background behavior remains pending. |
| R12 / S29–S30: free installation/renewal/recovery | `scripts/build.sh:18`, `MeView.swift:151`, `installation-plan.md` | Current arm64 IPA/help/sequence established. No physical free-signing, profile or same-network/expiry evidence; C-01. |

### C01–C34 projection

This table cross-checks the coverage document's complete scope, not just the initial milestone split. Native UI evidence for all rows remains owned by the independent product review.

| ID | Concrete source / interface projection | Evidence qualification |
|---|---|---|
| C01 | AuthView/MembershipView; Session login/register/refresh/logout/me | Session tests + narrow actual login; membership UI pending |
| C02 | ChatListView; ChatStore list/sync/read | DTO/list/state tests; native category/preferences/read scrolling pending |
| C03 | `ChatListView.swift:61` contacts/new direct/group | Real peer chat exists; group lifecycle pending |
| C04 | `ChatInfoView.swift:3` rename/participants/delete | Actual rename recorded; membership rename/removal regressions; full lifecycle pending |
| C05 | ConversationView composer; Markdown AST; ChatText/commands | Exact identity/Skill namespace tests; IME/GFM/paste native journey pending |
| C06 | TimelineItem union/TimelineMerge; ChatStore paged history | Overlap/discard and >one-page gap regressions; scrolling evidence pending |
| C07 | MediaViews + PhotosPicker/fileImporter/paste/raw upload | Origin test and source boundaries; real native media pipeline pending |
| C08 | Conversation fork menu; `ChatListView.swift:107` DistillView | API projection; actual fork/distill pending |
| C09 | ChatMessageView process and metrics, Work item/usage views | Work replay/data tests; chat metrics partial (W-01) |
| C10 | `ChatMessageView.swift:85` ChatPermissionCard | Actual options/submitted/resolved projection; runtime confirmation pending |
| C11 | TasksView/TaskGraphView/TaskNodeView | Search/pages/deep links/graph projected; initial DTO envelope is not populated graph evidence |
| C12 | `TasksView.swift:169` GroupTasksView; root reference appends draft | API and draft path projected; real relations/reference pending |
| C13 | AgentsView/Profile; contacts + direct conversation | Actual contacts DTO; nonowner/public and management boundaries pending native role evidence |
| C14 | AgentWorkView/TurnView/ItemView; sessions/turns/items cursor APIs | Child/paging DTO and replay tests; actual main/child execution journey pending |
| C15 | `AgentWorkView.swift:265` permission card | Actual options/owner boundary in code; real delay/confirmation pending |
| C16 | `AgentsView.swift:100` create; node caps/default/custom path | Creation/global/discovery payload tests; actual create/draft/error journey pending |
| C17 | AgentConfigView basic/model/fallback/effort/policy | Payload/order tests; conflict/pending behavior W-02 |
| C18 | AgentEditorFields features/tools/skills/custom prompt | Explicit-empty/discovery/prerequisite tests; full capabilities native interactions pending |
| C19 | Create/config prompt preview using current draft | Preview feature-switch and scope payload tests; actual preview UI pending |
| C20 | `AgentConfigView.swift:225` heartbeat/active hours/HEARTBEAT.md | Heartbeat payload preservation; actual read/save pending |
| C21 | AgentCronView at `/cron/jobs`; config cron toggle | View/delete/confirmation and node-state distinctions present; real deletion pending |
| C22 | AgentSkillsView list/agent/health, chart, refs | All source codes and server bucket order projected; populated usage/references pending |
| C23 | AgentChannelEditor; provider + keep/replace secure input | Existing contract projection; dedicated Bot write/credential behavior pending |
| C24 | Channel/removal state, reconnect/DELETE/retry CAS | Removal-state decoding test; actual stop/reconnect/retry pending |
| C25 | SettingsNodesView/NodeView alias/relay/report/create | Actual nodes DTO; owned node changes and offline transition pending |
| C26 | SettingsBindingView inspect/accept/decline/wait | Link/origin/fragment and state-only cancellation tests; actual commit/expired paths pending |
| C27 | SettingsAccountView `/me` profile/default/locale | Explicit-null contract test + actual account DTO; native save/reopen pending |
| C28 | SettingsCompanyView paging/approve/suspend | Server enforces admin/last-admin; actual role/mutation/revocation journey pending |
| C29 | SettingsPoliciesView all current policy fields/read-only role | Actual policy DTO; admin save/ordinary read/failure draft pending |
| C30 | SettingsCapacity loaded only for admin | Actual capacity DTO; permission/error presentation journey pending |
| C31 | RootTabs + MeView + locale helper + signOut | Four-stack implementation/session tests; complete language/accessibility journey pending |
| C32 | AgentProfileView Sessions placeholder | Matches the intentional Web placeholder; no invented endpoint or completed Sessions feature claimed |
| C33 | Optional local foreground banner + help; no APNs | Actionable target source verified; live/replay/background runtime pending |
| C34 | Unsigned arm64 archive + native help + install plan | Artifact is current; physical free signing/refresh/expiry recovery pending |

## Coherence

| Design decision | Result | Evidence |
|---|---|---|
| Independent native client; no internal Web container/fifth server/cross-product imports | Followed | SwiftUI/UITextView/Markdown/native Task/Work/management screens; client calls public IM HTTP/WS. No WKWebView management delegation. |
| HTTPS origin; Release ATS normal; no credentials to external sites | Followed | ServerOrigin and redirect delegate; Release plist; SessionTests foreign-origin assertions. Debug loopback permission is build-specific. |
| Keychain per-origin, WhenUnlockedThisDeviceOnly; access in memory, generation isolation | Followed | CredentialStore/Session; single-flight and logout/late-response tests. Simulator ad-hoc signing restoration addresses actual entitlement failure. |
| Caller-key uncertain send, no persistent automatic queue | Mechanism present, evidence incomplete | PendingSend/ChatAPI and `ChatStore.swift:175–204`; W-02. Native code does not promise cross-restart queued sends. |
| Versioned config, pending vs conflict, preserved draft; channel CAS/secret lifecycle | Mechanisms present, config evidence incomplete | `AgentConfigView.swift:91–106`; channel editor/receipt; W-02. Server permissions remain authoritative. |
| Stream invalidation rereads canonical snapshots; ID merge/tombstones; active only | Followed at inspected seams | ChatStore/UserStream, Timeline and ChatState tests. Real reconnect/replay still requires runtime evidence. |
| Global fixed tools; immutable existing workspace/mode; skills discovery distinction | Followed | AgentDraft/Editor/Create payload tests. Current capabilities supply directories/models. |
| Task reads and references, Work child sessions; no native task writes | Followed | Native Task view has read/reference actions; Work links preserve main/child identity and server-mediated chat authority. |
| No paid-signing/APNs requirement; actual tool owns expiry truth | Followed as implementation/plan | Help/install plan and unsigned archive; no derived build-date expiry status. Device capability remains unproven. |

### Prototype / Reference Contract

| Contract (`design.md:119–123`) | Milestone projection | Implementation evidence | Durable evidence / status |
|---|---|---|---|
| P1 entries/details/keyboard composer | M1-R1/W2, S1–2/S7 | Root stacks, Conversation safe-area composer, system form/input | HTML reference is documented; native widths/keyboard/IME/DT comparison pending |
| P2 graph→node→chat reference | M1-R1/W2, S14 | Tasks graph/node and draft reference callback | No completed populated native journey evidence at this snapshot |
| P3 Work→child, pending approvals | M1-R1/W2, S12–15 | AgentWork nested session/turn/items and permissions | DTO/replay tests available; actual main/child/approval reference comparison pending |
| P4 all management and errors | M1-R1/W2, S16–26 | Agent/config/channels, Me/node/company/policy native screens | All projected; runtime role/offline/conflict/long-form evidence incomplete |
| P5 reminders/install/background truth | M1-R1/W2, S27–30 | Banner/Me help, archive/install plan | Source/help established; live/background and actual signing comparison pending |

The verifier checks explicit structure, behavior and evidence linkage; visual quality remains the product reviewer's decision. Reference HTML screenshots do not satisfy native must-match evidence by themselves.

## Issues

### CRITICAL

**C-01 — M1 final exit standards are incomplete (known gate, not a code defect).** Contract: `design.md:168`, S1–S30, and coverage C01–C34. Evidence: `progress.md:25–29,43–55`, installation/resource records, and the matrix above. Independent simulator review is still active; the full native comparison and many real mutations/Task/Work/media/failure journeys are not yet recorded. Physical phone/free signing, USB-unplugged same-network renewal, genuine expiry recovery, and phone HTTPS/WSS access are explicitly later work. Remote CI/PR and current-spec merge also remain open. **Action:** finish the simulator journeys first, then execute the authorized phone/Mini stage and preserve actual evidence. Integrate independent product results and final current documentation/remote CI before closing M1. Do not waive or relabel pending resource gates as passed.

### WARNING

**W-01 — C09 omits existing chat response-metrics behavior.** Contract: coverage C09 and the delta's preservation of current IM business behavior; `docs/specs/im/response-metrics.md:18–20,38–49,62–72`. Implementation: `src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift:44–52`. While an Agent message is running, `elapsed_ms` is absent by server contract, so the native view shows no increasing wall-clock timer; it only renders final elapsed_ms. Token usage is one always-visible line without the default-collapsed inline detail and cache hit quantity required by the current contract. Existing process disclosures are not a usage disclosure. **Action:** implement the running/final Agent wall-clock and expandable inline usage/cache detail in the native message view, preserving unknown/absent values and current cache accounting; add focused behavioral/formatting protection and record native rendering evidence. Do not silently weaken C09/current spec. Caller independently confirmed the omission; fixes are outside this fixed snapshot.

**W-02 — Required uncertain-write and configuration-conflict behavior lacks regression evidence.** Contract: `design.md:85–86,168` (M1-W1), S8/S18, and testing guidelines' observable-seam rule. Implementation seams: `ChatStore.swift:175–204`, `ChatAPI.swift` caller key, `AgentConfigView.swift:91–106`. The 21-test suite exercises read/history/session/DTO/payload behavior. It does not simulate server persistence plus lost send response/503 and prove no automatic retransmission, stable key on explicit retry and one canonical message. Nor does it exercise config 409 or `config_apply_pending` with retained draft, blocked duplicate saves and authoritative re-read/resolution. Assertions that a payload contains profile_version are not conflict-recovery tests. **Action:** add the meaningful HTTPTransport-level send regression; for configuration provide reproducible real native concurrent-conflict/pending evidence, and the necessary enduring behavior regression at an appropriate seam if it can be exposed simply. Avoid tests that mirror private SwiftUI state. Until those required properties have evidence, M1-W1 is not satisfied; this warning does not assert that the current recovery implementation is wrong.

### SUGGESTION

None. No speculative compatibility or abstraction changes requested.

## Delta reconciliation

| Delta requirement | Reconciliation |
|---|---|
| Independent native client preserving IM business/permissions | Native full-scope projection present; inherited C09 mismatch W-01 must be corrected. |
| Session recovery/isolation and foreground convergence | Inspected implementation and existing regressions align; uncertain-send proof remains W-02; real background journey pending. |
| Native media authorization | Source boundaries align; system media/revocation/share evidence pending. |
| Foreground reminders/background limits | Native optional actionable banner and truthful help align; actual replay/background results pending. |
| Free personal maintenance/recovery | Build/help/plan align; final outcome unverified until actual installation/renewal/expiry evidence. |

No additional implementation behavior was found that requires a new delta requirement; the delta intentionally inherits full current IM business contracts. The existing current-doc cron spelling drift (`cron-jobs` versus actual `/cron/jobs`, already identified by design) should be corrected during the planned current-spec merge; no design or current document was edited here. Full outcome remains implementation-mismatch for W-01 and evidence-pending for final gates, not a corrected-delta pass.

## Targeted CI code review

Reviewed only the new iOS job at `.github/workflows/ci.yml` in `723414c9f` and its build.sh/scheme/project dependencies. Result: `ci-code-review-r1.json` is `[]` (no confirmed or plausible defect). This is not a remote CI success claim.

The [official runner inventory](https://github.com/actions/runner-images/blob/main/images/macos/toolsets/toolset-26.json) lists Xcode 26.4.1 with default runtime installation for macOS 26 on both architectures. The configured DEVELOPER_DIR matches its versioned path, the selected iPhone/iOS runtime matches the locally validated target, GITHUB_ENV propagates its new UDID to build.sh, and xcodebuild test can boot the selected simulator. Simulator test keeps default signing for Keychain entitlements; Release archive intentionally disables device signing and packages the actual arm64 app. The local test/archive results support these command paths; only an actual eligible GitHub run can establish remote execution.

## Handoff

- `unit_id`: feat-578-ios-app
- `review_round`: 1
- `verification_mode`: full
- `verdict`: not_pass
- `issues`: critical=1 (known incomplete exits), warning=2, suggestion=0
- `validated_issues`: W-01 source/current-contract mismatch; W-02 coverage/evidence gap; C-01 documented open gates
- `requires_full_verification`: false (full scope was covered in this round; fixes may be checked by targeted closure, and outstanding product/device evidence must still be integrated)
- `report_path`: `docs/changes/feat-578-ios-app/M1-native-app/verification-r1.md`
- `report_commit`: caller-owned, not committed by reviewer
- `top_concern`: preserve full final scope while closing C09 and the required behavior/evidence gaps; do not equate successful simulator unit tests or unsigned archive with complete native/physical acceptance.
