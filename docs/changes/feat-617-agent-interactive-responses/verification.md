# Verification Report: feat-617-agent-interactive-responses

> Validation snapshot: `cc47abe3f → 0373d8feca33a449c0ea7e7f5a01fa88909e3e87`

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

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| IM：共同持久化/授权、刷新/节点离线 | Messaging 投影、transaction、schema、Interactions 权限 | interactive-messages 持久化/隔离/离线 | aligned |
| IM：fork/原会话删除、只读、不复制草稿 | `conversation-actions.ts:331`；`interactions.ts:103` | fork copy 窄测；真实旅程待 C1 | aligned at implementation seam |
| IM：真实用户、原回复、实际选择、群中不同成员 | `interactions.ts:69`；`messaging.ts:575`；两条 PA 输入 | interactive-messages；PA interactive-replies | aligned |
| IM：已提交/被替代明确状态、不同意图冲突且保留输入 | backend 409 + `chat-api.ts:78` 类型化；card 停止重放保留字段/原结果链接；composer 去除冲突附件保留原文 | 原 backend 回归；Round 2 两卡片 + 一手写恢复场景，4 suites / 24 tests | aligned (W1 closed at aaa6bfc24) |
| IM：手写正文原样与草稿同时进入公开消息/模型 | `message-pane.tsx:647`；`interactions.ts:79`；withInteractionContext | interactive-flow、IM、PA 双路径“先别发送” | aligned |
| Web：调整后继续、已提交/实际业务结果区分 | Renderer + 自己消息 snapshot + ContinueButton；明确冲突单独展示 | catalog/card/flow；Round 2 冲突恢复回归；部分真栈记录 | aligned at implementation seam |
| Web：手机/桌面、生成/失败、摘要与输入 | 原 MessagePane 内嵌、CSS、RenderBoundary、既有运行投影 | 实现三宽度与异常对照待 C1 | evidence pending |
| Web：个人草稿恢复与跨设备 CAS 冲突 | GET/PUT 用户 key + CAS；load/save conflict | interactive-card PUT conflict、IM CAS/隔离 | aligned |
| Gateway：任意 Agent 按任务交付、真实用户执行链 | global-mode tool + PA public send / Relay/Inbox | 模型样本、communication-native、PA tests；完整 R1 待 C1 | aligned at implementation seam |
| Gateway：外部/原生可读摘要、不泄露 DSL | `global-agent.ts:291` strip + 不变正文 | PA web/feishu 参数化 | aligned |
| Gateway：Features 默认/关闭/重新开启/旧卡片保留 | capabilities + generic UI + DSH lifecycle + PA guard，未改变旧消息 API | 三层 Feature 回归与 progress 浏览器保存刷新 | aligned |

### Uncovered Observable Behavior

- 本 unit 顺带修改默认 E2E 模板：显式工具名单、两普通 Agent 加一个 Global Agent、空 Skill 禁用名单。它是已授权的开发/验收预设行为，已在 `docs/development/worktree-runtime.md` 与 `evidence/e2e-config-validation.md` 正确归属；不属于这三份产品 delta，无需把运维预设硬塞入产品 spec。
- 没有发现其他应进入三份产品 delta 却遗漏的对外行为。NO_REPLY 的特殊投影限定已确认交互的该 turn，属于单份公开回复契约的实现，未改变普通无卡片回复。

Outcome: **aligned**（实现与最终 delta，经 aaa6bfc24 的 W1 closure）。C1 产品退出证据仍 pending，因此完整 unit 尚不能给出 All checks passed / Ready for PR。
