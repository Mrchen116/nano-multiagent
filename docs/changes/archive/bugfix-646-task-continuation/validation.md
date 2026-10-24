# Final delivery validation

## Frozen source and selected gates

- Final behavior source: `00ffba95923751b2ef04cc561158f85cb66adfa0`.
- Final integrated main: `55376c1112ff870837a6ee65febf52e1f3686a9b`; fetched again after the final product pass and unchanged. The final sync was `defa49f2db762ab7e0e0415b4a10312f0dcaf764`.
- Design Round 6 is Approved, 0 CRITICAL / 0 WARNING. Later mixed-input correction restores the already-approved automatic-input behavior; it adds no allowed source, permission, or new contract. Static Round 6 independently confirmed that the design and all three deltas remain aligned.
- Code review Round 6: findings `[]`; verification Round 6 and corrected-delta: aligned, 0 CRITICAL / 0 WARNING, no full re-verification required. Actual source `00ffba959`, effective_base `55376c111`; earlier integrated R5 evidence is retained by explicit source-impact analysis.
- Product Round 5: pass, zero open in-unit issues, P4 closed. Actual source `00ffba959`; R4 stop/old input/new explicit resume, ordinary new task and pure notification results retained, R1–R3 Global/waiting/feedback evidence retained. Product R5's literal `executed_base: R4 defa49f2d` denotes the prior integration baseline, not a main merge-base: the actual main base for R4/R5 is `55376c111`. This metadata clarification does not claim an additional execution.
- Canonical reconciliation copies the reviewed Global replacement and Task/capability additions without changing their semantics. Gateway area counts are updated to 17 Task and 43 capability requirements. Archive movement and these documentation edits retain the above gates; the PR records the final effective_through commit.

## Passing local evidence

| Check | Version and result |
|---|---|
| Complete build | `defa49f2d`, `pnpm build`, passed; installer candidate bca4d1524c5d. Final PA source `00ffba959` was then compiled with Node 24 `tsc -p packages/personal-assistant/tsconfig.json` before real R5 acceptance. |
| Typecheck | `defa49f2d`, `pnpm typecheck`, all packages passed; the final PA compile also passed. |
| Input/settlement integration | Independent R5, final integrated lib: four PA/input-evidence files, 34 passed; real native stop regression, 1 passed / 12 deliberately filtered. |
| Final mixed-notice patch | Node 24, SingleThread + interactive suites, 26 passed. Meaningful final text, mixed human input, source spoofing and visible approval remain covered. |
| Frontend | 103 files / 963 passed at e2219e12b; `git diff e2219e12b..00ffba959 -- src/IM/frontend` is empty, so this result is retained. Dependency audit critical gate also passed. |
| Python tooling/contracts | Final integrated tree: 65 passed / 31 e2e deselected, 19.82 seconds. |
| Formatting | `ruff check .` and `ruff format --check .`, passed (85 files). |
| Packaged iOS runtime | `pnpm check:ios-runtime`, passed. No iOS source or native interaction change in this unit; native iOS build selection follows CI's path gate. |
| Documentation | `scripts/docs-check`, passed after canonical reconciliation; archive integrity is checked again after moving the complete unit. |

## Local full-suite failures and authorized remote gate

Local full backend execution is **not green** and is not represented as a successful immutable final-tree run. The bounded 126-file run started on compiled `3a2debdd5`, before the final main sync; the PA notice fix landed during that run. It ended with 629 passed / 2 failed (workspace-tools 90-second timeout and knowledge-policy step-limit observation timeout). The result is historical diagnostic evidence only. Final patch and integration checks above are separately versioned.

The machine concurrently ran independent worktree suites. Observed load reached 728 earlier and rose above 250 again during final checks. A final Node 24 narrow knowledge/fallback run also timed out (18 passed / 5 failed); this is recorded, not silently discarded. No test assertion, production timeout, reviewer model, evidence budget, or unrelated process was changed to obtain a pass.

A controlled source comparison extracted **main `55376c111`** into `/tmp/nano-646-main-baseline`, compiled its integration source, and ran its unchanged workspace-tools and knowledge-policy tests on the same host with Node 24. Main itself reproduced the 90-second workspace-tools timeout; its five knowledge-policy tests passed. Diagnostic copies of the unit tests identified slow runtime/install operations and observation windows; they were removed without committing or treating the longer diagnostic windows as acceptance. These observations establish that the workspace timeout is also present without this unit; they do not prove every local failure has the same cause.

The same main SHA passed all 621 backend tests in [CI run 39987767490](https://github.com/Mrchen116/nano-multiagent/actions/runs/39987767490): workspace-tools 60.138 seconds, knowledge-policy 4.783 seconds and native model-fallback 25.528 seconds. This is a baseline comparison, **not** final PR validation.

On 2026-10-24, after code, independent review and real product acceptance were complete, the user explicitly authorized retaining the local failures, archiving and opening the PR, with the **final PR's complete remote CI** as the required full-suite delivery gate. Delivery is conditional on that run succeeding; it cannot inherit main's green status. Raw logs and isolated runtime evidence remain local and are not committed.

## Known boundary

Product R4 recorded a separate ordinary pre-stop human reply for which the model chose literal NO_REPLY without a confirmed explicit send. The old reply did not resume the paused task. This unit preserves ordinary-human delivery semantics and does not generalize automatic-input silence to arbitrary human replies; the observation remains a separate experience issue in regression.md. No production merge or deployment is part of this delivery.

## Same-PR quiet-stop follow-up (2026-10-24)

This section supersedes the original delivery's source/gate metadata for the additional user request. Prior failures and prior product findings above remain historical evidence; they are not the final follow-up outcome.

- User explicitly requested passive stop notification and an audit of human/system Task mutation synchronization. Design R7–R9 approved the scoped changes. Native and IM regressions reproduced quiet-stop, passive-context/UI-resume, cold empty responsibility, dissolution notification and normal-teardown stop loss before fixes.
- Final integrated behavior source: `3bdcdc546`; main baseline: `63724d53f` (merged by `d44a48792`). The main capability separation is retained: callable Task tools remain available with Feature off, while feedback guidance and automatic execution remain Feature-gated. The added manual-tool regression covers this integration seam.
- Static R7 found a concrete latest-stop ordering defect after blocked admission reinserted older inputs last. The final source selects the newest distinct stop by first acceptance, then checks only that notice's consumed/pending state. Native red: 1 failed / 3 passed; integrated targeted green: 7 files / 39 passed.
- Full backend on the integrated final source: `pnpm test`, Node 24.22.1, **130 files / 675 passed**, 108.71 seconds. Frontend: **104 files / 987 passed**, 26.18 seconds. There are no final local suite failures; the earlier load-related failures belong to the initial delivery and have not been removed from this record.
- Complete build and typecheck, Web production build, Python **65 passed / 31 e2e deselected**, ruff checks, packaged iOS runtime, documentation integrity (**273 maintained sources / 67 routes**) and archive validation passed. The only post-source canonical edit corrects the alignment header to the required single latest unit; requirement counts remain 45 capability / 19 Task.
- Local raw logs: `/tmp/nano-646-followup-integrated.log`, `/tmp/nano-646-followup-integrated-full.log`, `/tmp/nano-646-followup-frontend-test.log`; stop-order failure is preserved in `/tmp/nano-646-stop-order-red.log`. None are committed.

- Independent static R8 (`48894194b`): findings `[]`, R7 P2 closed; verification/corrected-delta aligned, 0C/0W. Only report and validation metadata edits follow the frozen behavior source.
- Independent product R6 (`f4540f2dc`): Global/SingleThread stop zero-wake, old-input priority, same-Agent parent/child notice silence, another Agent's independent reply, explicit human Task API resume and normal-restart stop/empty-snapshot consumption passed. Group dissolution produced closed state and the actual native removed-responsibility context. The browser node-details path was not completed; API mutation and real native execution were verified separately.
- **Overall follow-up product gate remains inconclusive:** external reassignment reached the new owner, but DeepSeek returned `402 Insufficient Balance` before its result could be delivered. No implementation defect is inferred from this provider failure, and no successful reassignment delivery is claimed. Only that scenario needs re-review after test environment recovery. Model switching is pending the user's choice; no production service or reviewer policy was changed.

### R7 correction and R8 Codex completion recheck

R7 (`c0d9df475`) verified reassignment, actual delivery of 39 and the former owner's responsibility withdrawal, but its complete-pass judgment was incorrect: the human-created Task explicitly required completion, and both Tasks remained doing after CC-rule approval denials. The done writes were part of that request, not extra work. Product R8 records this correction without rewriting the historical execution facts.

The user subsequently requested Codex as the code default. Main commit `f07c6d760` changes the shared default and preserves explicit CC/DSH overrides; the unit carries the same patch in `b20458be3`. The default Task guidance remains Raft's in_review preference. No new completion restriction, human-message requirement, reviewer bypass or evidence truncation was added.

Independent product R8 (`8181da242`, runtime `b20458be3`) is **pass** for the same explicit-completion scenario. Authenticated human Task API created `tg_b137be86/n1` with the identical description and reassigned it from Global to e2e. The new owner delivered 39 to the Task chat and successfully applied done with the actual delivery reference. Native call `call_4798b2222f8649c2a566d1aa7daccfda` and the durable audit agree: rules=codex, classifier_allow, risk=low, authorization=unknown. Thus this demonstrates a low-risk allow, not successful extraction of explicit authorization. No extra completion-authorizing chat was supplied. Old CC-denied Tasks remain doing and were not silently completed.

The execution and review model remained gpt-6.1-sol. R6 stop/restart/resume and R7 former-owner evidence retain their actual versions and models; this narrow recheck does not claim a new browser or platform matrix. Production was not changed.

Independent patch review covered `fde4090c7..b20458be3`: findings `[]`, including default selection, owner/workspace explicit overrides, per-Agent cc/codex selection and null inheritance, runtime dispatch and denial/manual paths. Existing static/corrected-delta evidence remains valid for unchanged stop/sync behavior. Main build, typecheck, documentation and 6 focused files / 27 tests passed; the final unit build passed. Latest origin/main `d50559ea5` adds only the unrelated feat-652 specification and was merged without runtime changes. Final-head remote CI is recorded on the PR.
