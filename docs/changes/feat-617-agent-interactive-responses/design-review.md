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
