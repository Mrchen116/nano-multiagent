# Verification Report: feat-658

> Validation snapshot: `8e4054197908a1a433f748525c9650a831a950b6 → 3689a8b84ba09e69eae013bb79d93a1c4d1f2010`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现主链已映射；0/1 milestone 全部退出标准已收口，真实产品/原型对照/最终 CI 证据待 caller 补齐 |
| Correctness | 1 个已确认实现缺陷；1 个明确 design 投影遗漏；其余已审实现未发现具体偏离 |
| Coherence | IM/PA/integration 职责与 DSH 公开接入边界遵守；来源保留和模型投影存在下述偏离 |

Round: 1. `verification_mode=full`. `requires_full_verification=false`（本轮已覆盖完整实现；后续修正可做 targeted/delta，未完成证据按相关退出标准补验）。Verdict: **not passed; implementation changes and pending evidence required**. CRITICAL=0, WARNING=2, SUGGESTION=0。尚在进行的 acceptance 不被假记为产品失败或 pass；当前不能建议交付 PR。

## Completeness

- M1 为唯一 milestone，未设置独立 tasks.md。实施范围已按 design 及实际 84 文件 diff 核对，不能把文件数量当完成度。
- W1：原子消息/来源/事件/relay、身份冻结、本人证据排代发、成员权限、卡片 executor、根 PA 限制、参数规范化、Compose 解析与两端 host 路径均有实现及相关长期测试。历史查询送入 Codex 审核时的保留逻辑有 WARNING 1。
- W2：Web/iOS 源码与回归保护已核；调用者报告已有构建/窄验，但本报告收到的 progress 未含足够完整的构建命令/版本/输出定位，最终 CI、V1–V4 真实截图与对照结论待补。
- W3：迁移 CLI 与保留旧数据/重复执行/verify 拒绝改写的测试存在；副本演练、旧操作 self 解码及混合版本停发/恢复的最终证据待补。部署提示词已经规定版本协调；本轮没有生产部署授权，也未操作生产。
- R1/R2/R3：真实模型及双方 Web/iOS 验收正在 caller 进行。首次 journey A 明确失败于正式 mention 缺失（最后一个受审 commit 添加 schema 指导）；尚不能证明修正后的自然语言端到端执行、三次独立表述、联系 PA、恢复/子 Agent、撤回与越界场景通过。

### Evidence reviewed and limits

1. `M1-user-representation/progress.md`（冻结 head）：414 项首轮 411 通过、3 个 fixture 修正后窄验以及首次模型失败的记录；caller 交接补充 narrow 53 tests 通过、完整本地 CI 仍在后台。复用其风险覆盖说明，没有把未收到定位的最终 CI 记为通过。
2. `/Users/czj/.codex/reports/feat658-runtime-context/README.md` 及对应 ordinary/PA/SingleThread/child、restored-evidence、nano/codex/personal-review 请求样本：实际 DSH 注册、输入与审核组装，但 provider 为 synthetic model；不能证明真实模型的工具选择或真实受众交付。该样本的 sender.type 不代替 IM Work 的实际 sender.kind wire。
3. 本 reviewer 独立执行导出 `reviewInput` 的受控复现，见 `code-review.md`：实际历史消息形态确实会被遗漏。未改源码/测试，未启动真实服务。
4. 原型 `design-evidence.md` 为设计期证据。其页面截图不能替代本次真实 Web/iOS 对照。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 / 直接证据 | 状态 |
|---|---|---|---|
| 用户主身份、双方归属与后续查看（S1/S2/S5） | `apps/im-server/src/personal-actions.ts:205`；`messaging.ts:331`；Web `message-pane.tsx:1857`；iOS `ChatMessageView.swift:32` | personal-representation、stream-reducer、message-pane、ChatState；真实双端 V1/V2 待补 | 实现 covered；产品证据 pending |
| 自然用户口吻、可解指代及实质歧义（S1/S3） | `packages/dsh-integration/src/personal-security.ts:135`；`global-mode.ts:72` | 真实系统段/schema 可查；首次模型发送已记录失败，修后及歧义真实旅程待补 | pending real-model evidence |
| 一次委托进入正常执行（S1） | `personal-actions.ts:90`、`:159`、`:184`；`policy/sources.ts:8` | 冻结身份、完整审核 payload 测试；真实 Q commit/ref 与不重复索权待补 | 实现 covered；结果 pending |
| 历史查询/恢复/子 Agent 保留原范围（S5） | `work.ts:725`；`inbox.ts:258`；`single-thread.ts:144`；`policy/sources.ts:187`；`policy/codex-context.ts:42` | source/Inbox/runtime-child tests；独立 retention 复现 | **WARNING 1：历史 read/search 保留失效** |
| PA 自身发言和草稿仍归 Agent（S4） | `personal-assistant.ts:113`；`personal-actions.ts:205`；双端消息视图 | representation/self 分支、legacy 标签测试 | covered；真实对照待补 |
| 普通 Agent/子 Agent 不获代表工具，PA self 不借主人写权限（S4/S6） | `agent-config.ts:134`；`product-bridge.ts:21`；`global-agent.ts:381`；`personal-actions.ts:53` | personal-child-delivery 伪造调用拒绝、personal-security、personal-representation | covered |
| 原始主人证据、guard、source control、回声排除代发（S4/S5） | `personal-agent.ts:127`、`:181`、`:251`；`schema.sql:465`；`messaging.ts:665`；`attention.ts:14` | representation identity/event/guard/idempotency、Inbox/control tests | covered |
| owner 卡片实际 executor、参与/可用性、替换与 contexts | `interactions.ts:13`、`:25`、`:66`、`:79`、`:133`；`personal-actions.ts:60` | personal-representation 卡片参与/离群/重审/替换/contexts | covered；真模型提交/替换待补 |
| Compose 最新值、目标权限、冲突取消/替换、仅填稿、ToAssistant 区别（S6） | `interactive-source.ts:55`；Web `interactive-card.tsx:67`、`chat-workspace-page.tsx:1134`；iOS `InteractiveRuntime.swift:146`、`ChatStore.swift:65` | parser、Web card/workspace integration、iOS runtime/host tests | covered；双端真实旅程待补 |
| 共享 schema、常量由 host 补齐、退役 reply_draft（S6） | `message-arguments.ts:4`、`:17`；`policy/approval.ts:104`；`gateway.ts:588`；`work.ts:747` | actual runtime schema/skill、personal-security 参数与拒绝测试 | 输入 covered；**WARNING 2：历史模型投影仍带常量** |
| 旧消息/操作不升级、可重复迁移（S5） | `migrate-pa-representation.ts:16`、`:22`；`db.ts:18`；`personal-actions.ts:122`；`messaging.ts:332` | pa-representation-migration；旧 self 解码实现核对 | covered；副本/版本协调演练待补 |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1：直接用户作者，实际 PA 为可选来源，内部审核不公开 | 是 | `personal-actions.ts:205`；`messaging.ts:331`、`:437`；`schema.sql:479` |
| D2：self/owner 明确工具选择、根 PA 限制与实际成员权限 | 是 | `global-mode.ts:29`、`:72`；`agent-config.ts:134`；`product-bridge.ts:21`；`personal-actions.ts:53` |
| D2a：通用本地 Compose，公开 OpenUI 扩展，协议由 host 补齐 | 大部分；模型读投影遗漏 | Web `catalog.tsx:37`；`interactive-source.ts:55`；iOS `interactive-runtime.ts:31`；`message-arguments.ts:17`；`work.ts:747` |
| D3：原独立审核、真实原话与完整冻结动作 | 是 | `personal-security.ts:72`、`:81`；`personal-assistant.ts:145`；`personal-actions.ts:159`、`:184` |
| D4：已有历史委托不新增授权/触发，不降级原范围 | 部分偏离 | 来源/guard 排除已实现；`policy/codex-context.ts:42` 与真实 `work.ts:730` 不匹配 |
| D5：单 M1 完整链路 | 未收口 | R1–R3/W2–W3 的指定证据仍待补 |
| 跨包架构边界 | 是（源码检查） | 新逻辑分别留在 IM、PA、integration 与 product-contracts；无 DSH private import 或 runtime patch；最终 runtime dependency contract 输出待补 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| V1：用户主头像姓名、相邻代发、双方/群私聊归属 | R1/W2 | Web message-pane；iOS ChatMessageView；事件/消息模型 | 目前仅源码/测试与设计期原型，实施期双端同消息对照待补 | pending |
| V2：320/390/1280、长名、多段/附件/卡片 | R1/W2 | Web wrap/min-width/no-wrap badge；iOS fixedSize/Markdown/attachment | 实施期对应视口与原生截图/观察待补 | pending |
| V3：self/legacy/manual/draft 不混淆 | R2/W2 | messaging legacy/source 投影、双方条件渲染、删除旧专用采用入口 | 低层/组件测试存在；真实产品对照待补 | pending |
| V4：最新值、明确目标、冲突/拒绝、仅填稿及 ToAssistant | R2/W2 | Web host 和 iOS host 实际权限/冲突分支 | 自动化保护存在；真实双端编辑/采用/拒绝证据待补 | pending |

## Issues

### CRITICAL（提 PR 前必须修）

None confirmed in the reviewed implementation. This does not close incomplete milestone evidence.

### WARNING（提 PR 前必须修）

1. **历史查询的真实 sender 形态未进入审核历史保留。** 契约：`specs/gateway/personal-agent.md` 的“历史、恢复与子 Agent”；design D4 及 `design.md:192-204`。实现：`packages/dsh-integration/src/policy/codex-context.ts:42` 仅检查 type；生产者 `apps/im-server/src/work.ts:730` 为 kind。直接复现证明 original scope 在 41 个后续普通 evidence 条目后遗漏，尽管 budget=50000。建议：在 owning projection/retention seam 对齐真实字段，增加真实 read/search shape 的 retention 回归；复用现有 fixture，保留外部来源的现有语义。状态 CONFIRMED；代码 finding 另见 code-review。
2. **conversations 模型投影仍暴露固定 wire 常量。** 契约：`design.md:102` 明确“conversations/Inbox 的模型投影不重复灌入协议常量”，`:179` 再次要求不暴露无用协议常量。实际：`apps/im-server/src/work.ts:747` 原样输出 `m.interactive`，而 `Interactions.message()` 在 `interactions.ts:40` 必定包含 format/catalog_version。因此 read/search 任一已有卡片仍把常量带回模型；新的输入 schema 正确拒绝模型填写它们，但读投影没有完成设计中的规范化。建议：仅在模型专用投影省略这两个固定字段，保留 source、更新/只读语义与 wire/client 公开协议；补一个该 seam 的窄断言。状态 CONFIRMED implementation/design mismatch；不是声称存在权限提升。

### SUGGESTION（可以修）

None.

## Pending closure evidence

- caller 完成真实旅程后提供版本、命令、结果、消息/commit/ref/trace 定位，尤其三次自然委托、正式 mention 唤醒、一次授权后的实际执行、ID 联系 PA、恢复与子 Agent 原范围、撤回/超范围拒绝。
- 提供 V1–V4 Web 实际视口/双方/群私聊和原生 iOS 的可复查对照，不以 HTML iOS 构图代替原生结果。
- 提供最终 local CI、Web/iOS build/regression、runtime dependency contract/docs-check 与副本迁移/版本协调证据。无需为已有效覆盖且无新变化的范围重复全量重跑。
- 修正上述两项后进行指定 delta/targeted closure；最终校正 delta-spec 时再按 corrected-delta 对账，不把此初轮报告误用为最终 pass。

Report ownership: shared caller checkout; only this report and code-review.md written by reviewer. Caller owns report commit/reachability and all source fixes. No reviewer-created service/worktree needs cleanup.

## Round 2 — targeted closure and corrected delta

- `verification_mode=targeted-closure + corrected-delta`.
- `validated_at=16798fb3be2e46500ba25c01996f3c615ac29288`.
- `effective_base=b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`; `effective_through=16798fb3be2e46500ba25c01996f3c615ac29288`.
- Repair range reviewed from R1 head through validated_at; source repairs are `abdf2afc7`, related legacy tests `9c5aecd55`. Verified effective_base differs from the original base only in three feat-659 design files. No product-code drift invalidates R1 coverage.
- Four unit delta-spec files are unchanged since R1; this is **no textual spec delta**, with a requested reconciliation of every requirement/scenario against the repaired implementation and applicable tests. This is not a second full implementation or product review.

### Targeted closure summary

| R1 issue | Contract / repaired implementation | Direct evidence | Outcome |
|---|---|---|---|
| WARNING 1 history shape | Gateway PA history/restore/child; `policy/codex-context.ts:42` recognizes actual sender.kind as well as Inbox sender.type | actual-shape retention regression `approval-sources.test.ts:202`, independently passed | closed |
| WARNING 2 model wire constants | `design.md:102`; `work.ts:747` strips exactly format/catalog_version on model history only | `personal-sources.test.ts:142` confirms retained source and complete client wire, independently passed | closed |

Current static closure issues: **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. `requires_full_verification=false`. Static verdict: **pass for the dispatched repair and corrected-delta scope**. Overall M1/PR readiness remains pending independent product/native acceptance; R1 historical status above remains intact as a prior snapshot.

### Evidence additions and boundaries

- Independent narrow command is recorded in code-review R2: 4 files / 30 tests pass on the validated head, covering both repairs and the new legacy/migration tests. No full-suite rerun was needed for this delta.
- Read saved logs under `/Users/czj/.codex/reports/feat658-acceptance/`: backend 134 files / 717 tests; Web 107 files / 1025 tests; Python 70 pass / 32 deselected; Ruff check and 88-file format check pass; typecheck completes; generated iOS runtime check passes. Saved native logs end in BUILD SUCCEEDED, TEST SUCCEEDED and ARCHIVE SUCCEEDED. These are reused build/regression evidence, not native UI acceptance.
- `migration/results.json` identifies revision `9c5aecd55` and shows real CLI dry-run/apply/verify/reapply/verify all exit 0, pre-migration startup refusal and post-migration acceptance. It is a file database seeded from the base schema with **synthetic legacy rows**, not a production database copy. Six business-table counts and legacy NULL provenance remain preserved. No mixed-version production exercise was performed; deployment coordination remains an explicit deployment procedure.
- `journey-final-git.json` has B=`18bed6d...`, C=`c47c03e...`, D=`d6082fff...` as three distinct additions and local origin main at D, clean working tree, B/C unchanged and review-a absent. Reused caller records distinguish the failed A from successful B/C/D, with zero duplicate approval in those successful scenarios. These artifacts support actual isolated Git side effects and unchanged completed work; independent product reviewer owns final natural-journey verdict.
- Inspected real-context requests q-before-commit, q-after-restart, q-codex-review, q-execution-child and q-child-review. The child **execution prompt is a parent summary**, while child **independent-review evidence** includes original message `c2a5165e69b843ac972241c87dffe1ba`, owner `u_c3ibn6j3`, PA `pa_8b3969af44b2` and the explicit D-only/no-merge/no-deploy/no-release/B-C-not-redo/A-paused restrictions. Do not claim all original chat text was injected into the child execution prompt. The synthetic-provider ordinary/PA/SingleThread/CC matrix retains its original limitation.
- C/D successful messages contain an explicit PA ID in public text as well as metadata. Actual contact receipt matches the PA; this does not isolate a metadata-only addressing experiment.
- Product reviewer is still working. Source-level identity and Compose tests plus the saved Web observations do not close iOS native visual/interaction acceptance. Mac lock-screen blockage and pending user unlock are environmental, not inferred code defects. Baseline private-chat title behavior is not a feat-658 regression and is not added to this scope.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `gateway/personal-agent.md` — tool boundary / owner-only participation | `global-mode.ts:29,72`, `agent-config.ts:134`, `product-bridge.ts:21`, `global-agent.ts:381`, `personal-actions.ts:53` | personal-child-delivery; personal-security; personal-representation selected-author scenario | aligned |
| `gateway/personal-agent.md` — natural representation vs own speech / real scope | `personal-security.ts:72,81,135`, `personal-assistant.ts:113,145`, `personal-actions.ts:205` | personal-security frozen action; representation tests; real B/C/D records support delivery and execution; final product wording/ambiguity judgment pending | aligned (implementation/spec; product gate separate) |
| `gateway/personal-agent.md` — clear references and material ambiguity | `personal-security.ts:135` fixed guidance | actual assembled PA context retained; natural B/C/D relevant-context results; product reviewer owns explicit ambiguous-object scenario | aligned (declared behavior implemented; final product evidence pending) |
| `gateway/personal-agent.md` — normal execution and original limits | `policy/sources.ts:8,10`, `personal-security.ts:81`, `personal-actions.ts:159,184` | sources provenance tests; actual Q/Codex and child review preserve original limits; isolated B/C/D Git artifacts | aligned |
| `gateway/personal-agent.md` — history/restore/child/contact PA | `work.ts:725,730`, `inbox.ts:258`, `single-thread.ts:144`, repaired `policy/codex-context.ts:42` | actual-kind + 41-entry retention passed; child delivery; q-after-restart/q-child-review; matching PA contact receipt, metadata-only isolation not claimed | aligned |
| `gateway/personal-agent.md` — no self-authorization/history upgrade | `personal-agent.ts:127,181,251`, `schema.sql:465`, `messaging.ts:665`, `attention.ts:14` | personal-representation author/guard/idempotence and missing-representation self tests; migration legacy preservation | aligned |
| `gateway/agent-capabilities.md` — generic draft, ToAssistant, host constants | `message-arguments.ts:4,17`, Web catalog/interactive-card, iOS custom action/host, repaired `work.ts:747` | parameter normalization; real-shape model source vs client wire test; parser rejects sending mixtures; Web workspace/card and iOS runtime regressions | aligned |
| `gateway/agent-capabilities.md` — wake/restore/child/reviewer registration and receipts | `global-mode.ts:15`, `policy/sources.ts:187`, `global-agent.ts:212`, `capabilities.ts:71`, root-local registration | synthetic actual-runtime matrix (limited), real Q restore/Codex/child materials, personal-child-delivery and approval-sources | aligned |
| `im/personal-agent.md` — existing draft adoption / PA representation | `personal-actions.ts:205`, `messaging.ts:331`, Web compose host, iOS compose host | representation atomic projection; Web adoption no-send/conflict/permission and native host regression | aligned |
| `im/personal-agent.md` — both sides/later identity/self/legacy records | `messaging.ts:331`, Web `message-pane.tsx:1857`, iOS `ChatMessageView.swift:32`, realtime model propagation | reducer/message-pane/ChatState; legacy migration test; independent product V1–V3 verdict and native interaction still pending | aligned (static contract; native gate open) |
| `im/conversations-messages.md` — shared persistence/authorization, offline read and fork history | `messaging.ts:437`, `interactions.ts:13,25,66,79,133,154`, `conversation-actions.ts:332` | existing interactive persistence/fork suite retained; representation executor/participation/replace/context regression; complete backend suite reused | aligned |
| `im/conversations-messages.md` — edited local adoption, current clicker target rights | Web `interactive-card.tsx:67`, `chat-workspace-page.tsx:1134`; iOS `InteractiveRuntime.swift:146`, `ChatStore.swift:65` | Web card/workspace current expression/no-send; iOS host edited-value/no-send; independent Web observations; native product gate open | aligned |
| `im/conversations-messages.md` — invalid target and unsent conflict | same Web/iOS host permission/conflict branches | Web both-target integration and native conflict/cancel/replace/denied regression | aligned |
| `im/conversations-messages.md` — ToAssistant distinction and replaced/fork disable | `interactive-source.ts:55`, Web readOnly/source freshness, iOS current source checks, `interactions.ts:25` | parser mixture rejection; interactive-card stale source check; native host check; existing readonly/fork protection | aligned |

### Uncovered Observable Behavior

None requiring an additional canonical behavioral requirement was found in the unit diff. Private audit linkage, atomic source ordering, selected-author permission checks, root-only tool enforcement, relay/control/guard self-exclusion, protocol normalization and migration/history preservation implement the existing representation/interaction boundaries; operational transition and old draft-entry retirement are documented in deployment-prompt. The shared formal-mention schema guidance explains the existing attention protocol without changing group reply policy. Both review repairs implement the already-approved scope and add no independent external behavior.

Outcome: **aligned**. The four delta-spec files are suitable for canonical reconciliation after the independent product/native gates pass. This is not an overall milestone pass or authorization to merge/deploy/release. No new report commit was made in this shared checkout; caller owns commit/reachability. Only the two assigned reports were appended.

## Round 3 — targeted attachment guidance delta

- `verification_mode=delta`; `fix_delta_range=cfba1fcd3^..cfba1fcd3` (the specified two-file patch only).
- `validated_at=cfba1fcd345c3fb5cfd48ed7384846d0a243d967`; `effective_base=b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`; `effective_through=cfba1fcd345c3fb5cfd48ed7384846d0a243d967`.
- No textual change in the four delta-spec files. R2 corrected-delta reconciliation is retained through this patch with the following targeted impact check. `requires_full_verification=false`.

| Affected contract / delta area | Actual implementation and evidence | Result |
|---|---|---|
| Gateway PA natural delegation/full disclosure | `personal-security.ts:135` adds the already-supported native Markdown resource expression, says local paths are not uploads and requires reporting unreviewable contents. Unchanged `personal-actions.ts:28-41` resolves allowed sources, reads full bytes/hash and rejects unreviewable external disclosure; `personal-security.ts:55` places snapshots in the frozen review action. This supplies capability knowledge without granting authorization. | aligned |
| Gateway capabilities accurate context/schema | Only fixed PA context changes; shared send schema remains target/text/interactive with host constants, no upload or attachments parameter is invented. Caller reports personal-security 8 tests and integration build passed. | aligned |
| IM PA represented identity and attachment content | Unchanged `personal-actions.ts:204-207` rewrites reviewed native links, retains owner sender and PA provenance. Extended `personal-disclosure.test.ts:136` asserts reviewed full text, owner/PA identity, target URL and copied hash/storage. Independently ran this file: **17/17 pass**. | aligned |
| IM conversations/interaction/Compose | No code, protocol or local-adoption behavior changes. Existing `Messaging.copyReferences()` creates destination-authorized resource metadata pointing to the same stored blob; the original private URL is replaced in delivered text. This does not expose private source access or alter Compose/ToAssistant. | aligned; R2 retained |

Current static delta issues: **0 CRITICAL / 0 WARNING / 0 SUGGESTION**. Outcome: **aligned**, with no additional uncovered observable behavior requiring a new delta-spec requirement. The guidance clarifies the implementation of the already-approved native attachment preservation and disclosure behavior; it does not add a new upload feature.

Product evidence remains separate: `acceptance.md` R1/c966b3386 preserves both natural attachment failures, including the genuine upload followed by a refusal to forward. Its G2 cannot be closed by the added server test, the fixed guidance alone, or a caller success narrative. Independent targeted product R2 must observe natural forwarding and B's ability to download the destination resource. Native UI acceptance remains pending the environment unlock. Accordingly the static delta passes, while overall M1/product readiness is still undecided at this snapshot. No new full review or service operation was performed; caller owns committing the appended reports.
