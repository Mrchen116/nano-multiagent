# Verification Report: feat-617-agent-interactive-responses

> Validation snapshot: `cc47abe3f → 0373d8feca33a449c0ea7e7f5a01fa88909e3e87`

## Current verdict — full OpenUI restoration

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION；corrected delta aligned。**

最终有效代码 `60b311a48ac5e999a3594d81316acf3c69eac433`（产品代码等同定向 closure 候选 `19efc4031`），产品报告提交 `cff39b7164c29b6f764603f0a6f36ea51af3594d`。full 审查候选 `07ca4831c`、旧交付基线 `cf4b17f00`、unit/main 基线 `cc47abe3f` 均保留。W2、产品N1与C2均 closed；当前结论来自新版 full 静态、两项代码 closure、独立新产品旅程和相关专项证据，不依赖旧表单 PASS 外推。详见 Round 5/6/7。

## Previous delivery verdict — superseded by restored full OpenUI scope

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION；corrected delta aligned。**

- 最终实现候选：`a211d7643e64b820908397844cbd3125372c83e0`；unit executed_base：`cc47abe3f`。
- 产品 Round 2 报告提交：`2183e38708a4dcef24ba2ef559b2446bb9b7f2f5`，仅增加 acceptance/截图；未改变已审实现，不因报告 SHA 变化重跑已覆盖范围。
- 最新 closure：Round 4。Round 1/2/3 的失败与 pending 保留为历史，当前结论以此 verdict 和 Round 4 为准。
- `code-review.json` 为 `[]`；原 W1、产品 A1/A2 与证据 C1 全部 closed。实现核对与验收门禁已通过，可继续 canonical 归并、归档与 PR；不代表已创建 PR、CI 完成、合并、发布或部署。

## Round 1 metadata

- unit_id: `feat-617-agent-interactive-responses`
- review_round: `1`
- verification_mode: `full`，同时覆盖三份最终 delta 的 corrected-delta reconciliation。
- candidate / validated_at: `0373d8feca33a449c0ea7e7f5a01fa88909e3e87`
- executed_base: `cc47abe3f`
- checked_at: `2026-10-19T16:28:48+08:00`
- branch / worktree: `unit/feat-617` / `.worktrees/unit-feat-617`
- reviewer: 独立 reviewer；未参与受审实现。本轮只写 `code-review.json`、`verification.md`，不提交共享现场、不改源码/测试/配置、不启停服务、不触碰 feat-616。
- 固定审查范围为完整 `cc47abe3f..0373d8fec`。审查期间 caller 的 CSS/状态文案改动不纳入此快照；后续应按小 delta 复核。
- requires_full_verification: `false`（当前已是 full；修复与新增产品证据可按关联范围 closure）。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | W1 有起点证据；W2 自动化/构建主体有证据，真实 must-match 对照与 R1–R3 完整验收尚未交付 |
| Correctness | 消息、权限、状态、上下文与 Feature 主路径 covered；POST 确定冲突的前端恢复有 1 项偏离 |
| Coherence | 遵守 OpenUI 固定版、单一 catalog、现有公开交付链和包边界；1 项失败恢复未落实设计 |
| Verdict | **Issues Found — 1 CRITICAL / 1 WARNING / 0 SUGGESTION** |

当前不能宣称完整 unit 通过。CRITICAL 是退出证据未齐，不是据此推断产品功能失败；WARNING 是可直接从实际客户端与服务端路径确认的实现缺陷。

## Completeness

- M1 仅一个 milestone，主体实现已落地；截至本快照尚未满足全部退出标准，因此为 **0/1 milestone 完整退出**。
- W1：`evidence/openui-model-samples.json` 保存同一实际 provider 的行程、草稿、提醒和纯文字样本及输出量/耗时；`M1-interactive-replies/progress.md` 说明第一次 402、placeholder 问题与修订后结果。起点样本不证明真实消息全链路或所有普通/Global 产品旅程。
- W2：复用 caller 的固定候选交接与 progress 中窄测/全量/构建/架构证据，不重复运行已经有效覆盖的全量。真实浏览器与 prototype must-match 的持久对照尚缺，见 C1。
- Feature 最新要求：默认启用、关闭保存、提示移除、PA 拒绝新卡片和重新启用均有实现/窄测试；progress 另记配置页真实保存刷新操作。关闭不影响旧消息读取、草稿与提交接口。
- 受影响既有覆盖：原有 `communication-native.test.ts`、`capabilities.test.ts`、配置页测试、configuration 测试、worktree lifecycle 测试已扩展；保留普通消息、群策略与工具空名单语义。新增 tests 按 catalog/消息状态/PA 输入/Web flow 不同 seam 分工，没有发现需另建大范围重复测试的依据。

### Reused evidence and limits

| Evidence | Result / 能证明的边界 |
|---|---|
| M1 progress + caller 固定候选交接：功能 5 suites / 31 tests | Parser/Renderer、草稿、提交身份、PA 上下文及基本 Web flow；不覆盖 POST 409 的恢复 UI |
| DSH communication-native 2 tests | 真实锁定 DSH 子进程，默认提示、关闭提示、重新启用，以及公开通信入口 |
| Web 99 suites / 893 tests；新增后配置页 23 tests | 现有 Web 回归与 Features 保存；模拟 DOM 不等于真实 viewport 验收 |
| backend 95 suites / 366 tests + workspace-tools 单 worker 1 test | 主体 backend 通过；并发下安装超时的同 suite 已单独通过，不将并发超时抹成初跑全绿 |
| `pnpm build`、`pnpm typecheck`、Web production build、architecture 13 | 复用 caller 已完成结果；静态类型、构建与包依赖契约 |
| `evidence/e2e-config-validation.md` | 默认 E2E 模板旧工具名单回写问题、两种模式、配置重载 9 tests 与真栈生命周期 1 test，范围/授权清楚 |
| 本轮 `git diff --check cc47abe3f..0373d8fec` | 通过；未重新运行全量、未写入/重建 runtime |
| `evidence/prototype-review.md` 与原型截图 | 设计基线；**不能**充当最终实现的真实产品对照 |

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| Features 默认启用并可关闭/恢复 | `apps/node/src/capabilities.ts:15`；`agent-detail-page.tsx:83,1759`；`agent-config.ts:95,148`；`global-agent.ts:242` | capabilities、agent-detail-page、communication-native、PA interactive-replies；progress 中浏览器保存刷新 | covered |
| 多领域任务、简单文字与自然语言继续 | `interactive/catalog.tsx:29,50`；生成 skill；`features/intelligent-ui.ts:6` | 四类真实模型样本；catalog Renderer 测试；完整产品跨模式范围待 R1 | implemented / acceptance pending |
| 私有字段调整不触发模型/外发 | `interactive-card.tsx:71,108`；`interactions.ts:50` | catalog、interactive-card、interactive-messages 草稿隔离/CAS | covered |
| 按钮/手写原文与选择进入任务 | `message-pane.tsx:647,656,1789`；`interactions.ts:79,84`；`product-contracts/src/interactive.ts:32`；PA `single-thread.ts:117`、`inbox.ts:115` | interactive-flow 保留空白与正文；IM 持久快照；PA 双路径“先别发送” | covered |
| 执行对象/实际结果、重复点击不重复输入 | `catalog.tsx:7`；`interactions.ts:81–95`；`messaging.ts:530` | IM 相同语义返回原结果、不同正文/action 409、不同 viewer key 隔离；按钮只产生用户输入 | covered，冲突恢复见 W1 |
| 正文/交互共同持久化、离线可读、身份与读写权限 | `messaging.ts:307,398,521`；`interactions.ts:14,26,46`；`schema.sql:438` | IM 原子失败回滚、权限、离线持久 relay；draft 不进广播 | covered |
| 替代及重复提交 | `interactions.ts:36,86,90`；`message-pane.tsx:267` | IM 替代后旧成功重试仍返回原结果，其他人新提交拒绝；前端明确 409 处理缺失 | **W1** |
| fork 与删除原会话后可读、不复制草稿 | `conversation-actions.ts:331`；`interactions.ts:103`；schema FK | 窄测检查复制 source/read_only/不复制草稿；引用 remap 与内容独立保存经代码核对；真产品 fork/删除旅程仍待 R3 | implemented / acceptance pending |
| 生成与失败仍可读文本 | `interactive-card.tsx:28,97,120`；`message-pane.tsx:1780`；PA `single-thread.ts:221,399` | RenderBoundary/摘要保持；NO_REPLY 最终/流式投影回归；真实失败操作证据待 R3 | covered at seams / acceptance pending |
| 桌面、窄桌面、手机导航输入及布局 | `interactive-card.css`；既有 MessagePane 内嵌，不新增 chat shell | 原型是基线；实现三宽度 must-match 证据未齐 | **C1** |
| 群成员草稿隔离及唤醒原作者 | `interactions.ts:46,61,91`；`messaging.ts:575` | IM 双 viewer 隔离；mentioned_agent_ids 加原作者；未改其他 Agent 群策略 | covered at seams / real group pending |
| 外部/原生客户端文字摘要 | PA `global-agent.ts:291`；message.content 仍独立 | PA web/feishu 参数化回退；原生 DTO 忽略附加字段，摘要保留；真实原生/外部验收未声称完成 | covered at seam |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 固定 OpenUI 版本，不引入其 chat shell/托管服务/第二引擎 | 是 | 两个 package manifest、lockfiles；`catalog.tsx` / `interactive-card.tsx` |
| 单一 catalog 源、生成同版 server spec/提示/类型、CI 检查 | 是 | `scripts/generate-interactive-ui.ts:7`；Web `pretest`；IM `interactive-source.ts:1` |
| 每条消息一个不可变 UI、正文独立，Global prose 不公开 | 是 | message_interactive 主键；PA 原公开链；仅显式 `send_message` 增 interactive |
| ContinueButton 静态 id/可见 label，只继续对话 | 是 | `catalog.tsx:7`；`interactive-source.ts:43`；`interactions.ts:77` |
| 草稿私人 CAS，确认消息/快照/relay 原子持久化 | 是 | `interactions.ts:50,95`；`messaging.ts:530` |
| 完整 publication 身份、完整 source 披露审核 | 是 | PA `global-agent.ts:241`；IM `gateway.ts:519`；`policy/sources.ts:9` |
| 确定冲突和未知结果分别处理，保留新内容并说明恢复 | **否** | `interactive-card.tsx:89–95,104,126`，见 W1 |
| DSH 仅 integration 公开 exports；IM/PA/Channels 按既有方向 | 是 | 实际 diff 未增加跨边界 import；生成产物为 product-contracts 纯数据，IM parser 不 import React/DSH |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 同一回复：摘要在前，选择/主动作相邻 | R1/W2；1440/768/390 | `message-pane.tsx:1780–1788`、Renderer | 原型有；实现仅 progress 部分旅程描述，无完整三宽度对照 | C1 pending |
| 本地即时变化、本人选择消息、已提交只读 | R2/W2 | `interactive-card.tsx:108`、`message-pane.tsx:1789` | 窄测与部分真栈描述；未具备完整 must-match 真浏览器对照 | C1 pending；W1 冲突分支偏离 |
| 异常摘要可读、旧卡片不继续执行、输入仍可用 | R3/W2；390 | fallback、read_only、普通 composer | 后端/DOM 保护存在；真手机异常状态与 fork/替代对照未齐 | C1 pending |

## Issues

### CRITICAL（提 PR 前必须补齐）

**C1 — 完整 M1 退出与 must-match 真实产品证据尚未具备。**

- 契约：`design.md` 的“原型对齐契约”和“Milestones”中 R1/R2/R3/W2；`M1-interactive-replies/progress.md` 末尾明确“完整独立静态审查、产品验收与最终归档/CI 尚待完成”。
- 现有证据证明库起点、普通草稿附带“先别发送”、Global 行程和 Features 配置部分路径；未证明同一真实模型在普通/Global 两模式的全部三类任务、三 viewport must-match，以及真实群隔离/跨设备/失败/替代/fork 等完整退出条件。当前也未给出本候选 docs-check 结果。
- 建议：由既定产品 reviewer/caller 完成缺项并保存带候选、入口、viewport、操作/结果定位的真实对照与 acceptance；提供 docs-check 结果。verifier 只核 explicit contract 与证据链，不代替产品 reviewer 的体验判断。不要为已有效覆盖的测试重复跑全量。
- 状态：pending evidence，**不是**已证实功能失败。本报告完成后可随新增证据按关联范围 closure。

### WARNING（提 PR 前必须修）

**W1 — POST 确定冲突被当作未知结果无限重试。**

- 契约：`design.md:102`；消息 delta 的“已提交或被替代的卡片”和“带选择的手写要求与不同意图重试”。
- 实际证据：`interactions.ts:87` 返回明确 `interaction_already_submitted` 和原 `submission_message_id`，`:17` 返回 `interaction_read_only`；但 `interactive-card.tsx:94` 所有失败一律 `setError('send')`，`pending.current` 不清理，`:104` 因 pending 锁控件，`:126` 只允许原请求重试。候选中文 `chat.interactive.sendError` 表示“提交结果尚未确认，可重试同一次提交”，明确拒绝不会因该重试成功。
- 触发：两设备同时打开，A 已提交状态 A，B 未收到事件时提交状态 B；或 B 未获知旧卡片已替代时点击。无需并发写库异常即可沿现有合法流程发生。服务端正确防重复，客户端无法正确展示原提交/更新或引导单独发送新要求。
- 建议：保留网络未知的冻结 key 重试；对确定 409 保留本次未提交正文/状态，显示已提交/已有更新并展示或定位原提交，提示可单独发文字。增加最低层前端行为回归，验证 POST 409 不再显示未知重试且不丢新输入。不要改 spec 迁就实现。
- 证据等级：CONFIRMED（实际代码路径和既有 backend 409 回归直接支持；本轮未声称浏览器复现）。同一问题见 `code-review.json`。

### SUGGESTION

无。

## Round 2 — W1 targeted closure

- verification_mode: `targeted-closure`；code review mode: `closure`。
- executed_base / finding_origin_head: `0373d8feca33a449c0ea7e7f5a01fa88909e3e87`
- validated_at / candidate: `aaa6bfc24a052e4da3da1eeeec4a819f47d7a142`
- fix_delta_range: `0373d8fec..aaa6bfc24`
- checked_at: `2026-10-19T16:33:49+08:00`
- focus_issues: `W1`（确定 POST 409 被误当未知发送）；保留 Round 1 的其他实现结论。本轮未扩大为整条分支 full 重审。
- requires_full_verification: `false`
- verdict: **W1 closed — 1 CRITICAL pending evidence / 0 WARNING / 0 SUGGESTION**。

### W1 closure evidence

1. `chat-api.ts:78` 识别真实服务端 `{detail: {code, submission_message_id}}` 的两种明确 409，转成 `InteractionSubmissionError`。已核对 `server.ts:150` 与 `context.ts:20` 的真实响应封装；其他错误保留现有未知发送处理。没有依赖不匹配的假想错误格式。
2. `interactive-card.tsx:96` 的确定冲突分支清掉 pending、停止重放、保留当前 Renderer 字段并显示具体已提交/过期说明。已提交冲突提供指向原提交消息的链接；`ChatWorkspacePage` 原有 `message_id` locator 可消费该链接。网络未知仍保留原 frozen input/key，已有 uncertain retry 回归未被删除。
3. `message-pane.tsx:662,1091` 对确定冲突清掉附带选择；普通 composer 的原文保留，下一次发送可作为独立文字。`chat-workspace-page.tsx:873,1137` 显示具体冲突说明与原提交链接。卡片按钮失败路径同样去除冲突附件；没有显示业务已执行成功。
4. 新卡片参数化测试分别覆盖 alreadySubmitted/stale：保留本机字段、无重复重试入口、只读并有正确提示/原结果链接。新 flow 测试覆盖手写原文保留、移除冲突附件与再次按普通文字发送。caller 的 `/tmp/feat617-conflict-fixed.log` 显示 `npm test -- src/features/chat/interactive src/features/chat/chat-api.test.ts`：**4 suites / 24 tests passed**，包含旧 uncertain retry；caller 交接 production build 通过。复用有效窄验证，不重复全量。
5. 同 delta 的 CSS 将只读字段文字恢复可读，submitted 文案改为“选择已提交给 Agent”，避免在后续回复后继续声称等待。它们只改善现有只读/提交语义，没有扩大本 unit 能力或改变业务执行权限；最终真实视觉对照仍交 C1 的产品证据。

### Focus finding disposition

| Finding | Disposition | Current evidence |
|---|---|---|
| `code-review.json` 原 P2 / verifier W1 | **closed** | 确定冲突与未知发送分流，停止无效重放，保留新输入、原结果入口和独立文字恢复；2 个卡片场景 + 1 个手写场景回归通过 |
| C1 全部 R1/R2/R3/W2 产品退出证据 | **pending，未复验** | caller 已派独立产品 reviewer；尚未提供完整结果。不得将本次 closure 等同完整产品验收通过 |

`code-review.json` 更新为 `[]`：focus finding 已关闭，fix delta 未发现存活代码问题。报告仅包含上述范围的独立静态核对，未声称本轮实际浏览器复现或完整 unit 已可交 PR。

## Round 3 — A1/A2 fix delta and C1 evidence reconciliation

- verification_mode: `delta` + `targeted-closure`；code review mode: `patch`。
- executed_base: `cc47abe3f`（unit 基线，不随报告提交变化）。
- validated_at / candidate: `a211d7643e64b820908397844cbd3125372c83e0`
- fix_delta_range: `613f33765..a211d7643`
- checked_at: `2026-10-19T16:55:11+08:00`
- focus_issues: 产品 Round 1 A1（离线待处理反馈）和 A2（内部选项值）；C1 仅补证据核对。
- retained_from: Round 1 full 与 Round 2 W1 closure。`aaa6bfc24` 后此前仅报告/证据变化不触发重复全量重审。
- requires_full_verification: `false`
- 当前结论：**patch code review 无存活问题；delta aligned；C1 pending A1/A2 独立产品复验**。

### Fix delta findings and evidence

- **A1 implemented at the relevant seam**：`message-pane.tsx:1865` 只对带 interaction_reply 且持久状态为 pending 的本人选择消息显示“已保存，等待 Agent 处理”。原卡片 submitted 改为中性的“选择已提交”，不把中心持久化等同 Agent 接手或业务完成。`chat-workspace-page.tsx:746` 收到当前会话 `relay.delivery_receipt` 后重读权威消息；已核对 `gateway.ts:490–499` 更新消息状态并发该事件、`messaging.ts:321` 为事件附会话 ID，因此不是只在 mock 中成立的接线。离线不消失，恢复且回执后消失的真实体验仍待独立 reviewer。
- **A2 implemented without changing input identity**：`interactive-source.ts:78–81` 从校验后 source 的 option 元素建立 label 映射，`:116–120` 给 Radio/Select/CheckBoxGroup 增加可选 `display_value`。`value` 原样保留，提交 semantic identity 仍比较 raw canonical state，不改幂等和模型真实输入；display_value 随持久 snapshot 进入历史/事件，前端 `message-pane.tsx:1799` 优先显示它。历史旧 snapshot 无该可选字段时保持原有 raw 值回退，不改写不可变旧记录。
- IM 新测试覆盖 RadioGroup 的 bike→骑行、Select 的 am→上午，以及多选仅显示选中的雨伞，同时断言原 value 未变。Web 新 flow 测试覆盖 pending 提示与 running 后消失，新 workspace integration 测试由 receipt 触发权威 refetch 并消除提示。caller 的红→绿交接为 **IM 2 suites / 18 tests、Web 4 suites / 162 tests**；progress W3 已持久记录。`pnpm typecheck`、双 build 通过，前后端 build 日志 `/tmp/feat617-a1-frontend-build.log`、`/tmp/feat617-a1-backend-build.log` 与交接相符。复用有效证据，不重复已覆盖测试。
- 本轮独立 `git diff --check 613f33765..a211d7643` 通过；未改实现、测试、配置或 runtime。

### C1 current disposition

`acceptance.md` Round 1（独立实际旅程，产品代码 `aaa6bfc24`）现已提供普通/Global 三类卡片、纯文字、双用户隔离、双页面草稿冲突、失败重试、替代/fork、渲染降级，以及 1440/768/390 全部 must-match 对照，均给出入口、操作和 durable 截图。该证据补齐原 C1 大部分缺项，不能继续描述为“未进行完整产品验收”。原生真机和真实外部 channel 未执行的边界也明确，本文仍只保留此前摘要 DTO/回退 seam 的测试结论。

Round 1 因 A1 major 阻塞而 fail，A2 minor；两项实现修复和针对性回归已成立。本轮不代替产品 reviewer 宣称 A1/A2 真实体验闭环。已补核 a211d7643 的 `/tmp/feat617-a211-docs-check.log`：`PATH=<main .venv/bin> ./scripts/docs-check` 通过，249 maintained Markdown sources / 64 required routes；`/tmp/feat617-final-web-tests.log`：最终 Web 全量 **99 suites / 899 tests passed**。caller 确认最新 origin/main 仍为执行基线 cc47abe3f，无需新增集成范围。C1 **仅剩等待 A1/A2 targeted 产品复验**；收到报告后更新最终 closure，无需因文档 SHA 增长重审无关源码或重跑全量。

## Round 4 — C1 targeted evidence closure

- verification_mode: `targeted-closure`；focus_issues: `C1`。
- executed_base: `cc47abe3f`
- validated_at / implementation candidate: `a211d7643e64b820908397844cbd3125372c83e0`
- acceptance evidence commit: `2183e38708a4dcef24ba2ef559b2446bb9b7f2f5`
- checked_at: `2026-10-19T16:59:03+08:00`
- retained_from: Round 1 full、Round 2 W1 closure、Round 3 patch/delta。report-only 增量已经核对，不扩大代码审查。
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**。

### C1 — closed

已核对 `acceptance.md` Round 2 的实际操作、版本、Reference 对照、retained evidence 与新增 durable 截图：

- A1：390×844 下真实停止本 unit Node 后提交新 Global 卡片，本人消息出现 `Saved, waiting for Agent`，原卡片只表达 `Choices submitted` 并只读。恢复 Node 后无导航、无手动刷新，待处理 DOM 消失；Agent 随后按所选骑行/咖啡/拍照、排除读书继续规划。证据：`evidence/review-r2-offline.png`、`review-r2-resumed.png`，R2-T2。
- A2：Global 手机及普通 Agent 768×900 的单/多选确认分别显示“骑行／咖啡休息、拍照”及“线下／带书、带笔记”；刷新后保持相同标签和只读结果。原 raw value 继续用于状态/模型数据，不承诺迁移旧快照。证据：`review-r2-refresh-labels.png`、`review-r2-normal-done.png`、`review-r2-normal.png`，R2-T1/T3/T4。
- 独立产品 reviewer 裁决 A1/A2 **closed，新增问题 0，Web 验收整体 pass**，并逐项保留 Round 1 已实际覆盖的其余 Scenario 与 1440/768/390 must-match。三种任务/两种 Agent、配置关闭重开、手写“先别发送”、用户隔离、CAS、网络重试、替代/fork和降级均有具体入口与实际结果，不以代码未变代替体验证据。
- docs-check 已在 a211d7643 通过（249 maintained Markdown sources / 64 required routes）；最终 Web 99 suites / 899 tests 通过；此前 IM/PA/DSH/架构/构建证据按已审范围保留。M1 W1、W2、R1、R2、R3 在首版 Web 范围与相关回退 seam 的证据边界内满足，milestone **1/1 完整退出**。

真实手机硬件、原生 App 和外部 channel 未在产品现场接入；该边界沿用 acceptance，不扩展成真机或外部渠道通过声明。独立 verifier 负责核 explicit contract/证据链，产品体验裁决来自上述独立 reviewer；本轮没有操作或修改 runtime。

All checks passed. Ready for PR after the caller completes canonical reconciliation and archival.

## Previous Delivery Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| IM：共同持久化/授权、刷新/节点离线 | Messaging 投影/transaction/权限；pending 提示 + receipt 权威 refetch | 原 IM 测试；Round 3 IM18/Web162；acceptance Round 2 R2-T2 离线与无刷新恢复 | aligned |
| IM：fork/原会话删除、只读、不复制草稿 | `conversation-actions.ts:331`；`interactions.ts:103` | fork copy 窄测；acceptance Round 1 T8 真产品旅程 | aligned at implementation seam |
| IM：真实用户、原回复、实际选择、群中不同成员 | `interactions.ts:69`；`messaging.ts:575`；两条 PA 输入 | interactive-messages；PA interactive-replies | aligned |
| IM：已提交/被替代明确状态、不同意图冲突且保留输入 | backend 409 + `chat-api.ts:78` 类型化；card 停止重放保留字段/原结果链接；composer 去除冲突附件保留原文 | 原 backend 回归；Round 2 两卡片 + 一手写恢复场景，4 suites / 24 tests | aligned (W1 closed at aaa6bfc24) |
| IM：手写正文原样与草稿同时进入公开消息/模型 | `message-pane.tsx:647`；`interactions.ts:79`；withInteractionContext | interactive-flow、IM、PA 双路径“先别发送” | aligned |
| Web：调整后继续、已提交/实际业务结果区分 | Renderer/选择快照/静态动作；明确冲突；pending 单独反馈；server display_value 保留 raw value | catalog/card/flow；Round 2/3 回归；acceptance Round 2 A1/A2 closed | aligned |
| Web：手机/桌面、生成/失败、摘要与输入 | 原 MessagePane 内嵌、CSS、RenderBoundary、既有运行投影 | acceptance Round 1 Reference 表与 Round 2 retained 对照；A1/A2 修复后手机/窄桌面复验 closed | aligned |
| Web：个人草稿恢复与跨设备 CAS 冲突 | GET/PUT 用户 key + CAS；load/save conflict | interactive-card PUT conflict、IM CAS/隔离 | aligned |
| Gateway：任意 Agent 按任务交付、真实用户执行链 | global-mode tool + PA public send / Relay/Inbox | 模型样本、communication-native、PA tests；acceptance Round 1 T1/T2/T4–T7 | aligned at implementation seam |
| Gateway：外部/原生可读摘要、不泄露 DSL | `global-agent.ts:291` strip + 不变正文 | PA web/feishu 参数化 | aligned |
| Gateway：Features 默认/关闭/重新开启/旧卡片保留 | capabilities + generic UI + DSH lifecycle + PA guard，未改变旧消息 API | 三层 Feature 回归与 progress 浏览器保存刷新 | aligned |

### Uncovered Observable Behavior

- 本 unit 顺带修改默认 E2E 模板：显式工具名单、两普通 Agent 加一个 Global Agent、空 Skill 禁用名单。它是已授权的开发/验收预设行为，已在 `docs/development/worktree-runtime.md` 与 `evidence/e2e-config-validation.md` 正确归属；不属于这三份产品 delta，无需把运维预设硬塞入产品 spec。
- 没有发现其他应进入三份产品 delta 却遗漏的对外行为。NO_REPLY 的特殊投影限定已确认交互的该 turn，属于单份公开回复契约的实现，未改变普通无卡片回复。

Outcome: **aligned**（最终实现 a211d7643；W1/A1/A2 修复与 C1 产品证据 closure 均完成）。无 delta-mismatch、implementation-mismatch 或存活 CRITICAL/WARNING。


## Round 5 — full OpenUI restoration review

### Metadata and scope

- verification_mode: `full`，同时核对当前全部三份 corrected delta；code review mode: `full`。
- validated_at / candidate: `07ca4831c03e9fab4b9e5341eed6315317c17675`
- executed_base: `cc47abe3f`；prior-delivery baseline: `cf4b17f00`。
- checked_at: `2026-10-19T18:11:09+08:00`
- 先重读当前 spec/design/三份 delta 和 design-review R4 Approved，再审新实现；没有用旧表单原型、终身一次提交或旧产品 PASS 替代本次目标。
- 代码范围覆盖 `cf4b17f00..07ca4831c` 完整恢复 diff，并核对 `cc47abe3f..07ca4831c` 的原公开交付链与既有架构职责。未受改变的身份/权限、PA publication、Relay/Inbox、离线反馈、Features 和 fork 数据独立性沿用此前实际源码及窄证据；已改变的 catalog/状态/原生事件/工具/patch/迁移全部重新核对。
- requires_full_verification: `false`（本轮已为 full；后续局部修复和产品证据可定向 closure）。
- 本轮只改本 unit 两份报告；未改仓库源码/测试、未操作其他 worktree、未启停服务。临时独立窄复现场地位于系统临时目录，完成后清理。

### Completeness and evidence

| 项目 | 实现与证据 | 当前状态 |
|---|---|---|
| 完整组件库和旧卡片兼容 | `catalog.tsx:22` 仅增加旧 ContinueButton 并扩展 Form buttons union，未删除任意上游组件；catalog test 断言包含全部上游组件并验证旧消息编辑恢复 | covered |
| 本地状态、计算、条件、Each、Set/Reset/多个按钮 | 原生完整 library + Renderer；source/parser 不再以表单数量、静态字段/单按钮拒绝合法语言；catalog/native source 测试、本地 Set/Reset 无 host 请求 | implemented；真实知识讲解的 meaningful 变化待产品证据 |
| 完整原生事件和当前 state | `interactive-card.tsx:105,132,145` 完整 ref + formState 冻结，click capture 标签独立于 generated message/context；`interactions.ts:85` 和 DTO/withInteractionContext 保存独立字段 | native/Mutation 参数化测试覆盖 Set 后 scale=3 与最新 Form 草稿；PA 接收完整 state/event；covered |
| 多次探索/请求级幂等 | 新键各自请求，失败保留原 frozen input/key；submission 主键改 message_id，source/user 非唯一；确认后可继续本地操作和保存 | 后端重复/新键测试及 Web 两次请求 covered；revision 竞争见 W2 |
| Query/Mutation 与宿主工具 | generated interactiveTools 给静态服务端校验分类；仅 conversation_messages/read 与 continue_conversation/write；当前 cid/身份由 host 决定 | Query 真实 listMessages seam；Mutation 同一 submit；未知/读写错配拒绝；covered |
| 链接与未知事件 | `onAction` 只允许 http/https，noopener/noreferrer；未知动作显式 action error，未推断工具或网络目标 | 源码核对；未增加任意 JS/shell 执行器 |
| patch 不可变完整版本与发布重试 | `Interactions.record` 在现有 insert transaction 内 mergeStatements，完整校验后新版本/旧 superseded 原子保存；publication_json 保存原 normalized patch，Gateway 重试比较原输入 | patch 无root补丁合并、旧源保留、publication原输入断言通过；covered |
| 数据升级/旧消息 | migration 在事务内保留原 submissions，并取消 source/user unique；旧 source 在新 parser/evaluator 下读/交互；fork 复制完整源/快照不复制私有草稿 | 原兼容 tests retained + 新 schema/迁移代码核对；covered at seam |
| 表达选择无验收题专用逻辑 | Feature/生成 Skill/完整 prompt 为通用过程/关系/条件/编辑指导；针对产品源码、生成资产搜索无冒泡/排序/复利专用分支或答案 | covered by source inspection |
| 新 must-match / 普通原话和跨领域 | progress 记真实原话生成、首轮 Select 数值绑定失败与通用修复、跨领域普通问题结果；旧表单 acceptance 不覆盖新版连续探索 | **C2 pending independent product evidence** |

复用并核对 `/tmp/feat617-native-final-web-tests.log`：Web **99 suites / 905 tests passed**；`/tmp/feat617-native-im-tests.log`：IM/PA 相关 **22 suites / 108 tests passed**；progress 记录 pnpm build、Web build 通过及发布原输入断言的 11 tests 追加通过。本轮未重跑无关全量。`git diff --check cf4b17f00..07ca4831c` 仅报告 design.md EOF 新空行，不列为产品缺陷。

### Correctness and architecture

完整 OpenUI 作为注册语言/Renderer 使用，不是第二套 Agent Loop。IM 仅加载 lang-core 与 product-contracts 纯 catalog；PA/Channels 不 import DSH；宿主 Query 使用既有登录用户 REST read 权限，Mutation 只向当前 source 作者产生普通用户请求，不能指定其他会话/Agent/角色。生成上下文被标记为 UI 生成数据；正文保留实际标签或用户手写原文。原公开 source 披露审核仍覆盖整个 source，patch 沿既有公开 send_message/dispatch 交付；缺失 Feature 值默认启用，关闭接口拒绝新交互的旧规则仍适用。

交互状态完整保留及原生事件适配本身有实际 seam 测试；但同一次 native 按钮请求可能同时经 WS prop effect 和 POST 成功分支更新本地 CAS revision，构成下述确定问题。它影响新目标“继续探索后刷新恢复”，不能用旧单次提交的测试 PASS 关闭。

### Issues

#### CRITICAL C2 — 新用户目标的独立真实产品证据尚未最终收口

- 契约：当前 spec 的“无交互提示的知识讲解”“保留通用界面能力”“多次探索与继续提问”，design 的新 must-match 与 M1 R1/R2/R3/W2。
- 旧 acceptance Round 1/2 是被用户否定的静态表单切片，不证明此次目标。progress 新现场记录是有价值的作者证据，但独立产品 reviewer 的最终普通原话/跨领域、三宽度意义变化、连续提问与本地探索、查询/修改失败和 patch/历史/权限对照尚未交付。
- 建议：接收既定独立产品验收及 durable 对照，逐项闭合上述新目标；不要重启或清空既有现场，不用 API fixture 代替无提示真实模型入口。该问题为证据门禁 pending，不据此猜测新产品必然失败。

#### WARNING W2 — 同次提交的 WS/POST 双路径把草稿 CAS 版本增加两次

- 契约：`design.md` 私有状态 CAS、“继续对话可多次发生”与即时完整状态；Web delta“提问后继续探索”，IM delta“多次探索与请求幂等”。
- 位置：`interactive-card.tsx:76–82,111–113`，关联 `messaging.ts:536` 在 POST 返回前 publishMessages。
- 触发：当前本地 revision=2。按钮请求创建消息后，其 WS 回显先使 submittedMessageId 改变；effect GET 读取已提交草稿，revision=3。然后同一 POST Promise 返回，成功分支 `revision.current++` 又变4。下一次编辑 PUT expected=4，而服务端仍3，单设备被错误提示“另一设备更新”，重试相同版本仍失败；载入最新才能恢复但会替换刚编辑的值。
- 独立复现：系统临时目录中的一次性 Vitest 使用实际 InteractiveCard/Renderer；mock 初次 draft revision=2，延迟 onSend Promise，先 rerender submittedMessageId 并返回 GET revision=3，再 resolve 同一 onSend，编辑 TextArea。实际 `saveInteractionDraft` 的第3参数为 **4**，正确值为 **3**；1 test failed，`AssertionError: expected 4 to be 3`。未运行服务、未改仓库测试。这是正常网络可产生的合法事件先后，不需要另一个用户或异常数据库。
- 证据等级：**CONFIRMED**。现有“composer提交后读取revision”与“连续native两次请求”分别覆盖单一路径，没有覆盖两种消息确认同时指向同一次 native 提交。
- 建议：让 native POST 成功与 WS 提交同步通过单一权威 revision 更新路径收敛，不再在读回最新 revision 后盲目 +1。补最低层回归保护 WS→POST 与 POST→WS 顺序，断言后续编辑成功保存且值保留；无需引入额外状态框架。

### Current disposition

旧 W1、A1/A2/C1 在原交付范围的闭合历史保留。本次新问题 W2 open，C2 pending；当前代码审查 JSON 为本轮一个 CONFIRMED finding。静态核对本身已完整结束，不等待新产品报告才报告确定问题，不追逐假想边界。

## Corrected Delta Reconciliation

| Current delta item | 最终实现/证据 | 结果 |
|---|---|---|
| IM MODIFIED：真实用户/群隔离/手写正文原文 | 原身份/read-write checks + request snapshot + 完整 withInteractionContext；相关 backend/Web/PA tests | aligned |
| IM MODIFIED：多次探索与请求幂等 | request级key、完整semantic、source/user可多次、同键重试/不同语义409；新迁移/窄测 | aligned；W2 在 Round 6 closed |
| IM MODIFIED：patch 完整历史 | 公共 mergeStatements、完整校验、publication_json、同作者同会话限制、事务回滚 | aligned |
| Web ADDED：组件/计算/动作与连续本地探索 | 未删除完整上游组件；native Renderer；local Set/Reset无新请求 | aligned；Round 7 普通原话/跨领域和本地探索证据闭合 |
| Web ADDED：提问后继续探索、错误不抹可读内容 | 可多次submit、请求冻结、已提交不锁全卡、tool errors沿原生通道；私有revision双推进 | aligned；W2 在 Round 6 closed |
| Web ADDED：Query/业务动作边界 | 仅已登记只读Query和明确Mutation，host身份/cid固定，返回message receipt非业务完成 | aligned |
| Gateway MODIFIED：各任务通用交互及外部文字 | 通用 Feature、完整 catalog/skill、原公开交付与渠道strip retained | aligned；Round 7 作者Global+独立普通真实模型证据 |
| Gateway ADDED：无提示普通问题和跨领域 | 代码/提示无验收题逻辑；作者现场新模型样本保留失败 | aligned；源码无专用逻辑+Round 7两种主题自然触发 |
| Gateway ADDED：保留OpenUI并遵守权限 | full82+legacy组件、原生机制、仅两host工具，未接入文件/任意系统调用 | aligned |

### Uncovered Observable Behavior

无新增遗漏。旧 Features、消息读取/fork授权、Web基本阅读/失败与外部摘要 Requirement 在 current 原条目中保留；当前 MODIFIED/ADDED 类别与已交付 canonical 基线对应，未把未变旧条目重复 ADDED。恢复全部 UI 能力与业务工具接通范围已分别写明。

Outcome: **aligned**（Round 6 W2/重试修复 + Round 7 C2证据closure）；无存活 delta-mismatch / implementation-mismatch，0 CRITICAL / 0 WARNING。


## Round 6 — W2 and retry accessibility targeted closure

### Metadata

- code review mode: `closure`，focus 为 Round 5 W2；另外定向核对独立产品新发现的 retry accessibility 修复。verification_mode: `targeted-closure` + fix delta。
- validated_at / frozen candidate: `19efc4031bb858af5251410dec0c68849dbf77b1`
- fix_delta_range: `07ca4831c..19efc4031`
- executed_base: `cc47abe3f`（unit 基线不随 closure 改动）。
- effective_through: `60b311a48ac5e999a3594d81316acf3c69eac433`；额外 diff 仅移除 Testing Library getByRole 的无效 `exact:true` 测试选项，已独立核对单行，不改变产品代码/断言含义，不扩大复验。
- checked_at: `2026-10-19T18:18:46+08:00`
- retained_from: Round 5 full，其他实现/架构/规格结论保留；产品 C2 仍 pending。
- requires_full_verification: `false`
- verdict: **静态 closure 通过；1 CRITICAL pending evidence / 0 WARNING / 0 SUGGESTION**。

### W2 — closed

`interactive-card.tsx:75` 新 `syncSubmittedDraft()` 是 WS prop effect 与 native POST 成功共用的权威 GET 路径；读取服务端实际 draft_revision 并以 Math.max 与当前版本收敛，已移除成功分支盲目 `revision.current++`。同一确认不会再被算两次，晚到的较旧 GET 也不会倒退新版本；不 remount explorer、不改本地当前输入。

已读 `/tmp/feat617-w2-red.log`，相同 WS→POST 时序在修复前确实 **expected revision 3 / actual 4** 失败；`/tmp/feat617-w2-green.log` 显示真实 InteractiveCard/Renderer 的 WS-first、POST-first 与原输入/连续请求共 **2 suites / 16 tests passed**。这直接覆盖原 finding，不用作者手写追问的成功结果代替 native 按钮时序保护。

### Retry accessibility — implementation aligned

`AttachmentDropzone` 原本为整个 composer 子树设置 `aria-disabled=true`；未知发送等待重试时，textarea 应冻结，发送按钮却需要可操作。该祖先标记使实际辅助访问/浏览器定位把绿色 Send 仍视为 disabled。修复仅将 drop surface 状态改为 `data-disabled`；handleDragEnter/Over/Drop 的 disabled guard 仍阻止添加新文件，具体 textarea 的 native disabled 保持。它不解冻原请求，不改变 message/state/key，也不开放新附件变更。

已读 `/tmp/feat617-retry-red.log`，修复前 retry 的 disabled 祖先断言真实失败；green 日志 **3 suites / 18 tests passed**。interactive-flow 改用实际 Send click，断言按钮本身和祖先均可操作，仍比较两次 onSend 的完整冻结正文、state 和 key。dropzone 窄测同时断言 disabled 下 drop 不调用 onAdd 而子按钮可点击。修复与 Web 连续探索/错误恢复、IM 请求级幂等 delta 一致，没有扩大协议或业务权限。

### Evidence reconciliation and pending boundary

- 新作者 `evidence/native-browser-review.md` 和 `native-model-samples.json` 保存普通原话、失败源、修正后真实源及同卡两轮20000/620→30000/930的持久状态；它们是实际生成与作者旅程证据，不能代替独立产品 C2。
- `/tmp/feat617-native-final3-web.log` 已独立核对最终19ef Web **99 suites / 908 tests passed**。caller 交接全 backend 96/373、Python非E2E62、typecheck与ruff通过；上一有效 full build 等证据保留。60b311a48 删除无效测试类型选项后的 build 正在由 caller 重跑，未在本报告抢先声称该次完成。
- caller 的最终同步确认 origin/main 仍 `cc47abe3f`，无集成增量。无需因只追加报告或该测试类型修正重审完整 unit。
- C2 **继续 pending**：独立产品 reviewer 的新版完整旅程及19ef两项 targeted复验尚未最终交付。收到报告后只做证据 closure，不重复已有效覆盖的 full 静态或全量测试。

### Focus disposition

| Item | Status | Evidence |
|---|---|---|
| Round 5 W2 / code-review P2 | **closed** | 统一权威 revision、移除双推进；相同红测与双顺序绿测 |
| 新产品重试按钮不可访问问题 | **implementation fixed / independent product confirmation pending** | data-disabled 不影响Send；真click/冻结重试与drop guard的红→绿 |
| C2 新用户目标独立产品证据 | **pending** | 等待既定独立 full + targeted 产品报告 |

`code-review.json` 更新为 `[]`。本轮仅更改报告，未改源码/测试/环境、未触碰其他 worktree；没有对未证明的边界继续扩展审查。


## Round 7 — C2 final evidence closure

### Metadata and verdict

- verification_mode: `targeted-closure`；focus_issues: `C2`（新目标独立产品证据）。
- executed_base: `cc47abe3f`
- effective_code_through: `60b311a48ac5e999a3594d81316acf3c69eac433`；产品代码等同前次固定候选 `19efc4031`。
- evidence_commit: `cff39b7164c29b6f764603f0a6f36ea51af3594d`
- checked_at: `2026-10-19T18:26:44+08:00`
- retained_from: Round 5 full、Round 6两项定向代码closure；不重跑已有效覆盖的全量，不扩大源码审查。
- requires_full_verification: `false`
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**。

已核对 60b311a48..cff39b716 的新增内容只涉及 unit 验收/审查报告和截图，未改变有效产品代码。`code-review.json` 保持 `[]`，本轮仅追加/同步 verification；未改其他报告、源码、测试、配置或运行环境。

### C2 — closed: new requirements and meaningful evidence

| 新目标 / must-match | 证据与核对结果 | 结论 |
|---|---|---|
| 无交互暗示原话主动生成有意义界面 | `acceptance.md` Round 3，独立普通 Agent 新会话原话“给我讲解下冒泡排序”，自行生成步骤/状态数组/解释/上下步重置/Tabs，连续三步数组与说明匹配；浏览器仅本地私有保存、没有POST聊天请求 | covered |
| 通用性且无验收题专用实现 | 独立私有群原话“为什么月亮会有阴晴圆缺？”自行生成月相探索；另一领域普通样本和Global原话的作者实证见 native-browser-review/native-model-samples；Round 5 已直接核产品代码/prompt/Skill无题材专用分支或答案，黑盒样本不单独承担此证明 | covered |
| 本地探索后多次解释、当时状态保留 | 独立步骤3手写追问与步骤5继续追问，模型正确理解两次具体状态；原生按钮独立两次201，用户正文标签与generated event.message/context、state区分保存，模型对应解释；作者同卡20000/620→30000/930及原提交快照保留提供不同主题交叉证据 | covered |
| 私人状态和用户身份 | 原生月相 owner满月/peer上弦互不覆盖，分别提交形成各自真实状态与用户消息，后续模型分别解释；不是把先前表单隔离当新版状态证明 | covered |
| 错误后真实可重试、提交后继续保存 | 修复资产 `/assets/index-Bp2CmFPF.js` 由独立reviewer加载；手写POST受控断连后实际Send click成功201，两请求正文/source/state相同；随后连续原生按钮请求，立即本地操作的PUT均200，无虚假409；产品N1 closed。WS/POST全部交错的确定保护由Round 6双顺序窄测承担，不以有限浏览器成功样本过度外推 | covered |
| 三宽度与连续探索原型 must-match | 已重读 Round 3 原型对照，并直接打开 `review-native-1440.png`、`review-native-768.png`、`review-native-390.png` 核 explicit contract：参数/状态/解释和动作同属回复；按钮合理换行，主聊天滚动、导航及输入保持；可见当前上下文条与Detach。交互前后真实意义变化来自步骤轨迹而非仅截图上有按钮 | covered |
| 完整上游能力、Query/Mutation、patch与业务权限 | Round 5源码+有意义窄测试证明全部82上游组件注册（+旧ContinueButton）、原生Set/Reset、Form内外完整state、Query真实listMessages seam、Mutation同提交链、工具读写分类和未知工具拒绝、patch合并完整版本及原始发布幂等。独立浏览器只声称实际操作的组件/动作；未将新source替代旧source假称为patch协议验证 | covered at declared lower seams |
| Features、简单文字、离线/历史、fork与渠道摘要 | 保留旧证据的具体未变路径，以及本轮旧消息同时可读/新卡连续操作；只保留其已证明范围。原生iOS/外部channel未实际接入，不声称真机或外部现场验收；摘要边界仍由DTO/渠道回退专项承担 | covered within explicit boundary |

这次证据覆盖的是用户纠正后的“普通提问主动交互、完整原生机制、连续探索”目标；旧表单“一次确认锁死”不再作为新版验收标准。当前三份 delta 的 MODIFIED/ADDED 与最终实现无新增偏离，未接入任意文件/shell业务能力的边界已明确，未静默降低新目标。

### Final verification evidence

- 已实际读取 `/tmp/feat617-native-final-build.log`，最终前端类型/production build完成，资产 `index-Bp2CmFPF.js` 与产品复验记录相符；caller交接后端build、typecheck、ruff通过。
- 已实际读取 `/tmp/feat617-native-docs-prearchive.log`：docs-check **251 maintained Markdown sources / 64 required routes**。
- Web最终 **99 suites / 908 tests**，全backend **96 suites / 373 tests**，Python非E2E **62 passed**；前述相关源码、具体回归及已有日志核对按Round 5/6保留，未重复运行。
- audit critical gate通过，实际audit日志为 **5 low severity vulnerabilities，0 critical**；没有宣称依赖零告警，也不据低风险告警扩展本unit。
- caller最终fetch仍为 `origin/main=cc47abe3f`，无集成增量。后续 canonical归并/归档若只变契约归属和文档，不因文档SHA增加重复本轮有效实现验收。

### Final disposition

- W2：closed（Round 6权威revision及双顺序窄回归；Round 3产品定向保存亦成功）。
- N1：closed（dropzone可访问语义修复、冻结请求真实Send重试、独立最终资产复验）。
- C2：closed（本轮新版目标的独立产品证据与专项实现证据完整拼合）。
- M1 W1/W2/R1/R2/R3：按上述证据边界满足，milestone **1/1 complete**；corrected-delta **aligned**。

All checks passed. Ready for PR update after canonical reconciliation and archival. 本结论不代表PR已push、CI已完成、已合并、发布或部署。
