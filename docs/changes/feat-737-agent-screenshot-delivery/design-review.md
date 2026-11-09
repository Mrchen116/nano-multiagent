# feat-737 Design Review

## Round 1

- reviewer: `/root/design_review`，独立 Gate 2 reviewer
- target: `4d22e0c534910f1555ab691f4a42ff11e3ae03df` 与冻结的 staged blobs。design `bac8f801c`，Gateway delta `a6a4c5869`，IM delta `743321b0e`，M1 骨架 `e69de29bb`。
- review_mode: `full`
- mode_reason: 首轮，涉及产品发送、审批、模型上下文、两个客户端和长期行为契约。
- started_at: 2026-11-09T11:14:54+08:00
- completed_at: 2026-11-09T11:17:06+08:00
- duration: 2m12s
- verdict: **Issues Found · 0 CRITICAL / 5 WARNING**

### Coverage 与证据

- 范围按 [首文档](spec.md#范围与非目标) 核对。一次显式自身份发送覆盖普通截图和图文卡片，保留目标会话权限及历史回看。截图生成、Feishu、任意文件和普通 Markdown 本地路径转换留在本轮之外。新增字段只属于公聊自身份分支。现有 `send_message` 是公聊与父子消息的联合工具，`send_user_message` 又复用公开参数，落地时须分开声明和归一化两类入参。核对了 [工具注册与分支](../../../packages/dsh-integration/src/global-mode.ts#L61)、[共享参数](../../../packages/dsh-integration/src/message-arguments.ts#L3)、[审批入口](../../../packages/dsh-integration/src/policy/approval.ts#L104)。
- 真实组装从 [DSH product bridge](../../../packages/dsh-integration/src/product-bridge.ts#L19) 到 [节点 product.call](../../../apps/node/src/main.ts#L380)，由 [GlobalAgent 分派普通与 PA 发送](../../../packages/personal-assistant/src/global-agent.ts#L667)，经 [外部路由适配](../../../packages/personal-assistant/src/external.ts#L192) 到 [IM Relay 发布](../../../apps/im-server/src/gateway.ts#L571)。确认 [媒体路由](../../../apps/im-server/src/server.ts#L197) 已由实际 IM 进程注册，并按 [会话权限读取](../../../apps/im-server/src/media.ts#L59)。本机字节读取和认证上传放在 Node 边界，目标解析、重评和消息回执留在产品发送层，资源元数据与发布原子提交归 IM，职责适合沿用现有设施。由发布消费会话内资源，而非另建文件服务、公开 URL 或 DSH 上传通道。
- PA 私聊上传能复用 [Gateway 媒体权限](../../../apps/im-server/src/messaging.ts#L93)。对外行动会 [冻结附件与实际受众](../../../apps/im-server/src/personal-actions.ts#L124)，[审核输入带冻结图像](../../../packages/dsh-integration/src/personal-security.ts#L78)，[提交后在目标会话绑定复制引用](../../../apps/im-server/src/personal-actions.ts#L234)。审批旁路、原文件移走后回看以及错误恢复分别审查。会话内附件序号可跨 PA 复制沿用，前提是维持消息附件顺序。
- Agent Context 设计检查覆盖发送前说明、按需加载的 Skill、发送结果与恢复。工具可独立发普通图，UI Feature 下静态比较符合既有 [主动使用指导](../../../packages/dsh-integration/src/features/intelligent-ui.ts#L5)。Skill 来自 [前端 catalog 与生成脚本](../../../scripts/generate-interactive-ui.ts#L9)，适合在源头加入版本可辨认的图文范例及附件顺序说明。既有工作分派会让内部执行者把 UI 源码交给父级，实施验证应包含根 Agent 收到可读截图路径和顺序后完成群投递。当前只确认静态来源和设计意图，模型实际读取、选择及输出留给隔离实施验收。未知状态的可操作性见 R1-W1，路径的公开投影见 R1-W2。
- 前端体验设计检查从 [Web 消息](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L1926) 与 [iOS 消息](../../../src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift#L61) 的卡片和附件入口反查。Web 已有 [缩略图与原图查看](../../../src/IM/frontend/src/features/chat/attachments/attachment-chip.tsx#L17)，iOS 已有 [认证附件预览](../../../src/IM/ios/NanoIM/UI/MediaViews.swift#L35)。新版 iOS 走 [随包共享 renderer](../../../src/IM/ios/NanoIM/Features/Chat/InteractiveCardView.swift#L13) 及 [现有只允许当前 card generation 的桥](../../../src/IM/ios/NanoIM/Features/Chat/InteractiveRuntime.swift#L85)，历史只读场景应保留本地看图动作。设计约束足以复用现有交互，卡片构图由实际内容驱动，未发现需用独立视觉原型先决定的布局。实施时须分别在 Web 和原生模拟器观察版本标签、窄屏、历史只读时预览和返回、成功去重及失败保留附件。卡片图片失败若只影响桥而附件资源仍可读，须用该场景证明降级后的入口确能打开原图。本轮只有静态入口证据，未做界面运行验收。
- IM delta 以消息消费视角约束布局、权限、去重与失败回退，可作为 IM 消息的新增行为，既有会话附件访问和复制契约继续承接。Gateway delta 的目录落点正确，既有 Requirement 关系见 R1-W4。M1 骨架及单一交付范围与用户旅程一致，没有并行组重叠。方案沿用已有托管存储，无一次性迁移。实施证据种类覆盖关键结果，必需现场角色及构建前置见 R1-W5。

### Issues

#### R1-W1 同次未知发送的回执入口未闭合

位置为 [设计的数据流 3](design.md#接口与数据流) 和 [首文档的发送恢复](spec.md#scenario-图片准备失败与发送恢复)。

- 普通发送有 `agent.message.status`，只查 [普通 dispatch log](../../../apps/im-server/src/gateway.ts#L571)。[PA 对外发送](../../../packages/personal-assistant/src/personal-assistant.ts#L193) 在本地状态为 `sending/unknown` 时直接返回 unknown，早于已有 `pa.action.prepare` 读取已确认 PA 操作的路径。因此仅复用审核、提交和普通回执，无法核对已成功提交但响应丢失的 PA 发送。
- [媒体路由](../../../apps/im-server/src/media.ts#L169) 在接收完整字节并计算摘要后才查旧上传，已有上传回执只有节点收到后才能持久化。若 IM 已存图但上传应答丢失，当前路线无法从旧键取回冻结结果，源文件被覆盖后会冲突，移走后甚至无法请求。应明确两种响应丢失分别恢复哪层回执，以及各层何时仍可报告 unknown。
- [桥接的操作键](../../../packages/dsh-integration/src/product-bridge.ts#L24) 随工具调用 ID 生成，Agent 重发同样的参数会得到新操作。补齐经既有身份核对同次 PA 发送和上传结果的方式，并说明 Agent 或宿主通过何入口安全恢复。验收覆盖已提交后丢应答、未提交时不会自动重复发送，以及已冻结的截图无需重新读取旧路径。

#### R1-W2 聊天公开投影会带出审核使用的本地路径

位置为 [关键决策的路径边界](design.md#关键决策) 和 [模型可见失败信息](design.md#模型可见信息)。

- [SingleThread 的真实转发](../../../packages/personal-assistant/src/single-thread.ts#L319) 把 [工具入参和结果](../../../packages/personal-assistant/src/presentation.ts#L30) 投影到聊天消息，人工权限请求也使用 [原始 tool_input](../../../packages/personal-assistant/src/single-thread.ts#L429)。IM [实时事件与持久消息](../../../apps/im-server/src/chat-streaming.ts#L82) 携带这些值。即使成功交付气泡只包含托管 URL，另一个聊天过程气泡仍可能提前公开路径，失败回执中的路径也可被公开。
- 补充公开投影与审核/Agent 回执的分界。原始路径应留给实际执行和获准审核的表面，普通群友通过实时或历史数据看到的工具入参、结果和权限通知应使用安全表达。验证应包括一次需人工审批或失败的 SingleThread 群发送，并核对非 owner 群友可见消息。

#### R1-W3 图片接纳约定与实际校验、PA 审核上限不一致

位置为 [本地图片上限与类型](design.md#关键决策)、[媒体验证](design.md#接口与数据流)。

- 当前通用上传只探测 [文件头](../../../apps/im-server/src/media.ts#L28)，可将合法 PNG 开头的截断文件存为图片，也可按实测头部把声明为 PNG 的 GIF 改成 GIF。[当前通用上传契约](../../specs/im/conversations-messages.md#im-托管聊天附件按会话成员关系读取) 保留真实编码纠正。单靠这层现有校验无法兑现新工具只发 PNG/JPEG/WebP、失败不给群发残缺结果的要求。
- [PA 的实际审核接纳](../../../apps/im-server/src/personal-images.ts#L4) 还要求静态可解码图片、宽高各至多 4096、合计至多 20 MiB。五图各自小于 10 MiB 仍可能被拒，截断图和超限图若只返回已有总括错误，Agent 也无法按设计定位问题。请明确普通与 PA 各自的接纳规则、已有上传行为的边界，以及模型在哪一层得到可据以修正的反馈。复用现有可解码性校验和审核限制即可满足边界，避免改动普通用户上传语义。

#### R1-W4 Gateway delta 与既有显式图片交付条款重叠

位置为 [Gateway ADDED](specs/gateway/routing-delivery.md#added-requirements)。

- [现有 Requirement](../../specs/gateway/routing-delivery.md#当前会话的-agent-图片回复具有统一交付语义) 已定义显式 `send_message` 的本地图片、同次原快照与回执、权限及过时草稿。按本 delta 直接追加，会留下两套显式发送规则，且现有条款按不同来源计数、同来源不重复准备，新设计以两类附件的列表总数和顺序表达，归并后无法清楚判断同次重复来源如何计数和引用。
- 在现有 Requirement 下更新受影响的显式发送语义并说明重复来源的处理，保留普通回复、Feishu 路由、纯文本等本轮未改的 Scenario。新增仅独有的卡片引用或 PA 审核语义，避免重复定义既有规则。

#### R1-W5 Runbook 尚未落实必验的第二真人和 PA 发言资格

位置为 [Runbook 和 M1](design.md#runbook-for-reviewer)。

- [daily 种子](../../../scripts/e2e_daily.py#L170) 只创建一个真人与 P/E/Q 群，PA 默认仅能观察。当前 runbook 写检查两名用户可登录、创建临时私密群，却没有指定第二位真人从哪里来、何时作为非成员验证拒绝、何时入群，以及如何让 PA 以自身份取得发言资格。[PA 提交前检查](../../../apps/im-server/src/personal-actions.ts#L57) 需要 PA 自己能写。否则实际旅程只能证明 owner 可看，或只测到 PA 无权发送。
- 写明隔离账号开通、入群及 PA 参与权限的来源和可核对条件。给 iOS 复用 [仓库构建入口](../../../src/IM/ios/README.md#构建)，写明共享资源随包重建和隔离 IM 登录方式。通过只读设备列表确认本机有可用 iPhone 模拟器，客户端构建和连接应在实施验收时执行。

### Recommendations

- R1-R1 将完整的两张图对比写进生成源。把可见的版本标题和说明放在图旁，`alt` 用作无障碍名称，选用在窄屏下仍能按同一顺序读完的布局。注明本地路径依赖随 UI 源码一起交给根 Agent；发生混合附件时，以整条消息的附件顺序编号。

### Author Resolutions

- R1-W1 accepted。数据流分别规定截图上传、普通发布和 PA 提交回执。Agent 可通过原操作引用只读查回。增加相应窄测。
- R1-W2 accepted。原路径保留给实际工具执行及审核，公开过程、权限卡与失败投影使用安全摘要。
- R1-W3 accepted。Gateway 截图模式复用完整静态图片解码，设计列明逐图与 PA 总量的限制。
- R1-W4 accepted。Gateway delta 修改既有图片 Requirement，保留原场景，说明附件位置和同来源复用。
- R1-W5 accepted。Runbook 明确隔离第二账号、先拒绝后加入、PA 群写权限及随包构建 iOS。
- R1-R1 accepted。模型上下文说明补上窄屏、可见版本标题与向根 Agent 交接的要求。

## Round 2

- reviewer: `/root/design_review`，独立 Gate 2 reviewer，与 R1 同一身份
- target: `4d22e0c534910f1555ab691f4a42ff11e3ae03df` 与冻结的 staged blobs。design `c10b9c09`，Gateway delta `804f0228`，IM delta `743321b0`，M1 骨架 `e69de29b`。
- review_mode: `full`
- mode_reason: 修订加入共享发送工具的只读回执分支及两条宿主查询入口，重新核对审批、身份、重试、场景与 M1。未改的产品入口和客户端结论复用 R1 的静态证据。
- started_at: 2026-11-09T11:20:01+08:00
- completed_at: 2026-11-09T11:21:32+0800
- duration: 91s
- verdict: **Issues Found · 0 CRITICAL / 2 WARNING**

### Coverage 与证据

- 首文档、实现基线、IM delta 和 M1 骨架与 R1 相同。继续覆盖原生 IM 显式自身份发送、普通附件、图文比较、权限及持久回看。DSH 经既有 bridge 到 Node，Node 借认证媒体入口准备图片，普通发布与 PA 行动分别沿各自产品路径提交。新回执只读取各自存量状态，沿用现有认证与业务存储，架构边界和一次性迁移判断保持成立。只读查询分支需要完整区分公聊写入与父子通信，继续遵守现有宿主身份校验。
- Agent Context 复核了 [模型说明](design.md#模型可见信息) 的实际 tool、Skill 和回执表面。原操作引用能作为可复制参数用于只读核对，不以新发图调用替代状态查询。版本标签、窄屏阅读顺序和向根 Agent 交接路径的约束覆盖 R1-R1；真实输入及模型选择仍由隔离旅程证明。人工批准的内容范围见 R2-W1。
- 卡片布局、历史只读预览与失败回退设计未变，沿用 R1 核查的 Web 消息、iOS renderer 与原生预览入口。保留普通附件降级，尚无必须通过独立视觉原型确定的布局。M1 增加响应丢失、源文件移走、SingleThread 聊天脱敏等目标测试，双端运行验收继续使用修订的隔离 Runbook。

### 历史问题闭环

- **R1-W1 closed。** Author 接受并分开定义三类回执。已对照 [修订的数据流](design.md#接口与数据流) 和 [媒体上传入库时点](../../../apps/im-server/src/media.ts#L211)。截图上传支持按 Agent 与原键查询已提交资源，避免依赖再次读取本机文件。普通与 PA 主人私聊复用 [普通发送回执](../../../apps/im-server/src/gateway.ts#L571)，PA 对外新增受绑定身份及目标校验的只读查询，查 [PA 已确认记录](../../../apps/im-server/src/personal-actions.ts#L130)。模型显式查询原操作，确认、未知和发送动作分开。M1 覆盖上传与普通/PA 提交丢应答。
- **R1-W2 closed。** Author 接受并明确公开结果、SingleThread 过程及权限卡使用安全投影。该边界覆盖原 finding 的输入、结果和权限请求出口，实际执行与自动审核仍有完整路径。脱敏后人工授权依据属于这轮新决定的影响，另见 R2-W1。
- **R1-W3 closed。** Author 接受并在 [关键决策](design.md#关键决策) 独立定义 Gateway 截图模式，复用 [静态解码约束](../../../apps/im-server/src/personal-images.ts#L5)，逐图校验类型、10 MiB、4096，PA 另受既有审核 20 MiB 总量边界。失败归因返回 Agent，普通用户上传保持原探测语义。M1 增加非法图片验证。
- **R1-W4 still-open。** Author 已把 Gateway delta 改为 MODIFIED，保留其余原 Scenario，且同一来源只准备一次。对照 [设计](design.md#关键决策) 和 [delta 首段](specs/gateway/routing-delivery.md#modified-requirements)，显式截图的五位置约束仍未写入 delta。具体见本轮 R2-W2。
- **R1-W5 closed。** Author 已补 [隔离 Runbook](design.md#runbook-for-reviewer)，指定第二账号从 [注册及公司加入流程](../../../apps/im-server/src/identity-routes.ts#L197) 取得，先验证非成员再通过 [实际群成员入口](../../../apps/im-server/src/messaging.ts#L883) 加入，明确另验 PA 本人有写权限和准许/拒绝。模拟器来自 R1 已确认的本机资源，构建入口和隔离地址已落实。
- **R1-R1 accepted。** 修订的模型设计覆盖可见标题、窄屏顺序与子执行者向根 Agent 交接。实现时在生成源落完整范例，由实际出站上下文和行为验证。

### Issues

#### R2-W1 人工批准截图发送时缺少足够的授权依据

位置为 [关键决策](design.md#关键决策) 和 [数据流 1](design.md#接口与数据流)。当前 [审核的交互分支](../../../packages/dsh-integration/src/policy/approval.ts#L98) 可能在 Auto 关闭或审核分流时请求人工批准。SingleThread 将该请求发到 [当前群的权限卡](../../../packages/personal-assistant/src/single-thread.ts#L417)，[决定入口](../../../apps/im-server/src/conversation-actions.ts#L399) 只要求请求者拥有群写权限。修订稿同时约定该卡只展示图片数量及失败类别、审核保留实际路径。自动审核可以消费原参数，但既有人工入口没有私有的实际动作证据，群成员可在不知道所授权图片的情况下允许 Node 读取并发送本机文件。

明确该分支如何给授权者足够的待发对象与目的地证据并保持路径隔离，或者规定无法安全确认时拦截并给 Agent 可操作反馈。现有群权限卡仅见数量的通过操作不足以承接新加的本地读图与外发。M1 应核对手动批准分支的实际行为，不只核对聊天中路径已脱敏。

#### R2-W2 Gateway delta 仍欠显式发送附件位置上限

延续 R1-W4。现有正文在 [Gateway delta](specs/gateway/routing-delivery.md#modified-requirements) 只写每气泡至多五个不同来源，后续场景只说同来源准备一次。设计把既有 URL 与本地图合计限制为五个有序位置，同一来源的重复位置仍占槽。六个位置且只有五个来源的显式调用，根据设计被拒绝，按 delta 则未越限。补充显式发送限制并保留原普通回复的不同来源约定，避免消费者将重复引用规则理解为可以绕过显式附件数量。

### Recommendations

本轮无新增建议。

### Author Resolutions

- R2-W1 accepted。需转人工的发图调用在执行前拒绝，现有群审批卡不处理缺少私有待发证据的请求。设计、首文档与 Gateway delta 对齐，M1 覆盖无上传、无公开审批卡和无路径。
- R2-W2 accepted。Gateway delta 区分普通回复的来源上限和显式发送的五个有序位置。

## Round 3

- reviewer: `/root/design_review`，独立 Gate 2 reviewer，与 R1/R2 同一身份
- target: `4d22e0c534910f1555ab691f4a42ff11e3ae03df` 与冻结的 staged blobs。首文档 `35352921`，design `1c73f3e6`，Gateway delta `e2d4f96c`，IM delta `743321b0`，M1 骨架 `e69de29b`。
- review_mode: `delta`
- mode_reason: 首文档把原授权约束细化为手动确认不可行时的失败场景，设计选择执行前拒绝，并补齐已有五位置约定的 Gateway 表达。改动限于权限失败分支和契约，主要场景、接口、职责和 milestone 范围沿用此前审查。
- started_at: 2026-11-09T11:22:12+08:00
- completed_at: 2026-11-09T11:22:41+0800
- duration: 29s
- verdict: **Approved · 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- 对照首文档新增失败场景、设计权限分支、Gateway delta 及 M1。实际审核的 [交互决策](../../../packages/dsh-integration/src/policy/approval.ts#L98) 和 [执行前审核结果](../../../packages/dsh-integration/src/policy/approval.ts#L104) 能承接截图专有的拒绝，先于 [product bridge](../../../packages/dsh-integration/src/product-bridge.ts#L19) 的节点读取与上传。既有 [SingleThread 权限通知](../../../packages/personal-assistant/src/single-thread.ts#L417) 和 [群权限授权端点](../../../apps/im-server/src/conversation-actions.ts#L399) 留给可在现有界面有效确认的动作。实现验证应从真实工具决策核对最终需人工的分支、Agent 私有失败反馈、公开过程脱敏，以及无截图上传、无交付、无该权限卡。
- Agent Context 增量只涉及该拒绝分支，明确 Agent 得知本次未发送及现有人工附件入口。普通 Agent 已有明确允许的权限判定，PA 对外另有 [冻结实际附件及受众](../../../apps/im-server/src/personal-actions.ts#L124) 的产品审核，均可沿此前决定实现。
- retained_from: Round 2。工具的读回执、冻结上传、媒体接纳与公开投影方案、PA 提交链、角色及双端 Runbook 无实质变化。IM delta、布局、历史只读和原图失败回退均未受影响，沿用 R1/R2 的证据与实施验收安排。本轮为静态设计复审。

### 历史问题闭环

- **R2-W1 closed。** Author 在 [关键决策](design.md#关键决策) 明确截图操作需转人工时在读取、上传前拒绝，避开缺少私有证据的群权限卡。新增 [首文档场景](spec.md#scenario-群聊中缺少足以确认图片的人工审批入口) 和 [Gateway 场景](specs/gateway/routing-delivery.md#scenario-截图发送需要人工确认) 同步要求未发送反馈及群内无此审批或路径。M1 补充手动拒绝和脱敏。PA 的产品披露审核继续消费实际图片与受众。
- **R2-W2 closed，R1-W4 同时关闭。** Author 在 [Gateway Requirement](specs/gateway/routing-delivery.md#requirement-当前会话的-agent-图片回复具有统一交付语义) 分别规定普通回复的五个不同来源、显式发送混合列表的五个有序位置及重复位置计数。准备资源按来源复用，位置约定与 [设计](design.md#关键决策) 一致。既有普通回复和 Feishu Scenario 继续保留。

### Issues

无。

### Recommendations

无。

## Round 4

- reviewer: `/root/design_review`，独立 Gate 2 reviewer，与 R1–R3 同一身份
- target: `0bb73665c3198f8956c7a130ebf4e7f8b2d19de7` 与实施期间修订的 design blob `e09e6e6a`。只审 Changelog、组件决定、模型段及相关契约。
- review_mode: `delta`
- mode_reason: 同消息图片引用从普通 Image 的 URL 参数改为专用组件，影响卡片语法、模型说明和旧版渲染器的回退。其他已审决定沿用。
- started_at: 2026-11-09T11:32:26+08:00
- completed_at: 2026-11-09T11:33:10+0800
- duration: 44s
- verdict: **Approved · 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- 旧目录的 `Image` 把 `src` 交给只接收 HTTP(S) 的 `webUrl`，找不到有效图片时可用 `alt` 请求公开照片搜索。旧 Web 和 iOS 共用该组件目录。若把受保护附件编码成 URL 字符串，旧版可把图片说明送去搜索，或用无关图片替代截图。专用 `AttachmentImage(1, "改动前")` 使旧目录不会调用普通图片组件处理这一引用。Web 与原生 iOS 的旧消息视图都独立于卡片遍历普通附件，支持设计规定的原图回退。以上通过基线 `0bb73665c` 的 [普通图片组件](../../../src/IM/frontend/src/features/chat/interactive/open-intelligent-ui/components/media.tsx#L81)、[URL 校验](../../../src/IM/frontend/src/features/chat/interactive/open-intelligent-ui/components/style.ts#L19)、[旧目录](../../../src/IM/frontend/src/features/chat/interactive/open-intelligent-ui/library.ts#L26)、[Web 附件入口](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L1926) 和 [原生附件入口](../../../src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift#L68) 核对。
- [关键决定](design.md#关键决策) 与 [模型说明](design.md#模型可见信息) 一致。数字仍为同条消息完整附件列表中的一基位置，只能取图。Alt 用于说明，普通 `Image` 保有它原来的照片行为。更新目录生成源及完整图文范例即可给模型正确入口。实施验收应观察新旧目录对同一条消息的结果，包括新版可打开原图、旧版附件仍可点开，以及截图说明未触发公开图片搜索。
- [Gateway delta](specs/gateway/routing-delivery.md#scenario-卡片和附件对应同一批图片) 与 [IM delta](specs/im/conversations-messages.md#scenario-卡片或图像无法加载) 已按消息顺序、权限、显示结果及附件回退描述行为，无需写入组件名。设计 Changelog 记录组件语法调整及旧版回退。
- retained_from: Round 3。附件和 PA 的身份、文件、顺序、权限、上传、回执、原生桥接及里程碑范围与此前一致。前轮关闭问题沿用已有证据。本轮核对设计与旧版源码，运行效果由 M1 实施验收证明。

### 历史问题闭环

R3 已无开放问题。语法改动未影响此前闭环。

### Issues

无。

### Recommendations

无。
