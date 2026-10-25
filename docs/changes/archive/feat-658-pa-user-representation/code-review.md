# feat-658 Code Review

> 最新共享 host 集成审查见文末 R7；先前各轮保持其原冻结版本与证据范围。

- Reviewer: independent agent; did not implement the reviewed change.
- Mode: full.
- Reviewed range: `8e4054197908a1a433f748525c9650a831a950b6..3689a8b84ba09e69eae013bb79d93a1c4d1f2010`.
- Checkout HEAD was the frozen reviewed head. Untracked runtime `packages/personal-assistant/assets/skills/.usage.json` was ignored.
- Scope: all implementation and test changes in the range, with calling paths in IM messaging/PA/interactive/fork, PA admission/publication/Inbox/SingleThread, DSH tool registration/normalization/approval/context inheritance, Web/iOS identity and ComposeMessage, migration and generated assets. Requirements and design are review context; this report does not grant product acceptance.

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/policy/codex-context.ts",
    "line": 42,
    "summary": "[P2] Recognize the actual conversations sender shape when preserving user history",
    "failure_scenario": "A receiving Agent restores the original represented user instruction through conversations read/search, then performs more than 40 subsequent non-user evidence entries. IM Work emits sender.kind=user (work.ts:726-730), but the new retention predicate only accepts sender.type=user. The restored instruction is classified as optional tool evidence and can be omitted entirely, including pa_agent_id and original restrictions. A direct reproduction using exported reviewInput, a real-shaped conversations_result followed by 41 recent tool rows, and budget=50000 drops the original scope. Changing only kind to type preserves it. The new approval-sources fixture uses type for both Inbox and conversations and therefore misses the real wire shape. Normalize or recognize the existing conversations shape and protect it with a real-shaped retention regression; do not rely on the synthetic fixture shape.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Independent reproduction

Executed in the frozen checkout with `pnpm exec tsx -e` importing `reviewInput` from `packages/dsh-integration/src/policy/codex-context.ts`. No service was started or mutated. Input was one historical `conversations_result` containing `{message_id:"m",sender:{id:"u",kind:"user"},pa_agent_id:"pa",content:[{type:"text",text:"PRESERVE_ORIGINAL_SCOPE do not merge or deploy"}]}`, followed by 41 `{outcome:"ok",tool_result:"recent"}` rows. Planned action was `{tool:"bash"}`, budget 50000.

| Sender shape | Original scope retained | Evidence omission marker |
|---|---|---|
| actual `kind:user` | false | true |
| comparison `type:user` | true | true |

The controlled comparison isolates the field mismatch from token pressure. This establishes missing evidence; it does not assert that a real reviewer approved an out-of-scope action.

## Limits

The caller's narrow test and synthetic actual-context evidence was reused where relevant. Full local CI and true-model/client journeys were still pending at review time. The first true-model journey's missing mention is recorded by the caller as a failure and is not counted as product acceptance. This review did not operate the running daily instance or start new real services. Implementation/design conformance and outstanding evidence are reported separately in `verification.md`.

## Round 2 — targeted closure

- `review_mode=closure`; `finding_origin_head=3689a8b84ba09e69eae013bb79d93a1c4d1f2010`.
- `validated_at=16798fb3be2e46500ba25c01996f3c615ac29288`; `effective_base=b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`; `effective_through=16798fb3be2e46500ba25c01996f3c615ac29288`.
- Reviewed repair `abdf2afc75f11f38ec2e888cd2f31a9ea3011504`, related test delta `9c5aecd558e1d16c5e5d948c010859a70e0901f8`, and intervening changes. The merge contribution from old base to effective_base consists only of three feat-659 design assets; no product implementation or test changed upstream. R1 full-review conclusions are retained outside this targeted scope.

### Focus finding closure

| Focus | Status | Evidence |
|---|---|---|
| R1 sender.kind/type history retention finding | **closed** | `policy/codex-context.ts:42` now checks `sender.type ?? sender.kind`. `approval-sources.test.ts:202` uses actual history `kind:user` and protects scope plus PA ID after 41 later tool entries. |
| R1 verifier WARNING 2, model interactive constants | **closed** | `work.ts:747` filters only format/catalog_version in the model read/search projection. `personal-sources.test.ts:142` verifies source retained and client `Messaging.message()` wire unchanged. |

Independently executed at the validated head with Node 24.22.1:

```sh
/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin/node node_modules/vitest/vitest.mjs run packages/dsh-integration/tests/approval-sources.test.ts apps/im-server/tests/personal-sources.test.ts apps/im-server/tests/personal-representation.test.ts apps/im-server/tests/pa-representation-migration.test.ts --maxWorkers=2
```

Result: **4 files / 30 tests passed**, start 20:57:33, duration 593 ms. The additional legacy regression exercises missing representation payload, self decoding, owner identity conflict and confirmed commit retry; the migration fixture now also contains an actual legacy relay row. No further concrete defect was found in this repair/test delta. No source was changed and no running daily instance was operated.

Surviving code findings:

```json
[]
```

This closes the reviewed code findings, not the outstanding independent product/native acceptance gate. See verifier R2 for corrected-delta outcome and evidence limits.

## Round 3 — attachment guidance patch

- `review_mode=patch`; reviewed only `cfba1fcd345c3fb5cfd48ed7384846d0a243d967^..cfba1fcd345c3fb5cfd48ed7384846d0a243d967` (two files), plus the unchanged attachment snapshot/copy call paths needed to check the guidance.
- `validated_at=cfba1fcd345c3fb5cfd48ed7384846d0a243d967`; `effective_base=b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`; `effective_through=cfba1fcd345c3fb5cfd48ed7384846d0a243d967`.
- `personal-security.ts:135` accurately describes the existing native-resource path: Markdown URL in text is found by `PersonalActions.attachments()`, accessible resource bytes/hash are frozen and rechecked, original authorization and disclosure review still apply, and commit rewrites native URLs through `Messaging.copyReferences()`. Local filesystem paths are not uploads; nonreviewable resource contents still fail instead of being silently sent. No schema, upload tool, transport permission or identity path was added.
- The extension to `personal-disclosure.test.ts:136` checks the existing behavior on an owner-authored message: full text snapshot, represented owner/PA identity, target-conversation Markdown URL and copied resource hash/storage. This is a regression assertion for a depended-on transport capability; it is not presented as a red reproduction of a previously broken server copy implementation.
- Independent command: Node 24.22.1 `node_modules/vitest/vitest.mjs run apps/im-server/tests/personal-disclosure.test.ts --maxWorkers=2`; **1 file / 17 tests passed**, 21:18:22, duration 539 ms. Caller-reported personal-security 8-test result/integration build are reused and were not repeated.
- Read product R1's two preserved attachment failures: local-path request lacked upload capability; after a genuine owner upload, natural forwarding still refused because PA did not discover the supported native-resource expression. Those are pre-fix product failures. A static review or successful transport test does not close the natural-model/product finding; targeted product re-review remains separate, and native UI remains blocked.

Surviving patch findings:

```json
[]
```

No new defect was found in the dispatched patch. R1/R2 conclusions outside its affected scope are retained. Only report appendices were written; no source/test/service mutation was performed by this reviewer.

## Round 4 — final upstream integration

- `review_mode=patch/integration`; `validated_at=7e67ccc7e66e1fd2392181e2064c586107679c84`.
- First-parent baseline: `d778f1cc7`; integrated upstream / `effective_base=1219d903b1ba851cf49631fe37e5d52b49e8474c`; `effective_through=7e67ccc7e66e1fd2392181e2064c586107679c84`.
- Scope: merge-sensitive feat-658 intersections against both parents: IM PA prepare/review/commit, message/provenance/relay and observation schema; Node/PA publication/Inbox/SingleThread and runtime identity/lifecycle adapters; root/child source registration; Compose hosts. Unrelated upstream lifecycle internals and the already-reviewed complete unit were not re-reviewed. R1–R3 conclusions remain applicable outside this integration impact.
- Both manual conflict resolutions are correct: `PersonalActions.validate()` keeps lifecycle validation before `destination()` (which retains source scope and selected-author checks); `Submit.source` and runtime `submit()` preserve lifecycle_revision together with sender/pa_agent_id through a spread rather than reconstructing/dropping feature provenance.
- Auto-merges retain represented user identity plus PA provenance before card/event/relay creation. Relay lifecycle revision belongs to each receiving Agent, independent of the public user author. PA publications now carry binding.agentId for upstream cancellation ownership. Global/SingleThread execution wrappers stamp host lifecycle state while retaining message content, source identity and operation identity. Per-Agent runtime routing validates product/root/owner lineage; it does not give ordinary or internal child Agents the representation tool. Compose destination permission, edited-value and conflict handling remain the feature's local host paths; upstream chat lifecycle notices do not substitute a send or Agent request.

### Agent Context Review — Mode B

Trigger: runtime partitioning, cold lifecycle fences, product-call admission and source serialization affect delivery/recovery even though the representation guidance is unchanged. Read the new context-review skill, context-engineering authority and actual-context observation guidance. Consumer surfaces examined: PA root sender/tool choice and fixed attachment guidance; receiving Global/SingleThread original-user source and history; independent reviewer evidence; child/root lineage across runtime ownership. No new agent or review gate was created.

| Surface | Expected and integration observation | Evidence and limit |
|---|---|---|
| Source injection / serialization | Original user sender, PA ID, scope and message ID survive; lifecycle revision is host-derived execution state, not model permission. Combined Submit source and spread in `index.ts:818-820` preserve these fields; SingleThread retains its source projection. | Actual pre-integration Q/PA/Codex/child requests already inspected in R2; source-path integration checked here. These older captures are **not** integrated-head provider-request evidence. |
| Tools / fixed guidance | Root PA remains sole representing sender; ordinary/child capability restrictions and native Markdown resource expression remain discoverable, with target/current source checks and honest sent/held/unknown states. | R2 actual registration/child matrix and R3 guide/transport evidence retained for unchanged semantics; partition routing and generation checks inspected. Integrated actual registration/provider input and representative behavior are still required below. |
| Recovery / expiration | Historical original delegation remains evidence; disabled generation must not reuse a permit. Clearing cancelled execution inputs does not turn old user messages into fresh permission. | Source/reviewer retention repair is unchanged; independent in-memory combination test below rejects old permits and preserves fresh owner identity. Upstream cold barrier is an execution fence, not provenance rewriting. |

Independent combination check used actual IM classes with an in-memory database, without importing Vitest fixtures, starting a service or writing test files: approve owner proposal at revision 1 → disable at revision 2 rejects its commit → enable at revision 3 still rejects the old permit even with current dispatch revision → freshly reviewed revision-3 owner message succeeds with sender=user/u1 and pa_agent_id=a. All assertions passed. The initial direct-fixture attempt was invalid because its afterEach hook requires Vitest; it supplied no product result and is not counted as a product failure or successful validation.

Reused `/Users/czj/.codex/reports/feat658-acceptance/final-sync-targeted.log`: **6 files / 54 tests passed** at 21:32:14. These cover representation/disclosure/sources/migration/lifecycle/approval source intersections. Full integrated build/tests and actual partitioned runtime validation were caller work in progress at this report snapshot.

Required remaining integration evidence is focused: a representative integrated-head PA delegation reaching the actual receiver/reviewer, with original user/PA/scope preserved in the next serialized request; history readback and root/child capability/lineage checks can share that task or a bounded actual-registration capture. Prior full acceptance need not be repeated where unaffected. Native reviewer on the older backend/client combination cannot independently prove this new runtime integration.

Surviving integration findings:

```json
[]
```

Static integration review found no defect requiring implementation changes. Agent Context Mode B's final assembled/provider delivery and representative integrated behavior remain explicitly unverified until caller supplies the focused runtime evidence; absence of that evidence is not misreported as a deterministic bug or a final product pass. Only code-review/verification appendices were changed.

## Round 5 — native protected Markdown attachment patch

- `review_mode=patch`; range `9e1b81516d3b6531ac6b3c5f4278bd9b1c8fb6d7..8b517546da5a9abc23eec13a2fd48fe712d9157c` (the specified two files only).
- `validated_at=8b517546da5a9abc23eec13a2fd48fe712d9157c`; upstream / `effective_base=1219d903b1ba851cf49631fe37e5d52b49e8474c`; `effective_through=8b517546da5a9abc23eec13a2fd48fe712d9157c`.
- Read `MarkdownContent.pieces()` and the affected Markdown block rendering, then followed existing `AttachmentView.prepare()` → `IMClient.protectedResource()` → `Session.request()` and `ServerOrigin.resource()`. Matching same-origin conversation attachment links render through the existing native authenticated download/QuickLook component. The URL and link filename survive; source ordering and neighboring text remain intact. Different-origin resource-shaped links and ordinary links keep their link rendering. Authentication uses the current session and refresh path, and protectedResource rejects resources outside the configured server; this patch adds no new network identity or backend permission.
- Reused saved build/test evidence at this patch: `native-fix-build.log` ends TEST BUILD SUCCEEDED; `native-fix-tests.log` contains the new Markdown test passing, MarkdownContentTests **3/3**, full native tests **46/46**, and TEST SUCCEEDED. No duplicate native test run was needed.
- The product failure screenshot `independent-review/r3/native-attachment-open.png` is the pre-fix missing-authorization behavior. A successful parser/render test does not itself prove the recipient's native click/download experience; independent product closure remains required after the new build is installed.
- This patch changes client rendering only, not LLM inputs, tools, Skill loading or context lifecycle. No additional Agent Context Mode B loop is triggered; R4's pending integrated runtime evidence remains pending.

Surviving patch findings:

```json
[]
```

No implementation change is requested for this reviewed patch. Only assigned report appendices were edited; no running app/runtime/service was operated.

## Round 6 — final integration evidence closure

- `review_mode=closure/evidence`; `validated_at=000dac07c6f9e3ecaf1eaca2dbe25cbf4489c4c5`; product/source `effective_through=8b517546da5a9abc23eec13a2fd48fe712d9157c`; `effective_base=1219d903b1ba851cf49631fe37e5d52b49e8474c`.
- Confirmed no source change after 8b517546d; subsequent commits change acceptance only. This round closes R4's pending integrated runtime/context/test evidence, retains R5 and prior corrected-delta conclusions, and performs no new broad code review or test rerun.

### R4 Context Mode B evidence closure

Inspected `final-integration-contexts/` messages, both confirmed PA operations and controlled provenance rows, real PA/Q/reviewer requests, actual Work tool execution/result and Git outcome. The fresh official daily instance is IM 49803 / node `wt-.e2e-final-integration-93894`, separate from the preserved old IM 49303. The integrated code executes a natural owner request through root PA representation to Q, retaining user sender, actual PA, original message IDs, destination and original local-only/no-merge/no-deploy scope. Root PA has send_user_message; Q does not. Both Q-to-PA receipts target the actual PA ID.

Per the actual-context observation contract, did not stop at proxy-ingress request files: independently read corresponding serialized **upstream Responses** payloads under `/Users/czj/Repos/LLM_PROXY/logs/raw/openai_codex/`:

- `2026-10-25_21-51-06_582-upstream-req-anthropic_messages.json`: Q `input` contains the actual Inbox result for represented continuation `8d8186e30c7e45398e0d71969ed0eb32`, owner `u_2do5cthz`, PA `pa_d2f6246b3d4b`, same existing commit and no-recommit/no-other-file/no-merge/no-deploy limits; tools exclude representation.
- `2026-10-25_21-51-50_967-upstream-req-anthropic_messages.json`: PA system/input retain original owner scope, both represented-message provenance and the Q completion; actual tools include root representation. Fixed guidance and sent/held/unknown distinctions remain composed.
- `2026-10-25_21-51-41_353-upstream-req-anthropic_messages.json` and first-action review at `21-46-36_374`: independent Codex review input retains original user/PA and scope alongside exact pending action. These are real provider-bound serialized requests, not the prior synthetic-provider registration matrix.

Actual behavior is accurately staged: owner `7f8985...` → represented `1e77adad...` → one commit `04420a5a8e42d266bb0f3a34d42fb263a58da945`. Initial daily fixture prohibited all push; Q receipt `c35915...` and PA owner report `4f5446...` correctly say push incomplete. Caller restored the already-authorized fixture delta permitting only this local bare origin, preserving full before/after in environment-delta. Natural continuation `2aa21d...` → represented `8d8186e...` → actual Q bash `call_d0a91463fcd946e0bc6cd8774f6c53f9` performs non-force push of that **same commit** and asserts all non-.git file hashes, status and HEAD unchanged. Successful result and `git-final.json` show local/bare main identical, one new business commit and only final-integration.md added; three template files remain their preexisting untracked state. No duplicate user approval was required because of PA origin; continuation addressed a genuine environment-policy mismatch.

Completion receipt `3cb1efe6ed364dd7b69bb263340bb008` reaches the correct PA. Refreshed messages and independent product R5 confirm final PA→owner `0165f8e6401641e781001cadce2a3b8c` accurately reports verified push, same commit and unchanged scope. The initial partial result is retained and is not relabeled as first-attempt full completion. Product R4 closes native attachment preview; final acceptance R5 at 000dac07c is pass with limits retained.

### Test and migration limits

Inspected final build/typecheck/iOS-runtime, Web 1031 pass, Python 70 pass, Ruff, docs 283 sources/68 routes, native 46 XCTest + 25 Swift Testing pass and unsigned archive logs. Backend full run was **752 pass / 4 failures** (two test timeouts and two poll-until-timeout assertions); same-code 4-file serial follow-up passed 12/12 without product or timeout changes. This supports closure of those observed failures without claiming the first full run was green or proving a unique load root cause.

Old shared-runtime migration is **not passed**: final-sync-migration-plan contains unsupported/unowned workspace, preview/reviewer and schedule ownership plus source-changed planning blockers; apply was not executed. Caller retained complete backup/data and used fresh per-Agent partitions for integrated runtime proof. This inherited upstream deployment limitation is distinct from the passed feat-658 additive PA-column migration and remains a deployment prerequisite, not a new feature code finding.

R4 pending evidence: **closed** within the stated fresh-partition integration scope. R5 findings remain empty. Final surviving findings:

```json
[]
```

Final code/context review outcome: pass, with the documented old-runtime migration and test-stability limits. No source modification, service mutation or extra review loop occurred. Caller owns canonical reconciliation, archival, PR and PR CI; this report does not authorize production migration/deployment/release.

## R7 — Shared runtime compatibility review (2026-10-26)

Independent reviewer `feat658_shared_runtime_review` reviewed the merged working tree of `871cdf5c3` and main `dfb871662`, focused on feat-658 provenance/authorization versus bugfix-660 shared lifecycle. Caller transcribed the result here; reviewer did not modify implementation.

- Result: `[]`, no confirmed or plausible surviving compatibility finding. Relative to corrected main, the only overlapping product change in `index.ts` extends `Submit.source` with `sender` and `pa_agent_id`; the per-Agent enabled/revision checks and source spread remain intact.
- OwnedSessions restores the original session/preset; disabled-revision barriers cancel old queued execution without erasing history. Disposed sessions clear transient Inbox observation flags, while restored review context retains historical provenance. Root-only PA delegation, trusted ProductBridge identity and publication lifecycle checks do not require ordinary Agent process isolation.
- Independent verification: `approval-sources.test.ts` and `personal-security.test.ts`, 22/22 passed; diff whitespace check passed. Reviewer assessed the added cold-recovery provenance assertion; caller subsequently corrected its observation from consumed `user/message` to the native persisted inbox event because this fixture deliberately keeps the input pending. Product code was unchanged.
- Context Mode B inspected source projection/restored approval composition and prior real provider requests from the two component versions. Those separate samples are not a new integrated real-model journey. The caller's native shared-host/cold-recovery regression supplies merged-runtime evidence; unchanged UI acceptance is reused.
- Earlier R6 split-migration prerequisite is superseded by PR #409, which removed that layout and tool. The feat-658 IM representation-column migration remains required. This review does not authorize production changes.
