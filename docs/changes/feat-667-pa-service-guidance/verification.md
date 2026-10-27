# Verification Report: feat-667-pa-service-guidance

> Validation snapshot: `c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5` → `7ddaceb942423436bc656fba6707b04f131c9cb1`

## Round 1

- Reviewer: independent `/root/pa667_static_review`.
- verification_mode: `full`; review_round: `1`.
- Scope: all M1 exit criteria, all unit Requirements/Scenarios, design decisions, gateway delta-specs, and currently available implementation/test evidence. Reuses the full Context Implementation Review in `code-review.md`.
- verdict: **pending evidence / not pass**. One CRITICAL completion-evidence issue, zero WARNING, zero SUGGESTION. No confirmed implementation defect or implementation/design mismatch was found.
- requires_full_verification: `false`; remaining work is bounded completion-evidence reconciliation for the existing M1 criteria, not another full code review.

## Summary

| Dimension | Result |
|---|---|
| Completeness | All 10 unit scenarios have implementation mapping; M1's required real-model/product evidence was not yet supplied at this snapshot. M1 remains incomplete. |
| Correctness | Available native runtime/schema/enforcement/depth tests support the engineering claims; real model behavior remains unverified. |
| Coherence | Implementation follows the A+B design and repository boundaries. No current-spec merge is performed in the active unit. |

## Completeness

- Tasks: single M1; implementation exists, but its combined worker/reviewer exit criteria are not all closed. No tasks/progress artifact is required for this simplified workflow.
- Spec: all declared scenarios map to the three service texts and existing runtime/product mechanisms; the additional delegation layer and root-only product chat boundary are implemented.
- Prototype / Reference: N/A; no frontend prototype or client change.
- Current specs reviewed: `gateway/personal-agent.md` (identity, observation, source permissions, disclosure, configurable guidance); `gateway/global-agent.md` (root coordination, explicit public delivery and lifecycle); relevant `gateway/agent-capabilities.md` and `gateway/task-graphs.md` contracts. The active deltas intentionally extend behavior; they do not overwrite current specs before completion.

## Correctness

| Requirement / Scenario | Implementation location | Available evidence | Status |
|---|---|---|---|
| 小事直接完成 | `apps/im-server/src/personal-agent-defaults.ts:2,10` | Default text and existing first-create configuration seam | Implemented; real result pending |
| 长事项持续交付并说明能力边界 | default instructions; `nano-ongoing-work/SKILL.md:9-21,52-59` | Actual executor ID/record/delivery instructions; native continuation tests | Implemented; real long-task result pending |
| 更正与短问题 | `nano-ongoing-work/SKILL.md:25-28` | Native same-child continuation available; no supplied two-work real-model correction/short-answer trace | Implemented; real scenario pending |
| 单项停止 | `nano-ongoing-work/SKILL.md:30-34` | Existing cancellation semantics retained; explicit user scope and no late-result restart guidance | Implemented; actual A-only stop/B delivery pending |
| 承诺后的实际准备 | `nano-proactive-care/SKILL.md:8-21` | Source verification/private preparation/delivery limits in text; source and disclosure mechanisms retained | Implemented; real private draft and absence of public send pending |
| 已处理、无新价值和覆盖不足 | `nano-proactive-care/SKILL.md:12-14,23-27` | Instructions preserve uncertainty and stop stale/redundant preparation | Implemented; real processed/quiet/incomplete-source cases pending |
| 自定义、清空和禁用保持 | unchanged PA creation/config paths; `agent-config.ts:133-134,155-176`; `capabilities.ts` Skill filtering | Existing personal-agent, personal-security and capability coverage; no backfill logic added | Engineering protection available; product choice checks pending |
| 任务执行者可再委派一层 | `client.ts:26`; unchanged native subagent mechanism | `/tmp/pa667-child-green6.log` 2 passes, `/tmp/pa667-depth-green2.log` 3 passes; reviewer explicit-override probe | Default depth engineering verified; #361 two-level Ready PR/CI and progressive delivery pending |
| 子 Agent 只进行内部通信 | `agent-config.ts:105-139`; `global-mode.ts:79-86`; `global-agent.ts:411-415`; role-sensitive Task/UI/security | Ordinary Global/PA actual runtime schema + spawn/fork/cold resume and internal tool results; direct product-send rejection; reviewer deferred-feedback capture | Engineering verified; real parent source request/read/final public delivery pending |
| 主人要求接续已停止事项 | `nano-ongoing-work/SKILL.md:32-34` | Native same-ID cold continuation available; no automatic restart promise added | Implemented; explicit owner resume of stopped original worker pending |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| A limited to editable initial Persona plus two packaged Skills | Yes | Exactly the declared service-text locations; no new ledger/scheduler or #414 memory structure |
| Native default maxDepth 1→2; caller override preserved | Yes | Default preceding caller patches in `client.ts:26`; native depth tests and reviewer explicit maxDepth=1 execution probe |
| Product chat tools only on Global roots, native internal messaging retained | Yes | Root-local registration, actual child send schema, product session guard and cold-resume evidence |
| Root handles Task responsibility and executor coordination without new hard binding | Yes | Skill/Task guidance; no Task-child field, executor manager or Task protocol migration |
| Child current guidance consistent with available tools | Yes for covered engineering seams | Static Task/UI/security branches plus actual runtime child prompts, schemas and deferred feedback; real model consumption still pending |
| Existing user choices and source/disclosure boundaries retained | Yes in implementation | No default backfill or replacement configuration path; inherited source/approval checks remain; existing user-choice testing retained |
| No independent observer, runtime fork/private import, client rebuild or production migration | Yes | Full diff inspected; no such additions |

### Prototype / Reference Contract

N/A.

## Evidence ledger and limitations

- `/tmp/pa667-child-green6.log`: `global-child-tools.test.ts`, 2/2 passed. Ordinary Global and PA, real locked native runtime, model-stream fixture; root/first/second child schemas, fork, internal messaging and cold continuation. It does not prove real-model task selection.
- `/tmp/pa667-depth-green2.log`: `trajectory-runs.test.ts`, 3/3 passed. Default depth-2 execution, rejected depth-3 ordinary creation, causal run records and cold reads.
- `/tmp/pa667-affected.log`: 82 passed / 1 failed, where the failed personal-child-delivery expectation still required the now-forbidden child public send. This is a historical run, not an all-green result. The committed test now expects refusal; its corrected case passed in `/tmp/pa667-depth-green.log`. That later log's trajectory failure was an incorrect result-field locator, subsequently corrected and passed in green2. Do not count either historical failure as an unresolved product failure or as a fully green combined gate.
- `/tmp/pa667-build.log`: workspace build passed. The generated installer footer names the pre-commit base; the caller supplied it as the build of this implementation before commit, so it is used as caller-attributed build evidence rather than independent commit-stamped provenance.
- `/tmp/pa667-static-probe.log`: independently executed during this review on confirmed HEAD, Node 24.22.1, locked runtime. A later explicit maxDepth=1 overrides the new default and rejects second-level creation. A Global child Task.apply produces actual next-request feedback routed to parent via agent_id/message, preserving fixed conversation and not repeating the root public-send demand. Controlled model responses; no real-model behavior claim. Isolated runtime shutdown and home cleanup completed.
- No final real-model/product acceptance artifact or main/candidate finite comparison was available to this reviewer. No production data, service or #414 old workspace was used.

## Issues

### CRITICAL

- **V1 — M1 completion evidence is still outstanding (CONFIRMED evidence gap, not a confirmed product defect).** Contract: `design.md:101-107,113`. Current runtime fixtures cannot satisfy the mandated real-model/product results: finite baseline/candidate comparisons; actual Skill discovery/loading; user-requested #361 two-level implementation with independent Ready PR/CI and root delivery; two simultaneous works with correction/short question/A-only stop/B result and explicit original-worker resume; private useful preparation followed by handled/no-value quietness and incomplete-source uncertainty; user-choice product checks; child request → root source read → root public delivery. These activities were explicitly reported as in progress, and none is presumed failed or complete. **Action:** retain incomplete/Draft status, supply version/model/config/input/tool-result/output locators from the independent acceptance work, then reconcile only these criteria and any actual discovered fix delta. Do not amend spec to erase them or re-run an unrelated complete suite.

### WARNING

None.

### SUGGESTION

None.

## Delta reconciliation

The three active gateway delta-specs match the intended implemented changes: PA service guidance/private preparation, Global root-only product tools and lifecycle consistency, and default two-layer delegation with native refusal at the third layer. No additional externally observable behavior in the unit diff was found missing from those deltas. Task data and IM protocols remain unchanged. This is implementation alignment, not confirmation of the pending model behavior outcomes.

Outcome: implementation aligned; final M1 verdict awaits V1 evidence closure.
