# feat-617 Design Review

## Round 1

### Metadata

- reviewer target: `/root/genui_design_review`，独立 reviewer；未参与受审 spec/design/prototype 编写。
- review_mode: `full`
- mode_reason: 首轮 Gate 2，覆盖需求、现状、设计决定、接口、delta、原型和 milestone。
- started_at: 2026-10-19T15:13:35+08:00
- completed_at: 2026-10-19T15:19:03+08:00
- duration: 328 秒
- baseline: `main` / `e7088f9d5e84d98663e42803b94ab788ed517702`；已核对既有 dirty/untracked，未修改它们。
- 冻结范围：`spec.md`、`design.md`、`specs/**`、`prototype.html`、`M1-interactive-replies/.gitkeep`、`evidence/prototype-review.md` 及代表性截图。研究包仅作为选型支持材料。
- 本轮仅写本报告；未改产品代码、未运行产品测试、未重启或写入 feat-616 现场。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

总体职责、选型边界和交互方向成立。R1-W1 是带选择的普通文字如何保存和去重的接口歧义，会直接影响“先别发送”等用户真实指令；需要作者收口后复核。当前不通过 Gate 2。

### Coverage 与证据

#### 现状与真实组装入口

- 从 `apps/node/src/main.ts:230` 起核对 `SingleThread`、`GlobalAgent` 的实例化，以及 `runtime.handle('product.call', ...)` 确实转给 GlobalAgent 产品桥接；`packages/dsh-integration/src/agent-config.ts:86` 为实际运行配置安装 GlobalMode。`global-mode.ts:27` 的公开 send_message target/text 分支与 native agent_id/message 分支实际存在，普通模式只过滤 inbox。因此普通 Agent 复用显式公开发送是已有接线，不是新增第二套执行环。
- `packages/personal-assistant/src/global-agent.ts:237` 的发送目前比较 target/text、准备 publication 并调用 agent.message；`apps/im-server/src/gateway.ts:504` 实际接收并解析可信 Agent、dispatch key、目标权限，再写消息。设计明确把 interactive 纳入 publication、Node 和 IM 重试比较，定位正确。
- `apps/im-server/src/server.ts:83` 实例化 Messaging/Gateway，并在 `:166` 注册真实消息 routes。`messaging.ts:347` 插入消息并创建事件；`:453` 起处理真实用户发送，`:537` 构造持久 relay。设计要求 message/interactive、确认快照/本人消息/relay 在同一事务提交，是对现有路径的必要扩展；当前代码并不已具备该原子交互流程。
- `packages/product-contracts/src/index.ts:31` 的 RelayInput 目前没有交互结构；`single-thread.ts:112` 由 message.content 构造普通输入；`inbox.ts:98`、`:115` 将 Global 消息投影成可读内容。设计同时覆盖两条输入路径是必要且正确的，正文保留问题见 R1-W1。
- Web 真实路由 `src/IM/frontend/src/app/router.tsx:38` → ChatWorkspacePage → `components/message-pane.tsx:1039` 的 MessageBubble；`chat-api.ts:48` 的 CreateMessageRequest 明确含 content，实际 createMessage 按原文发送。新增可选交互字段应接此路径，不另建聊天 shell。

#### 需求、边界与架构判断

- 需求覆盖任意普通/Global/Personal Agent，行程、草稿和提醒均使用通用组件；feat-616 不作为依赖，不复用其 incidents 特殊协议。简单回答仍文字，生成期间沿用运行态，Web 之外保留可独立阅读的 text，符合已明确的首版切片。
- OpenUI 只承担语言、组件、局部状态和渲染；身份、公开交付、草稿、去重、历史与调度仍归 Nano。product-contracts 放纯 DTO/生成数据，IM 不加载 React/DSH，dsh-integration 通过公开 DSH 接缝接入。相比引入上游 chat shell 或重新建设消息服务，当前复用方案没有可见的多余运行机制。
- 单一 catalog 源经构建产出模型提示与服务端 library spec，避免手写两个组件列表；ContinueButton 只提交可见动作和用户状态，实际业务仍由 Agent 使用已有工具完成。不可变消息和新消息 supersedes 简化了历史与重放，个人草稿独立于群公开确认，责任归属合理。
- 已核对 [固定 commit 的 Renderer](https://github.com/thesysdev/openui/blob/8d9c4c3b108a7b5352192a6a9d7327bdf7ea19b5/packages/react-lang/src/Renderer.tsx)：公开 response/library、onAction、onStateUpdate、initialState 可支持拟用接缝；initialState 同时包含表单和 reactive 变量。结合 [官方交互文档](https://www.openui.com/docs/openui-lang/interactivity)，没有发现必须引入托管模型或其聊天壳的约束。本轮没有安装和运行固定 npm 版本，也没有证明该版本在本机模型上的 DSL 生成成功率；M1-W1 明确把固定版本实际生成/渲染验证放在起点，失败先改设计，不悄悄接第二引擎，此证据边界可接受。
- source 校验、披露审查、实际 user 来源、群内定向唤醒、草稿 CAS、本人唯一提交、只读 fork 与外部文字回退已有明确目标；本轮不要求提前实现它们或增加通用权限平台。完整请求语义的保存/重复比较仍缺一处决定，见 R1-W1。

#### 独立体验判断

先看实际画面并操作，再核对作者记录。独立打开 `http://127.0.0.1:8767/prototype.html`，当前浏览器为 1280×720；另查看作者已渲染的 1440×1000、768×900、390×844 代表性图片。当前产品对照查看 `/tmp/feat617-baseline.png`（作者从既有 feat-616 实际页面取得，本轮未接管或修改该服务），并对照真实 MessageBubble 路由与组件。

- 行程：独立改出发时间为 11:00、勾选博物馆，滚到当前选择和继续按钮；摘要与动作相邻，提交前不需要记住屏外字段。提交后只有一条本人确认消息，卡片字段禁用，另有 Agent 继续细化的回复。浅灰 Agent 内容、浅绿本人消息、主列表滚动和常驻输入框延续当前产品的身份与阅读关系。
- 草稿：独立修改正文，再在普通输入框发送“先别发送，把语气改得随意一点”。原型的本人消息同时显示限制语和修改后的草稿，演示回复明确先不发送；这构成 R1-W1 要求保留的具体产品语义。窄屏对应画面见 [手机文字附带选择](evidence/prototype-mobile-context.png)。
- 通用提醒：独立触发提交失败，看到“未能提交，当前选择已保留”与重试入口；切至已有更新后按钮禁用、普通输入仍可用。该例由文字/布局/动作构成，没有把隐私业务做成必须采用的专用 UI 协议。
- [窄桌面](evidence/prototype-compact.png) 保留侧栏后字段上下排列；[手机初始](evidence/prototype-mobile.png)、[提交状态](evidence/prototype-mobile-submitted.png) 和 [降级](evidence/prototype-mobile-fallback.png) 可辨认内容、选择、主动作和输入。卡片较长，但随主列表滚动，按钮与选择总结相邻；没有足以阻断当前方案的视觉或交互问题。浏览器实操为桌面；手机/768 尺寸的本轮判断来自现有实际渲染图片及作者操作记录，未声称独立完成手机软键盘或跨设备试验。
- 原型是手写模拟，视觉通过不证明 OpenUI 能产出同等内容，也不证明提交、业务执行或持久化。must-match 已对应 R1/R2/R3 与 W2，导航背景和演示控制也明确标为 out-of-scope。

#### Delta、milestone 与验收前置

- 三份 delta 分别锚定现有 `docs/specs/im/conversations-messages.md`、`docs/specs/im/web-chat-ux.md`、`docs/specs/gateway/agent-capabilities.md`，使用 ADDED Requirements，未删除或改写既有 Scenario；消息授权/历史、Web 交互、Agent 能力的消费者划分合理。仍须通过 R1-W1 保证“带当前选择发送文字”的真实语义。
- 单一 M1 覆盖 DTO → 工具/PA → IM → Web 完整纵向旅程，没有假并行分工或依赖 feat-616。R1/R2/R3 覆盖真实模型、不同任务、三种宽度、本地交互、两条输入路径、草稿隔离、失败、替代、fork 和文字回退；W1/W2 对应版本验证、窄测试及原型对照。
- Runbook 指定本 unit 自己的 worktree、e2e-up/down、health 与 node ready、两测试账号和测试群；外发限定第二测试用户。资源证据明确记录本机模型 HTTP 200、正文 OK 和 end_turn，足以证明验收入口可用，不能推导 OpenUI 生成已通过。无需真人联系人或生产变更；本轮未新增验收资源缺口。

### 历史问题闭环

无；本轮为首次独立设计审查。

### Issues

#### R1-W1：带选择的手写正文与完整提交身份尚未闭合

- 严重性：WARNING。
- 位置：`design.md:96-102`，关联 `:106`；Web delta 的“调整后继续”与原型草稿修改路径。
- 证据：POST 定义只描述新增 interaction_reply；虽然说复用 createMessage，但紧接着规定“公开消息的 content 是服务端基于可见 label 与字段值生成的简短摘要”。这与真实 createMessage 的用户原文 content 发生重叠。模型输入段仅说从持久快照取得 text，没有说明 typed content 被存在哪、如何与服务器摘要组合。唯一提交规则又只规定“表单内容不同”时 409，未覆盖同样 state、不同手写正文或不同 action 的请求。
- 具体后果：原型已演示“先别发送，把语气改得随意一点”必须和草稿一起进入本人消息与模型；按当前摘要替换规则实现，可能只保存草稿/选择而丢掉停止发送的指令。多设备或不确定结果重试若 state 相同但正文/按钮不同，还可能把不同意图当作同一提交成功，公开回显与用户刚刚发出的要求不一致。这是已纳入核心旅程的输入语义问题，不是假想新功能。
- 修订要求：明确按钮提交与普通文字附带选择的请求/持久快照/公开正文/PA 输入映射。普通文字原文须原样保留，服务器生成的选择摘要独立标识；可继续复用既有 content，不要求增加另一套消息 API。相同 source/user 的幂等比较应覆盖本次语义有效的 action_id、用户原文和规范化 state；内容相同返回原结果，不同则明确冲突。补一组“先别发送 + 已改草稿”从请求到普通 Relay/Global Inbox 的示例及对应窄验证预期即可。
- 状态：open。

### Recommendations

无额外建议。保留当前有界选型和单一 M1，不因本轮问题扩大原型、引入第二引擎或提前实施产品代码。

### Author Resolutions（Round 1）

- **R1-W1 — accepted**。核对现有 createMessage.content 与原型草稿路径后确认歧义成立。design 的“用户状态与提交”明确区分按钮（省略 content，服务器取可见 label）与手写（content 原样保存）两种路径；选择摘要独立保存在 interaction_reply_json，并作为本人消息附加区展示。PA 的普通 Relay 与 Global Inbox 均保留 content 原文再追加选择数据。
- 完整提交身份比较 source、实际用户、action_id、typed_content 和 canonical state；不同意图返回 409 并保留新输入，不能只比较表单。新增“先别发送 + 已改草稿”贯通示例与 W2 验证预期，同时补入 IM 消息 delta。
- 原型已呈现上述语义，无需修改原型、选型或 milestone 骨架。受审变更限 `design.md` 与 `specs/im/conversations-messages.md`；本段为作者追加，未改 reviewer 原文。研究支持文件仅补 docs-check 必需 frontmatter，无结论变化。


## Round 2

### Metadata

- reviewer target: `/root/genui_design_review`，与 R1 相同的独立 reviewer，未参与作者修订。
- review_mode: `closure`
- mode_reason: 本轮修订是 R1-W1 所要求的局部语义闭合：保留手写正文、区分选择 snapshot、完整比较提交身份，以及对应 delta/验证示例。没有引入新消息 API、变更职责或选型、扩大需求和 milestone，现有上下文足够核对；因此不重复 full 审查。
- started_at: 2026-10-19T15:20:45+08:00
- completed_at: 2026-10-19T15:21:42+08:00
- duration: 57 秒
- baseline: `main` / `e7088f9d5e84d98663e42803b94ab788ed517702`；本轮仍仅追加本报告，保留原 R1 与 Author Resolutions。
- 受审修改：`design.md` 的用户状态与提交段、`specs/im/conversations-messages.md` 的正文保留要求及新增 Scenario。研究支持文件只增加 frontmatter，不改变本轮判断依据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1 已关闭，当前冻结设计通过 Gate 2。此结论是设计审查通过；OpenUI 固定 npm 版本与真实模型生成/渲染、真实客户端及持久化链路仍按 M1-W1/W2/R1–R3 验证，未提前宣称实现或产品验收通过。

### Coverage 与证据

- `retained_from: Round 1`：需求、真实产品组装入口、开源复用边界、模块职责、其余接口、三份 delta 的 canonical 归属、原型视觉/操作、milestone 与验收前置沿用 R1 证据。原因是本轮仅将原型已表达的文字加选择行为明确到服务器和 PA 的契约，未改变 UI 内容关系、组件交互、其他客户端范围或运行拓扑。无需重新渲染未改的原型。
- 本轮重读 `design.md:94-115`、完整 IM 消息 delta 和 Author Resolutions，并重新核对真实 `chat-api.ts:59` 的 content 发送、`single-thread.ts:112` 的普通输入以及 `inbox.ts:115` 的 Global 文本投影。修订继续沿用这条正文链，选择数据附加在持久正文之后，没有把原文改写成摘要或转为 system 指令。
- 本轮没有运行产品测试，没有修改设计/代码，没有访问或重启 feat-616 服务。新增验证预期是后续实施验收要求，不作为已完成证据。

### 历史问题闭环

#### R1-W1 — closed

- **Author Resolution**：accepted；区分按钮与手写路径，完整比较 source/user/action/typed_content/canonical_state，正文和选择摘要分开保存；补“先别发送”贯通例与 delta。
- **本轮核实**：
  - `design.md:104-107` 明确按钮省略 content，由服务端 registry 的可见 label 生成正文；普通输入框 content 原样保存，选择快照与摘要独立存在 interaction_reply_json。混合请求返回 422，按钮在既有非空校验前生成可信正文，两种入口可直接实施。
  - `design.md:109-111` 明确普通 Relay 和 Global Inbox 均保留持久化 content，再附加有来源标识的选择数据；示例包含“先别发送，把语气改得随意一点”及已改草稿，并要求 REST、历史/事件和两条 PA 输入分别验证。
  - `design.md:98` 明确相同 source/实际 user 下比较 action、原样 typed_content 和 canonical state；语义相同返回原消息，任一不同返回 409 并保留新输入。已成功提交之后卡片被替代也先按历史提交比较，避免同一次成功重试被当作新的旧卡片动作。
  - `specs/im/conversations-messages.md:19` 与 `:29-32` 将正文保留和不同意图冲突写为消费者可观察契约，与 Web delta 和 R1 实操的原型相符。
- **关闭理由**：原问题中的“手写限制语被选择摘要覆盖”和“相同表单下不同意图误报成功”均已得到明确的请求、保存、回显、模型输入及去重规则；没有遗留需下游自行猜测的实质决定。

### Issues

无新增 CRITICAL / WARNING；无历史未关闭问题。

### Recommendations

无。

### Author Resolutions（Round 2）

作者核实 R2 的 R1-W1 closure 与 retained 范围，接受结论；无剩余实质问题。R2 后未修改首文档、设计、delta、原型或 milestone。仅追加本段结论与提交本轮产物，Gate 2 retained。

## Round 3

### Metadata

- reviewer target: `/root/openui_restore_design_review`，本轮新独立 reviewer；未参与受审设计、原型或产品实现。
- review_mode: `full`
- mode_reason: 用户否定原静态表单切片，本轮同时改变能力范围、原生事件接口、状态快照、多次请求身份、工具接线、patch 发布和 M1 退出标准；R2 closure 的范围不足以覆盖，不能继承其 Approved 结论。
- started_at: 2026-10-19T17:30:00+08:00（约；入口未记录秒级时间）。
- completed_at: 2026-10-19T17:41:22+08:00。
- duration: 约 11 分钟，含源码核对及独立 Chrome 原型操作；开始时刻为估计值。
- baseline: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-617` / `unit/feat-617`；冻结 HEAD `d44e176a0f68be2683f08333673607187d733fc5`，此前交付 `cf4b17f00`。开始时 `git status --short` 为空，定稿前 HEAD 未变。
- 冻结范围：新版 `spec.md`、`design.md`、三份 `specs/**`、`prototype.html`、`evidence/prototype-continuous-review.md`、响应式 wrapper 与截图。旧产品和旧报告仅用于现状、兼容性及既有交付证据。
- 本轮仅追加本报告；未修改产品/配置、未调用模型、未重启隔离服务，未触碰主 checkout、feat-616 或生产。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

恢复完整 OpenUI 能力、连续本地探索和按请求去重的方向符合本轮用户要求，独立原型操作未发现阻断体验的问题。但原生事件适配与固定版本真实契约不一致，delta 的归并类别仍沿用首次实施前的状态，保留数据的验收重启路径也未落实。三项关闭前不通过 Gate 2；不要求提前完成真实模型产品验收来关闭设计问题。

### Coverage 与证据

#### 现状与真实组装入口

- `src/IM/frontend/src/features/chat/components/message-pane.tsx:79,268,1794` 实际 lazy-load InteractiveCard，并从本人历史提交推导 submittedIds；`interactive-card.tsx` 以 submitted/done/readOnly 锁定 Renderer 和 fieldset。`catalog.tsx` 当前主动删除上游组件、覆盖 Form、关闭 toolCalls，并将 plain questions 归为 plain text。`apps/im-server/src/interactive-source.ts` 当前拒绝 Action/Set/Reset/Query/Mutation，要求静态具名表单。因此设计所针对的收窄确实存在于产品组装路径，非只在 fixture 中存在。
- `apps/im-server/src/messaging.ts:488,521-537` 的真实发送路由调用 Interactions.prepare，并在同一事务中保存本人消息、确认和 relay；`interactions.ts` 当前以 source/user 查旧提交，writeDraft 通过 `submission_message_id IS NULL` 锁定，替代/fork 通过 writable 拒绝新提交。多次请求必须同步调整这些服务端条件以及 Web 的 submittedIds，而不只移除按钮 disabled。design 已列出请求键、迁移和提交锁的目标，落点与现有职责一致。
- `packages/personal-assistant/src/single-thread.ts:117` 和 `inbox.ts:115` 均调用 product-contracts 的 withInteractionContext；该 helper 目前仅附带 fields/selected_action，新的原生 message/context 与通用绑定变量必须进入新快照及这两个真实输入路径。design 的 PA 上下文范围、来源标记和 M1-R2 已覆盖目标；原生回调到底提供什么仍存在 R3-W1。
- `packages/dsh-integration/src/agent-config.ts:95,148` 的真实 Features 组装，以及 `global-mode.ts:27-30` 的 send_message schema，是生成指导和 patch envelope 的实际接缝；`global-agent.ts:241-243,292` 已有 Feature 禁止新卡片、publication identity 和外部渠道文字分流。设计继续使用这些接缝，不引入第二执行环。

#### 用户约束与架构判断

- spec 保留 only617、不接入 feat-616、Features 默认开启及关闭后历史可读；普通/Global 均可使用。指定原话“给我讲解下冒泡排序”、不得提示生成交互、不得在组件/提示/Skill 植入题目专用逻辑，以及另选跨领域普通问题，都进入 Runbook 与 M1-R1。本轮原型用运动关系演示设计，没有被当作模型样本或冒泡排序验收结果。
- 完整上游组件、状态、条件/Each、本地动作、Query/Mutation 与 patch 不再被静态表单限制裁掉；真实宿主能力仅声明 conversation_messages 与 continue_conversation，明确未接入文件编辑能力。这符合“保留 UI 能力、业务工具遵守既有权限”的边界。
- 职责选择合理：Web 承担 Renderer 与当前用户 REST 适配，IM 承担公开版本/私有状态/请求身份，PA 承担来源与公开交付，DSH integration 承担模型能力指导。复用现有 listMessages、消息 API 和 relay/Inbox，比新增通用工具代理或聊天服务更小；没有发现需要另起通用权限框架的理由。
- 固定 npm 安装中核实 react-lang/lang-core 1.0.1 与 react-ui 0.18.1：lang-core 公开 exports 包含 createParser/evaluateRoot/mergeStatements；react-lang RendererProps 公开 toolProvider、onAction、onStateUpdate、initialState。完整库、工具 provider 与 patch 使用公开接缝可行。具体 ActionEvent 的标签和状态语义不支持 design 当前假设，见 R3-W1；不能仅因同名 API 存在就判定接口闭合。
- patch 采用同作者同会话、同事务验证和完整源落库、保留原始发布输入比较重试，避免把补丁输入与归并结果错误比较；按请求键去重替换 source/user 唯一键，同时保留不可变确认快照，适合连续探索。旧 ContinueButton 只作为已存在历史兼容，不要求保留旧能力收窄。

#### 独立体验判断

先独立查看真实渲染并操作，再核对作者走查记录。本轮使用 Chrome / cua_repl 打开提供的原型服务，桌面窗口实际 1538×944；随后打开 `evidence/prototype-sizes.html` 的 768×900 与 390×844 iframe。基线对照查看旧产品的 [桌面截图](evidence/product-desktop.png) 及 [实施浏览器记录](evidence/implementation-browser-review.md)。

- 桌面：先有普通问题和简短解释，探索区内依次是运动方式、位置图、时间/速度/距离、参数、本地操作和当前解释。独立点“下一秒”，2 秒/4 米变为 3 秒/9 米；“解释当前结果”留下当时快照。随后切匀速、再下一秒、再次解释，得到第二条 4 秒/2 米每秒/8 米请求，第一条仍为匀加速的原状态。用户可从同一内容区看懂参数与结果对应，不需要把本地操作误当成连续聊天请求。
- 手机：独立点下一秒和解释，再点重置；UI 回到 2 秒/4 米，旧请求仍保留 3 秒/9 米，底部出现可取消的“附带当前探索状态”。参数上下排列，本地三按钮可读，解释按钮整行；主聊天滚动能触达操作，输入入口保留，没有第二层卡片纵向滚动。中等宽度保留列表和聊天关系，参数纵向排布，没有看到关键控件被裁切。
- 相比旧产品，原型保留摘要先于交互、本人消息与 Agent 内容分离、底部输入及主列表滚动；增量是探索反馈与多次请求。原型用运动数值演示可理解的变化关系，非仅展示“有按钮”。按钮解释请求显示等待回复，不冒充最终业务完成。没有因视觉风格偏好提出阻断项。
- 原型仍是手写模拟，不能证明上游 Renderer、真实模型、持久化或 Query/Mutation 已成功。刷新/CAS/离线/替代等旧证据只作为既有体验参考；新状态语义仍须 M1-R2/R3 实际回归。手机为真实 CSS iframe 观察，不声称设备软键盘或原生 iOS 验证。

#### Delta、milestone 与验收前置

- 三份 delta 的 canonical target 与消费者归属正确；但首次交付已把旧条目归并入 current，当前全部标为 ADDED 会保留互相矛盾的旧提交语义，见 R3-W2。
- M1-R1/R2/R3 和 W1/W2 覆盖无交互提示真实生成、本地探索、多次请求、权限/私有状态、patch/fork、Features 与跨宽度，原型 must-match 有对应出口。无需拆成第二套生命周期，也无需扩大至 feat-616 或原生客户端。
- 隔离栈 `http://127.0.0.1:58769/health` 本轮只读返回 `{"status":"ok"}`；账号、普通/Global Agent 和模型由 Runbook 指定，旧真实产品证据提供既有资源来源。此检查只证明 IM HTTP 健康，不证明新功能或模型在线。Runbook 引用的工作树文档没有落实“保留现有数据重启”且推荐脚本会删除数据库，见 R3-W3。

### 历史问题闭环

#### R1-W1 — closed（原问题关闭保留；新事件缺口另记 R3-W1）

- Author Resolution / R2：手写正文原样保存，独立选择摘要，完整语义去重。
- 本轮证据：新版 design:61 保留手写原文与生成附属上下文区分；:63 要求同键同语义返回原结果、不同语义冲突；IM delta:34-37 保留“先别发送”例及正文/状态/动作比较。当前 messaging.ts:527 与 withInteractionContext 仍保留正文链。
- 原“摘要覆盖手写限制语”的问题没有重新出现；source/user 终身唯一则被用户明确要求的多次探索替换为请求级幂等。R2 对旧表单整体设计的 Approved 不延伸为本轮通过。

### Issues

#### R3-W1：原生回调没有设计所依赖的完整标签与状态，适配契约尚未闭合

- 严重性：WARNING。
- 位置：`design.md:15,61-70`。
- 证据：固定安装 react-lang 1.0.1 的 `dist/exports-CLfR509v.mjs:601-606` 中 getFormPayload(formName) 对具名 Form 仅返回 `{[formName]: raw}`，否则才返回完整 store snapshot。`:637-644` 的 ToAssistant 回调把 `step.message` 放到 humanFriendlyMessage，params 只含 context，并没有传入 Button label；Button 虽调用 triggerAction(label, formName, action)，这个 label 在 ToAssistant 分支已被丢弃。lang-core `dist/index.d.cts:284-296` 的 ActionEvent 也没有单独的可见 label/full-state 字段。Mutation 的 toolProvider 仅得到 args，更没有该事件对象。
- 未修后果：按“原生事件携带可见按钮标签”“Web 使用事件自身当前 state”直接实现，会把模型生成的 ToAssistant message 当成用户看到的按钮文字，或丢失 Form 外的 `$` 绑定和独立输入。例如用户在图表区调整参数后点击 Form 中的继续按钮，持久快照与 Agent 输入可能只有该 Form，不能复现用户刚看到的结果。原型展示的“实际标签 + 当时完整状态”不能靠目前声明的接口自然取得。
- 修订要求：在不裁剪本地能力、不 fork 上游的前提下，明确实际宿主适配决定：可见动作文字如何取得或以什么明确区分来源的文案替代；完整当前状态如何与事件的 formState 合成，Set 后紧接 ToAssistant/Mutation 时采用哪个时点；Mutation 复用提交时如何取得同一快照。给出一组含 Form 外绑定、Form 内动作、不同 Button label/ToAssistant message 的端到端字段映射，以及对应窄验证。这里需要收口接口与用户回显语义，不要求本轮实现适配代码。
- 状态：open。

#### R3-W2：恢复 active 后的 delta 未切换到现有 canonical 基线

- 严重性：WARNING。
- 位置：三份 `specs/**` 的 `## ADDED Requirements`；尤其 `specs/im/conversations-messages.md:17-37`。
- 证据：当前 `docs/specs/im/conversations-messages.md:523,535`、`web-chat-ux.md:567`、`gateway/agent-capabilities.md:739,751` 已含同名条目。current IM 仍写“已提交或被替代的卡片”再次提交返回原结果；新 delta 则要求后续新请求独立保存。`docs/specs/CONTRIBUTING.md:142-154` 明确 ADDED 追加、MODIFIED 替换同名完整条目。
- 未修后果：按声明归并会重复 Requirement 并留下“一次提交即终身返回旧结果”与“可多次提交”两套相反契约，实施者/验证者无法据此确定正确行为。不是纯格式问题。
- 修订要求：以冻结 HEAD 的 current 为基线重分 ADDED/MODIFIED；真正新增的连续探索等条目仍 ADDED，已变更的同名条目用 MODIFIED 并带全未改变 Scenario，完全未变化的条目不重复追加。明确旧单次提交 Scenario 由请求级幂等替代，保留既有权限、fork、外部文字和 Features 契约。
- 状态：open。

#### R3-W3：Runbook 宣称的保留数据重启路径不存在于所引用流程

- 严重性：WARNING。
- 位置：`design.md:97-101`。
- 证据：design 要求保留 58769 栈和运行数据，并称“保留数据重启按 worktree-runtime.md”。该文档推荐 `e2e-up.sh`，且明确写明启动清理旧 E2E 状态；实际 `scripts/e2e-up.sh:161,182-189,222-224` 重分端口/配置并删除现有 IM sqlite/WAL/SHM 与绑定状态。该文档没有针对当前栈的保留数据重启命令，另一个“手工调试”段还列旧 Python IM 命令，不能作为当前 Node 栈实施后复验入口。
- 未修后果：下游为验证新 build 而照推荐脚本起栈会销毁本次保留的用户实测、旧消息兼容和历史数据；若完全不重启，则可能测试旧 build。两者都会破坏本轮验收前提。
- 修订要求：在 unit Runbook 写出或链接实际可用的本栈停止、构建、保留原端口/config/DB/identity 的启动及健康/Node 就绪检查命令，明确常规 e2e-up 是新现场入口而不能用于本轮保留现场。只需补此 unit 的真实复验路径，不要求扩展成生产部署流程；本轮 reviewer 未执行任何重启。
- 状态：open。

### Recommendations

无额外扩展建议。修订应限于上述接口、delta 归并和验收入口，保留完整 OpenUI 与通用生成目标。

### Author Resolution / R3

- R3-W1：以 click capture 可见标签与 Renderer message/context 分离；onStateUpdate 完整 ref + 具名 formState 合并，Set 后立即冻结，Mutation 共用提交。设计给出具体 Form 内外状态/不同标签映射及窄测试。
- R3-W2：按 current 基线整理：IM 修改交互确认完整 Requirement，Web 仅新增连续探索，Gateway 修改任务表达并新增普通提问；未变条目不重复。旧单次提交 Scenario 被请求级幂等完整替代。
- R3-W3：Runbook 补入当前栈保留数据 stop/build/start/health/status 命令与 PID 验证，明确禁止重跑会清库的 e2e-up。


## Round 4

### Metadata

- reviewer target: `/root/openui_restore_design_review`，与 R3 相同的独立 reviewer；未参与作者修订。
- review_mode: `closure`
- mode_reason: 修订仅闭合 R3-W1 的宿主事件映射、R3-W2 的 delta 归并类别和 R3-W3 的保留数据复验入口；需求、核心模块职责、原型和 milestone 未变化，R3 full 的其余证据仍有效。
- started_at: 2026-10-19T17:44:04+08:00。
- completed_at: 2026-10-19T17:45:42+08:00。
- duration: 98 秒。
- baseline: `unit/feat-617` / `55c0b23f4630a273ad4be449534cb0f2f9931254`；开始时 working tree 干净。
- 受审范围：`design.md:61-73,99-122`、三份 delta、R3 Author Resolution。本轮仅追加本报告；未执行重启、模型调用或产品改动。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R3-W1/W2/W3 均关闭，本轮冻结设计通过 Gate 2。该结论不代表普通提问已生成交互，也不代表新版代码、真实客户端和持久化已验收；这些仍须按 M1-R1/R2/R3/W1/W2 完成。

### Coverage 与证据

- `retained_from: Round 3`：用户普通提问与跨领域通用性要求、only617/Features 边界、完整 OpenUI 复用、模块职责、patch/请求级幂等、桌面与 768/390 原型实操、真实产品基线及 milestone 覆盖。理由：本轮没有改变这些决定或原型，三项修订是已要求结果的接线与交付细化，重复原型走查不会增加证据。
- W1 闭环重新核对固定安装 react-lang 1.0.1 的实际 Action 回调和 store subscription，而非只读作者声明；W2 将每个 ADDED/MODIFIED Requirement 与当前 canonical 的实际名称逐项匹配；W3 对照 Node CLI、lifecycle、IM main/server 和已有 `.e2e-ports.env` 的非敏感端口/identity 信息静态核实。未执行 Runbook 中的停启命令。

### 历史问题闭环

#### R3-W1 — closed

- **Author Resolution**：click capture 提取用户可见动作文字，与 Renderer message/context 分开；完整 onStateUpdate ref 合并局部 formState 后冻结；ToAssistant/Mutation 共用提交；增加明确映射例。
- **本轮证据**：`design.md:61` 已不再假设上游提供可见 label，改为宿主捕获 aria-label/可见文字，缺失时使用明确的“向 Agent 提问”，不拿生成 message 冒充用户所见按钮。`:63` 明确用完整 state ref 加当前具名 formState，按本次事件时点复制，不等 debounce；Mutation 也走相同提交。`:67` 的 Form 外 scale、Form 内草稿、不同按钮文字/ToAssistant message 例明确本人正文、附属上下文与完整快照，并要求 Mutation 复验。
- **可实现性核实**：固定 react-lang `exports-CLfR509v.mjs:570-577` 的 store 订阅把当前完整 snapshot 同步传给 onStateUpdate；lang-core `index.mjs:5202-5230` 的 store.set 先 rebuildSnapshot 再同步通知 listeners。结合原 Action Set 顺序执行，宿主 ref 可在后续 ToAssistant/Mutation 之前取得更新值，不依赖下一次 React render。上游 Button/Form 行为不需要被替换或裁剪。
- **关闭理由**：可见文字、模型生成信息和完整状态不再混同为一个上游回调字段；已明确适配来源、取值时点与窄验证，足以指导实施。实际点击/键盘、表单与 Mutation 的结果仍由后续测试兑现。

#### R3-W2 — closed

- **Author Resolution**：以 current 为基线重分 MODIFIED/ADDED，删除重复未变条目。
- **本轮证据**：IM delta 以 MODIFIED 替换“交互确认保留真实用户、原回复与选择语义”，保留群中身份/草稿隔离和手写限制语 Scenario；旧单次提交规则被请求级幂等与新请求独立保存替代，新增 patch 历史目标。Gateway 的已有通用交付 Requirement 使用 MODIFIED，保留外部渠道文字场景；“普通提问能主动获得适用交互表达”使用 ADDED。Web 只 ADDED“通用交互支持连续本地探索”。逐项检查显示两个 MODIFIED 名称均存在于 current，两个 ADDED 名称均不存在。
- **关闭理由**：归并不会再产生重复 Requirement 或保留相反的终身单次提交规则；未变化的消息权限/fork、Web 阅读/失败体验、Features 默认开启等仍由 current 原条目承担，没有被删除。

#### R3-W3 — closed

- **Author Resolution**：补当前栈 stop/build/start/health/status，核对 PID 和 owner 节点，禁止重跑清库入口。
- **本轮证据**：`design.md:101-120` 固定当前 worktree，先停止该 config 的 Node 和 `.im.pid` 的 IM，构建后 source 原端口环境，显式使用原 sqlite/upload/config 并重启当前 Node/IM；声明先核对 PID、停止后确认端口释放，以及 IM health、Node ready/connected、owner 的节点 online 检查；明确当前现场不得重跑 e2e-up。
- **命令核实**：`apps/node/src/cli.ts:42-48,138-147` 接受带显式 config 的 stop/start/status；`lifecycle.ts` 按 config 路径与进程出生时间约束停止对象，不删除运行数据库。`apps/im-server/src/main.ts` 接受 serve/host/port，server 从 IM_DB_PATH/IM_UPLOAD_DIR 读取指定数据路径。已有 `.e2e-ports.env` 的 58769 与本 unit node identity 对应，并通过 source 保留既有环境。未执行这些命令，因此未声称重启成功。
- **关闭理由**：下游已有具体保留数据的复验路径，不必再自行猜测或调用会清库的默认起栈流程；构建与运行版本、健康及节点连接均有明确检查。

### Issues

无新增 CRITICAL / WARNING，无历史未关闭问题。

### Recommendations

无。按既定 M1 实施及真实普通提问验收，不扩大为新的设计循环。
