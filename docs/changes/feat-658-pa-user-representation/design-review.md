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

## Round 3

### Metadata

- reviewer_target: `/root/feat658_design_review`（继续由原独立 reviewer 审查）
- review_mode: `full`
- mode_reason: 用户新增 S6，变更公开发送工具、PA 自身发送权限和通用 OpenUI 动作，并扩大 M1 的客户端及上下文范围；涉及需求、核心边界与共享接口，不能只做旧 finding closure 或局部 delta。
- started_at: `2026-10-25T18:18:50+08:00`
- completed_at: `2026-10-25T18:23:49+08:00`
- duration: `PT4M59S`
- baseline: main `797b225df`，审查作者已暂存的九个 unit 文件；未修改这些文件。审查时相关 IM/PA/integration/双端实现相对 R1 基线 `e5856ec23` 无差异，现有实现仅用于判断改动落点，不作为新功能完成证据。
- artifacts: 更新后的 spec、design、四份 delta、prototype、design-evidence、deployment-prompt，以及 R1/R2 和 Author Resolutions。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

新版工具身份、发送权限、通用草稿采用和模型上下文方案闭合。此结论批准设计；不代表新工具、原生客户端或真实审核执行已实现，也不授予实施、发布或生产部署许可。

### Coverage 与证据

#### 用户约束与需求覆盖

已对照本轮 spec 原话和 S1–S6：`send_message` 保留 Agent 自身身份及成员写权限；绑定根 PA 的真实委托改用 `send_user_message`；普通 Agent/子 Agent 不获得代表能力。通用 ComposeMessage 适用于普通 Agent 和 PA，采用只预填输入框，取消、权限失败保留编辑，后续目标消息不触发旧草稿过期推断。删除新调用的 reply_draft 与模型填写 format/catalog_version，未新增草稿工具或默认代表模式。

S1/S3 的自然用户口吻、指代澄清、完整原始委托审核仍在；S2 的用户主头像姓名与 PA 次级标记、本人侧归属保持；S4 自身报告、草稿、伪造和越界继续区分；S5 的历史、恢复、子 Agent 继承仍保留既有范围而不新增许可或重复执行。新增工具名没有替代来源证据或正常执行审核。

#### 实际组装、工具与权限

再次从真实组装核对 `agent-config.ts` 的 GlobalMode / PersonalTools / Feature 安装、`capabilities.ts` 的 scope 限制与 product-contracts `fixedTools`。仅更改全局工具清单会使 PA 子会话继承新工具，设计已明确按根 PA 注册和产品边界双重验证；不以隐藏 schema 代替权限检查。

`product-bridge.ts` 将执行会话与 rootSessionId 分别传给产品；`global-agent.ts:378` 起校验产品绑定、处理正式调用，再进入 `personal.send`。因此现有可信调用身份足以区分根 PA/子 Agent，无需新授权票据。设计已将 product bridge、capabilities、tool-references 与实际注册一致性纳入清单。ToolReferences 对 external target 的短引用仍保留其类型，Compose 只接受明确原生 conversation id，未扩大到外部渠道。

`PersonalActions.prepare/validate/commit` 当前依赖 PA 来源可写并集，不能自然满足“PA 自身必须参与”的新限制。设计已要求两工具在正式边界及 prepare/commit 分别核验实际 Agent 或主人权限，representation 来自可信工具分支并进入冻结内容、去重和 planned_action；禁止把自身发送失败自动升级为代表发送。主人私聊、外部渠道、系统通知与 task action 的边界也明确。继续复用既有事务与独立审核，比新增代理发送服务或授权账本更简单且责任清楚。

#### ComposeMessage 的公开扩展与双端执行

独立核对已安装 `@openuidev/lang-core@1.0.1` 的公开声明：`defineAction`、`LibraryExtension.actions`、JSON schema 的 `actions` 和求值后的 `custom_action {name,params}` 都存在。`scripts/generate-interactive-ui.ts` 实际从 Web library 的 `toJSONSchema()` 生成共享 catalog、integration prompt 和随包 Skill，故设计的单一 catalog 源可复用，无需 fork 上游或再加模型工具。

同时核对真实消费端：IM `interactive-source.ts` 自建 parser 和 value library；iOS `Runtime/interactive-runtime.ts` 自建 parser/library，并在 activate 中处理 set/reset/run/continue/open_url；Swift `InteractiveRuntime.activate` 才拥有网络与原生 UI 副作用。新设计明确共享 parser/校验、iOS action 定义与 custom_action 事件、Swift host 都须接线，避免“Web 能解析，原生点击未知动作”的断链。

Web `InteractiveCard` 的 onAction、MessagePane 的每会话 composer 状态，以及 iOS `ChatStore.drafts/attachments` 提供所需现成责任边界。Compose 使用点击时求值的文本，由 host 检查源卡状态与实际登录用户的目标写权限，只导航/填稿；取消保持两处内容，替换显式清除旧附件，相同文本只聚焦。没有把该动作送入现有 continue_conversation/交互提交路径。共享校验禁止采用与 ToAssistant/Mutation 的隐藏混用，正常本地 Set/Reset 仍可用。真正发送继续经普通用户消息入口，不由卡片获得额外业务权限。

R2 的 executor 方案仍保留：公开作者与卡片执行 PA 分离，source/contexts/prepare/替换/生命周期使用实际 executor，owner 卡片仅在 PA 当前参与且可写时发布。Compose 的本地行为与需要 PA 接收的明确提交分开；readonly/fork/被替换旧卡禁用新采用。旧 reply_draft 入口退役已在设计和部署提示中明示，保留历史源码与审计数据，不猜测改写旧按钮。

#### prompt、回执、审核与历史

核对了当前实际冲突点：global-mode 要求公开回复用 send_message；intelligent-ui Feature 与生成 Skill 仍要求旧参数；Skill 仍写“一次点击记录用户消息”；`policy/approval.ts:118` 起仅识别 send_message 的 alwaysAllow 排除、产品审核与 messageContext；CC security_monitor 仅描述 send_message_result 和旧恢复限制。新版 context 清单覆盖这些实际路径，而非只修改工具名。

系统补齐协议字段在 publication/digest/审核之前完成；持久 wire 仍有必要字段，模型投影精简不裁剪交互内容、选择或可信原文。两工具的真实身份、完整标准化内容进入 planned_action，新工具不能因旧名称分支漏匹配而默认放行。固定提示、工具 schema、catalog/生成 Skill、wake/task/heartbeat、CC/Codex 与 PA 独立审核均使用相同身份与动作含义，用户 custom_prompt 保持不变。

来源链仍为 IM 可信公开消息 → RelayInput/Inbox 或正式 conversations → integration 来源段 → 当前及继承审核材料。`policy/approval.ts` 的 parent history/codexEntries 和 `sources.ts` 的 append/restore 是真实父子与恢复入口；两工具回执均须保留，只有 sent 证明送达，内部 accepted、本地采用、held/unknown 均不等价。设计明确实际组装 context 与真实模型选择验证，文本搜索不能替代运行验证。

#### 独立原型走查

本轮 IAB 不可用，使用独立 Chrome 本地原型标签走查；未使用生产聊天或修改作者文件。先看实际渲染和操作结果，再核对 V1–V4 与作者证据：

- Web 320、普通 E 编辑器：Agent 名字、目标“与 Q 的聊天”、编辑区、“采用到与 Q 的聊天”和“请继续修改”分离，窄宽下动作与编辑内容可读，普通 Agent 不被画成 PA。
- 将内容实际改为“Q，请只提交报告，不推送。”后采用：目标聊天输入框取得相同文字并聚焦，未出现新发送气泡。随后单独点发送才出现用户消息，且没有 PA 代发标记，说明本地采用与公开发言的后果可辨。
- 目标已有正文与附件：冲突框明确替换将只保留新文字；取消回到编辑器，修改值保留；再次采用并确认替换后进入目标输入框，仍未自动发送。
- iOS 构图、PA 编辑器、不可写目标：采用后停留原卡，显示不可写原因，修改后的“Q，先暂缓推送，等我确认。”保留；“请继续修改”另显示向本会话发起请求的结果，与采用反馈不同。

这些证明原型的内容关系与关键操作设计，不能证明真实权限、附件存储、原生键盘或 Swift action bridge 已通过。身份消息布局的 R1 独立观察仍适用；本轮没有将 iOS HTML 构图算作原生体验 pass。V4 已把新增双端采用、冲突、权限及 ToAssistant 区别映射到 M1 R2/W2。

#### delta、M1、资源与部署

四份 delta canonical target 正确。IM conversations-messages 的 MODIFIED 完整保留“刷新与节点离线”“分支与原会话删除”；IM personal-agent 仍保留编辑采用和真实回执。新增 Gateway agent-capabilities 承载通用交互和上下文语义，PA 专属工具边界归 personal-agent；没有把通用 Compose 仅写在 PA 契约内。

单 M1 保持一个完整身份/交付闭环，范围新增输入框、双端 runtime、catalog/generator/Skill 和审核模板，R2/W1/W2 对应新增行为。Runbook 包含普通/PA 编写、编辑后采用、同会话、冲突、无权限、后续消息、手动发送与原生旅程；两工具权限对照、根 PA 限制、实际恢复/子 Agent/审核 context 也有明确验证对象，未把审核成功当作执行结果。

资源可用性沿用 R1/R2 已核验的隔离 daily、模型回复及 Xcode/iOS 26.4；本轮只增加本地模拟动作，不依赖新外部账号或第三方权限。正式实现须重建独立实例，并真实验证新增模型 context 和原生桥接。作者报告的 docs-check 不替代上述门禁；本轮独立 `git diff --cached --check` 无错误。

部署仍要求协调 IM/节点/Web/在用 iOS 后开放新代表工具及 Compose，旧缺失 representation 的操作按 self 解码并重新满足成员权限；保留旧历史、旧草稿审计及未发送用户内容，不回填授权、不猜测源码迁移。未新增长期双轨兼容路径或生产操作授权。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R1-W1 | R2 已接受并明确独立 executor、参与资格与卡片验收 | 新版设计保留 source/contexts/prepare/替换/生命周期同一 executor，普通与代表工具仍独立审核；新增 Compose 没有把实际 PA 解析退回公开用户作者 | **closed** |

R2 无其他遗留问题。R3 对需求和共享接口重新做 full 判断，不以 R2 Approved 直接放行。

### Issues

无新增 CRITICAL/WARNING。

### Recommendations

无；停止于已覆盖的实质范围，不增加无关 UI 改造或假想兼容要求。

### Author Resolutions

- Round 3 无 finding；作者核对真实工具权限、公开动作扩展、双端执行与上下文覆盖证据，接受 Approved，0 CRITICAL / 0 WARNING。受审 spec/design/delta/prototype/部署方案保持冻结。
- 收尾仅把 design-evidence 的临时静态服务状态改为已停止，并追加本结论；没有实质方案变化，R3 证据 retained，无需再次复审。

## Round 4

### Metadata

- reviewer_target: `/root/feat658_design_review`（继续由原独立 reviewer 审查）
- review_mode: `full`
- mode_reason: 本轮将共享消息来源对象改为顶层可选 PA ID，并补充 S5 的联系 PA 行为及 M1 验收；涉及共享接口与需求，使用 full。完整重核身份、审核、历史与路由闭环；没有变化的原型交互保留此前独立观察，不重复启动服务。
- started_at: `2026-10-25T19:43:32+08:00`
- completed_at: `2026-10-25T19:44:40+08:00`
- duration: `PT1M8S`（本轮有计时的文档及代码核对区间，报告落笔另计）
- baseline: main `f31339119`；审查五个已暂存 unit 文档的实际 diff。相对 R3 基线 `797b225df`，IM、PA、integration、product-contracts 和双端实现目录没有变化。只追加本报告，不改作者产物、不暂存、不提交。
- artifacts: 当前 spec、完整 design、四份 delta、deployment-prompt、design-evidence，以及 R1–R3 和 Author Resolutions；原型本轮未修改。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

普通用户 sender 加可选 `pa_agent_id` 足以表达新消息的主体和实际代发 PA。简化没有撤掉发送前审核、卡片执行者或 PA 原始证据控制，也没有在接收端引入新的授权等级。本结论是设计通过，不代表字段、真实模型上下文或客户端已实现。

### Coverage 与证据

#### 用户要求、共享字段与实际消费链

spec 已保留用户关于“有无 PA 代回答、给 PA ID、方便直接联系”的原话与确认。D1/D3、消息示例、Inbox/历史说明、Gateway delta 和 M1 使用同一含义：sender 表达用户主体，顶层可选 PA ID 只表达本条实际代发者；普通亲发省略。新代表消息不带 delegation 对象、kind、authorized_by 或重复 PA 名字/标签，模型与公共发送请求不能填写该字段。

真实 `messaging.ts:330` 当前将旧代发表直接投影为 delegation；`RelayInput.message` 尚无该来源字段；`inbox.ts:258` 和 `work.ts:722` 起均独立组装消息片段。新版设计已明确由 IM 受控事务的同一 `message(id)` 投影产生新字段，再贯穿事件、relay、Inbox 每片、正式历史查询和审核/恢复/子 Agent，不假定只改 TypeScript 类型便能自然传递。旧行继续保留 Agent 作者和 UI 标签，不从旧对象反填新字段，也不新增旧对象到模型上下文；既有原始记录无需破坏性改写。

S1–S4 的用户主身份、自然口吻、实质歧义澄清、范围限制及自己发言区别保持；S6 的两工具和通用草稿采用保持。新增 S5 使用字段定位实际 PA，没有新增联系人服务或权限协议。现有 `work.ts:549` 起的 resolve_target 与 `messaging.ts:738` 起的 `agent:`/Agent ID 解析提供寻址入口，仍执行原会话和空间访问限制。设计明确后续联系经过这些现有路径；PA ID 本身不赋予联系或读取私人 Work 的权限。

#### 审核、来源说明与恢复

从真实组装核对 `agent-config.ts:105` 安装 GlobalMode；`global-mode.ts:15` 的来源段目前只在 global 注入，`classifier.ts:16` 和 `codex-context.ts:35` 已引用共享 inboxSourceInstructions。设计复用这一个说明来源，仅增加约定的三句字段解释，并明确补齐 SingleThread/执行子 Agent 的实际系统上下文；不是只把字段放进数据后假定模型知道它。每条消息结果只携带数据，不重复附解释，不覆盖用户 custom_prompt。

`single-thread.ts:119` 起现在将消息转为正文和来源 envelope；`policy/sources.ts` 的 humanInputs、appendResult、restoreEntries 与 `policy/approval.ts:59` 起父子继承均是必须适配的真实消费路径，已被设计清单和 M1 的实际 context 证据覆盖。旧历史规则仍需区分“保留已有用户委托”与“产生新许可/事件”，两种审核 provider 也同步该语义，不能只改普通 Agent 提示。接收端按普通用户规则理解正文并审核实际动作，三句说明不承担完整授权算法。

发送前真实原始委托、披露、完整 payload、受众、guard、两次权限检查、permit 和幂等事务仍保留；内部 representation 与 representation_operation_id 不因公开字段减少而删除。PA 专属原始证据排除与普通接收者规则分开：`personal-agent.ts:128` 的 directOwnerMessage、messageEvidence、authorizationGuard，及 `personal-actions.ts` 的 last_owner_message_id 均被设计明确列入排除代发的路径，避免自身公开表达成为新的主人原话。

#### 路由、卡片与架构判断

`messaging.ts:645` 的用户消息 relay 将消息投影作为 payload，能够沿用既有目标、群策略和去重。新版设计仍要求排除实际发送 PA，并覆盖观察 feed；Slash 控制不能因 sender 变成 user 而触发 `/stop`、`/new` 或来源设置。普通接收者继续读作用户消息，控制证据的排除由产品与 PA 专属指导承担，没有把额外的 PA 授权判断散布给所有 Agent。

R1-W1 的卡片方案没有退化：`Interactions.source/contexts/prepare/record` 仍从内部受控 operation 关联解析同一 executor，不使用公开用户 username 截取 Agent ID，也不把简化后的公开字段当作客户端签发的执行身份。owner 卡片要求 PA 当前参与、可用且可写；提交者仍是实际点击用户，同 PA 替换逐次重新审核。公开来源精简与内部执行资格各自有明确职责。

与额外代表对象、授权等级或独立身份表相比，当前方案复用用户作者、旧代发表与审核事务，只增加一项实际需要的公开 ID。IM 保有消息和身份事实，PA 编排发送/收件，integration 维护模型来源及审核，客户端本地化标记；依赖方向与 R3 一致，未新增 DSH 私有接口或运行时机制。

#### 前端、delta、M1 与部署

- `retained_from: Round 3` — Compose 原型、V1–V4 内容关系、交互动作和冲突/失败状态未变；R1 的身份布局与 R3 的独立编辑采用走查继续适用。本轮唯一文案调整是屏幕阅读标签改为“用户名字，由 PA 代发”，与不再提供额外 PA 名称相容，不需要新布局或新交互。未启动原型、真实服务或模拟器；原生 VoiceOver 和真实客户端仍由 M1 检验。
- 四份 delta 的 canonical target 与未变 Scenario 保留正确。Gateway personal-agent 增加普通 sender/PA ID 的消费者含义及按用户要求联系 PA，其余三份无需重复协议字段。S5、Runbook 旅程 4、M1 R3 对应联系正确 PA；旅程 5、W1 验证真实 context 的字段唯一、亲发省略、旧历史不回填，未把本轮文档审查当作实际模型通过。
- 单 M1 的工具身份、审核、双端、历史/子 Agent 与卡片退出标准完整保留；不产生并行实施冲突。资源可用性 `retained_from: Round 1–3`，本轮没有新外部资源前置，也不将旧资源探针升级为新功能证据。
- deployment-prompt 保留协调版本后启用、旧操作 self、旧数据不升级、停止新代发后前向修复，并补新投影及旧标签不回填核对。内部 nullable operation 迁移不因公开对象删除而改变。独立 `git diff --cached --check` 无错误。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R1-W1 | R2 已闭合独立 executor、参与资格与卡片验收 | R4 仍以内部 representation_operation_id 对应 PA 解析 source/contexts/prepare/替换/生命周期；公开来源改为可选 ID 未撤销此方案 | **closed** |

R2/R3 无其他遗留 finding；本轮依据实际字段变化及消费链重新判断。

### Issues

无新增或遗留 CRITICAL/WARNING。

### Recommendations

无。当前简化已经满足确认范围，不另加身份元数据、授权解释或兼容分支。

### Author Resolutions

- Round 4 无 finding；作者核对共享字段、简短来源说明、内部审核/卡片身份与实际消费链，接受 Approved，0 CRITICAL / 0 WARNING。受审产物无后续实质修改；未启动服务，无新增清理项。
