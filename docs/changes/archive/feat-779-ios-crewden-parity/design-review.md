# feat-779 · 独立设计审查

## Round 1

- reviewer: Codex 独立 reviewer（design_review），未参与设计编写
- target: feat-779 的首文档、design、两份 IM delta、iPhone 原型与设计截图、M1/M2/M3 骨架。Web 对照 b405a96a7，审查 checkout b36e37a8d，两者之间 Web 与应用代码无差异。
- review_mode: full
- mode_reason: 首次 Gate 2，跨原生导航、聊天持久状态、Work 和管理入口。
- started_at: 2026-11-21T00:09:05+09:00
- completed_at: 2026-11-21T00:12:31+09:00
- duration: 3m26s
- Verdict: **Issues Found · 1 CRITICAL / 4 WARNING**

### Coverage 与证据

- **需求与职责。** 对照 spec 的三条用户旅程、Web router 实际挂载的 onboarding、聊天、任务、Agent profile、节点和公司页，以及 NanoIMApp 的 AppModel、RootTabs 和各业务 NavigationStack。角色头像可以从现有 AssistantPortrait 的角色、四种轮廓、六套配色和稳定 ID 复现。iPhone 可以复用其现有账号分区、ChatStore、前台事件流、AgentWorkView 的 session/turn/items/controls 分页。IM 继续掌握消息身份和 Work 授权。新增 Swift 表示与本地可空草稿字段成本合理，无需引入第二条用户流、DSH 依赖或线上人工迁移。
- **实际接线与消费。** 核对 onboarding-page 对进行中创建的重试与原聊天 ID、personal-agent-api 的 revision 和风险处置、chat-api 的历史搜索和 Swift ChatAPI 的冻结请求、Web agent-work-panel/activity popover 的 readiness 订阅，以及 AgentWorkView 已有回退和分页入口。建议只写草稿、主动发送才向收件 Agent 投递的方案成立。群内引用某个 Agent 会进入其定向依据，私人卡片背景按各自作者选择。此处的客户端与服务端职责须按 R1-C1 修订。下游应对照同一输入的中心 relay 收件人、引用来源、正文和背景归属；本轮未实际运行模型。
- **前端判断。** 独立查看已有团队列表、首次私聊、320 宽度的当前活动弹层和派工画面，并核对原型状态转换。头像与发送者相邻，弹层强调当前工作，派工缩进能把子执行及其用量放在同一阅读层次，主任务不依赖操作桌面大图。已有 PA 和新建 PA 重返列表仍有误导，见 R1-W4。真实键盘、VoiceOver、深色和滚动预留到受审 iOS 构建，没有用 HTML 截图判定这些系统能力已通过。
- **契约与里程碑。** iOS 的 MODIFIED 保留输入法、可访问动作、原生入口、外链资格等原有场景。新加的工作记录与派工允许原生列表等价实现。普通开会话与带消息锚点入口、DSH 查看器与产品子执行的适用条件尚有冲突，见 R1-W2、R1-W3。M1 身份/首用、M2 聊天/Work、M3 管理按序交付，两轨退出标准和三个空目录符合设计阶段；末段的基线逐操作证据表也覆盖低频动作。daily 可复用作跨端基线，default 不能独自提供已准入新用户绑定新电脑的待确认环节，见 R1-W1。
- **证据边界。** 本轮核验设计、已落地基线、原型和验收资源的准备方式，没有对未来 App 或第三方实际交付给出验收结论；未启动服务或模拟器。

### 历史问题闭环

首轮，无既有 issue。

### Issues

1. **R1-C1 · 客户端冻结私人卡片背景违反既有发送与隐私契约。** [design.md §接口与数据流，第 30 行](design.md#接口与数据流)把卡片背景列为 ChatAPI.prepareMessage 冻结项。[原生契约](../../../specs/im/ios-client.md#requirement-原生通用交互回复)明确禁止客户端选择、缓存或上报私人背景。[IM 实际发送路由](../../../../apps/im-server/src/messaging.ts)先命中原幂等发送，再从中心已保存草稿挑选背景并按收件 Agent 交付；显式卡片动作与 reply_to_message_id 同时出现直接返回 422。照设计实施会把私人信息持久化到手机的未确认发送中，或使从已选引用进入卡片操作的发送失败。需分清普通引用请求、显式卡片动作及中心一次性背景的归属，明确在带引用草稿旁执行卡片动作时该草稿的处理，并用已有的草稿保存、丢回执和真实 relay 核对其结果。
2. **R1-W1 · 首用 runbook 缺少可以绑定给新账号的电脑。** [design.md §Runbook for Reviewer，第 89、94 行](design.md#runbook-for-reviewer)给出的 default 实例在 [e2e-up.sh](../../../../scripts/e2e-up.sh) 第 359–388 行已绑定节点且校验 owner 为 nano。该实例能验有电脑/无 PA；同实例新增账号可以看到空态，但脚本已消费唯一节点的实际绑定，无法按表中步骤由新账号确认自己的电脑并继续配置、创建。需落实同一隔离 IM 上额外的独立节点身份、配置与绑定命令，或给出等价可执行的空账号首次绑定路径及清理方法。
3. **R1-W2 · 带消息锚点的入口与当前原生重入契约有重叠。** [iOS delta](specs/im/ios-client.md)新增“从搜索或引用回到原文”，design 第 29 行从 Chats 的历史搜索进入；保留的[原生聊天阅读连续性](../../../specs/im/ios-client.md#requirement-原生聊天阅读连续性)第 88–90、103–107 行要求从 Chats 打开/重开一律到底。长历史命中不在最新一屏时，同一路径无法同时满足两条判断。固定基线 [Web 切换聊天](../../../specs/im/web-chat-ux.md#requirement-web-切换聊天保持会话界面和阅读位置)还区分有无新消息。需明确原生普通进入、显式消息锚点、详情/Work 返回各自的优先级，决定普通重入沿用哪一条已知平台行为，并收窄相应 canonical scenario 的适用条件；用一次跨出最新页的命中和一次普通重入验证。
4. **R1-W3 · Work delta 对 DSH 例外的作用范围过窄。** [Work delta 第 5–7 行](specs/im/agent-work.md)限定的是“双视图”一项；canonical 另有[本次范围忠于真实执行且保留完整检查](../../../specs/im/agent-work.md#requirement-本次范围忠于真实执行且保留完整检查)第 163–166 行，只要用户进入已有真实边界的子执行就要求加载完整会话轨迹、在原生时间轴选择起止。按设计从 iPhone 派工列表进入正确的产品子执行也满足该 WHEN，仍会被判缺 DSH 查看器。应在契约层统一明确查看器特有保证适用的平台或入口，同时保留跨端真实执行身份、状态、授权及返回父级的要求。
5. **R1-W4 · 固定 PA 的 must-match 原型会把尚未发生的交付显示为最近消息。** prototype.html 第 27、36、41 行（历史文件 `prototype.html`）中从首次设置创建 PA，先不发送，再退回 Chats，固定行仍硬编码“已整理好明天要跟进的事项。”；已有团队的列表画面（历史文件 `design-evidence/chats-390.png`）也缺少该会话的时间。design 第 17、61 行及 [PA 固定聊天契约](../../../specs/im/personal-agent.md)要求复用真实末条、时间和未读。按当前原型做对照，会把空会话误验为助手已工作，也无从核对有未读时能否看到实际进展。应让新建空历史和已有 PA 的示例状态分别驱动固定行，已有消息的示例包含时间和适用的未读数，并查看返回后的结果。

### Recommendations

无。

### Author Resolutions

- R1-C1 accepted。修正 design 中引用与重试、模型消费边界。普通发送的请求与显式卡片提交分开；中心按收件人选择已保存的私人草稿背景，手机不冻结背景。
- R1-W1 accepted。Runbook 增加同一隔离 IM 下第二个独立 setup 节点的配置位置、启动与清理命令，默认栈已绑定的节点继续归测试主人。
- R1-W2 accepted。iOS delta 完整修改「原生聊天阅读连续性」，区分普通会话重入、显式定位和从 Work 返回。
- R1-W3 accepted。Work delta 同时收窄子执行自动时间轴选区到 Web 的 DSH 查看器，保留共同状态/身份依据。
- R1-W4 accepted。在新的用户视觉反馈后撤下 HTML 原型与旧截图，以实际 Web 路由画面作为基线。M1 明确检查空 PA 与已有 PA 的真实摘要、时刻和未读；iPhone 验收改用首个可运行 SwiftUI 切片。用户微信截图只作为交互参考。

## Round 2

- reviewer: 同一独立 reviewer（design_review）
- target: feat-779 修订后的 spec、design、两份 IM delta、三个 milestone 及真实 Web 画面。Web 基线 b405a96a7。
- review_mode: full
- mode_reason: 用户重新指定了整个客户端的视觉参照，作者撤下 HTML 原型并调整实际对照方法。重看整体需求及三个里程碑的判断依据，同时复核五个历史问题。
- started_at: 2026-11-21T00:22:43+09:00
- completed_at: 2026-11-21T00:23:44+09:00
- duration: 1m1s
- Verdict: **Approved · 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- **用户目标与产品基线。** 首文档保留登录后能力范围 B，完整 DSH 轨迹由 Web 提供。按[设计中的窄屏走查](design.md)复核了聊天列表、群聊和活动层。列表能看到固定 PA、末条消息、时间和未读数；群聊能辨认发言人、正文和引用；320 像素宽的活动层仍能看到助手状态和工作记录入口。审查使用合成数据。原生长按、键盘、VoiceOver 和返回读点列入后续验收范围。
- **架构与里程碑。** 固定基线与当前 checkout 的 apps、Web 和 iOS 源码无差异。复核实际组装、归属和比较方案，Round 1 的 AppModel/RootTabs、ChatStore、本地分区、现有 Work 分页与管理 API 证据继续适用。M1 产出可运行首用/聊天切片，M2 承接引用、活动与交付定位，M3 完成管理及基线逐操作核对。资产、客户端与中心各自的职责清楚；不需要另造业务网页或改动模型运行时。三段退出标准都可依照对应截图、实际操作与业务回执判断。设计成立，原生视觉、手势、键盘以及跨端完整能力仍须在实施时验证。

### 历史问题闭环

| ID | Author Resolution、本轮核验与结论 |
|---|---|
| R1-C1 | **closed**。设计第 30、53 行将普通引用与显式卡片动作分开，卡片提交保留旁边的普通引用草稿，中心负责按收件人消费背景。与 messaging.ts 的互斥校验、幂等命中后读取背景及逐 Agent 交付一致。实施时有实际 relay、原引用、收件人和一次性消费的核对方法。 |
| R1-W1 | **closed**。Runbook 第 90–98 行补上同一隔离 IM 的第二台合成节点。核对 apps/node/src/bootstrap.ts 与 cli.ts：全新 config 产生单独 node ID、workspace 及 owner 根，setup 发起绑定并启动该配置的节点，stop 作用于同一配置。iOS SettingsBindingView 支持通过当前服务的绑定链接确认，原 default 节点可继续归 nano。已核实设计阶段的接线，本轮未运行节点。 |
| R1-W2 | **closed**。iOS delta 对普通会话行无锚点重入保留原生到底行为，对历史搜索、来源链接和引用优先定位，对从 Work 返回恢复读点，并保留原有跟随/历史阅读和交互卡片场景。搜索到已离开最新页的消息时不再同时命中两条互斥要求。 |
| R1-W3 | **closed**。Work delta 完整保留两个 MODIFIED 要求下的场景，将自动选区和完整轨迹的入口限定为 Web 原生轨迹查看器。iPhone 以产品工作记录展开子执行，跨端仍需保证真实身份、报告状态及返回上下文。 |
| R1-W4 | **closed**。作者撤下虚构 PA 交付的 HTML 原型。设计第 63、112 行分别约束空 PA 与已有消息的 PA，M1 要用同一数据核对真实摘要、时间及适用的未读。已提供的真实列表画面支持有历史、有未读的情形；首次空历史和实际 iPhone 显示列入 M1。 |

### Issues

无。

### Recommendations

无。

### Author Resolutions

认可第二轮复审结论。实施时按相同数据对照窄屏 Web 与运行中的 SwiftUI 页面，并在 iPhone 模拟器验证原生交互。
