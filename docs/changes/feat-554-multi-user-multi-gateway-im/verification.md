# Verification Report: feat-554

> Validation snapshot: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4 → a62b98d45991b47a0a874403e6625c58142cdd6a`

Final ordinary verification verdict: **PASS**, recorded in Round 4 below after the bounded fixes and independent acceptance reconciliation. Earlier blocked/pending snapshots remain historical evidence. Corrected-delta reconciliation, canonical merge and deployment migration are separate steps and are not claimed complete by this report.

## Round 1 — Full verification

- verification_mode: `full`
- review_round: `1`
- validated_at: `a62b98d45991b47a0a874403e6625c58142cdd6a`
- executed_base: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- fix_delta_range / focus_issues / prior_verification_path: N/A (first full verification)
- requires_full_verification: `false`
- Independent verifier used detached `.worktrees/verify-feat-554` at the dispatched commit. Implementation source, configuration and tests were not edited; the implementation/reviewer stack was not restarted or modified.
- Verdict: BLOCKED at this snapshot (V1); independent acceptance also pending. Closure of a later fix is recorded separately and does not rewrite this result.

## Summary

| Dimension | Result |
|---|---|
| Completeness | Implementation mapped for all 18 specification scenarios and M1 R1–R7 / W1–W4; native IM configuration-boundary delivery missing (V1), actual product evidence pending reconciliation below |
| Correctness | Independently executed 128 relevant backend, PA consumer and architecture tests passed; retained frontend/full CI evidence inspected |
| Coherence | Fixed membership / owner-management / public global Work boundaries follow the design; no new permission engine or package dependency violation |

## Completeness

The unit has one vertical milestone. The simple workflow does not require worker `tasks.md` or `progress.md`; [M1 implementation](M1-collaborative-im/implementation.md) supplies the implementation record. Requirement coverage is assessed from actual routes, repositories, runtime consumers, frontend integration and tests, not from its completion claims.

| M1 exit | Implementation and direct evidence | Status |
|---|---|---|
| R1: contacts, human DM, no Gateway | `web_im.py:223,305`; public SQL directory excludes synthetic identities; `new-chat-modal.tsx:9`; member pair/title regressions | implementation covered; product evidence pending |
| R2: mixed groups and governance | `web_im.py:274,734,777`; explicit group type, current-member operations and creator protection; cross-account HTTP tests | implementation covered; product evidence pending |
| R3: real multi-Gateway messages / configuration boundary | `messages.py:424`; each target dispatches independently; boundary API validates actual node/profile, but native ingress cannot produce its boundary intent | blocked: V1; product evidence pending |
| R4: single-thread shared approvals / global mode unchanged | `messages.py:671`, repository CAS, `execution.py:444`, durable registration replay and PA original request handling | implementation covered; product evidence pending |
| R5: complete global Work / private source | `agent_work.py:13–90` removes only Work GET owner restriction; source messages/images retain membership; original Work repository and child association retained | implementation covered; product evidence pending |
| R6: own configuration, multiple / zero devices | owner configuration routes retained, public profile dispatches only own Agent to original `AgentDetailPage`; node query / bind / Heartbeat pages retained | implementation covered; product evidence pending |
| R7: original capability matrix, both Skill scopes | original management forms and chat workflows retained; distill owner/single-thread/node qualification, pinned new execution chat and existing resolver; builtin scope fixed to `agent/global` | implementation covered; actual scope writes and product matrix pending |
| W1: identity / resources / approvals | verifier's first test group: 64 passed; JWT and opaque machine token separation, source resource and real execution checks, current recipients, independent preferences | covered |
| W2: frontend build / comparison | recorded full frontend 80 files / 753 tests and build; source comparison confirms original shell and management forms preserved; real desktop/mobile evidence pending | partial evidence pending |
| W3: isolated real stack, shadow, credential expiry, migration MD | record identifies actual 3-account / 3-Gateway stack; independent tests exercise HTTP/WS credential rotation and shadow split auth; migration document matches actual target schema/resource metadata | implementation / automated covered; product evidence pending |
| W4: language and affected existing behaviors | original dictionaries, setLanguage and shell controls preserved; new strings localized; independent consumer test group 64 passed; full frontend suite includes distill/fork/slash/draft/settings/i18n | automated covered; product evidence pending |

`migration-prompt.md` is the only old-data conversion deliverable. It describes backup/WAL, exact member fields, `messages.rowid` read boundaries, NULL old `direct_key`, stable identities, resource associations / reference conversion, quiescence, rehearsal and coordinated rollback. Actual legacy conversion is explicitly deferred to the deployment agent and is not claimed as implementation acceptance. The diff adds target schema only and removes the three shared-preference startup additions and public uploads mount; unrelated pre-existing initialization code remains unchanged.

## Correctness

Paths below are repository-relative; line numbers identify the reviewed snapshot. Product observations are separately reconciled with the independent acceptance report and do not follow from passing unit/API tests.

| Spec scenario (spec.md) | Implementation evidence | Regression / product evidence | Status |
|---|---|---|---|
| 1. No-Gateway user starts communication (97) | `src/IM/api/routes/web_im.py:223,305`; `src/IM/infra/repositories/users.py:46`; `src/IM/frontend/src/features/chat/components/new-chat-modal.tsx:9` | `test_conversation_membership_api.py:34,149`; `agent-profile-page.test.tsx:44` | implementation covered |
| 2. No matching contact (102) | directory q/filter/paging; NewChatModal separate empty state and no selectable wrong identity | `test_conversation_membership_api.py:34`; product empty-search evidence pending | implementation covered |
| 3. Two accounts converse and reread (108) | `conversations.py:442,475`; `messages.py:424,738`; both participants share direct key; uncustomized human title projects peer | `test_conversation_membership_api.py:87,149`; user-stream / message API suites | covered |
| 4. Same person owns multiple devices (116) | original node binding and owner config; public `node_name` uses saved alias; per-Agent node dispatch | `test_gateway_auth_boundary.py:20`; `test_conversation_membership_api.py:130`; product device evidence pending | implementation covered |
| 5. Collaborator cannot edit others' config (120) | public contacts projection; `AgentProfilePage` owner-only delegation to original detail; management owner guards retained | `test_agent_work_api.py:288–302`; `agent-profile-page.test.tsx:27`; auth-boundary tests | covered |
| 6. One device goes offline (125) | `_project_contact_status` uses NodeService/live sessions; per-target relay failure; Work offline execution becomes unknown | gateway status / auth tests; actual offline journey pending | implementation covered |
| 7. Contact another manager's Agent (132) | public participant check limits group addition only; real machine Agent membership accepts reply/images without human-owner membership | `test_conversation_membership_api.py:212`; `test_gateway_auth_boundary.py:20`; implementation image journal; product journey pending | implementation covered |
| 8. Establish mixed project group (140) | explicit type and stable Actor normalization; only each manager adds own Agent | `test_conversation_membership_api.py:149,212` | covered |
| 9. Different humans jointly assign work (145) | sender derives authenticated identity; RelayService retains per-Agent node and existing trigger/context rules | gateway group/direct integration coverage; real mixed-group evidence pending | implementation covered |
| 10. Rename/add/remove/leave/dissolve (151) | `web_im.py:658,696,734,777`; former/current ID-only invalidation; `user_stream.py:260,291`; frontend cache and draft revocation | `test_conversation_membership_api.py:149`; `test_user_stream.py:99`; draft late-upload and user-stream recovery regressions | covered |
| 11. Global mode has no approval card (158) | original global runtime automatic permission behavior retained; `_permission_target` rejects chat cards for global Agents | original global permission tests and real global journey pending | implementation covered |
| 12. Non-owner/non-initiator chooses any offered option (163) | `claim_permission_decision:1169`; real human membership, actual Agent/node, offered option validation; no owner restriction | `test_member_permissions_api.py:98` parameterizes choices; actual independent click evidence pending | covered |
| 13. Competing card decisions (169) | conditional DB update preserves first submitted decision; repeat cannot overwrite; only original node/run resolution; durable submitted replay on registration | `test_permission_decisions.py:98`; `test_member_permissions_api.py:98,155`; delayed-card UI tests | covered |
| 14. Agent owner cannot read private DM (175) | `deps.py:352`; all human chat/resource access uses current membership; no owner shortcut | `test_gateway_auth_boundary.py:20`; `test_message_images_api.py:34,87`; actual image journey in implementation record | covered |
| 15. Nonmembers cannot read group (181) | same access guard; send-time recipient recheck for live and replay; membership-aware sync | `test_conversation_membership_api.py:149`; `test_user_stream.py:99`; image access tests | covered |
| 16. Complete global Work regardless of source (185) | `agent_work.py:27,54,73`; original Work repository returns main/linked child records; visible-page polling | `test_agent_work_api.py:15`; `agent-profile-page.test.tsx:27`; actual main/child evidence pending | implementation covered |
| 17. Work links do not grant original chat access (191) | links remain ordinary chat/resource URLs, protected fetch; Work GET neither adds membership nor mints a source credential | same Work/API and private-resource tests; actual source navigation pending | implementation covered |
| 18. Existing data / working capabilities (198) | deployment-only migration document; existing target-format histories/forks; original chat and management components retained; single-thread distill scopes unchanged | verifier consumer group: 64 passed; frontend 753; actual preserved capability matrix and both scope writes pending | implementation covered; deployment conversion explicitly deferred |

### Automated evidence examined

- Independent verifier commands ran in the detached `a62b98d` worktree with the repo `.venv` and this checkout's pytest `pythonpath=[src, tests]`. First group: 64 passed in 18.34 s (`/tmp/feat554-verifier-focused.log`), covering membership, commands, original-node card decisions/restart, runtime authentication, protected resource/fork access, personal state, user-stream delivery, Work, external Agent messages, PA shadow/auth clients and package dependency contracts. Second group: 64 passed in 6.18 s (`/tmp/feat554-verifier-consumers.log`), covering users/conversations distill API, ordinary message/pinned route behavior, fork variants, Gateway local distill resolver, image resolver and permission pipeline.
- Directly inspected retained logs: `/tmp/feat554-ci-agent-pa.log` (1877 passed), `/tmp/feat554-ci-remaining.log` (1963 passed), `/tmp/feat554-frontend-final.log` (80 files / 753 passed). These are prior `1f14e77db` implementation-tree results, not a claim that all suites reran at `a62b98d`. The post-review source delta is confined to human title projection, public alias label and the mobile Policies row; relevant backend regressions were included in verifier execution and the MePage fix has its own recorded test.
- New permanent files protect meaningful API, persistence, runtime/consumer or UI seams. Existing permission tests using the retired forward-only/private mock path were removed in favor of actual HTTP/WS decisions and durable replay; retained CAS tests cover competing DB connections, a distinct lower-level failure cause. No migration program, one-time browser acceptance script or screenshot was added to the permanent test suite.

## Coherence

| Design decision | Adherence | Code / evidence |
|---|---|---|
| Fixed chat membership, public global Work and owner-only management rules | Yes | `deps.py:352`; `agent_work.py:13`; original config routes / `AgentProfilePage` |
| Contacts independent of private chat discovery | Yes | `users.py:46` returns a small projection from login humans / nonstale profiles; chat list remains member-filtered |
| Explicit groups, ordinary direct uniqueness, independent special chats | Yes | `conversations.py:108–198`; HTTP creator/member normalization; fork/distill default `reuse_direct=False` |
| Shared group governance; each person's preferences/read boundary | Yes | participant table fields and `conversations.py:491,529`; creator-only dissolve; per-user SQL counts |
| Current recipients and cache cleanup after removal / reconnect | Yes | `user_stream.py:260,291`; runtime sync before reconnect; `use-membership-cache.ts:9` and composer/image invalidation |
| Actual sender and per-Agent delivery; pure humans need no Gateway | Yes | `messages.py:424,738`; RelayService existing fan-out; no participant Agent means no route fallback |
| Original permission tuple, submitted versus resolved, durable retry | Yes | `execution.py:444–525`; `messages.py:1169–1279`; GatewayControl registration replay and PA stable request IDs |
| Owner JWT identity / current registered machine token data | Yes | `sessions.py:253,269`; `deps.py:322`; `composition.py:420`; shadow separate clients and token rotation tests |
| Resources remain private and immutable, legitimate fork copies independently | Yes | `messages.py:383`; `message_images.py`; `resource_access.py:18`; original resource store with new attachment URL |
| IM does not access Gateway local transcript/config roots | Yes | commands uses existing RPC and opaque HMAC; distill resolver runs in PA, IM only passes validated identities |
| Single-thread distillation / agent-global Skill scope preserved | Yes | `web_im.py:347`; original local prompt resolver; builtin `target_scope` documentation corrected only |
| Existing UI forms and control shapes retained | Yes at source level | original AgentDetailPage has only create-message payload change; shell/Nodes/Account/Policies source remains; separate mobile Policies row added |
| Migration Markdown only, no new old-version fallback | Yes | target schema diff, removed public upload mount and old preference-column additions; migration document checked against final source |
| Package architecture | Yes | IM still independent of kernel; PA continues SDK-only composition; relevant dependency contracts passed independently |

### Prototype / Reference Contract

The prototype is a reference, not an implementation. The verifier checks explicit contract and evidence chain only; visual quality verdict belongs to the independent product reviewer. The ten must-match rows from `design.md:286–295` all have the M1 projections shown below. Existing whole pages remain the baseline where the prototype is simplified.

| Reference contract | M1 projection | Implementation | Durable product comparison | Status |
|---|---|---|---|---|
| Contact search/direct chat, empty/no-Gateway states | R1 | NewChatModal / contacts / explicit direct | PENDING_ACCEPTANCE | pending |
| Mixed group creation/add own Agent, desktop/mobile, empty selection | R2 | original NewGroupModal plus human Actor options; server manager guard | PENDING_ACCEPTANCE | pending |
| Group messages/senders/device names/multi-node/offline | R3 | original MessagePane with authenticated self identity and public device names | PENDING_ACCEPTANCE | pending |
| Shared single-thread card and consistent result | R4 | original PermissionCard + submitted/resolved state; server original tuple/CAS | PENDING_ACCEPTANCE | pending |
| Work main/child/source links | R5 | original Work panel/read repository, non-owner profile entry | PENDING_ACCEPTANCE | pending |
| Own configuration only; multi/zero/offline devices | R6 | original owner pages, public profile wrapper, original Nodes | PENDING_ACCEPTANCE | pending |
| Language/refresh/draft/content preservation | W4 | original i18n/setLanguage, dictionaries, per-chat draft store | PENDING_ACCEPTANCE | pending |
| Multi-chat Skill generation, both scopes and failed preflight | R7/W4 | original distill selection/prompt workflow, single-thread/owner/node constraints | PENDING_ACCEPTANCE | pending |
| Original chat/Agent/settings entrypoints and qualifications | R7/W4 | original components and route/qualification adjustments | PENDING_ACCEPTANCE | pending |
| Independent settings rows, icons, EN/中 controls | W2/W4 | unchanged original UserMenu/MePage controls, separate Policies row | PENDING_ACCEPTANCE | pending |

## Issues

### CRITICAL

**V1 — Native IM configuration changes do not generate the required visible boundary.** M1 R3/W3 and `reviewer-runbook.md:100` require a manager's configuration change to be adopted by their Agent in another person's mixed group and displayed to current group members. At `a62b98d`, `inbound_pipeline.py:273–281` deliberately leaves native `im_relay` messages without a shadow reference. `session_run_coordinator.py:2292–2317` nevertheless constructs a boundary only from `routed.shadow.ref`; the native message's durable `im_relay.im_message_id` and conversation ID are ignored. The resulting native runtime replacement can adopt the new configuration without recording or publishing its boundary. The pending-shadow alternative also cannot handle native messages because they have no shadow saga. This independently confirms the product review's observed missing divider. Existing repository/API boundary tests do not close the missing ingress-to-coordinator connection. Restore construction from the native relay anchor, retain the external-shadow branch, and verify a real native group configuration change plus direct/group regression fixtures.

Required acceptance evidence also remains pending; passing automation alone cannot close all M1 exits.

### WARNING

Pending final contract/evidence reconciliation. One concrete corrected-delta item has been reported to the orchestrator: current `im/conversations-messages.md:142–165` still says an external 1:1 owner message is shown as “you”; this unit deliberately uses an independent non-login shadow sender (`messages.py:767–783`) and renders self only by real current user identity (`message-pane.tsx:1456`). The final delta must explicitly reconcile external display identity instead of leaving the obsolete self-identity promise. This is a documentation alignment obligation, not a recommendation to undo the approved non-impersonation boundary.

### SUGGESTION

None. No speculative permission, migration compatibility or visual redesign proposals were added.

## Round 2 — Targeted closure

- verification_mode: `targeted-closure`
- review_round: `2`
- validated_at: `086467a12489dbfbe53423b25ce0ee5ca6f2edec`
- executed_base: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- fix_delta_range: `9b4ed2e93a93f56ff49dbe523328157b4621a3d8..086467a12489dbfbe53423b25ce0ee5ca6f2edec`
- focus_issues: `V1`; reconciliation of required independent acceptance evidence from Round 1
- prior_verification_path: this file, Round 1
- requires_full_verification: `false`
- Verdict: BLOCKED pending V2 and acceptance. Code and regression closure of V1 is established; the native mixed-group product observation and the independent full acceptance report remain required.

### Fix-delta validation

Compared `a62b98d` through this snapshot: the only additional source changes are the 17-line coordinator fix and its admission regression adjustment; the intermediate commit updates only `code-review.md`. This does not invalidate the remaining Round 1 coverage.

`session_run_coordinator.py:2303–2333` now uses the native relay's durable message ID and actual IM conversation ID before considering an external shadow reference. `web_relay_adapter.py:298–315` directly establishes that `external_chat_id` is `envelope.conversation_id` and `im_relay.im_message_id` is the relayed message's ID. The fix does not invent an anchor for messages without one, change the original external shadow/pending-saga flow, or loosen IM node/Agent/membership validation. The resulting intent continues through the existing atomic applied-runtime/outbox persistence and publisher notification before the next run is submitted.

Independent verification at `086467a12`: `test_session_run_coordinator_admission.py`, `test_gateway_boundary_outbox.py` and `test_gateway_web_relay_adapter.py` — **42 passed in 2.63 s**, recorded in `/tmp/feat554-verifier-boundary-closure.log`. The replacement regression uses real native ingress without a shadow, in both direct and group fixtures, verifies no first-run divider and exactly one changed-runtime boundary with the real node/Agent/conversation/message anchors. The same run preserves delayed external-saga promotion, same-session next-run configuration, missing-baseline behavior, durable outbox restart/ACK semantics and adapter mapping coverage.

### Validated issues / remaining evidence

| Item | Closure status |
|---|---|
| V1: native IM configuration boundary | Source and automated regression closed at `086467a12`; actual mixed-group boundary observation pending independent acceptance |
| Full M1 / spec / prototype product evidence | Await independent `acceptance.md`; source/test coverage above remains valid, pending entries are not a pass |
| External shadow sender display contract | Corrected-delta obligation remains; orchestrator has acknowledged replacing obsolete “you” promises with explicit source identity/display name |

No additional source issue was introduced by this fix delta. No new full verification is required for the bounded anchor correction; any later source change must be evaluated on its actual range.

### Additional full-acceptance finding

**V2 — Global `send_message` replies publish workspace image paths without the existing image projection.** The independent product reviewer reproduced a broken global Agent image after successful input image reading and standard Markdown output. Source inspection at `086467a12` confirms `InternalDispatchHandler._dispatch_global` passes `dispatch["text"]` directly to `send_agent_message` and the external text router (`internal_dispatch.py:367–424`), while its composition constructor (`composition.py:1228–1238`) has no `ReplyImages` preparation/projection dependency. Ordinary assistant and background reply paths already use that service. Thus input download/read success and single-thread image success do not establish global reply delivery. The orchestrator is repairing this required resource/old-capability journey at the existing known `c_` conversation boundary and corresponding external projection, then obtaining independent real acceptance. This finding does not request a new conversation-resolution protocol for first-contact `u_` targets that lack a conversation anchor.

The orchestrator's `M1-collaborative-im/implementation.md` records a real persisted-DB IM restart, concurrent A/B decisions returning the same submitted result, C's reverse choice not overwriting it, and the original Gateway resolving that request/run/node with one successful tool write. **Evidence correction:** the initial `daabe6364` wording claimed a continuously suspended Gateway; `06183073c` corrects that claim because the tmux child resumed immediately. The real evidence proves IM restart, common CAS result and original-process completion, not a frozen-Gateway submission window. This remains additional implementation evidence for R4/W3, not a replacement for independent acceptance. The full CI rerun at the native-boundary source state is 1878 + 1965 = 3843 Python tests (both retained logs independently inspected) and the unchanged frontend 753 tests; the forthcoming V2 fix requires its own validation.

## Round 3 — Global image and language closure

- verification_mode: `targeted-closure`
- review_round: `3`
- validated_at: `513ee21637917dabe16f2f2080136ed63510f7d9`
- executed_base: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- fix_delta_range: `086467a12489dbfbe53423b25ce0ee5ca6f2edec..513ee21637917dabe16f2f2080136ed63510f7d9`
- focus_issues: `V2`, independent acceptance findings I4/I5 and retained-language behavior
- prior_verification_path: this file, Rounds 1–2
- requires_full_verification: `false`
- Verdict: PENDING_CLOSURE. V2 source/automated closure is established for new workspace images; final product evidence and the independently reported hosted-URL candidate still require reconciliation.

### Delta and direct evidence

Only two product changes follow the prior snapshot: `00dff29be` replaces raw distillation-preparation errors with the existing localized error key in both languages, retaining preflight-before-chat creation; `513ee2163` connects the existing shared `ReplyImages` service to explicit delivery. The other commits add implementation/acceptance/code-review reports.

The image path obtains source Agent and workspace from registered session provenance. Preparation is keyed by Agent/session/tool-call identity, so retrying the same call reuses the snapshot and provider/upload receipts even if the original file has disappeared. It projects known `c_` targets with the actual Agent ID and current runtime token, keeps the native group's existing unread-input/Kernel commit gate before image preparation, and does not add a first-contact `u_` conversation-resolution protocol. External delivery uses the same prepared image data and original provider account/receipt projection, while its confirmation still waits for both required routes. A partial IM upload failure yields the existing readable placeholder instead of exposing an inaccessible machine path. No package dependency, file-visibility rule or extra permission model was added.

Verifier independently ran `test_global_dispatch_images.py`, `test_global_gateway_runtime.py`, `test_internal_dispatch_endpoint.py` and `test_reply_images.py` at `513ee2163`: **32 passed in 15.17 s**, with two pre-existing third-party deprecation warnings (`/tmp/feat554-verifier-global-images.log`). The eight new cases exercise actual Gateway/Kernel composition with controlled model/HTTP-provider seams: direct/group image projection, stable retry receipts, withheld/stale group output without premature preparation, upload failure, and external success/failure before recorded delivery. These are integration regression evidence, not a claim of real model/provider acceptance. Combined verifier execution across snapshots is 202 passing tests.

### Independent acceptance reconciliation in progress

Directly read `acceptance.md` committed at `fc5c093c7`, whose Round 1 snapshot is `1f14e77db`, independent from implementation/code review/verifier. It reports **fail**, five actual issues I1–I5 and U1–U4 incomplete required coverage. Its 18 scenario rows, ten reference rows and concrete real object IDs substantiate the covered journeys; they do not establish completion of the remaining mobile/distillation/settings/resources/reconnect checks. I1/I2/I3 were repaired at `a62b98d` before the verifier's full snapshot; I4 maps to V1 and I5 to V2. Final acceptance must explicitly close these and the U1–U4 gaps at their actual running versions. No pending row above is silently promoted by the presence of a UI entry or a successful automated suite.

The separate code-review candidate concerning already-hosted IM URLs entering generic image preparation is being independently reproduced by the orchestrator's reviewer. This report records no unverified source verdict for that candidate; if confirmed, its repair must preserve valid protected resource references and receive targeted verification before final pass. Corrected deltas must also describe the newly supported explicit known-conversation image entrypoint alongside the external sender-display clarification.

## Round 4 — Hosted image references and final acceptance

- verification_mode: `targeted-closure`
- review_round: `4`
- validated_at: `274ad07bc61bb0f17eb9bee8708f1f37bec83ebd`
- executed_base: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- fix_delta_range: `513ee21637917dabe16f2f2080136ed63510f7d9..274ad07bc61bb0f17eb9bee8708f1f37bec83ebd`
- focus_issues: hosted-IM-image candidate confirmed in independent code review; final V1/V2 and required product-evidence reconciliation
- prior_verification_path: this file, Rounds 1–3
- requires_full_verification: `false`
- Verdict: **PASS** (ordinary implementation-verification gate). Critical: **0**; Warning: **0**; Suggestion: **0**. Final product-source snapshot is `274ad07bc`; the test-only split at `c3046c6a2` and independent acceptance report at `e0af8f139` were also read and reconciled without changing historical validated-at fields.

### Hosted-reference closure

`274ad07bc` addresses the confirmed case in which an otherwise valid existing protected image URL was mistaken for a local path during explicit delivery. `ReplyImages.prepare` now accepts the actual target conversation and recognizes only that conversation's exact protected `/images/<32 lowercase hex digits>` reference. It stores a reference receipt without granting access to bytes or minting a new resource association. `project_im` reuses that receipt only for the same conversation; the IM's existing membership/resource checks remain authoritative. Malformed or foreign-chat references still produce a readable failure. Mixed old/new-image replies preserve a valid receipt even if a new upload fails. The external projection cannot export the protected IM reference or expose its private URL; ordinary prepared local images retain the existing provider-account/receipt behavior. Optional context defaults leave other preparation callers' established behavior intact.

Independent verification at the exact snapshot: `test_global_dispatch_images.py`, `test_reply_images.py`, `test_shadow_reply_images.py` and `test_background_reply_images.py` — **38 passed in 16.60 s**, two existing third-party deprecation warnings (`/tmp/feat554-verifier-hosted-images.log`). The new SDK/Gateway cases cover hosted-only and mixed-local replies plus stable retry; the source tests cover foreign-chat/malformed references and the external integration covers absence of private IM URLs in the provider's output. Total independent verifier execution across recorded snapshots: **240 passing tests**. No implementation/design or package-boundary mismatch remains in this bounded delta; no full restart of the verification is required.

### Mechanical test-layout follow-up

`c3046c6a208714dee1842f6ee964f1bb0886ee99` changes only the image test layout after the full run found the native file exceeded the repository's 400-line new-test-file contract. The final files contain 298 and 165 lines. The verifier independently compared parsed ASTs at `274ad07bc` and the split revision: all nine top-level test/helper function/class definitions are identical, including the moved parameterized external test. Product source is unchanged, so this does not invalidate either source verification or the real acceptance version. The orchestrator's recorded focused image/size-contract run passed 14 tests; independent code review at `c3046c6a2` ran 29 and returned no findings (`code-review.md`, report commit `912d3895f`). This does not misreport the preceding full run's single size-contract failure as already green before its fix.

### Final independent product-evidence reconciliation

Read the formal independent `acceptance.md` Round 2 at `e0af8f139`: **pass**, 18 implementation-period scenarios pass, I1–I5 and U1–U4 all closed. Its live product snapshot is `513ee2163`, frontend `00dff29be` / bundle `index--ymP6Kyu.js`; unchanged earlier journeys explicitly retain their own observed versions. The verifier does not relabel these observations as having run at `274ad07bc` or `c3046c6a2`. The later hosted-reference correction is bounded, separately verified above, and does not invalidate the accepted local-image, membership, management or UI paths.

| M1 exit / original reference | Final evidence and disposition |
|---|---|
| R1 / must-match 1 | Round 1 J1 plus R2-J1: real zero-device registration/contact search, empty search, two-user messages, corrected peer labels and durable explicit rename. Pass. |
| R2 / must-match 2 | Round 1 J3 plus R2-J7: real mixed group with each owner adding their own Agent; mobile bottom sheet/empty selection, shared name/member operations and correctly versioned creator-only dissolution. Pass. |
| R3 / must-match 3 | Actual multi-node replies and isolated offline state retained; saved node alias verified in final UI. R2-J2 closes V1/I4: A/B/C see one persisted system divider before the first request using C's new configuration, and Muse replies with the new marker. Pass. |
| R4 / must-match 4 | Round 1 J4 plus R2-J4 independently observe the original pending request after real IM restart, concurrent A/B submission, C's contrary repeat retaining A's decision, and exactly one completed write in the original run. This does not claim a frozen Gateway or an independently observed submitted-state disconnection window; real HTTP/WS persistence/replay tests supply the finer-grained durable replay evidence. Global real tool work has no approval cards. Pass. |
| R5 / must-match 5 | Round 1 J5 supplies complete main/linked-child Work for C, including B's private-source input, while source chat and attachments remain inaccessible; R2-J3/J6 reaffirm new/fork resource boundaries. Pass. |
| R6 / must-match 6 | Three original accounts show multiple/zero/one device; unrelated-device failure remains isolated. Public non-owner profile cannot GET/PATCH management config; R2-J5/J7 create actual Agents on two chosen nodes and save original owner controls. Heartbeat/last-online surfaces retained. Pass. |
| R7 / must-match 8–9 | Both agent/global Skill scopes were actually created and read back in Round 1 J6; R2-J5 completes same-node selection, mobile selection, missing capabilities/offline/missing transcript preflight, unchanged selection and no empty execution chat. R2-J6/J7 covers actual file download/fork, copy/code copy, touch-menu behavior, drafts, original forms and operation qualification. Pass within documented existing capability scope. |
| W1 | Independent verifier membership/resource/card/auth/stream/Work/consumer tests plus later concrete regression tests total 240 passes across declared snapshots; original API, DB, SDK-only package seams preserved. Pass. |
| W2 / must-match 10 | Original desktop/mobile references are explicitly reconciled in acceptance's ten-row table. Mobile independent Policies row was exercised through save/reload; icons and original language controls preserved. Frontend 753/80 and build evidence retained; all product changes reviewed. Pass. |
| W3 | Independent real three-Gateway stack, original-request restart journey, runtime-token/identity/shadow integration regressions and actual image/read/return evidence. Source JSONL failure fixture restored with matching SHA256. Only `migration-prompt.md` defines old-data conversion, delegated to production deployment as the user requested. Pass for implementation-period scope. |
| W4 / must-match 7 | Actual language persistence, unchanged drafts/message content, existing controls, localized failure/approval states, fork/slash/images/settings; R2-J1/J4/J5/J6 and inherited Round 1 J7. Pass. |

The acceptance report's ten must-match comparison rows are all **match**. Its coverage table has **18 pass / 0 fail / 0 inconclusive** for the spec's original scenarios. Thus the earlier pending rows in Rounds 1–3 are resolved by identifiable independent observations, not by implementation claims. V1/V2 and the hosted-reference candidate are closed; the earlier peer-title/alias/mobile-policy issues are likewise closed. No missing M1 exit, material implementation/design mismatch, missing relevant regression or architectural violation remains.

### Retained limitations and next gate

- Acceptance SF1 is an existing ordinary-file model-input limitation: browser upload/download/history/fork succeeds, while an arbitrary txt may still be routed through the pre-existing image resolver. The verifier compared `94338a2a7..274ad07bc`: `web_relay_adapter.py` has no change and `image_attachments.py` changes the authenticated downloader/Agent identity, not MIME classification. This is not a newly working arbitrary-file-understanding feature and not a regression introduced by this unit.
- No real third-party Feishu message or formal old-database conversion was required or claimed. External provider projection and shadow/token behavior have controlled production-consumer integration evidence; channel UI qualification and validation were actually reviewed. Production conversion/rollback remain in the deployment-agent Markdown.
- The corrected-delta gate must still reconcile all final delta files and omitted outward behavior, including explicit external sender identity in place of obsolete “you” wording and the supported known-conversation explicit image entrypoint. These are required upcoming document-alignment checks, not a claim that canonical specs have already been updated. This ordinary gate does not waive or pre-approve them.

`requires_full_verification: false`. The original full scope remains covered; subsequent fixes are bounded and independently closed. The verifier changed only this report and retains its detached worktree for the separately dispatched corrected-delta continuation.
