# feat-617 Design Review

> 本文提到的截图仅保存在仓库外；定位见[本地证据说明](evidence/local-artifacts.md)。

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
- 草稿：独立修改正文，再在普通输入框发送“先别发送，把语气改得随意一点”。原型的本人消息同时显示限制语和修改后的草稿，演示回复明确先不发送；这构成 R1-W1 要求保留的具体产品语义。窄屏对应画面见 手机文字附带选择（本地截图 `prototype-mobile-context.png`）。
- 通用提醒：独立触发提交失败，看到“未能提交，当前选择已保留”与重试入口；切至已有更新后按钮禁用、普通输入仍可用。该例由文字/布局/动作构成，没有把隐私业务做成必须采用的专用 UI 协议。
- 窄桌面（本地截图 `prototype-compact.png`） 保留侧栏后字段上下排列；手机初始（本地截图 `prototype-mobile.png`）、提交状态（本地截图 `prototype-mobile-submitted.png`） 和 降级（本地截图 `prototype-mobile-fallback.png`） 可辨认内容、选择、主动作和输入。卡片较长，但随主列表滚动，按钮与选择总结相邻；没有足以阻断当前方案的视觉或交互问题。浏览器实操为桌面；手机/768 尺寸的本轮判断来自现有实际渲染图片及作者操作记录，未声称独立完成手机软键盘或跨设备试验。
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

先独立查看真实渲染并操作，再核对作者走查记录。本轮使用 Chrome / cua_repl 打开提供的原型服务，桌面窗口实际 1538×944；随后打开 `evidence/prototype-sizes.html` 的 768×900 与 390×844 iframe。基线对照查看旧产品的 桌面截图（本地截图 `product-desktop.png`） 及 [实施浏览器记录](evidence/implementation-browser-review.md)。

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


## Round 5

### Metadata

- reviewer target: `/root/openui_restore_design_review`，独立 reviewer；未参与本轮 spec/design/prototype 或产品修订。
- review_mode: `full`
- mode_reason: 新用户要求改变手写消息的共享接口、私聊/群聊状态边界和后续输入语义，不能仅以旧问题 closure 放行。本轮完整检查受影响的生成后探索 → 普通发问 → relay → 普通/Global 输入链、权限、delta、增量体验与验收前置；未改变的 OpenUI 生成/明确操作能力使用具体保留证据，不重复全部组件或模型样本。
- started_at: 2026-10-19T19:36:20+08:00。
- completed_at: 2026-10-19T19:39:47+08:00。
- duration: 207 秒。
- baseline: `unit/feat-617` / `72791ffadc9e3c0e3bb0bc9543c8a049bcf44dbb`，受审为其上尚未提交的 active 恢复与自然上下文修订；开始时已有 staged renames、design/spec/delta/prototype 修改及 prototype-continuous.html，本轮全部保留。
- 受审快照 SHA256 前16位：spec `db8861c867719b8b`；design `05206d89611b8d21`；prototype `2f262935ee08920c`；IM messages delta `e4c3601c3921d75b`；Web delta `fd0e7ce07f36cf91`；Gateway delta `819a64d3e6b70759`。
- 本轮只追加本报告；未提交、未修改产品/配置、未重启服务、未调用真实模型，未触碰 feat-616 或生产。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本轮自然上下文设计通过 Gate 2。私聊发问背景与明确提交分离、群聊未提交状态不传递、普通消息保持原路由和原文，均有可实施的接线与验证出口。此结论不证明后台快照已在产品生效，也不将模拟回复当成模型会准确理解或忽略背景的证据；实施后的普通/Global、群聊拒收和持久化必须按本轮增量验收。

### Coverage 与证据

#### 用户要求、范围与保留结论

- 已读取 spec 末尾两次用户原话及最终确认：去掉保存成功、Current choices 和 Detach；私聊发送时由 Agent 判断背景是否相关；群聊所有 Agent 包括卡片作者均不得读取未提交状态，只有明确卡片动作才共享。最终边界覆盖此前“群聊仅作者获得背景”的草案。design 的自然上下文段与三份 delta 均按最终边界写明，未将背景改为隐式业务授权。
- 原来的手写消息附带选择/定向卡片作者由本轮明确替代；原生 ToAssistant/Mutation/ContinueButton 的明确请求、公开快照、实际用户和幂等规则保留。Features 默认开启/可关闭、only617、无排序题专用生成逻辑、完整库/本地动作/条件/Each/工具与 patch 能力没有被再次裁剪。
- `retained_from: Round 3 / Round 4`：OpenUI 公开接缝、模块职责、原生事件标签与完整状态适配、patch 完整历史及请求级幂等的设计判断。它们不证明新的自然消息路径已实现。
- 另核对当前 `acceptance.md` Round 3 的真实冒泡排序/月相、连续原生按钮、原状态恢复及三宽度记录，以及 `preview-workspace-fix.md` 的能力预览目录修复范围。仅保留各报告实际观察的能力与修复事实；旧手写附带选择、群内普通文字公开快照和 Current choices 体验已被本轮目标替代，不作为新体验通过证据；preview 修复不受影响，无需因此重做其生命周期。

#### 真实组装入口、接口与数据流

- Web 实际 `message-pane.tsx:260-283,642-678` 当前将最近一张卡片存为 selection，手写发送构造 interaction_reply，成功后清除选择；`:1113-1117` 渲染附带横条。InteractiveCard 当前保存/恢复并通知 onSelect。新设计把这里改为会话内最多三张背景候选、初始/恢复完整状态可用、实际操作优先、成功不清缓存，是对当前产品路径的明确替换，并非只隐藏文案。替代、会话切换/删除不会把背景带到另一会话；历史可读背景不重新获得业务提交权限。
- `chat-api.ts` 的普通 createMessage 本就承载正文和附件；`messaging.ts:468-518` 在会话写权限之后分流 interaction_reply 与普通消息。新可选 interaction_contexts 走普通路径、明确动作继续走 sendInteraction，故正常附件无需被旧 interaction_reply 的“另发附件”限制阻断。发问时深拷贝正文、附件、候选快照与 key，未知结果重试原请求、后续编辑只影响下一次发问，已写为具体规则。
- `messaging.ts:568-580` 已逐目标 Agent 保存完整 relay payload，metadata 为现有纯数据接缝；`apps/node/src/main.ts:173-174` 读取 RelayInput，product-contracts 的 metadata 当前为 Record。把服务端按来源生成的规范快照注入各 relay 的 metadata，不需要新存储表、广播字段或第二消息模型。当前普通路径先 insertMessage 再 enqueueRelays，design 已要求本轮将本人消息与对应 relay 同事务提交后发布；这项必须实施，不能误认为现有路径已原子化。
- `messaging.ts:310-313,405` 的公开消息投影只含现有 interaction_reply/interactive；设计明确新背景不进入 public Message DTO、message.created、history/fork 或 interaction_submissions，不修改个人 draft revision。因此自然发言不会被误回显为“已确认选择”，也不会靠以后读取可变草稿重建先前问题。已有 key 返回原消息/原 relay，对已保存背景采用首次提交语义，防止重试覆盖背景。
- `single-thread.ts:117-120` 与 `inbox.ts:115-119` 都经 product-contracts 的 withInteractionContext 生成文本；新设计要求同源格式化新背景，再交给原 session input / Inbox，沿既有正文和附件链。背景标记为发问时可用数据、按原话决定相关性、换题忽略、歧义澄清、无授权；没有添加按题材关键词强制路由或另一 Agent Loop。模型是否实际遵守需真实普通/Global样本验证，原型固定回复不能替代。

#### 权限、职责与复杂度

- 后台字段的服务端来源校验限当前会话可读交互消息与正常人类写权限；source 的作者与摘要由保存源取得，浏览器不选择接收者。direct relay 只向卡片作者提供其自己的背景，不因源 id 添加 mention 或唤醒别的 Agent。原明确提交仍沿已有 source Agent 定向语义。
- 群聊前端普通发送不带 interaction_contexts，服务端拒绝该字段；旧/直接客户端也不能绕过。群内 interaction_reply 要求 action_id/event，堵住原“只给 state + 手写 content”就公开私有状态的路径。原 `interactions.ts:52-58` readDraft 已拒绝 Gateway/Agent，且按当前人类 user_id 读草稿；设计没有放宽此接口。群成员和所有 Agent 取得的只能是明确提交后的公开快照。
- 状态最多三张、每份沿用16 KiB、摘要160字；服务端复用已保存源和既有 state/fields 规范化，无需把独立后台缓存变成新的授权或公开业务对象。Web 负责即时状态与冻结请求，IM 负责来源/权限/事务与 relay 定向，PA formatter 负责来源标记和模型输入；各职责延续现有边界。未见需要新工具、权限平台或通用事件总线的实际理由。

#### 独立增量体验判断

Chrome / cua_repl 独立打开 `57336` 原型服务并操作，另使用现有 prototype-sizes wrapper 的 768×900、390×844 iframe；对照 真实旧界面（本地截图 `native-bubble-desktop.png`） 和当前 MessagePane 入口。新原型明确标注回复/失败为模拟，属于现有聊天内容区与 composer 的局部增量，不以其简化 header 替代整个产品导航。

- 旧真实截图中，长来源摘要被塞入 Current choices 横条并附 Detach，占用输入框上方一整行；新原型只保留内容、参数与自然输入。改变年率时结果即变，既无保存成功提示，也无“需要管理附带状态”的操作。用户可以直接问问题，删除这行没有丢失本次任务需要的参数含义和操作入口。
- 独立将年率改10%，发送“Why is there a difference?”，再改回5%。本人消息只显示原话，模拟回复仍解释发问时10%/差值310，而当前卡片为5%/差值76.25。该画面明确表达“后台冻结当前帧，继续探索不改变旧问题”的目标，不再显示 Submitted choices 区块。
- 独立模拟发送未知结果：5%时发送“Explain the current parameters”，看见明确的原请求重试提示；改到10%后再次 Send，回复仍使用原5%/差值76.25。接着发送“Hello”，正常得到换题响应，没有被强制拉回图表。此处只证明原型交互意图，固定脚本不证明真实模型判断能力。
- 768 与390实际渲染均没有附带横条，参数、结果和输入可读；手机独立触发失败后，红色未知结果提示位于输入上方，文字完整、Send仍可达。变化从“正常状态不断提示”改为“有错误才提示”，用户无需主动维护草稿/附带模式。未观察到足以阻断增量设计的布局或操作问题；没有执行真机软键盘检查。
- 自动持久化/恢复、CAS、多人群聊拒收和多卡相关性属于后续真实产品与协议验证；本原型未连接这些机制，本轮不提前宣称通过。既有对应布局/错误体验作为参考保留，数据语义按新规则重验。

#### Delta、milestone 与验收前置

- IM delta 的 MODIFIED 正确锚定 current“交互确认保留真实用户、原回复与选择语义”，保留群中身份、多次请求/幂等、替代/fork与patch场景；明确替换旧手写附带确认场景。新增“自然消息的交互背景保持准确且不改变路由”描述冻结与私聊/群聊边界。
- Web delta 的 MODIFIED 替换现有“交互内容保持聊天阅读与操作连贯”，保留桌面/手机、生成/渲染失败，改写普通输入/静默保存与真实失败；不改已有连续本地探索 Requirement。Gateway 新增 Agent 按原话判断背景及群聊不读私人操作，锚定消费者正确。ADDED 名称在 current 尚不存在，没有再次产生重复式 delta。
- 继续同一 M1；自然追问与无关话题覆盖普通/Global，状态冻结/失败重试覆盖正文与附件，多卡/群内普通文字/明确动作及权限窄测均有 must-match 出口。原完整库与普通生成结果只保留原范围，本轮重新验证 R2/R3/W2，符合实际影响。
- 沿用 R4 已审的当前 worktree 保留数据 Runbook、58769 owner/普通/Global资源及既有独立群用户证据；未改变服务拓扑、账号资源或外部业务依赖。受影响产品复验不能仅靠API注入背景或原型模拟，必须驱动真实Web普通发问，并核对持久relay、公开消息缺字段和群内拒收/明确提交。

### 历史问题闭环

R3-W1/W2/W3 保持 closed：本轮不改变原生事件标签/完整状态适配、已有 Runbook 或已归并的旧能力。新 delta 已重新按当前 canonical 编写；原 R1-W1 的“手写限制语不被替换”继续成立，但后台快照是否公开/如何传给 Agent 以此次用户确认的新规则为准。无旧 open issue。

### Issues

无 CRITICAL / WARNING。

### Recommendations

无额外机制或范围扩展建议；按本轮契约实施并执行受影响真实旅程即可。

### Author resolution after Round 5

Root核对R5覆盖最新用户确认的私聊/群聊边界、真实组装入口和增量原型，0C/0W，无需修订设计。普通/Global与群内Agent的数据输入将在实施后分别取证；旧功能与preview修复保留原有效证据。R5之后首文档、设计和delta无实质变化。


## Round 6

### Metadata

- reviewer target: `/root/layout_design_review`，独立 reviewer，未参与布局方案编写或产品实施。
- review_mode: `full`
- mode_reason: 用户新增消息布局 Requirement，范围从交互卡片扩展到普通短消息、长文、代码和表格，需完整核对这条用户阅读与操作流程；不能仅以 R5 的自然上下文审查放行。后端协议、权限和完整组件能力按未变范围保留，不重复全 catalog 验证。
- started_at: 2026-10-19T21:01:26+08:00。
- completed_at: 2026-10-19T21:04:43.938487+08:00。
- duration: 197 秒（正式汇总与修订复核阶段；此前源码/画面预查未单独计时）。
- baseline: `unit/feat-617` / `e615886161bb21ecba35f1af8a04e0e93ffff355`；开始时仅 spec/design/Web delta 与新增布局原型/作者走查记录未提交。本轮只追加 design-review.md，不修改产品、配置或历史审查，不提交。
- 最终受审快照 SHA256 前16位：spec.md `6c2a74e14189ecd5`；design.md `d3b46cef54c3e3ca`；specs/im/web-chat-ux.md `8a87109fe691d596`；prototype-layout.html `bc1d85f2cfd6beac`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

布局方案通过 Gate 2。宿主释放消息空间、短句按内容收缩、交互外壳去灰底、宽代码与表格采用全宽外壳并限制内部滚动，足以指导当前 M1 实施。此结论是设计审查，不证明真实产品已完成新布局，也不证明实时链路、移动真机或全部上游组件已经重新验收。

### Coverage 与证据

#### 需求、边界与真实接线

- spec 末尾保留用户两段原话：不浪费聊天面板右侧空间，从美学和 UX 重新设计，并继续本 feat。新增三个 Scenario 覆盖宽交互、混合消息和手机；design 将其收口为保留边距/头像、Agent 内容列占余宽、短消息 fit-content、长文64rem、宽内容全宽、交互透明外壳和 min-width:0，不引入宽窄切换或新配置。
- 实际路由 `src/IM/frontend/src/app/router.tsx:38-39` → `chat-workspace-page.tsx:1177` → `components/message-pane.tsx:1046,1744-1789` 渲染消息列表、头像、内容列、正文与 InteractiveCard。不是只在测试中存在的布局。`global.css:2364` 的72%及`:4981`的88%，与 `interactive-card.css:1,12` 的680px限制叠加；在真实 `58769/chat/c_8iutij8v` 读 DOM，四张互动卡片内宽均约654.00px、父壳680px，与作者现状断言一致。
- 当前消息菜单/复制工具条仍由 MessageBubble 的 cardRef 与 `global.css:2435` 的定位承担，身份和时间是邻接节点；去背景/改宽度不需要重写菜单、发送或 Renderer。InteractiveCard 的 fieldset、原生 onAction/onStateUpdate、Query/Mutation与状态恢复继续复用。宽内容识别和样式归 Web 消息宿主；不向 IM/PA/DSH 下放视觉职责，不增加协议字段、另一个渲染引擎或 viewport 测量机制。
- 本人消息继续右对齐；其他人类消息使用普通气泡，不因统一 Agent 侧内容列而取得交互透明样式。图片保持原有比例/预览尺寸，工具过程、复制、失败状态及自然输入继续使用原入口。后续验收须检查宽度变化后的可达性，而不把未变业务逻辑重实现。

#### 独立体验判断

- 独立通过 CUA 实际打开 `8768/prototype-layout.html`，观察桌面、768和390容器，切换旧/新布局并与真实58769页面对照。原型在产品区外说明简化背景和模拟内容，未伪装成真实生成或持久化证明。
- 桌面新布局的摘要、标题、参数、指标和图表共享左边界，图表与参数区域使用余下横向空间；旧模式灰底窄条右侧保留大片空白。去掉重复灰底后，内部输入卡和指标卡仍有明确分组，头像、名称、时间仍能区分消息。短句继续收缩，没有为了填满面板变成大色块。
- 768容器保留侧栏后，实际聊天区更窄，三列参数及指标仍可读，未出现挤出容器。390容器隐藏侧栏，参数纵排，指标标签与数值配对。独立把本金改20000，结果变为53066、33066、13066；随后在底部输入问题，输入区仍可见。继续滚动可阅读图表、正文、代码和表格，代码/表格的宽内容限制在各自区域。该交互证明原型空间关系与输入可达，不代表真实模型响应或真机软键盘验证。
- 本轮发现原型末条宽Markdown仍受普通64rem气泡上限限制，作者在审查中增加 wide 外壳和段落64rem约束。已重新加载并实际观察：代码外壳延伸到面板右侧，正文仍有阅读上限，表格不被强制拉伸。这与最终设计一致，不留未决实现选择。
- 原型图表及控件排列只展示宿主空间，不承诺替换上游组件主题、Tabs、网格或模型源。真正的“复利探索馆”含四Tab和四指标，实施后必须对同一保存源验证；原型中三指标演示不能替代该结果。

#### Delta、milestone 与验收前置

- Web delta 路径正确投影到 `docs/specs/im/web-chat-ux.md`。新增“消息随聊天面板和内容伸缩”在 current 尚不存在；旧 MODIFIED“交互内容保持聊天阅读与操作连贯”与 current 相同，四个 Scenario 完整保留，不回退自然上下文和失败语义。新增要求属于 Web 消费者的阅读/操作契约，不扩展 Gateway 或权限契约。
- 继续 M1；design 新增 must-match 明确关联同一真实复利消息、普通短长消息、代码/表格、1537/768/390、输入、复制与滚动，并分别投影到 reviewer 的用户结果和 worker 的截图/几何/交互证据。组件源和生成提示保持当前，只有受布局影响操作复验，范围可执行。
- 独立打开既有会话并观察真实卡片，`/health` 返回 ok；原 Runbook 的账号、当前端口、保留数据重启和节点检查仍可复用。初稿 iframe 路径受到现有防嵌入策略阻断，作者已将最终 Runbook 改为 CUA Chrome viewport set/reset 直接检查真实页面；不改安全头、不依赖新前端服务。此项是验收驱动澄清，未扩大产品改动。
- 真实页面本轮出现“Real-time updates are busy”重试横条，已向作者明确反馈；它不阻止读取当前布局，但不能据此声称实时更新正常。实施后的产品验收需核实连接并记录该状态，不能只靠截图或 health 代替实时链路证据。本轮未发新消息、未重启栈、未调用模型。

#### 保留范围与历史问题

- `retained_from: Round 5`：私聊背景/群聊明确提交边界、普通/Global输入、冻结与幂等、公开消息投影、原生动作适配和已有完整组件能力的设计判断；本次文档/布局变化没有修改这些接口。
- R3-W1/W2/W3 维持 closed；R5无未关闭问题。本轮原型宽Markdown和窄屏驱动的两处消歧已由作者修改并复核，不留跨轮待办。R5的设计通过和旧产品证据均不直接推导本轮新布局通过。

### Issues

无未解决 CRITICAL / WARNING。

### Recommendations

无新增范围或机制建议；按最终布局契约实现并验证同一真实消息及受影响操作。

### Author Resolutions after Round 6

Root 接受 R6 的两处文档/原型对齐意见，已在本轮最终 Approved 前修正：真实客户端以浏览器 viewport 能力直接验收（不绕过 frame-ancestors）；宽代码/表格原型全宽且段落保留上限。0C/0W，无实质异议。进入同一 M1 布局实施；后端、自然上下文和完整组件目录未变。
