# Code review: feat-587-first-run-onboarding

## Round 4 — targeted closure + patch

- `review_round: 4`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05`
- `validated_at: f881314a469e97178cd91e59a308c0d3625404d9`
- `diff_range: eac3c2ffd7e0c5725b0647faf4aa3eb2f3fa094f..f881314a469e97178cd91e59a308c0d3625404d9`

```json
[]
```

The one source change in `packages/dsh-integration/src/global-mode.ts:18` repairs the overly broad completion guidance: a direct human request requires explicit `send_message` delivery to its actual source unless the human requested no reply; tool success/private drafts are not delivery; once delivered, an extra completion is unnecessary; background work without an actionable update remains silent. Existing sent/held distinction, source authorization and denial handling remain intact. Tool schemas/execution, permission routing, Inbox, targets and terminal mechanisms are unchanged. Design/progress additions accurately describe the observed product failure and this bounded repair.

Closure: the misleading prompt condition is **closed at source/contract level**. Product R3 #5 remains pending independent real-model confirmation; this review does not infer delivery from task_graph success, Work prose or the deterministic communication fixture. R3 implementation findings/closures are retained and no new confirmed/plausible code defect survives this patch.

Read-only evidence reuse: `delivery-build.log` completed root build and emitted the `f881314a469e` release; `delivery-native-tests.log` reports communication-native 2/2 passed (2.32s). The tests cover actual public-send bridging and silent completion after delivery/no-op, plus preservation of other failures. Their model output is controlled, so they do not prove this guidance changes a real model's decision. No redundant run or prompt-string test was added. `git diff --check eac3c2ffd..f881314a4` passed. No full review, source edits, service changes or unrelated documentation staging.

## Round 3 — closure + patch

- `review_round: 3`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05`
- `validated_at: 07f55e7140c0194dae3504ae03126e1e4dbee71a`
- `diff_range: 00dd42398d4b9ec9baf0e136d786299659cf8cd3..07f55e7140c0194dae3504ae03126e1e4dbee71a`

```json
[]
```

### Finding closure

| Focus | Status | Direct evidence |
|---|---|---|
| R2 Work registration loss after handoff | closed | Revoked registrations retain only immutable session identity/scope/parent structure; revoked event payloads are not inserted, projected or broadcast. Mixed-node handoff regression now advances through seq4 for company and personal work and excludes the revoked title. `session_linked` uses the same metadata-only path. |
| R2 same-page offline masked by ready selection | closed | Actual offline status now precedes `viewStep`; the create-success → offline refetch test switches the same mounted component to recovery and removes the first-task button. |
| Product R2 private task refused because of company-only guidance | closed at implementation contract | Tool/system guidance now states fixed personal/company resource spaces, joining-company privacy and context-only discussion target. Tool execution, mutation/retry and ordinary deletion approval remain unchanged. Real-model product acceptance remains separate. |
| R1 journal/discovery/official Node runtime findings | retained closed | Discovery/runtime source and tests are unchanged from R2; Work's revised recovery supersedes the earlier discard-only implementation and closes R2's regression. |

Reviewed the three changed source files, their two updated behavioral test files and M1 evidence. Independently ran tenancy 6/6, socket control/Work 4/4, onboarding 6/6 and native task deletion permission 1/1. `git diff --check` passed. Retained the independently observed final Web log (88 files, 833 tests passed). At inspection, HEAD differed from the frozen source commit only by the product acceptance report; no source/build/service changes were performed. No surviving confirmed or plausible finding within the requested patch/closure scope; no full re-review required.

## Round 2 — closure + patch

- `review_round: 2`
- `executed_base: b70d4a7bd80b4424fea430e507390c5dde7c0a05`
- `validated_at: 00dd42398d4b9ec9baf0e136d786299659cf8cd3`
- `diff_range: 59650f196642afbbc63f1475c0b874a6b1dc6ea9..00dd42398d4b9ec9baf0e136d786299659cf8cd3`

```json
[
  {
    "file": "apps/im-server/src/work.ts",
    "line": 121,
    "summary": "[P2] Recover session registration before accepting work after device handoff",
    "failure_scenario": "The new revoked-event ACK discards session_registered together with content. If the first registration was pending when company access was revoked, it is permanently acknowledged without a server session. Hand the same mixed company/private node to another approved member (deviceCommit updates node/profile owners and personal spaces but preserves runtime sessions/journal): subsequent authorized company turn events now reach this.session and return scope_not_allowed because the registration is absent, rolling back the batch including private work. InboxStore.append deduplicates the stable <session>:registered event_id, so GlobalAgent.main cannot issue a fresh registration after the ACK. Independently reproduced through real IM Work: discard company seq1 registration while suspended, accept private seq2, apply the exact owner/space transition used by deviceCommit to an active recipient, then append company seq3/private seq4 turn_started. Append throws scope_not_allowed, through_seq remains 2, and private seq4 is absent. This fixture exercises the IM seam and owner transition, not the full interactive handoff protocol. Recover required registration metadata or provide idempotent re-registration without replaying revoked content; protect the handoff recovery path.",
    "review_mode": "closure + patch",
    "status": "CONFIRMED"
  },
  {
    "file": "src/IM/frontend/src/features/onboarding/onboarding-page.tsx",
    "line": 62,
    "summary": "[P2] Let actual offline state override the completed-step selection",
    "failure_scenario": "The offline fix changes suggestedStep only; step=viewStep??suggestedStep still honors create.onSuccess setViewStep(3). Create an assistant, leave the completion screen open, and let its computer disconnect. Even after the existing onboarding query has refreshed to status=offline, the page continues saying the assistant is ready, leaves Start your first task enabled and provides no reconnect command. Independently rendered the actual OnboardingPage with real React Query/router, mocked only API boundaries: online verified model -> successful Create -> invalidate onboarding with offline node. Asserted authoritative cached status offline, ready heading present, first-task enabled and recovery instruction absent. Temporary behavioral fixture passed all four assertions and was removed. Give offline recovery precedence over viewStep and add the same-component online-to-offline regression; the new initial-offline mount test does not cover this.",
    "review_mode": "closure + patch",
    "status": "CONFIRMED"
  }
]
```

### Historical finding closure

| Finding | Status at validated_at | Evidence |
|---|---|---|
| W1 revoked company event blocks private journal | closed for the original suspended-owner scenario; new handoff recovery regression above | Revoked events advance ACK without content storage/broadcast; mixed-journal and no-replay regression passes. Missing registration after later handoff is separately reported. |
| W2 stale local connection discovery | closed | Public status rediscovers on each call; absent-to-available regression passes. |
| W3 interrupted official Node extraction | closed | Temporary extraction, Node/npm validation and completion marker precede promotion; first-failure/second-success shell regression passes. |

Reviewed every file in the specified 17-file patch, including the two product repairs and generated-profile link migration. Independently ran tenancy/model-setup/installer 12/12, profile link migration 1/1, and original onboarding suite 5/5. Two temporary fixtures each reproduced the reported failure with 1 passing behavioral test; both were removed. `git diff --check` passed. Existing wider test/runtime evidence is retained in M1 progress. No source edits, no full-suite rerun. The frozen version is the review target; caller changes after that snapshot are outside this round.

## Round 1 — retained historical findings

Snapshot: `b70d4a7bd80b..59650f196642afbbc63f1475c0b874a6b1dc6ea9`; review mode full.

```json
[
  {
    "file": "apps/im-server/src/work.ts",
    "line": 98,
    "summary": "[P1] Do not let a revoked company Agent block the private Agent's shared journal",
    "failure_scenario": "A personal-enabled company member can receive a company device and create a private global Agent on that same node. If company membership is suspended while a company Work event is unacknowledged, agentAvailable rejects that event and rolls back the entire append batch. GlobalAgent.flushWork uses one node-wide InboxStore journal and throughSeq for all Agents, so it resends the rejected company event before every later private event. GlobalAgent.receive awaits main()->flushWork() before wake(), and therefore even a new private chat never reaches session.submit. Independently reproduced at 59650f196 through real IM Work, InboxStore, NodeStore and GlobalAgent.receive with a stubbed runtime: private receive failed with scope_not_allowed; runtime calls were only [session.ensure]; session.submit was false. A private-only seq=2 retry also returned expected_seq=1. Preserve the company authorization denial while allowing the private journal/work to advance; add a mixed company/private revocation regression at the appropriate seam.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/im-server/assets/install.sh",
    "line": 29,
    "summary": "[P2] Promote a downloaded Node runtime only after extraction completes",
    "failure_scenario": "On a computer without an existing supported Node/npm, the installer extracts the official archive directly into the final tooling directory and treats executable bin/node as a complete installation. If extraction fails after bin/node is written (for example disk full), a repeat of the advertised recovery command skips extraction and runs with missing npm/libraries. Independently reproduced by executing the actual frozen install.sh with local download/tar fixtures: first extraction created executable final bin/node then failed; attempt1 exited 1 with the preserve/retry message; attempt2 skipped tar and exited 127 with npm: command not found. This is a controlled extraction-failure reproduction, not a claim about which files the product review's separate disk-full run had written. Extract into a temporary directory and promote only a complete verified runtime; failed attempts must remain safely retryable.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/node/src/model-setup.ts",
    "line": 64,
    "summary": "[P2] Refresh local discovery when the user repairs or starts a connection",
    "failure_scenario": "The first setup status permanently memoizes discoverLocalModels, including an absent or stopped optional proxy. Starting/fixing the proxy afterward does not make it discoverable on any status poll, explicit query retry, browser refresh or re-login; only restarting the node creates another ModelSetup. Independently reproduced at 59650f196 by changing the discovery fixture from no proxy to a live proxy between two public handle({action:status}) calls: both snapshots returned {codex:false}, with discovery calls=1. The recovery journey says to repair/retry and reuse a local connection without editing configuration; the cached result prevents that path. Use a bounded refresh policy or explicit discovery retry and protect absent-to-available recovery with a behavioral test.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```


## Round 5 — integrated feat-588 completion audit

- `review_round: 5`; independent code-review / change-verifier roles retained.
- `validated_at: 77622d2152fe7e1bb2966fb656adf9e41613aed6`
- `executed_base: b7e367cc08a642133dea28e372816cd79038818d` (origin/main, ancestor of validation head).
- Worktree: `/Users/czj/.codex/worktrees/feat-588-model-services/nano-multiagent`; branch `codex/feat-587-final-review`. The archived original feat-587 worktree was not accessed.
- Modes: integration-delta and completion-audit. Reviewed affected onboarding/model/credential/installation/current-documentation seams; retained unaffected full and closure reviews. No additional full review or implementation changes.

### Findings

```json
[
  {
    "file": "docs/operations/local-stack.md",
    "line": 13,
    "summary": "[P2] Document verified Release manifest promotion before enabling installation",
    "failure_scenario": "The current operations entry says pnpm build creates dist/node-release/manifest.json and that IM needs the archive alongside it. The integrated build now writes only manifest.candidate.json; install.ts enables the installer only with the separately verified manifest.json, while the archive is downloaded directly from the fixed GitHub Release. An operator following this current instruction on a clean deployment gets an unavailable installer/503 and no documented publication/promotion step, or may rename an unverified candidate to make it work. The new correct instructions exist only in archived feat-588/guidance.md, which itself acknowledges the current local-stack text is obsolete. Update the current operations route with candidate versus verified manifest, fixed-version publication/anonymous hash validation, IM-only metadata deployment and coordinated rollback; do not imply publication/deployment already happened.",
    "review_mode": "integration-delta + completion-audit",
    "status": "CONFIRMED"
  },
  {
    "file": "docs/operations/gateway.md",
    "line": 9,
    "summary": "[P2] Replace removed proxy autodiscovery instructions in current product entrypoints",
    "failure_scenario": "Gateway operations still promises that an existing local proxy can be directly discovered and tested, and README.md:12 lists that discovered connection as the first setup path. User-approved feat-588 explicitly supersedes feat-587's old discovery-first S6: the current common editor defaults to API providers/custom service, and Node no longer scans developer proxy configuration. A new user following the current entrypoints is sent looking for a removed discovery action rather than using the supported API-first path. Align README and Gateway instructions with current IM agents-nodes contract: built-in/API first, optional Codex login, custom API including manually entered loopback proxy, plus the permanent model-services entry. Retain historical S6 in archived spec as superseded rather than claiming it passed again.",
    "review_mode": "integration-delta + completion-audit",
    "status": "CONFIRMED"
  }
]
```

### Retained closures and integration evidence

- No new runtime-source correctness finding. feat-587 historical W1/W2/W3 and R2 Work/offline repairs remain closed within their applicable contracts. The removed discovery-specific W2 implementation is superseded by feat-588's explicit API-first scope; it is not missing work. feat-587 product R4 at f881314a4 independently closed actual private-save → original-chat delivery (tg_6bd77847), superseding this report's earlier pending-product wording.
- Retained feat-588 M1 full R1 and targeted R2–R4 static/verification evidence. Legacy remaining-service credentials have stable immutable-ID env bindings; vendor catalog identity remains separate from editable service labels. The temporary probe, shared Agent/model write queue, revision/dependency rechecks, local credential store and safe IM projection remain as reviewed. Product R1/R2 actual API onboarding, edit/key retention, conflict/offline/dependency/restart and same-assistant replies, plus R3 menu visual evidence, are retained with their fixture/platform limits.
- Independently checked `0247eb0e6^{tree}` equals `77622d2152^{tree}`: `85a9120442e4b5a7ed2df13360d77bf9da90558f`. Since the last semantic cleanup `1bb8ff98e`, only archived reports/progress/guidance changed; the integration introduces no unreviewed runtime-source delta.
- Read-only GitHub checks: PR #339 is MERGED into `codex/feat-587-first-run-onboarding` at 77622d2; PR #337 remains OPEN with base main. CI run 38349265822 for 0247eb0e6 is completed/success: TypeScript backend/tooling, frontend and iOS build/tests all successful, including Release device archive. Tree identity supports retaining this run after the merge commit; no new full test run is needed solely for the commit shape.
- Independently passed range `git diff --check`, `bash -n apps/im-server/assets/install.sh`, and `node --check` on build/publish release scripts. Existing tests were read with trusted recorded results; no test/service/build/release operation was repeated.

Conclusion: **changes required for the two current-documentation findings before completion approval**. Implementation and existing functional/CI gates can be retained. New integrated product confirmation and the requested API-first new-user video are separately owned next steps; Release publication, anonymous public asset download and production deployment have not been executed and are not asserted by this code review. No merge-main, push or external message action was performed.


## Round 6 — closure of integrated documentation findings

- `review_round: 6`; mode: targeted closure.
- `validated_at: 22aa42c62af979671366d2a1ebc2644f1d7618e0`
- `pre_fix_head: ea547e6eddb118c5798d25a524a7e0f59e18a309`; inspected the entire five-document patch.
- `executed_base: b7e367cc08a642133dea28e372816cd79038818d`; runtime-source validation retained at `77622d2152fe7e1bb2966fb656adf9e41613aed6`.

```json
[]
```

| R5 focus finding | Status | Closure evidence |
|---|---|---|
| W5-D1 / P2 obsolete installation publication runbook | closed | local-stack now separates build candidate from verified manifest, names manual fixed-SHA publishing and anonymous hash validation, uses the workflow artifact for metadata-only IM deployment, requires matching/atomic manifest switches and retained rollback, and distinguishes public first-use acceptance from fixtures. Compared with actual build/publish scripts, workflow and install routes. |
| W5-D2 / P2 removed proxy discovery promised in current entrypoints | closed | README/Gateway now present API-first built-in/custom setup, optional Codex and manually entered compatible proxy. Permanent per-computer model-services entry and local YAML/credential-store boundaries are explicit. No promise of developer-config scanning remains. |

Reviewed both index changes: they route current readers to the corrected current operations section, with valid file targets and an existing heading. `git diff --check ea547e6ed..22aa42c62` independently passed; caller's focused docs-check passed (243 sources / 64 routes), reused without another full check/test cycle. The complete patch changes only five current documents; relative to runtime 77622d2, all additional changes are those documents plus the R5 reports. No runtime source, tests, dependencies or behavior changed.

Result: **PASS, both P2 findings closed and no surviving findings**. R5's implementation review, test/CI evidence, historical issue closures and explicit supersession mappings are retained. Independent product review and the requested new video remain separate. Publication, public anonymous asset acceptance, production deployment and merge-main remain unexecuted/outside this closure. Only these two archived reports were appended; no push or runtime operation.
