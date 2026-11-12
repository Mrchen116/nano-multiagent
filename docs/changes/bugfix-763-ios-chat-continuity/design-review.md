# bugfix-763 Design Review

## Round 1

### Metadata

- reviewer：独立 delegated `change-design-reviewer`，session `07871190-134a-4121-bbb7-e2ac47b16be7`；未参与受审首文档、设计或实现创作。
- reviewer runtime：执行环境不支持显式 model / effort 参数，未声明固定模型；本轮没有调用产品模型。
- review_mode：`full`。
- mode_reason：首次 Full Gate 2；无历史 Round，需要独立核实全部现状、需求、关键决定、delta、milestone 与证据安排。
- reviewer_target：worktree `/private/tmp/nano-ios-chat-continuity`，branch `unit/bugfix-763-ios-chat-continuity`，HEAD `2b65a5dc3674dff8e0c33f5f694f046b4527e9a4`；基线 `origin/develop` / `45babb2b49e314754c6ca390f4ca3da61fe9f107`。
- 版本核对：上述 HEAD 相对基线仅新增本 unit 的 incident、design、delta 和 `M1-continuity/.gitkeep`，未含原生实现修改；检查时 working tree clean。
- started_at：`2026-11-12T11:34:17+08:00`。
- completed_at：`2026-11-12T11:36:29+08:00`。
- duration：`00:02:12`（首个可复核时钟读数至结论冻结；此前已开始的材料读取不计入此值，不代表本轮总耗时）。
- 已加载能力：`change-design-reviewer`、`frontend-experience-review`（设计模式）、`product-journey-review`（验证方案判断）、`performance-review`（设计模式）、`codebase-design`。无模型可见内容变化，不扩为 Agent Context 审查。
- 执行边界：只新增本报告；未改受审文件，未实现、启动服务/模拟器、操作手机或生产、提交、push、部署或 merge。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

整体方向与用户已确认的体验取舍一致；滚动所有权方案具备可实施的主体结构，delta 和单 milestone 范围基本一致。但连接故障的来源/恢复归属尚未闭合，性能退出标准也不足以作确定判断。应先修订并复审，不能仅凭 baseline build、旧报告或未来 helper 的准备进度进入“已通过”状态。

### Coverage 与决定性证据

#### 1. 首文档、用户约束与 current 对齐

已完整读取 `incident.md:1-89`、`design.md:1-147`、unit delta `specs/im/ios-client.md:1-79`、空的 `M1-continuity/.gitkeep`，并对照 canonical `docs/specs/im/ios-client.md:1-250`。

- 本次为新 unit，不重开 714/716；已有 local-first、撤销清理、发送身份、私人编辑语义是保持项，不以重做旧事项扩范围。
- 明确覆盖 Chats 与会话的短重连零文字/图标/toast、持续失败与首次无缓存的诚实反馈、发送/账号失效不隐藏、Chats 重进到最新、详情返回/前后台保留阅读、动态高度/键盘/输入区、主动最新与旧分页竞争。
- incident 对手机 SHA、帧停顿和根因的不确定性表述准确，没有把“本地 SQLite / WebKit 存在”冒充卡顿归因。
- 用户允许本轮新建独占合成真实 IM / 专用模拟器与必要停启；不涉及手机、生产或部署。首文档直推被工具拒绝后的独立 unit branch → PR develop 路径已在 `design.md:145-147` 明确，本轮未重试直推。

#### 2. 实际产品组装入口及现状断言

不是仅核对引用行存在，已沿实际组装入口核实：

- `NanoIMApp.swift:107-113,225-246,305-320`：AppModel 持有同账号 ChatStore，RootTabs 的 NavigationStack 组装 Chats / ConversationView；scenePhase 驱动 run/stop，`chatPath = [id]` 打开会话。故滚动意图应归当前导航实例，而不是账号级永久位置。
- `ChatListView.swift:25-59,101-109` 与 `ConversationView.swift:39-46,47-132`：连接提示确实是条件插入的内容行；读取/业务错误确实存在共用展示入口。
- `ChatStore.swift:381-448`、`UserStream.swift:19-54`：run 在 HTTP sync 后、socket connect 前写 online 并清 attempt；connect 发送 resume 后返回事件流。D2 将完整可用性延后确认的方向有源码依据，但还有其他状态生产者，见 R1-W2。
- `ConversationView.swift:75-80,111-131,155-188`：旧分页完成无条件 top、restore 无条件 center；count / 末条正文才触发单次 bottom；详情 push 与页面 disappear/task 生命周期是本次必须覆盖的实际路径。
- `InteractiveWebView.swift:5-10,66-69` 已把桥接高度变为原生行高；`MediaViews.swift:5-32` 从进度占位切换图片后可变高。统一监听宿主几何、而非新增卡片完成协议，符合现有责任边界。
- `ChatStore.swift:648-715,719-725,951-975`：打开先读本地，历史权威校正和清理恢复另有异步链；读回执会请求并更新会话投影。`MarkdownView.swift:9-15` 每次 body 构建 AST，`CommonViews.swift:134-146` 解析日期；这些只能列为待测代价，不能先宣称主因。
- `src/IM/ios/README.md:3,24-64` 与真实 `UITests/LocalFirstLaunchUITests.swift` 支持最低 iOS 26、独立 NanoIMJourney 和真实登录/缓存连续旅程；既有测试不能直接证明本轮动态尾部和滚动性能已过。

#### 3. 状态与滚动生命周期 / 竞态

D3/D4 对以下设计决定表达充分，可以指导实现，不要求在 Gate 2 提前实现：

- `followLatest / readingHistory` 与几何分离；初次创建显式到底，而详情 pop / foreground 不按每次 onAppear 重置。
- tracking 暂停，实际用户滚动推进 revision；无位移触碰恢复原意图；程序定位/异步增高不当作用户上翻。
- 最新动作立即取得定位所有权、无长途动画，不等待网络；旧分页与清理 restore 必须核对仍有效的 revision。合法历史合并与权限校正不能为位置取消而丢弃。
- readingHistory 保存稳定消息及相对有效视口偏移，动态增高/分页只作锚点纠偏，用户交互期间不反向抢位；删除锚点不能复活内容。
- adapter 独占 ScrollPosition，几何驱动尾部纠正且同代合并，不依赖固定 500ms 延迟。worker 仍必须实测 LazyVStack 估高后的真正尾部、用户中止、分页迟到、详情/foreground 返回；本轮没有把这些目标写成实现 pass。

连接五秒静默与稳定 slot 的用户体验决定基本明确；但“连续不可用”的来源、何种成功结束该期间、谁负责重试仍有未闭合路径，见 R1-W2。

#### 4. 最小接口、职责与依赖

- 可复用的 repository / TimelineMerge / 权限 fence 保持权威，View 内私有值策略负责用户意图与定位仲裁，SwiftUI adapter 负责实际滚动；卡片/图片只报告自然布局结果。比在多个 onChange 各自强制 scroll 或扩展卡片协议更有 locality。
- 当前设计没有新增 IM API、schema、跨包依赖、第二运行时或 DSH 入口；不需要迁移或 `deployment-prompt.md`。回退为撤销客户端变更可行。
- 连接展示的 `update / presentation` 小接口可复用、可注入时钟，但其上游状态结果必须收口，不能用展示延迟掩盖原始状态所有权问题（R1-W2）。无需为此引入公共泛化 coordinator。
- 性能优化限定私有路径，缓存必须有界/随生命周期，不缓存授权与受保护媒体，保持范围可审；哪些候选真正值得改，应由测量决定。

#### 5. Delta、milestone 与验收安排

- delta 镜像并锚定正确 canonical `docs/specs/im/ios-client.md`；两个 MODIFIED Requirement 都保留未改变的 Scenario，新增阅读连续性从用户结果描述，不把五秒、类名或偶然性能值写成长青契约。
- M1 同时覆盖连接/滚动/受测量支持的呈现优化及相关回归，串行集成合理；骨架仅 `.gitkeep`，未提前造任务台账。
- 对首读失败、发送失败、登录失效、权限/清理 fence 与 timer epoch 安排相关回归合理。真实原生 journey 必须与单测互补，单测不能代替动态尾部或布局判断。
- runbook 提供独占服务启停/健康检查、Xcode build-for-testing / test-without-building、fixture owner/凭据、专用 UDID、停启授权与清理责任；无需 Gateway 或产品模型，和局部 iOS 任务相称。helper 正在准备不是已完成验收。
- 同模拟器、纯文/卡片、冷暖、大滚动/远距最新、请求和必要主线程 profile 的维度选得对；但仍不能确定何时性能目标成立，见 R1-W1。

#### 6. 前端体验与产品旅程：设计判断及限制

本次恢复已明确交互，不因改 SwiftUI 就强制 HTML 原型。`design.md:53-60,97-101` 给出了导航标题/稳定辅助 slot 与正文、返回、主操作的关系，可审查其意图；不另造原型合理。

短重连空 slot 且无辅助访问噪音、持续失败一处可展开恢复、最新箭头沿用右下角，符合安静内容优先的目标。固定 44pt principal 在长标题/辅助大字号下是否真不遮挡、是否与相邻现有界面协调，以及连接断开时输入/键盘/阅读是否不跳，**实际视觉与操作均未验证（inconclusive）**。设计已将基线/候选原生画面及连续操作列为必须证据，不能把本轮设计判断改写为 UI 体验通过；也不要求尚未实现的真实产品在本轮提前验收。

### 历史问题闭环

首次 Round，无历史 finding 或 Author Resolution 可关闭。父层在审查期间提出的 fixture / 测量补充意向不是本轮受审版本，不作已修复证据。

### Issues

#### R1-W1 — 性能测量维度有列出，但缺少可复现协议与可判定退出标准

- severity：**WARNING**；status：**open**。
- 位置：`design.md:83-87,109,137,143`；对应 `incident.md:84-89`。
- 证据：目前只约定“相同历史规模”“冷/暖”“适用的 CPU / wall-clock”，未冻结历史总数与实际加载窗口、文本/卡片/图片负载与页边界、冷暖/缓存定义、手势/跳转起点、样本与波动处理。没有定义点击到稳定尾部的计时终点/稳定窗口、可比较滚动代价的选定指标，以及何种改善/无回归/无法取得指标允许或禁止退出。M1 只要求“实测卡顿因果与性能对照及限制清楚”，有几份计时且限制写清就可能被判退出，即使仍有明显停顿或样本未触及大历史路径。
- 未修后果：候选可因装载更少历史、卡片未挂载或偶然一次暖缓存显得更快；也可能把正确到尾部等价于解决帧停顿。reviewer 无法独立判定用户报告的卡顿已闭环，形成有数据却不可裁决的实施返工。
- 需修订：在设计/runbook 或其明确绑定的协议中冻结有代表性的 fixture / 实际加载范围、同设备/字号/build/config/缓存条件、确定动作和重复规则；规定真实尾部与稳定的可观察判据、选定的原生操作/滚动代价及请求证据，明确候选无回归、基线可复现 hitch 时的改善判据与波动处理。允许基线无法复现时诚实限定结论，但不能以“已记录限制”直接把必要性能目标判 pass；无法取得决定性测量时如何阻止退出也应写清。数值可由作者结合基线选择，不要求宣称通用行业 FPS 标准或真机无掉帧。

#### R1-W2 — 后台读取与实时传输仍共写一个 connection，恢复与重试所有权未闭合

- severity：**WARNING**；status：**open**。
- 位置：`design.md:53-64,89-94`。
- 证据：D1 要把后台读取 transport / 服务不可用错误送入连接策略，D2 又把 online 的成功点限定为 sync + socket 确认；但实际 `ChatStore.loadConversations`、`inspectConversation`、`loadChat` 的失败分别在 `ChatStore.swift:550-557,592-603,709-715` 独立写 connection，成功路径只清相应错误，不向连接策略确认恢复。run 已在 `413-427` 的健康 socket 事件循环时，这些方法失败不会让 run 抛错并启动重连。因此“健康 WS + 单次 HTTP 读取失败 → 同一读取重试成功”可能仍留在 offline / 稳定『自动重试中』，却既无故障也无下一次重试。另 `scheduleAccessRecovery` 在 `915-922` 仅 HTTP sync 成功就写 online，会绕开 D2 以及 D1『HTTP 成功但 WS 失败不重置静默时钟』的不变量。
- 这不是要求逐行实施细节：当前小接口仅消费最终 state，但尚未决定不同故障来源如何合成该 state、相应成功清除什么、谁保证辅助文案承诺的自动恢复；只在 run 的既定位置延后 online 不能闭合这些已存在的入口。
- 未修后果：要么部分 HTTP 故障把健康连接永久标为不可用，后台/页面重试后仍残留提示；要么 HTTP-only 恢复误清实时故障，使持续失败再次循环五秒静默。都会违背本轮“不闪且诚实”的主要目标。
- 需修订：明确实时连接健康、内容校正故障、业务操作错误的最小私有责任/合成规则及成功/失败/取消/epoch 入口，覆盖所有 online 写入点；每个持续不可用状态有真实且有边界的恢复/重试 owner，不用笼统文本过滤。补上可确定控制时序的验证：① WS 健康时 HTTP 失败再成功，清除对应故障且不误伤 WS；② HTTP sync/access recovery 成功而 WS 未可用，不结束实时故障或重置静默期间；③ 重试/前后台/退出迟到结果不恢复旧 owner。不要求新服务端 API 或公共连接框架。

### Recommendations

无额外阻断或风格建议。修订后可针对上述两项及其真实波及范围选择复审模式；其余已经核实且未失效的 current/delta/滚动主体证据可引用本轮，不机械重跑全产品或重建相同现场。

### Author Resolutions

- **R1-W1 — accepted**：D5冻结两组300消息/同文本、2卡2图及真实加载页边界；固定同模拟器/配置/冷暖定义、动作、warmup+5样本、波动复测上限；定义真实尾部稳定窗口、handler→tail与外部墙钟区别、hitch/CPU/内存指标及明确退出/阻止退出规则。M1同步绑定全部D5判据。仍无原生测量结论，不冒充实施通过。
- **R1-W2 — accepted**：D1/D2与接口段改为raw实时传输由run/terminal独占、校正错误按surface相关scope独立持有/清除；成功读只清对应scope，fullsync/access recovery不写rawonline；raw真实退避自动重连，scope仅承诺显式重试或既有正常校正，不虚构自动重试。timer/stop/reset/epoch规则和healthyWS+HTTP失败成功、HTTP-only成功但WS仍失败的回归写入M1。
- 同时将默认44pt导航slot改为按Dynamic Type适配、同字号下状态切换不改高度，避免固定高度裁切；不改变已定导航反馈位置/信息层级。以上是实质修订，交原独立reviewer复审，未自行关闭Gate2。
