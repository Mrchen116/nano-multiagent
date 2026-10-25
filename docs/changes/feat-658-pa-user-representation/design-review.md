# feat-658 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/feat658_design_review`（独立于设计作者）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖 spec、完整设计、两份 delta、原型、部署提示词、设计证据与单一 M1。
- started_at: `2026-10-25T17:14:37+08:00`
- completed_at: `2026-10-25T17:16:15+08:00`
- duration: `PT1M38S`（已记录的末轮现场核对与报告整理区间；此前文档/代码阅读和原型走查未单独计时，不计入此值）
- baseline: 受审基线 `e5856ec23`；审查时 main 为 `a54d11aed0d0fffbd7968de34da36f63ae732ac6`。核对两者在本次涉及的 IM、PA、integration 与双端代码目录无差异。保留现有未跟踪设计产物，仅新增本报告，不实施、不提交。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**。

用户主身份、审核签发、来源保留与双端身份层级的总体方案成立。交互卡片的实际执行者解析尚未闭合，需要补齐后再通过 Gate 2。

### Coverage 与证据

#### 真实组装与职责

从真实入口而非孤立工具或测试核对：`apps/im-server/src/server.ts:88` 组装 Messaging / Gateway / PersonalAgents；PersonalAgents 构造 PersonalActions。`apps/node/src/main.ts:356` 同时组装 SingleThread 与 GlobalAgent，`product.call` 实际进入 GlobalAgent；`packages/personal-assistant/src/global-agent.ts:56` 创建 PersonalAssistant，`:522` 将个人发送交给 `personal.send`，`:337` 起为观察 feed 摄入。这些入口覆盖设计所述发送、参与 relay 与观察来源两条路径。

`PersonalAssistant.send` 现有 publication 去重、prepare/review-result/commit 编排与 `PersonalActions.commit` 的数据库事务可以复用；`messaging.ts:330` 的消息投影确实读取旧代发记录，现有 commit 在 insertMessage 后才插入来源。设计把来源落库提前到事件快照之前是必要修正。owner 模式纳入 frozen payload/digest、两次权限检查和 operation 关联，避免仅更换 UI 作者或另建授权账本。

架构职责合理：IM 决定用户/绑定/受众/公开消息事实，PA 编排发送和收件，integration 利用公开 DSH 会话与审批入口构造可信审核材料，客户端只呈现来源。与 `SPEC.md` 的依赖方向一致；无需新增运行时、通用代理框架或授权票据服务。实际仍需维护的第二种身份是卡片执行 PA，当前设计在此处尚缺消费端解析规则，见 R1-W1。

#### 需求、审核与历史语义

- S1/S3：`send_as=self|owner`、默认 self、原话委托与披露许可分开审核、固定口吻指导和实质歧义澄清共同覆盖需求。`personal-security.ts` 的现有 planned_action 与有效上下文审核是正确改动入口；不能只改发送工具描述。
- S2：消息存用户主身份可以统一普通作者查询、本人归属及历史显示；保留服务端生成的实际 PA 来源，并禁止由公开消息请求体指定它。Work 链接、用户亲发判断和卡片是身份变更后的实际消费者，设计已识别前两项，卡片见 R1-W1。
- S4：主人私聊、外部渠道、草稿、系统通知和 task action 与 owner 组合拒绝；普通 Agent schema 不暴露 owner；自己的代发不能成为新的主人原始证据。明确排除 `directOwnerMessage`、authorizationGuard、last_owner_message_id、抢先回复及来源设置的代发自证，符合现有 `personal-agent.ts:128` 起的事实链。
- S5：`InboxStore.read` 当前按片段投影消息，`work.ts:706` 起历史分页投影确实未携带 delegation；设计要求逐片保留身份、来源、完整性和原消息标识，覆盖现有丢失点。`policy/sources.ts` 当前只为 Inbox/send_message 建立专用来源行；扩展正式 conversations read/search 而不信任正文中的同名字段，是正确的可信边界。
- 子 Agent 审核继承入口是 `policy/approval.ts:59` 的 parent history / codexEntries 持久投影；恢复经 `restoreEntries` 重投影。设计保留已有授权、区分 historical/restored 与新事件，不新增许可或任务触发，符合这些入口。需要在 M1 检验实际投影与模型执行，设计审查不声称此目标已实现。

#### 原型与人的使用过程

独立打开 `http://127.0.0.1:63358/prototype.html`，先观察实际画面，再切换状态和核对文字契约；同时查看 spec 引用的原始 Web 截图，并核对 `message-pane.tsx:1845` 起及 `ChatMessageView.swift:27` 起的实际布局。

独立走查结果：

1. 桌面默认收件人群聊：用户姓名在正文前、PA 代发为相邻次级标记；Q 仍是另一条 Agent 身份，正文直接表达同意与限制。原截图中 PA 为主、主人在辅助标签和正文前缀内的辨认负担得到解决。
2. Web 320 内容宽、本人、长姓名与附件：右侧本人气泡与头像明确；长姓名、标记、正文和附件可读，没有把来源挤进正文。此为原型内容容器宽度，不宣称真实设备 viewport 通过。
3. iOS 构图、本人、与 Q 私聊：本人身份行和 PA 标记在私聊仍可辨认，右侧归属明确。它是设计示意；没有取得当前原生实机画面，也未验证新原生实现、字体缩放或 VoiceOver，不给原生体验 pass。设计已经明确各端内容关系与原生 M1 验证要求，不把“原生适配”当作未决布局。
4. Web 390 草稿：PA 仍为作者；点击“采用草稿”后进入目标聊天并预填输入框，未新增已发送用户消息。草稿与代表发送的后果可区分。

可复查入口与作者代表性截图见 [design-evidence.md](design-evidence.md)；上述为 reviewer 自行重新操作所得，不以作者的通过结论替代观察。V1–V3 已映射 R1/R2 与 W2，平台气泡细节允许沿用原组件，没有要求复制 HTML 到 SwiftUI。现有原型没有主动交互卡提交旅程；卡片功能须先解决 R1-W1 再纳入 M1 的决定性验证。

#### delta、milestone 与验收资源

两份 delta 均锚定正确的 canonical personal-agent spec。IM MODIFIED 完整保留“编辑并采用”Scenario，改变“PA 代发”Scenario；新增双方身份、旧历史与自然口吻/接收 Agent 的消费者语义。未把协议字段或数据库表复制进长期消费者契约。

单一 M1 适合本次不可分割的身份与授权链；W1/W2/W3 和 R1/R2/R3 已覆盖事务、审核、双端及恢复，未新增并行冲突。部署提示词要求单次 nullable 列迁移、旧操作 self、不回填历史授权，以及 IM/节点/客户端同步后启用，保留新数据优先前向修复；本轮没有生产授权。

只读核验 daily 清单：独立 IM `63283`、节点 `wt-feat-658-design-resource-check-18953`、P/E/Q 与真实 PA、群和 PA 私聊齐备；`/health` 实际返回 `ok`。`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available` 实际列出 iOS 26.4 的 iPhone 17 等设备。正式实施仍须独立 checkout/实例，不复用设计期资源。

作者在审查中补充的 `/Users/czj/.codex/reports/feat-658-design-resource-check/model-probe.json` 已只读核对：PA 对测试私聊请求返回 completed 的“环境可用”（消息 `d4465166b7174537a1e14980be743a7f`）。这是现有模型与回复链可用性证据，不是 feat-658 实现或 owner 审核通过证据。无必须依赖的第三方账号、真机签名或外部租户；其余 B 账号/专项会话/虚构 Git 仓库均可在隔离实例准备。

### 历史问题闭环

无；本轮为首次审查，无既有 Author Resolution。

### Issues

#### R1-W1 — 卡片执行者仍从消息作者反查，传入 record 的 PA 身份不能闭合后续交互

- 位置：[design.md](design.md) 第 110 行“公开消息与实际执行者”，及 M1 的卡片归属验收。
- 证据：设计将 `messages.sender_user_id` 改成主人，并要求 `interactions.record` 使用实际 PA 的 Agent user id，以保持提交回到 PA。但真实 `apps/im-server/src/interactions.ts:72` 的 INSERT 不保存该 sender；`:13` 的 `source()` 在后续读取时始终从 `messages.sender_user_id` JOIN users。`:54` 的背景上下文和 `:121` 的提交快照以 `username.slice(6)` 解析 Agent；`:67` 的替换校验也与消息作者比较，`:129` 则把它用于 Agent 会话参与资格检查。这些代码在受审基线和当前 main 均相同。
- 未修后果：按当前明确方案创建的 owner 卡片虽可显示，但点击提交会把普通用户 username 截成 Agent id，通常报“source Agent is no longer available”；同一 PA 后续替换自己的 owner 卡片也会被用户 id/Agent user id 不等阻止。若目标是 PA 未参加、仅主人可写的会话，原 membership 判定也与设计允许的 owner 发送范围不一致。这是设计承诺保留的现有交互能力断链，不是可选增强。
- 所需修订：明确由 Interactions 从受控代发来源解析实际 PA，统一用于 source、contexts、prepare snapshot、替换所有权及生命周期/会话资格校验；可以复用现有 delegation，不必再建身份账本。并明确“主人可写但 PA 未参与”会话中交互卡的支持或拒绝边界，不能到点击时才依赖旧作者推断失败。M1 增加一条 owner 卡片提交与同 PA 替换的决定性证据，包含所选会话参与边界。仅再次声明“执行归属仍是 PA”不足以关闭此项。

### Recommendations

无额外建议；不扩展到无关 UI 重设计或假想兼容分支。

### Author Resolutions

- **R1-W1 — accepted**：核对 Interactions.source/contexts/record/prepare，确认 record 的 sender 仅用于校验，并未持久保存执行归属。已在 design「公开消息与实际执行者」明确由同一受控代发记录解析 executor，统一用于背景上下文、提交快照、替换所有权及生命周期/参与/写权限；保留公开作者不变。owner interactive 只支持当前可用且参与的 PA，prepare/commit 在未参与时明确拒绝，普通 owner 正文/附件仍支持观察会话。Runbook 旅程 2 和 M1 R1/W1 补上真实提交、同 PA 替换及参与边界证据。无需新增身份账本或会话权限。
- 资源证据补充：design-evidence 更新隔离真实模型回复的已验证事实；不改变范围、模型配置或产品验收标准。其余受审产物未变。

## Round 2

### Metadata

- reviewer_target: `/root/feat658_design_review`（与 Round 1 相同的独立 reviewer）
- review_mode: `delta`
- mode_reason: 变化限定在卡片执行者解析、owner 卡片参与资格以及对应验收项；超出纯文字消歧，因此不选 closure。公开消息/RelayInput 契约、核心授权边界、需求和单 M1 拓扑没有改变，Interactions 内部解析调整不改变跨包接口，已有完整上下文足够，无需重做 full。
- started_at: `2026-10-25T17:21:08+08:00`
- completed_at: `2026-10-25T17:21:21+08:00`
- duration: `PT13S`（本轮现场核对区间；报告落笔时间另计）
- retained_from: `Round 1`
- scope: design「公开消息与实际执行者」、相关文件范围、Runbook 旅程 2、M1 R1/W1、design-evidence 资源补充和 R1 Author Resolutions。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

R1-W1 的实际卡片来源解析和参与权限已形成可实施、可验收的闭环。本结论只批准设计，不代表实现完成或授权实施/部署。

### Coverage 与证据

#### 本轮变化与影响

1. **执行者单一来源**：修订后的 `Interactions.source()` 明确分离公开作者与 `{executor_user_id, executor_agent_id}`，owner 来源由受控代发关联解析；不再假定 `record(sender)` 会保存身份。对照现有 `interactions.ts:13`、`:54`、`:67`、`:121` 的实际消费者，source、背景上下文、提交快照和 supersedes 已全部纳入同一解析职责。复用现有来源记录，不新增重复身份表，责任仍由 IM Interactions 承担。
2. **参与和生命周期闭合**：owner 卡片要求 PA 当前参与、可用、可写，在 prepare/commit 拒绝未参与目标，正文/附件仍按主人写权限与来源范围发送。它保留现有卡片的参与资格，没有扩展 PA 会话权限；离群或失效后的提交仍拒绝，历史可读。避免了 R1 所述“创建成功、点击时才因用户作者推断失败”。
3. **用户点击的含义保持**：修订明确提交者是实际点击用户，执行者为原 PA。现有 `messaging.ts:598` 起的 `sendInteraction` 使用认证用户 `p.id` 写提交消息，再以 `prepared.snapshot` 排队 relay；新 executor 解析与此入口相容，无需把点击者伪装成最初的被代表用户。
4. **替换不会扩大许可**：比较同会话/同 executor 的卡片所有权，每条新 owner 卡片独立审核；旧 readonly、来源与公开作者仍保留。没有借卡片替换复用旧外发许可。
5. **决定性验收已落实**：Runbook 旅程 2 与 M1 R1/W1 增加真实 owner 卡片提交、同 PA 替换、未参与会话发送前拒绝且无落库、普通正文仍发送、离群后提交拒绝；并将 interactions 纳入明确文件范围。既有 daily 可创建参与/未参与会话，不增加外部资源依赖。

#### 保留项及理由

- `retained_from: Round 1` — spec、两份 delta、prototype 和 deployment-prompt 未改变；新边界只收口原有卡片参与条件，未改变 S1–S5 的代表回复、用户身份或历史授权要求。canonical target、Scenario 保留及部署结论继续有效。
- `retained_from: Round 1` — 双端身份层级、窄宽、草稿采用和普通消息阅读路径不变，R1 的独立原型观察可复用，本轮不重复渲染，也不宣称原生实现体验已经通过。卡片执行行为仍由 M1 的真实产品旅程证明。
- `retained_from: Round 1` — 实际组装、独立审核、来源恢复及子 Agent 继承的代码基线未漂移；再次比较 `e5856ec23..HEAD` 的相关实现目录无差异。完整来源链和架构依赖结论保留。
- `retained_from: Round 1` — 模型资源补充与 R1 已核验的 `model-probe.json` 相符。文档明确只证明现有模型/工具回复链可用，没有将其升级为本功能或独立外发审核通过证据。

### 历史问题闭环

| Issue | Author Resolution | 本轮核对证据 | 状态 |
|---|---|---|---|
| R1-W1 | 接受问题；以受控来源统一解析 executor，前置限定 owner 卡片参与资格，补充提交/替换/离群验收 | design 的 source/contexts/prepare/record/生命周期定义覆盖现有实际消费者；Runbook 旅程 2 与 M1 R1/W1 明确检验成功和拒绝结果；普通正文和附件能力不受新增卡片条件限制 | **closed** |

### Issues

无新增问题；无遗留 CRITICAL/WARNING。

### Recommendations

无。

### Author Resolutions

- Round 2 无遗留 finding，作者核实并接受 Approved。受审方案与原型不再改动。
- 交付收尾仅将 design-evidence 的临时服务状态更新为已停止；不改变方案、原型或验收前置，R2 证据 retained，无需新增设计审查。
