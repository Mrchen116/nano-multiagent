# Verification Report: feat-703-pa-create-agent

> Validation snapshot: `1580df55443b4404a85777b707f147ae36575b33 → 6a588bde10f95b2bf8a408c80287b54595bb67ca`

## Round 1 metadata

- verification_mode: `full`
- reviewer: `/root/static_review_703`, independent static code reviewer + verifier
- review_round: 1
- validated_at: `6a588bde10f95b2bf8a408c80287b54595bb67ca`
- executed_base: `1580df55443b4404a85777b707f147ae36575b33`
- report status: provisional, final product report pending
- requires_full_verification: false (this is the full verification itself)

## Summary

| Dimension | Result |
|---|---|
| Completeness | Implementation present for all four spec requirements; M1 exit evidence incomplete pending real product report |
| Correctness | One confirmed lifecycle-boundary defect; remaining reviewed deterministic paths align |
| Coherence | Shared operation/catalog and identity design followed; first-operation lifecycle boundary needs correction |

## Completeness

M1 is the sole milestone. IM shared creation/catalog, PA request association, native tool, Skill, protocol and regressions are implemented. Final end-to-end product acceptance is still running; implementation presence is not milestone completion.

Prototype / reference: N/A. No client UI change or new reference contract.

## Correctness

| Requirement / scenario | Implementation | Tests/evidence | Status |
|---|---|---|---|
| Explicit owner request; ordinary discussion, observation, child and ordinary Agent boundaries | `personal-agent.ts:141-145,280-283`; PA root gates; Skill lines 12-20 | IM source/owner tests, host child/non-PA tests, native catalog contrast; real discussion self-check reported by caller | Deterministic identity aligned; semantic discussion/withdrawal behavior awaits product evidence |
| Persistent Agent, discoverable, chat/configurable, truthful links | `personal-agent-creation.ts:87-93`; shared `createAgent` + existing configuration commit | IM actual durable profile/user/conversation + links checks | Implemented; final real-model full journey pending |
| Ask about real options; default PA computer; explicit alternative owned computer | `personal-agent-creation.ts:40-56`; `personal-assistant.ts:115-123`; Skill lines 14-16 | Real catalog test; separate owned-node success; foreign/offline reject | Deterministic aligned; live agreement wording pending |
| Low-frequency guidance and fixed tool | `personal-security.ts:209-213`; `capabilities.ts`; bundled Skill | Four actual serialized HTTP requests in native fixture; tools/system stable and body loaded on demand | Mechanism proven; real tool choice still pending |
| Same-key pending/unknown/restart recovery; conflict/rejection truth | `personal-agent-creation.ts:58-99`; `agent-creation.ts:124-138`; reserved operation ID in `control.ts` | Lost ACK + recreated PersonalAgents recovery uses one operation; key conflict, existing ID, rejection and unknown tests | Aligned at tested seams |
| Current producer execution authority at actual new-operation boundary | `gateway.ts:413-416` versus `agent-creation.ts:123,146,185-187` | Independent held-queue reproduction in `code-review.md` R1-C1 | **CRITICAL: queued creation survives PA disable** |

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| One fixed short schema + one on-demand Skill | Yes | Native tool registration, fixedTools + existing Skill selection; serialized-request fixture |
| Existing creation/catalog semantics shared with Web | Yes | `control-routes.ts:149-157,187-191` delegates shared module; extraction checked against base |
| Host identity separated from model target | Yes | `personal-assistant.ts:117-119`; `PersonalAssistant.request` overwrites transport identity from host; owned second-node test |
| Original owner provenance + main PA only | Yes at admission | Existing `ownerMessage`, root ProductBridge + GlobalAgent gates; lifecycle after wait is the separate defect |
| Request → exact operation; no second apply state machine | Yes | `pa_agent_creations` key/unique operation; caller-reserved ID; ConfigOperations remains authoritative |
| New writes obey lifecycle/management boundary | No | R1-C1: asynchronous wait is not followed by producer generation guard |
| Context proof and representative real behavior separately recorded | Partially | Native fixture proves assembly; real product acceptance report not yet received |

### Prototype / Reference Contract

N/A.

## Evidence and limits

Reused applicable caller-provided test runs: 72 narrow IM/PA/catalog tests, 50 native PA/context + PA host/contract tests, build/typecheck, pytest 129 and ruff passed. Independently read `.feat703-backend-tests.log`: 210 test files / 1121 tests passed. These are regression evidence, not substitutes for missing model behavior.

Mode B Context checks were performed by this same code reviewer and reused here. See `code-review.md` for surfaces, final serialized request evidence and its controlled-provider limitation. No actual provider cache-hit claim. Caller reports the final daily stack uses Astra PA/medium with Codex automatic approval and no permission skip; ordinary discussion did not create, and explicit request produced actual options. Confirmation, final successful creation and independent scenario report were still in progress at this snapshot.

## Issues

### CRITICAL (1)

- **R1-C1 — New operation can be accepted after its PA is disabled.** `apps/im-server/src/agent-creation.ts:185-187` checks target availability after waiting, but not the initiating PA lifecycle/current authority. Deterministically reproduced: lifecycle admission revision 1 → shared queue wait → disable producer revision 2 → release → `agent.create`, durable new Agent, returned `created`. This violates current execution authority and allows a newly created independent Agent beyond PA shutdown. Revalidate a trusted producer guard at the first configuration-operation acceptance/dispatch point, and add a focused wait/disable regression. Keep receipt/status recovery of already accepted work distinct. Evidence: `code-review.md`, R1-C1.

### WARNING (1, evidence gap; not a confirmed product defect)

- **R1-E1 — M1 final real-model/product evidence incomplete.** `design.md:79,104,110` requires representative real chat agreement, long-lived created Agent/use links, non-creation discussion/withdrawal, explicit-node/offline/conflict/unconfirmed-result outcomes, ordinary approval and independent product journeys. The four-request native fixture proves assembly only. Supply the final product reviewer report with version/configuration/locators; reconcile it here before declaring M1/pass. This is still running, not an asserted product failure.

### SUGGESTION (0)

None.

Verdict: **not pass** — one critical defect and one provisional evidence gap. No source, test, config or design changes; no reviewer-started services to clean.

## Round 2 — targeted closure of R1-C1 / current static result

- verification_mode: `targeted-closure`
- review_round: 2
- executed_base / fix_delta_range: `6a588bde10f95b2bf8a408c80287b54595bb67ca..f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- validated_at: `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`
- focus_issues: R1-C1 and its associated new-operation authority invariant; R1-E1 evidence status carried forward.
- requires_full_verification: false
- prior report: Round 1 above; full static review remains applicable to unchanged implementation.
- report status: **static implementation aligned; final product evidence provisional**.

| Issue / invariant | Closure evidence | Result |
|---|---|---|
| R1-C1: first operation accepted only while initiating PA generation/binding/source are valid | `agent-creation.ts:187-189` invokes synchronous guard after all preparation waits; `personal-agent.ts:403-406` checks current authority, original lifecycle revision and original owner source | **closed** |
| Already accepted operation keeps existing receipt/result recovery | `agent-creation.ts:125-134` exits through own operation recovery/result before new guard; `personal-agent-creation.ts:80-86` returns not_started for unaccepted status | aligned |
| Existing Web creation and one authoritative apply state machine remain intact | Guard is optional and only PA first-create supplies it; existing `ConfigOperations.create` remains the insertion/apply owner | aligned |
| New regression protection | Independently reran actual IM creation suite: 9/9 passed; queued disabled/binding/source cases assert no dispatch and no configuration operation; prior loss/restart recovery remains green | covered |
| Design clarification preserves contract | Unknown transport versus accepted pending split and effective-authority clarification match implementation; no new tool/Skill surface or weakened permission contract | aligned |
| R1-E1: final independent real-model/product evidence | Final fix-head stack is being rebuilt/reviewed; report not yet supplied | **pending; evidence gap, not asserted product defect** |

The new guard executes synchronously immediately before configuration-operation creation, so a lifecycle/source change during queue or omitted-Skills catalog waiting is observed. The fix does not rely on prompt changes and does not introduce another state engine. No new implementation/spec/design mismatch or architecture violation found in the targeted delta. Agent Context Mode B checks from code-review Round 2 are reused; unchanged serialized tool/Skill evidence from R1 remains applicable.

Independent command on frozen fix HEAD: `pnpm exec vitest run apps/im-server/tests/personal-agent-creation.test.ts --maxWorkers=1` → 1 file / 9 passed, 2026-11-03 17:05:57 +08:00, duration 606 ms. Caller reports 28 IM creation/config/catalog tests and IM build/typecheck passed.

### Current issue totals (supersede R1 totals)

- CRITICAL: **0** — R1-C1 closed.
- WARNING: **1 provisional evidence item** — R1-E1 remains until final product report is reconciled.
- SUGGESTION: **0**.

Current verdict: **static closure passed; overall verification remains provisional pending final product evidence**. No source/test/design edits or commits; no reviewer-started services.

## Round 3 — final evidence reconciliation

- verification_mode: `targeted-closure` of R1-E1, plus `corrected-delta` below for both delta files.
- review_round: 3
- validated_at: `e106b07bd1db3d20947682de7805ce1fe1d809ab`
- current PR base: `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`.
- product/code closure snapshot retained: `f8800afaa8a2b60b9a3577c4cc9ea85e681fd950`.
- requires_full_verification: false.
- independent reviewer: `/root/static_review_703`, 2026-11-03 17:24 +08:00.

I checked `git diff f8800afaa8a2b60b9a3577c4cc9ea85e681fd950..e106b07bd1db3d20947682de7805ce1fe1d809ab -- apps packages src tests scripts package.json pnpm-lock.yaml SPEC.md`: **empty**. The rebase brings unrelated feat-705 requirement text; feat-703 product code, tests, dependencies and architecture are unchanged. R1 full static review, R2 code closure and the independent f8800afaa product run therefore remain applicable. No broad test rerun is justified by this documentation-only delta.

### M1 exit criteria and acceptance evidence

The committed independent `acceptance.md` supplies version, real Astra/medium PA with Codex approval, two isolated nodes and public message/list/config evidence. It reports **9/9 scenarios pass, 0 blockers/major/minor**. This closes the missing behavior evidence without treating the controlled native fixture as real model proof.

| M1 / spec obligation | Final evidence | Reconciliation |
|---|---|---|
| Explicit creation and one acceptance of recommended configuration | `acceptance.md:11-13`, messages `2a3c7ffd3dce428d86ee98739e67c0d1` / `f0722103442242d18d72c017859c1556`; list 4 → 5 | covered; no duplicate approval or form refill |
| Long-lived discoverable Agent, actual use and configuration | `acceptance.md:13`: unique morning-reading-buddy, independent reply `13f869d1732f4bb0a5887916a60bd380`, configuration PATCH 200 and GET readback | covered |
| Discussion/observation and withdrawal do not create | `acceptance.md:9,27`; observed group name was subsequently correctly read; final list excludes withdrawn/observed names | covered |
| Default own computer, explicit other owned computer, offline does not silently switch | `acceptance.md:11,17`: real target choices and actual owner-visible offline result, then creation on second node | covered |
| Unconfirmed result reported truthfully; same-request continuation creates one entity | `acceptance.md:21`, messages `ab6af5fdb3c24849867e523b72e4be22` / `af84764dde524591b2048cbedeb4d55e`, list 6 → 7 with unique spelling-notebook; independent operation association/restart tests from R1/R2 | covered; public materialization does not claim a measured RPC count |
| Configuration/ID conflict leaves original intact | `acceptance.md:23`: conflict message `f59d87727a3743cfa350cedc422509b1`, list stays 7 and prior saved responsibilities unchanged | covered |
| Fixed schema, Skill on demand/selection, normal approval | Four native HTTP-request fixture + ordinary/PA catalog tests from R1; independent representative product behavior with real model/approval from `acceptance.md:5,9-13,27` | complementary mechanism and behavior evidence; no provider cache assertion |
| Current owner/source/child/node/lifecycle boundaries; exact operation recovery | R1 full static coverage, R2 synchronous guard closure and 9/9 independent test rerun, worker 28 creation/config/catalog regression group | covered at applicable deterministic seams |

### Validation and limits

Retained valid results: backend **210 files / 1121 tests**, Python **129 passed / 28 deselected**, ruff check/format, typecheck, IM build, `check:ios-runtime`, frontend critical audit and docs-check as recorded in `M1-create/progress.md`. The 9-test independent guard closure and 28-test worker group cover the only product-code correction after the broad backend run.

I also inspected the frontend repeat and targeted logs: unchanged single-file **13/13 passed**, then the same full command **111 files / 1056 passed**. The first full run's Set/ToAssistant failure remains recorded; no claim that its underlying cause was established or repaired. This is a disclosed test-run limitation, not evidence of a feat-703 regression after the unchanged code, focused pass and complete repeat.

Product acceptance is a bounded real journey, not proof across all models or every concurrent failure. It intentionally does not claim all-computers-offline, adversarial cross-tenant or long-term-restart model behavior; owner/node/restart invariants are separately checked by implementation and deterministic tests. No viewport requirement applies because this unit changes no client UI. No provider cache rate is claimed.

### Final issue reconciliation

- R1-C1: **closed** by the reviewed f8800afaa admission guard; unchanged at final HEAD.
- R1-E1: **closed** by committed independent real-model/product `acceptance.md`, reconciled above.
- CRITICAL: **0**. WARNING: **0**. SUGGESTION: **0**.

M1 implementation, applicable regression protection, independent code/context review and independent product acceptance are complete. Canonical delta merge/archive and PR/remote CI are subsequent delivery work owned by the caller; this result does not claim those actions already occurred.

**Final verification verdict: PASS.**

## Corrected Delta Reconciliation

verification_mode: `corrected-delta`; snapshot `e106b07bd1db3d20947682de7805ce1fe1d809ab`. Both corrected delta files were checked in full against final implementation, unit spec/design/M1, prior static/context review and final applicable tests/product evidence.

| Delta item | Implementation evidence | Test / acceptance evidence | Outcome |
|---|---|---|---|
| `specs/gateway/personal-agent.md:7` — 创建前对齐并交付 | bundled nano-agent-creation Skill lines 12-24; shared real options `personal-agent-creation.ts:40-56`, actual creation/links at 85-92 | `acceptance.md:11-17,33,36-38`; IM real options/owned second-node tests | aligned |
| `specs/gateway/personal-agent.md:12` — 讨论与执行边界 | Skill intent/withdrawal rules; native child filter and root ProductBridge/PA host gates; original owner source authority | `acceptance.md:9,27,34-35`; native ordinary/PA catalogs and host/source tests | aligned |
| `specs/gateway/personal-agent.md:16` — 固定工具与按需细节 | one fixed registration in `personal-security.ts`, fixedTools role list; existing selected Skill mechanism; ordinary create approval | four serialized native HTTP-request test (same tools/system, body only after load); real ordinary-versus-creation journeys | aligned |
| `specs/im/personal-agent.md:7-10` — 创建可在现有产品中使用及原主人来源 | shared ConfigOperations commit/profile; current owner/node checks and `ownerMessage` rejects observation/other sender/represented messages | IM source/owner/target tests; `acceptance.md:13,17,27` actual list/chat/config | aligned |
| `specs/im/personal-agent.md:11` — wait 后首次 operation 的 binding/lifecycle/source 仍有效；旧回执恢复 | `agent-creation.ts:125-134,187-189`; `personal-agent.ts:403-406`; status-not-started guard | three queued-revocation regressions; R2 independent 9/9; existing lost-ACK/service-recreation recovery | aligned |
| `specs/im/personal-agent.md:13` — 同次请求恢复与冲突 | binding/request unique association + host operation ID; frozen node/config conflict check; truthful not_started/pending/created/rejected; PA transport unknown uses same key | IM conflict/rejection/recovery tests + host unknown test; `acceptance.md:17,21,23,40-41` | aligned |

### Uncovered Observable Behavior

None. Checked the full unit product diff for omitted public behavior: Web creation/catalog extraction preserves existing semantics; the new fixed PA-only entry, on-demand guide, real options, independent target selection, source/lifecycle authority, same-request recovery, transport-unknown guidance, truthful product links and default ordinary Agent identity are covered by these deltas or the explicitly reused current Agent creation/management contracts. Adding the IM wait-boundary clause records the required authority invariant; it does not redefine behavior to conceal the original defect.

Outcome: **aligned**.

## Round 4 — 用户追加工具开关 · delta verification

- verification_mode: `delta` + 本轮新增 Scenario 的 `corrected-delta`。
- validated_at: `37b1a70775c40f4162d6a3184658e12f29ec1802`；pre_fix_head: `b2b9a8c0dbec963590c58b3847562bbf2e13502d`。
- executed_base: `492b72603cebc5f904f7001b12e3d4475ce55639`。
- reviewer: `/root/static_review_703`；2026-11-03 18:02 +08:00。
- requires_full_verification: false。本轮只核工具选择增量；原创建/恢复/来源/lifecycle与9/9产品旅程在未变部分保留，原 R1-C1 / R1-E1 闭环不重开。
- 范围：用户新增“PA配置页可关闭/重开创建工具”，设计审查 Round 2 Approved。feat-705为main文档增量，无共享产品代码变更。

| 新增契约 / 设计决定 | 实现与证据 | 结论 |
|---|---|---|
| 新PA默认选中，工具可单独关闭/重开 | `personal-agent.ts:462` 首次candidate持久白名单；`fixedTools:53-56`不再强制创建工具；IM首次PA测试 | implemented / aligned |
| 关闭后不可调用，旧历史call不可绕过 | runtime按当前白名单筛选；`PersonalAssistant.createAgent:117`产品转发前拒绝；native请求5/6缺schema、强制call error且dispatch不增 | covered |
| 重开恢复同一短定义 | native请求7/8与初始tools序列化值完全相同，dispatch恢复；不修改工具definition | covered |
| Skill/工具分别选择 | shared changeCapability回归保留Skill；Skill正文不授予执行权限；新增不可绕过提示 | aligned |
| 沿既有即时收缩、next-turn完整应用与busy占用保护 | `agent-config.ts:172-184`、configuration.apply既有实现；`capability-state.ts:45-70`现有移除目标/占用检查。本patch未新建开关状态或中断已接受操作 | aligned at existing seams |
| 配置页真实关闭/保存/重开 | 沿用既有Web/iOS能力选择器；独立产品reviewer尚未提供本次增量旅程报告 | **pending evidence** |

本轮 Mode B 由同一 code reviewer 完成并复用。核读 `.feat703-toggle-tests.log`：2026-11-03 17:59:28，4文件/67项通过（20.78秒）。8轮原生HTTP fixture证明最终序列化与强制旧call拒绝；不充当真实provider选择或配置页实操证据。新增 broader build/typecheck及相关回归由caller运行中，此处不提前登记成功。原门禁只在本次未变范围保留。

### 本轮 corrected-delta 对账

目标是归档 `specs/gateway/personal-agent.md` 新增“配置页独立关闭与重新开启”Scenario；原 Gateway/IM 已校正项目结论按未变实现保留，IM无本次新delta。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 配置页独立关闭/重开；新PA默认选择 | 首次PA白名单 + 移出fixedTools + 现有配置页选择/保存链 | IM默认测试、shared capability独立切换测试；真实页证据待补 | aligned（实现；产品证据待补） |
| 关闭后不可调用、Skill独立 | native选择与PA产品白名单双层检查；Skill保持独立选择并说明不得绕过 | 8轮serialized HTTP请求；当前空名单host拒绝且零转发 | aligned |
| 原生能力生效/占用保护；不撤销已接受操作 | 沿用原configuration preparation/busy与即时收缩；未改IM operation/receipt | 现有机制适用；未变创建恢复测试保留 | aligned |

Uncovered Observable Behavior: **None**。新建默认选中、主人配置变更影响工具集合、旧调用拒绝与重开恢复均由新增Scenario和复用的current能力契约覆盖；无启动迁移、不回填已有主人选择与既有配置持久化约束一致。没有用delta修改掩盖源问题。

Corrected-delta outcome: **aligned**（无 implementation-mismatch / delta-mismatch）。

### 当前问题与结论

- CRITICAL: **0**；确认的实现/设计偏离: **0**。
- WARNING: **1 provisional evidence item — R4-E1**：`design.md`“本次增量验证”要求真实配置页关闭/保存/重开。补入独立产品reviewer的版本、当前配置与真实交互证据，再关闭本项；这不是已确认产品缺陷。
- SUGGESTION: **0**。

**本轮静态 delta / corrected-delta 对齐；整体增量 verification 暂待配置页产品证据。** 原历史结论保留。只追加两份审查报告，无代码/测试/设计修改，无提交，无本reviewer启动的服务。

### 本轮追加验证证据

随后核读 caller 完成日志：`.feat703-toggle-regression.log` **4文件/34项通过**（原生capabilities/busy/收缩、IM创建9项、config/catalog）；`.feat703-toggle-full-build.log` 完整build成功；`.feat703-toggle-typecheck.log` typecheck成功。build在产品提交0a11feaa9前启动、候选release metadata仍含旧b2，但caller确认其时本次产品源码已完成且之后未变；独立核对0a11feaa9到冻结37b1a707的产品source/tests/dependency diff为空，37b仅main文档同步。此处将metadata差异作为证据限制保留，不宣称是提交后启动的build。R4-E1仍仅等待独立真实配置页/聊天增量验收，不重复轮询或运行既有有效门禁。

## Round 5 — R4-E1 产品证据收口（最终增量结论）

- verification_mode: `targeted-closure`，仅关闭 R4-E1；不重复代码审查或测试。
- validated_at: `37b1a70775c40f4162d6a3184658e12f29ec1802`；executed_base: `492b72603cebc5f904f7001b12e3d4475ce55639`。
- reviewer: `/root/static_review_703`，2026-11-03 18:06 +08:00。
- 冻结产品版本未变；本轮dirty仅验收/审查报告。requires_full_verification: false。

已核读独立 `acceptance.md` Round 2。真实Chromium桌面Web配置页在同一PA完成 **默认选中 → 关闭/保存/刷新保持关闭 → 原聊天明确要求时不创建 → 重开/保存/刷新 → 原聊天承接并成功创建**。主PA为真实Astra/medium与Codex审核；独立报告保留实际配置v3/v4、消息、列表事实及两张刷新后截图定位。

| R4-E1所缺证据 | 独立产品事实 | 结论 |
|---|---|---|
| 现有配置页能够真实关闭并持久保存 | 刷新后agent_creation无pressed，配置v3不含工具；Skill仍选中；off-after-reload.png | covered |
| 关闭时实际聊天不绕过 | 主人消息 `7f35328bdf1b4478ba2a1dda463481ad`；PA回复 `2cae3af89eb74148920872e6a65019fe` 说明工具不可用及配置页开启路径，保留职责；列表仍4 | covered |
| 重开后同聊天恢复使用 | 配置v4包含工具且刷新仍pressed；主人继续消息 `61b14654d183417b9c78952a107c716c`；成功回复 `c2826630de4743499e79f59ae940a7c7`；列表4→5，仅新增morning-translator；on-after-reload.png | covered |
| Skill与工具独立 | 工具关闭保存后Skill仍on；另在未提交草稿里取消Skill时工具仍pressed；持久Skill反向组合未作产品声明 | covered at stated scope；独立选择持久机制由R4共享能力/native测试补充 |

本轮对账同时核读 `.feat703-toggle-frontend.log`：现有能力编辑器/面板 **2文件26项通过**；`.feat703-toggle-python.log`：**129 passed / 28 deselected**。caller提供ruff check/format通过和本次docs-check **284 sources / 68 required routes**；最终canonical归并后另由caller复查，不提前声明已完成。R4已核读的67项、34项、完整build/typecheck及其旧installer metadata限制保持，不重跑或抹去限制。

R4静态patch/ModeB/schema选择证据与本次真实UI/模型消费证据互补；固定短定义在工具开启时仍稳定，用户主动关/开会改变集合，未据此承诺缓存命中。未变的创建/恢复/主人来源/lifecycle与原9/9场景仍按原版本适用证据保留。本次复用既有客户端选择器，未新增iOS控件，独立报告也未声称完成iOS复测；此范围限制保留。

**R4-E1 closed。最终delta verification PASS；corrected-delta outcome: aligned；CRITICAL 0 / WARNING 0 / SUGGESTION 0。** 原R1-C1、R1-E1保持closed，无新问题、无遗漏对外行为。后续canonical归并/提交/远端CI/交付由caller执行；本次只追加verification.md，无提交，无新服务。
