# feat-634 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review` — independent `change-design-reviewer`; 未参与受审设计和实现。
- review_mode: `full`
- mode_reason: Gate 2 首轮；覆盖需求、现状、核心接口与状态流、原生体验、delta-spec、milestone 和验收前置。
- started_at: `2026-10-22T00:34:32+08:00`
- completed_at: `2026-10-22T00:41:26+08:00`
- duration: `6m54s`（首个记录时间至完成；此前已开始读取材料）
- checkout: `/Users/czj/.codex/worktrees/ios-cards-recovery/nano-multiagent`，detached HEAD `49520f85fb27ac5af1b667ecd7aac32ad68ae28e`，设计基线 `a782cdd3f`。
- 受审对象：`spec.md`、`design.md`、`prototype.html`、`specs/im/ios-client.md`、`M1-native-chat/.gitkeep`。本轮只新增本报告，不修改受审对象或产品代码，不提交。
- 最终受审 SHA-256：spec `4a729716acecff28218b61bea9c8660547ebfce668736a4ef7c9e488b915af55`；design `b104221b3f8a5305e7bb84f9aa6c333c595528ee7544a3ae0ad67cb3c48aa163`；prototype `bd776e38ecc28bf51e00deac7b5806fe0ed690b9effb51af7d5b6025fbfbe016`；delta `f82d67eb0bddd3d92ff41a8663230a52391bfbf036c5485a2fe68aaf2a90a42f`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案能够在既有原生客户端、公开 OpenUI 解析能力和现有 IM 协议内兑现需求。原型已提供足以指导本次实施的内容关系与关键恢复操作；通过限于设计，不代表真实后端、进程重启恢复、IPA 或手机更新已经验收。

### Coverage 与证据

#### 现状和用户约束

- 从真实入口 `NanoIMApp → RootTabs → ConversationView → ChatMessageView/ChatStore → ChatAPI → Session` 核对。`ChatMessageView.swift` 现有正文、附件和专用审批没有通用交互呈现；`ChatAPI.swift:14` 每次调用 `ChatText.wire`；`ChatStore.swift:253` 将原始内容放入内存 pending，未知结果后保留该对象但没有磁盘恢复。这与 design 现状断言相符。
- `apps/im-server/src/message-attempts.ts:12` 冻结普通正文、附件和私人背景，`:26` 对同 key 不同内容返回 409。冻结 wire 正文、附件、背景和序列化请求，而非重试时重新按成员列表转换，直接对应本次提及改名兼容问题；没有通过放宽服务器约束规避它。
- 用户要求的原生呈现、完整通用交互语义、普通/附件/交互发送恢复、409 兼容、验证、打包与 AltStore 现有应用更新均进入 spec 和 M1。安装后的实际版本与源码可追溯要求保留，没有把续签当成代码更新。

#### 职责、依赖和复用判断

- 新职责在 iOS：JSCore bridge 解释既有版本化源；SwiftUI 呈现与收集原生输入；InteractiveRuntime 管卡片状态、工具调用和动作；ChatStore 统一可靠发送和时间线；磁盘 owner 只持久化不可变 attempt；Session 继续负责凭据及代际。这个划分避免把凭据、网络和磁盘能力放进解释器，也没有新增业务服务、第二套 Agent Loop 或 DSH private import。
- 本地安装的 `@openuidev/lang-core@1.0.1` 公开 package exports 与 `dist/index.d.mts` 确认存在 createParser、evaluateRoot、evaluate、createStore、resolveStateField、builtInValidators，并公开 ActionPlan 的有序步骤和 Query/Mutation 元信息。相较重写语法、表达式和状态求值，复用该解释器且仅补原生宿主与组件呈现更符合现有边界。
- `packages/product-contracts/src/interactive-catalog.ts` 含完整 nano-1 注册目录。design 明确所有显示组件对应原生呈现、数据子组件由父级消费，覆盖表格、各类图表、表单、选择、Tabs、Accordion、Modal 等；不是只实现原型中的数字输入。W1 承担全目录与类型/动作契约验证。
- 绑定元数据是必要约束而非可省略细节：lang-core 的 `evaluateElementProps` 在空组件 library 下会把 reactive binding 求为标量，服务端 `interactive-source.ts` 的只读求值方式不能直接充当编辑器。design 已明确保留绑定元数据并使用 resolveStateField；实现需以公开 markReactive/组件 props schema 或保留 AST 的方式兑现，验证字符串、Slider 数组、选择对象及 Set 后捕获快照。此项已由 design 与 W1 覆盖，不需另造解析器。

#### 接口和状态流

- 公开内容读取、私人草稿、业务提交分开：`interactions.ts:76` 按登录用户读草稿，`:84` 以 expected_draft_revision CAS 保存并检查写权限，`:100` 校验源、动作、状态及幂等语义。design 的默认值合并、本地联动、合并保存、冲突停止覆盖与读取最新、显式动作不可变快照与重复探索，与现有契约闭合。
- `interactive/catalog.tsx` 和 `interactive-card.tsx` 确认当前白名单只有 conversation_messages Query 与 continue_conversation Mutation。design 保留当前会话授权读取、明确动作才修改、未知工具实际报错、http/https OpenUrl，以及 Set/Reset/ToAssistant 的动作顺序，不把历史恢复当业务动作，也不把入队回执写成业务已完成。
- `messaging.ts:589` 把交互 key 保存为 `interaction:${userID}:${key}`，`message-attempts.ts:40` 按实际存储 key 查询本人消息。design 已明确交互 lookup 的用户前缀，普通及交互发送均在首次 POST 前持久化，恢复只查结果，用户重试先查后以原 bytes/key POST；409 也先核实已有结果，未盲目生成新 key。
- `message-pane.tsx:720` 的私聊背景过滤与最近三张排序已核对；design 同时过滤只读/替代源，并把背景与附件一起冻结。群聊普通文字不隐式共享私人草稿，手写正文不改写。
- `Session.swift:56`、`:82` 与 `NanoIMApp.swift:178` 核实退出失效请求、前后台 stop、view 消失 clear 的现有边界。design 明确将磁盘记录删除绑定 logout/切服务/资格或聊天访问撤销，view 消失与后台只停止 UI/请求；epoch 加 Session generation 阻止迟到结果回填。普通/卡片 pending 的归属及“只在当前草稿仍等于原快照时清空”覆盖旧确认破坏新草稿的问题。

#### 原生体验与原型独立走查

浏览器 file URL 已被安全策略拒绝，本轮没有更换浏览器或代理 HTML 绕过。独立审查实际查看同内容的临时 SwiftUI 原型，目标为 `Nano feat634`（iOS 26.4，UDID `8874240E-8E65-43C4-9405-CCA73C94440D`）；源码 `/tmp/nano-feat634-prototype/NanoIM/Prototype.swift`。原型未接后端。

- 实际查看 `/tmp/nano-feat634-prototype-normal.png`、`-conflict.png`、`-recovery.png`、`-large.png`。主结论、带“分钟”单位的控件、周结果与日序图形构成连续阅读顺序，说明明确图形表示时间投入；明确继续与恢复默认有主次。未知发送和冲突提示紧邻卡片与 composer，不要求用户理解后台阶段。
- 通过 CUA 独立操作原生控件：20 改为 35，结果 140 变 245 分钟/周；恢复默认回到 20/140；点击明确继续出现“请求已发送，Agent 将在聊天中回复。”；切只读历史后业务按钮移除并出现历史说明；触发冲突后点击“读取最新”，20/140 变 30/210；触发未知发送后点击“重试核对”，提示消失且新草稿“稍后请提醒我”保持。
- accessibility1 大字体截图中标题、说明和图表标签换行，底部草稿保持可见；审查者在大字体下实际点击主动作后，原生滚动定位显示主按钮及回执。普通 scroll/drag 自动化未产生位移，不把它记为触摸滚动通过。真实客户端的大字体触摸滚动、键盘及全部目录仍属于 M1 验收；当前信息组织和原生 ScrollView/控件决策足以指导实施。
- 与现有 `ChatMessageView/ConversationView` 的消息身份、正文、附件、审批及固定底部输入布局核对，并查看 feat-617 保留的 `new-policy-interactive-mobile.png` 历史画面作为交互层级参照。原型为新增内容的设计目标，不把它当作当前客户端聊天截图。must-match 已投影到 M1 R1–R3 / W1–W2；原生图表和控件的可变形式有明确语义约束。

#### Delta、milestone 与验收前置

- delta 镜像 canonical `docs/specs/im/ios-client.md`，以 ADDED 新增原生交互和持久恢复两条 Requirement，保留现有场景；内容为原生消费者可观察结果，未把 Web 专属行为原文覆盖到 iOS。
- M1 是一个完整用户闭环：R1 覆盖本地探索/条件/图表/查询及可读性，R2 覆盖私人 CAS/明确动作/只读与权限，R3 覆盖重启不确定恢复/无重复/新草稿/安装打开；W1–W3 对应解释器目录、不可变发送、会话撤销、构建与验证。单 milestone 无并行文件冲突；仅 `.gitkeep` 的骨架符合当前 workflow，不预填实施记录。
- Runbook 给出隔离 IM 的启动/停止/健康、Debug origin、测试账号来源、独立模拟器、构建/测试/archive 和真实客户端驱动方式。模拟器本轮可用；物理设备、AltStore 与官方 UI 登录交接由主任务当前证据及 runbook 明确，不要求把 Apple 凭据写入仓库。最终仍需真实栈、手机更新与打开证据，不能用此原型替代。

### 历史问题闭环

无历史 Round 或待关闭 issue。本轮过程中补充的冲突、未知发送新草稿和大字体原型证据已纳入上述最终受审版本与独立走查，不遗留为下游未定设计。

### Issues

无。

### Recommendations

无额外范围建议；按 M1 已列退出标准完成实现及验证即可。

## Author Resolutions after R1

用户随后明确“你模拟器测就行，测好了提pr，合入之后再发到手机”。仅调整交付及手机验收时序，原生体验、接口、权限和持久恢复设计不变；R1 技术/原型结论 retained，当前模拟器验收不以手机登录为前置。合入后另行执行物理更新，不声称已经完成。
