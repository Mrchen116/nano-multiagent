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

## Round 2

### Metadata

- reviewer：原独立 delegated `change-design-reviewer`，session `07871190-134a-4121-bbb7-e2ac47b16be7`；未参与受审设计修订或实现，延续 Round 1 独立身份。
- reviewer runtime：不支持显式 model / effort 参数，不声明固定模型；本轮未调用产品模型。
- reviewer_target：同一 worktree / branch，HEAD `aab91da798f815e2064a866b6932c0b0da1c113e`；基线仍为 `45babb2b49e314754c6ca390f4ca3da61fe9f107`。
- review_mode：`full`。
- mode_reason：不是仅勾选旧问题关闭；本轮实质改变连接展示私有输入边界、故障恢复所有权和 M1 性能退出规则，另有 Dynamic Type 导航适配，按 full 重新核查全部决定及覆盖。未改变的源码事实和契约证据明确 retained，不冒充重跑真实旅程。
- started_at：`2026-11-12T11:47:26+08:00`。
- completed_at：`2026-11-12T11:49:43+08:00`。
- duration：`00:02:17`（本轮首个可复核时钟读数至结论冻结）。
- 专项：继续使用前端体验 / 产品旅程的设计与证据方案判断、性能设计审查、codebase-design；模型 Context 无变化，无需新增 Context 范围。
- 版本/边界核实：相对 R1 target 仅 `design.md` 的实质修订及 `design-review.md` 的 R1/Author Resolutions；incident、delta、M1 骨架、canonical 与实现均未改。审查开始时 working tree clean。本轮只向本报告追加 Round 2，无服务/模拟器启动、运行演练、实现、提交或 push。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。R1-W1、R1-W2 均在设计层关闭。**

受审设计现在能指导实施与独立裁决，没有发现会使下游实质走偏的未解决设计问题。此结论是 Gate 2 设计结论，**不是原生体验、性能收益或实现验收通过**；D5/M1 的决定性测量仍须在实施闭环取得，不得以此次 Approved 替代。

### Coverage 与证据

#### 1. 需求、版本、delta 与产品组装

- 完整重读修订后的 `design.md:1-162` 和本报告 R1 / Author Resolutions；复核 `incident.md:44-89`、完整 delta `specs/im/ios-client.md:1-79` 与空 `M1-continuity/.gitkeep`。Git 对比确认需求、delta、canonical 和源码没有变化。
- `retained_from: Round 1`：首文档全部用户约束与 canonical 对齐、AppModel/RootTabs → Chats/ConversationView 实际入口、UserStream/本地 repository/动态 WebView 与图片路径、权限/发送/媒体边界、delta 的完整 MODIFIED 与正确 canonical target。保留理由是相关文件及产品组装未变，本轮变更不另造数据源、schema、服务端 API 或 Context 入口。
- 本轮再次读取 `ChatStore.swift:381-448,658-747,904-951`，核对新故障所有权与实际 run、HTTP 读取、access recovery 的落点，而非仅采纳 Author Resolution。
- 714/716 不重开；首文档/设计/实现仍在本 unit branch → PR develop，不改变拒绝直推后的边界。无需部署迁移文件。

#### 2. 连接来源、恢复、文案和生命周期

`design.md:53-66,104-109` 现在明确三个不同责任：

1. run / 明确 terminal 结果持有 raw 连接状态，sync + WebSocket ping 确认后才 online / attempt 归零；后台读取不得回写 raw 健康。
2. list / detail(id) / timeline(id) / access 校正故障独立记录连续失败起点；只在当前 surface 合成，读取成功只清其负责的 scope，full sync / access recovery 不能清未校正的 timeline 或 WS 故障。
3. 业务发送/上传/访问结果仍由对象自身反馈，不用连接静默隐藏；raw 真有 run 退避才承诺“自动重试”，单次 HTTP 校正失败提供真实 scope 的显式重试，不虚构后台循环。

原有 `ChatStore.swift:920` 的 HTTP-only online 点被设计明确列入“检查所有 online 写入点”，不再作为绕过 D2 的例外。stop / 新 run 的 deadline 重新注册、reset / 退出清 scope、时钟及任务、旧 epoch 禁止回填均已规定；M1 同步要求 healthy-WS/HTTP 失败成功与 HTTP-only/WS 未恢复的验证。`updateTransport / readFailed / readSucceeded / presentation(surface)` 是有实际调用方的小私有边界，相比新增泛化网络 coordinator 更贴近现有 Store 生命周期，未额外引入公共机制。

#### 3. 滚动所有权、动态尺寸与返回

`retained_from: Round 1`：D3/D4 未改；重新核对修订后的全文仍保留 followLatest / readingHistory、tracking 与真实用户位移区分、latest 推进 revision、分页/清理恢复不得抢后操作、有效视口与真实尾部、历史 id+相对偏移、删除锚点不复活，以及单一 SwiftUI adapter。

新增 scope 错误只改变同字号下固定的导航 slot，不插内容行，不改变上述定位所有权；失败/恢复计时也不应重建消息、输入或键盘。M1 仍要求动态增高/键盘、读历史、详情/foreground 返回、旧定位竞争的连续原生证据。没有因修 R1-W2 而缩减滚动目标。

#### 4. 性能协议的可执行性与可判定性

`design.md:85-102` 及 M1 `158` 已把“有测量”改成有边界的可复核协议：

- 同模拟器/iOS、字号、竖屏、键盘、Xcode、Debug、source/fixture；基线产品树和测量 harness 均绑定实际 SHA。
- 两组各 300、同 base Markdown，混合组两卡两受保护 PNG；UI 的真实 Earlier 加载与 API 页边界双核对，不仅 seed DB 就声称已触及大历史。实际 `ChatAPI.swift:4-7` 请求 60 条，`ChatRepository.swift:65-68,369-372` 保留 300 窗口，与协议规模可对上。
- 冷启动采用相同已确认本地窗口而不是空库对暖缓存；确定滚动/Latest 起点，warmup 与 5 measured 分开，保留每次值、中位与范围，失败样本不剔除，额外复核次数有上限。
- 三次约 200ms 观察和 4pt 漂移判定的是测试稳定尾部，不是产品固定延迟；handler→tail 与 XCTest 外部墙钟分列，既有内容与新挂载卡片分别有时延界限，不伪称触摸到呈现延迟。
- hitch ratio 有明确无回归边界、基线明显停顿时的改善门槛；CPU/内存回归与例外须解释并有对照，不能靠减少必要内容/授权工作换收益。
- 非空原生指标、负载触及、操作时延为必需；无法取得等效指标或样本持续不稳明确为 inconclusive 并阻止作为已完成交付，不再以“限制清楚”替代退出。基线未复现时只作该负载限定结论，不冒充原手机根因。

为验证所选测量入口不是假定存在，本轮只读核实本机 Xcode 的 XCTest 公开 headers：`XCTMetric.h:211-219,265-269,376-386` 声明 scrollingAndDecelerationMetric 与 iOS 26 XCTHitchMetric；`XCTMetric+UIAutomation.h:12-40,60-72` 声明 application 定向 CPU / memory / hitch 初始化。**这仅证明 API/target 能力有静态依据，不证明模拟器会产出非空 hitch 数据**；后者仍按 D5 fallback / inconclusive 规则在实施时核实。

这些值是本 unit 的工程工作阈值，不是行业或真机保证；不需要把它们写入长期 delta。本轮没有替作者提前做基线测量，也没有降低测量门禁。

#### 5. 导航体验、旅程证据与实施资源

- `design.md:57` 从永久固定 44pt 改为默认约 44pt、按 Dynamic Type 适配、同字号状态切换高度固定，保持标题/辅助 slot 一贯布局与静默时无文字/图标/可访问噪音。没有引入新业务流程，不要求另造 HTML 原型。
- `retained_from: Round 1`：独占 IM / 专用模拟器、真实登录入口、凭据/manifest、健康检查、获准短长断开恢复及清理责任的 runbook，和 frontend / journey / code / performance 的必要覆盖。M1 现显式绑定全部 D5 退出条件及新增状态边界测试，串行集成范围仍成立。
- 父层交接称 300×2 fixture 的 API/DB 已核实、baseline 原生与 journey 构建成功；本 reviewer 未读取其运行原始产物，因此只作资源准备进展，不据此宣称 App 内观察或性能已完成。真实截图/连续操作、导航长标题/大字号、输入/键盘不跳及性能数均仍未验证，须在实施 review 保留。

### 历史问题闭环

| ID | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|
| R1-W1 | 冻结实际负载/冷暖/样本/动作与可判定尾部、时延、hitch、CPU/内存及不能退出条件，M1 同步 | 受审 design D5 `85-102`、M1 `158`；60 条 API / 300 本地窗口与 XCTest 公开测量 API 只读核实；不再允许零必要测量即完成 | **closed（设计层）** |
| R1-W2 | raw 与读取 scope 分离，成功仅清负责 scope，所有 online 点收归 run/terminal，文案按真实重试 owner，补 lifecycle/竞争测试 | 受审 design D1/D2 `53-66`、接口 `106`、M1 `158`；对实际 run / loadChat / access recovery 路径独立核对后，原两种反例已有明确落点与预期 | **closed（设计层）** |

### Issues

无新增 CRITICAL / WARNING；无仍开放的设计 finding。Round 1 的历史结论保持不变，本轮关闭状态不回写旧 Round。

### Recommendations

无新增建议。实施时按已批准方案取得本轮真实原生与性能证据；若指标/fixture或业务边界需实质改变，应记录差异并重新判断设计影响，不能借本轮 Approved 默默降标。

### Author Resolutions

Author 已完整核实 R2 与受审设计，无实质异议；0 CRITICAL / 0 WARNING，Gate2通过。R2之后仅追加本确认，不改incident/design/delta/骨架；独立原生体验和性能仍待实施验证。沿用主Agent确认的独立unit分支交付，不直推develop。

## Round 3

### Metadata

- reviewer：原独立 delegated `change-design-reviewer`，session `07871190-134a-4121-bbb7-e2ac47b16be7`；未参与受审设计或实现创作。
- runtime：未指定/声称固定模型或 effort；未调用产品模型。
- review_mode：`delta`。
- mode_reason：本轮只改变 D5 测量方法和 M1 对应退出分支，不改用户目标、产品接口或连接/滚动决定；重点重新审查替代方法的可证伪性、时间绑定、窗口覆盖、可比性和证明边界。
- target：`/private/tmp/nano-ios-chat-continuity` / `unit/bugfix-763-ios-chat-continuity`；HEAD `ed5248dc1fa74358ac74b65f9a98589cc4142d8d` 加冻结的未提交 design 修订，SHA256 `d1f1b83c49ea4e22541843db6a3d2cfeb87e2a5222b8de05a06d3d3d3f3615fb`。implementation 及其他在途文件不是本轮审批对象。
- started_at：`2026-11-12T14:04:45+08:00`；completed_at：`2026-11-12T14:05:40+08:00`；duration：`00:00:55`（可复核时钟读数区间）。
- abilities：`change-design-reviewer`、`performance-review`（方案模式；此前已加载，沿用官方证据边界）。
- 执行边界：只读研究/设计审查并追加本报告，未起 trace/build/test/GUI/录屏/模拟器，不占用 helper 的独占测量资源，不改受审对象。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。R3 替代测量分支暂未批准实施。**

有界能力探针、真实采集链校准、预先冻结 X、独立 receipt、不能成立就 inconclusive 的结构合理。它不是 Apple hitch 的数值等价物，也没有声称是。但完整预期运动区间与“合格窗口”的关系仍存在实质漏检通路，应修订后复核。

### Coverage 与证据

- 已完整读取新 D5 `85-115`、对应 M1 `171`，核对 git diff 仅新增 R3 六条和 M1 分支绑定；incident/delta 无本轮修改。`retained_from: Round 2`：既有产品目标、current/delta、D1–D4 生命周期/所有权方案、300×2实际加载、冷暖、动作/样本、真实尾部和 Latest 时延、CPU/内存边界及其他必要原生旅程。它们不因 hitch 工具不可用而被豁免。
- 原始 `baseline-animation-hitches-support.log:1-7` 已直接读取，实际提示平台不支持；空 hitch 不能作为零值。Apple 的 hitch 定义涉及预期与实际呈现，视频 sample PTS 名称不自带原 App vsync 保证；相关官方资料和本机 simctl help 的边界已在本轮前只读研究中核实。R3 正确承认这些限制。
- 一次 ≤15s Game Performance probe 有次数/时间/非空数据与 target/present/deadline判据，不把模板存在当能力已证实；不得取得就有限转支，合理。
- 校准 App 与产品 renderer 隔离，不借私有 hook 或降低实际负载加速；真实主线程冻结比只在分析器复制帧更能检测采集链问题。50/100ms 最小合格档、同档以上 positives 全检出、negative 无假停滞、误差与采样间隔、3对录制扰动、严格递增 PTS、≤X/3 事件绑定、分析 hash 和候选分析前 receipt 独立复核，形成可证伪的 fail-closed 结构。
- 采集是否逐帧输出、时钟映射及 ≤X/3 事件精度能否在本机真正满足仍未知；设计允许由校准失败作 inconclusive，没有宣称已实现或通过。capture 对源图形的扰动也不能只用 callback 无回归证明不存在；本轮允许它作为有限校准条件，不将 callback 间隔升级为 presented 帧。
- 候选每个保留样本不得有 ≥X 的合格停滞，比均值不回归更明确；但零停滞只能在充分覆盖的预期运动范围内成立，现有覆盖判据未确保这一点（R3-W1）。
- 正确保留本 Mac / sim / 负载 / 检测下限限定，不推出真机、单帧 hitch、Apple ratio 或原手机根因。无须改 consumer delta，也没有新增产品界面原型需求。

### 历史问题闭环

R1-W1/W2 在 Round 2 的设计层关闭状态保留；R3 是实际工具限制后的新验证分支，不把旧 Approved 当新分支已经通过。当前 implementation review 的 CODE-763 findings 不由本轮处理或关闭。

### Issues

#### R3-W1 — 每个 swipe 存在合格片段，不足以证明完整运动过程无可见停滞

- severity：**WARNING**；status：**open**。
- 位置：`design.md:108-110`，R3 第3–5条，尤其第4条“任何一次无有效可判定运动窗口”与第5条“全部合格窗口内”。
- 证据/反例：一个 swipe 开始后明显不响应 ≥X，之后平滑移动；或先移动、中间卡住、末段继续移动。现规则允许只取其有可靠位移的短片段作为该 swipe 的“有效窗口”，把开始无位移或中间低运动段归入未合格/自然减速区间。每次 swipe 仍各有一个窗口，候选“全部合格窗口零停滞”仍可能成立，却漏掉最应检出的卡顿。至少3 patch和前后同向能验证已选择的运动，不能证明选择过程未切掉停顿；匀速控制 App 的 freezes 被检出也不自动证明产品减速/输入边界的 eligible 算法无此漏洞。
- 未修后果：候选的坏片段可能因其坏而失去资格，构成只统计平滑部分的选择偏差。原协议的“不能只挑流畅段”意图正确，但目前可执行覆盖判据不足以强制它。
- 需修订：候选分析前定义每次 swipe 的完整预期活动/减速区间，边界来自独立输入事件和预先冻结的规则，而非候选画面有没有移动；所有应评估区间必须被覆盖，无法分类/追踪的片段使整 sample 无效，不能只丢片段。自然减速到阈值以下、首尾等合法排除需有独立依据和可审查的边界，不能据像素停住就循环推断“非运动”。校准用同样的窗口算法验证开始不响应、中途冻结、冻结后继续及实际减速/边界案例，证明 positives 未被 eligibility 排除；若公开事件/时间绑定无法支持完整区间，就按原 fail-closed 规则判分支失败，不降标准。

### Recommendations

无额外门禁或工具套餐要求。校准 App/采集链本身仍是后续独立 receipt 的对象；本轮不要求先做真实重任务来审方案。父层已接受 R3-W1 方向，但修订尚未成为本轮受审版本，因此仍为 open。

### Author Resolutions

- **R3-W1 — accepted**：D5 R3第4条改为候选分析前以独立输入event/冻结规则界定完整活动+减速区间并建立≤X/3的MOV绑定，所有应评估片段必须全覆盖；开始不响应、中间停住、恢复运动不能因无位移退出eligibility。未知片段使整sample无效，合法首尾/减速/反向排除须独立依据。校准同一窗口算法覆盖开始/中段/恢复、匀速到减速与触界positive/negative；公开event/时间/边界证据不足即分支失败，不降标。只改该验证方法消歧，用户目标与其他D5不变。交原非作者复核，不自行关闭。

## Round 4

### Metadata

- reviewer：原独立 delegated `change-design-reviewer`，session `07871190-134a-4121-bbb7-e2ac47b16be7`；未参与受审设计或实现创作。
- runtime：未指定/声称固定模型或 effort；本轮未调用产品模型。
- review_mode：`closure`。
- mode_reason：针对 R3-W1 的完整区间、排除依据与校准窗口消歧；没有改变其余测量门槛、用户需求、产品接口或 M1 范围。按 closure 核对旧反例是否仍能满足新规则，不重开未受影响的设计。
- target：`/private/tmp/nano-ios-chat-continuity` / `unit/bugfix-763-ios-chat-continuity`，HEAD `ed5248dc1fa74358ac74b65f9a98589cc4142d8d` 加冻结 design，SHA256 `9738e6f4b4c7a9fefeb3dc1e48bcc138ae5c69020d508d3516653cb2983da7f2`。其他 working-tree 实现与测试修改不作为本轮审批对象。
- started_at：`2026-11-12T14:15:57+08:00`；completed_at：`2026-11-12T14:16:36+08:00`；duration：`00:00:39`（本轮首个可复核时钟至结论冻结，不含此前材料读取）。
- abilities：`change-design-reviewer`、`performance-review`（设计模式）。
- 执行边界：仅静态读取、版本核对和追加本报告；未运行 trace/build/test/录屏/GUI/模拟器，未改受审设计、实现或测试，未提交或 push。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。R3-W1 在设计层关闭；R3 有界验证方法分支可按其条件实施。**

本结论不表示捕获链校准已通过，也不表示可见停滞、原生 hitch、功能体验或性能验收通过。独立校准 receipt 仍须满足已定规则并由非作者复核，才能分析候选；不能取得事件精度、完整区间或决定性测量时仍按 D5 判 inconclusive，不能借本次 Approved 退出 M1。

### Coverage 与证据

- 已完整重读当前 `design.md:1-175`、本报告历史 Round 及 R3 Author Resolution；核对冻结 design hash、HEAD 和 git diff。`incident.md` 与 unit delta 相对 HEAD 无修改。定向变化在 `design.md:109`，没有改 R3 第1–3、5–6条或其余 D5 数值门槛。
- **R3-W1 关闭依据**：第4条现要求独立实际输入 event 和候选分析前冻结的边界规则定义每个 swipe 的完整活动/减速区间，并以 ≤X/3 误差绑定 MOV PTS。窗口不是由候选有位移的片段反推；开始未响应、中途停住及恢复仍必须留在完整应评估范围内。因此原有“仅保留起始停顿之后或中途冻结之外的平滑片段”反例不再满足设计。
- 全部应评估区间逐段覆盖，任何一段采样、分类或追踪不明使整 sample 无效；合法的等候、反向、首尾及低分辨率减速排除必须逐段给出独立输入/几何边界与冻结规则，明确禁止用像素停住循环推断减速结束。这使第5条“全部合格窗口零 ≥X 停滞”不再允许通过选择性窗口规避坏片段。
- 校准明确复用同一窗口算法，覆盖开始不响应、运动中冻结、恢复、匀速至减速和触界/窗口边界的 positive/negative，并证明 ≥X positives 未被 eligibility 排除。不支持公开 event 精度或独立边界依据即校准失败，不能改为缩小区间。实际能否做到仍需后续 receipt，不在设计轮提前宣称可用。
- `retained_from: Round 3`：一次有界 Game Performance probe、真实捕获链校准、50/100ms 最小合格档、采样/误差/扰动条件、候选分析前独立 receipt、每个保留样本零合格停滞、失败即 inconclusive、非 Apple hitch/非真机证明边界。保留理由是这些条件本轮未变，窗口修订没有削弱它们。
- `retained_from: Round 2`：D1–D4、用户/权限/媒体/发送不变量、canonical/delta 对齐、产品组装与模块责任、原生体验证据安排，以及 D5 的 300×2 实际加载、冷暖、动作/样本、真实尾部/Latest 时延、CPU/内存门槛。保留理由是本轮不改这些产品路径或要求；在途实现仍需单独代码/体验/性能审查。
- 只读重核 `baseline-native-measurement-binding.json:1-40`：绑定同一本轮 UDID、产品基线/fixture 与实际 Animation Hitches exit 2；文件明确空 hitch 不是零，支持 R3 的问题背景，但不构成新校准通过证据。
- **环境事实更正交接（非指标变更）**：主 Agent 转述 helper postflight 核实，同一 UDID 两版实际使用 iOS **26.4.1 / 23E254a** runtime，SDK/xctestrun 标签为 26.4，并未中途换设备。本 reviewer 未独立读取该 postflight 原始 runtime 回执，故按有来源的交接记录而非自证测量；冻结设计现有 `26.4` 环境文字尚待 author 对应更正。只更正该已核实事实、不换 runtime/UDID/指标/路径时属事实整理，不因本轮待更正文案新增设计阻断。

### 历史问题闭环

| ID | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|
| R3-W1 | 完整活动/减速区间由独立 event/冻结规则定义；全覆盖、未知整 sample 无效；合法排除有独立依据；同算法校准边界 positives/negatives；不足即失败 | `design.md:109` 明确封闭开始/中途 stall 被 eligibility 切掉的原反例，并与第3条候选分析前 receipt、第5–6条 fail-closed 相接 | **closed（设计层）** |

R1-W1/W2 保持 Round 2 的设计层关闭状态；不改变历史 Round 原结论。本轮不关闭任何 implementation finding，也不把 helper 完成组数视作最终性能通过。

### Issues

无新增 CRITICAL / WARNING；无仍开放的设计 finding。

### Recommendations

无新增可选工具套餐或门禁。后续只按已批准方案核查实际能力探针/校准 receipt；保留无法证明时停止并报告 inconclusive 的路径，不以实现成本或模板名称替代证据。

### Author Confirmation

Author完整核实R4与受审方案，接受设计层关闭，未把它记作校准或体验通过。R4后仅更正同一设备实际runtime事实（已直接读postflight原始JSON：26.4.1/23E254a，SDK标签26.4），并按reviewer建议消歧固定动作：6次向尾手势保留真实终点frame，不把反向次数当已回尾；独立Latest及动态尺寸真实尾部/时延目标保持。此澄清交原非作者定向核查是否保持R4，未自行据现有metrics宣布完成。

### Retained-diff 核查（Round 4 后事实/歧义整理）

- 原独立 reviewer `07871190-134a-4121-bbb7-e2ac47b16be7` 于 `2026-11-12T14:23:28+08:00` 起静态定向核对；HEAD 仍为 `ed5248dc1fa74358ac74b65f9a98589cc4142d8d`，当前 design SHA256 `04000c0cf9cc174939d5940594c8509a67ea7443f7637c29c643d06ff6e7aa2c`。不另开设计 Round，**retained_from: Round 4，Approved / 0 CRITICAL / 0 WARNING 保持**。
- `design.md:91` 是 runtime 事实精确化，不是换设备/系统的测量条件变更。本次已独立读取 `baseline-metrics-postflight-proof.json:3,42-45`：同一 UDID 的路径、runtime identifier `iOS-26-4`、实际 version `26.4.1` / build `23E254a`。这补足 R4 当时仅按父层交接记录的证据，不回写历史。
- `design.md:94` 将“6次回尾”消歧为固定的6次向尾输入动作并保留逐次/终点真实 frame，明确动作次数不证明成功到尾；独立 Latest 仍须达到原真实尾标、稳定窗口及原时延，动态尺寸跟随终点不减免（`96-97`、D3/D4 与 M1 未改）。这是区分性能动作执行与功能成功断言，没有把停在284改判为尾部成功，也没有减免原 Latest/动态尾部目标。两版真实加载范围、相同输入、实际路径与终点仍须如实报告，现有非空 CPU/内存仅支持其实际走过的测量路径，不能替代连续旅程或流畅性通过。
- R3 完整窗口/校准/时间绑定/失败即 inconclusive 及其他数值门槛保持；本核查未复核 calibration helper 的 SDK 调查或新几何诊断产物，不据没有时钟保证的 manifest timestamp+PTS 推导精度，也不据诊断一次未复现关闭 keyboard blank。未执行运行时操作或实现修改。

## Round 5

### Metadata

- reviewer：原独立 delegated `change-design-reviewer`，session `07871190-134a-4121-bbb7-e2ac47b16be7`；未代写受审设计或实现。此前提供的是只读风险审查反馈，不是方案/代码创作，本轮保留非作者身份。
- runtime：执行环境未提供显式 model / effort 参数，不声明固定模型；未调用产品模型。
- review_mode：`delta`。
- mode_reason：实质改变 D3/D4 的私有 SwiftUI 执行 adapter，由绑定 String ID 的单一 API 改为统一仲裁下的 Reader ID 请求与无 String ID 跟踪的 y 请求；不是仅关闭旧 finding，故新增 Round。变化有界于原生执行接线及其生命周期，未改需求、策略所有权、公共接口、数据/权限边界、delta 或 M1 退出门槛；展开审查该边界及其全部波及的滚动/恢复场景，其余明确 retained。
- target：worktree `/private/tmp/nano-ios-chat-continuity`，branch `unit/bugfix-763-ios-chat-continuity`，HEAD `7c3b1929ad4e2eb29f3ad120d91319adfa9e9c9c` 加冻结的未提交 design；design SHA256 `fc8264f365bb19de2732079f2c45c5adce80e6119f42d0599b9ed9871da45423`，开头与结论冻结时两次一致。
- 需求/契约绑定：incident SHA256 `d101a5856fe6ed9f0320feb99e46f2dee6c4d79ce01c3aa8ba90cd34523cdb4a`；unit delta `specs/im/ios-client.md` SHA256 `f8c9a5e99a929fe1ba238ab662a336f91e68bb9c76b9a75b64c12db486aad8d9`；canonical `docs/specs/im/ios-client.md` SHA256 `86250e5a24bc0e5065621315e143d4002ec4c476a5bb02f7ef1a5459c534858e`。
- started_at：`2026-11-13T16:11:26+08:00`；completed_at：`2026-11-13T16:16:06+08:00`；duration：`00:04:40`（首个可复核时钟至结论冻结）。
- abilities：`change-design-reviewer`、`codebase-design`、`frontend-experience-review`（设计模式）、`product-journey-review`（验证方案判断）。D5 未变，本轮不重开性能方法审查或执行测量；无模型 Context 变化。
- 执行边界：只读文档、公开 API 资料、产品组装与已有运行产物，仅向本报告追加 Round 5；未改首文档/design/delta/源码/测试，未运行 build/test/trace/录屏/GUI/模拟器、服务操作、提交或 push。现场源码仍是 K 临时诊断，尚无新 adapter 实现，不作为实现批准对象。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。R5 私有执行 adapter 修订在设计层通过。**

新执行通道的职责、安装/解除、请求丢失防护、旧 point 与 ID 请求的先后仲裁、几何完成与取消边界已足以指导实施；未发现会让下游实质走偏的未解决设计漏洞。这不是已证明新接线可解除卡死，也不是 A/C/B、远距 Latest、恢复、网络旅程或 D5 通过。K/J/H 的失败不能转写为确定的框架内部根因；I 无绑定的诊断绿也不能作为产品修复。

### Coverage 与决定性证据

#### 1. 需求、delta、版本与真实落点

- 完整读取当前 `incident.md:1-89`、`design.md:1-180`、unit delta `specs/im/ios-client.md:1-79`、canonical `docs/specs/im/ios-client.md:1-250`、本报告 R1–R4 及 resolutions/retained-diff；读取 `M1-continuity/progress.md:1-80` 区分旧准备记录与当前已知失败。核对 git diff，首文档、delta 与 canonical 无本轮修改；未把进度叙述当独立运行结论。
- D3 新三条 `design.md:78-80` 与 D4 首条 `84` 是本轮实质变化；`75-77` 的有效视口、实际末行与 contentMargins 补充也在本轮读取并纳入影响检查，不仅核对新增文字存在。它们仍兑现原尾部/横向/历史需求，不新增消费者可见选择。`no spec delta` 指本次 adapter 修订不再改变既有 unit delta，不表示整个 unit 没有 delta。
- 重新沿实际入口核实 `NanoIMApp.swift:225-246,305-320`：RootTabs 的 NavigationStack 按聊天 ID 创建 ConversationView，详情导航与前后台不是 Chats 重进。`ConversationView.swift:14,38,46-147` 持有当前 View 的 coordinator，真实 ForEach 消息 ID、行 global frame、ScrollView global frame、scroll geometry/phase、Latest、分页/restore 与 appear/disappear 都接到该实例；不是只在测试中使用 adapter。
- 读取 `ChatScrollCoordinator.swift:1-100,180-256` 和已读 `ChatScrollPolicy.swift:1-66`，核对现有 ID 发送点确有 latest、followLatest correction、restore 与未实现历史锚点四类；新统一出口必须覆盖全部，而不是仅替换最新按钮。`ChatStore.swift:1133-1149` 的阅读/pending/restore 清理权威仍由 Store 持有，不能因 View adapter 变更取消必要历史合并/权限校正。

#### 2. 证据支持的是接线边界，不是内部根因

直接读取以下本轮原始日志及各自 `artifacts/<name>/binding.json`，不只采纳主 Agent 的红绿摘要：

| 诊断 | 已读取的实际结果 | 证明范围 |
|---|---|---|
| H `target-layout-h-earlier.log:63-138` | Earlier 路径第三次历史手势后 event loop 不返回，主线程忙导致 AX 超时，单 case failed；尚未点击 Earlier | 单独禁用 target layout 不足解除此现场卡死；该 case 不是新的 12 手势 case，不能混称完整同 case 对照 |
| I `position-binding-i-twelve.log:63-273` | 同 A 的 6 历史＋6 向尾输入全部执行，两端有 AX/截图 attachment 记录，单 case 54.332s / 0 failure，整体 TEST EXECUTE SUCCEEDED | 移除绑定的诊断路径可完成本次 bounded 操作；未验证程序 Latest/锚点定位，也不是 D5 性能样本 |
| G `position-control-g-twelve.log:63-140` | 相同 bounded case 第三次历史手势后等待 idle 与 AX 超时，294.283s / 1 failure，整体 TEST EXECUTE FAILED | 恢复绑定后同类阻塞仍存在，支持以绑定参与路径为下一接线边界 |
| J `user-ownership-j-twelve.log:63-141` | 第三次历史手势后 idle 超时，最终 TEST EXECUTE FAILED；runner 超时重启后的“0 tests passed”不是原 case 成功 | 仅首个真实位移写 public user-positioned 语义不足以解决；不证明 viewID 或内部 solver 的确切状态 |
| K `automatic-handoff-k-twelve.log:63-141` | 同类第三手势后阻塞，execution allowance 超时，整体 TEST EXECUTE FAILED；同样不能把重启后的空 suite 当绿 | 首个真实位移重建 automatic String position 仍不足；不再把此小补丁保留成产品方案 |

- 五份 binding 明确是 diagnostic-only，并记录具体 App 文件与 Swift source hashes。I/G 的 coordinator hash 同为 `d1764d901f54922de30fb5201516bccdcec24cec75cddc861209dcaaaca4a2e5`、Conversation hash 不同；J/K 与 G 的 Conversation hash 相同，coordinator hash 不同；H 的主要 adapter 变化在 Conversation。正文 Markdown source hash 在这些 manifest 中一致。它们支持有来源的受控变体区分，不替代完整 installed/runtime/input receipt；本轮未重新安装核验、重新提取 xcresult 或独立读这些新 attachment 画面，不升级为全旅程/性能或精确内部归因。
- 已读 `ChatReadingContinuityUITests.swift:89-117`：bounded case 明确是功能诊断，断言响应性并保留两端图/AX，不断言六次向尾必已到真尾。这与 D5 的动作/终点区分一致，不得以它取代远距 Latest 的真实 completion。

#### 3. 两通道仍需一个所有权与执行序列

- **职责有界**：policy/coordinator 继续拥有意图、revision、目标选择、有效视口、完成与重试；View 提供当前 Reader 的私有执行闭包，不在 onChange/按钮中另造定位策略。复用原生 Reader/ScrollPosition 公开能力，比改数据源、为卡片另造协议或引入 UIKit 私有查找/滚动桥更局部；无需泛化公共 driver 框架。
- **生命周期闭合**（`design.md:79`）：action 内安装，attach 后重调度，未安装不记 correction 已发；detach 取消旧任务并使旧 adapter 失效，generation 防旧回调清新实例。详情返回保留原 policy/revision，安装不被当作新进入或无条件 latest；其他聊天不共享 coordinator。这同时覆盖 initial content/restore 先于 attach 的实际调用顺序风险。
- **双通道仲裁闭合**（`78,80`）：ID 请求前清旧 programmatic point，目标仍为当前实际 ID；ID 之后必须等新目标行/scroll 几何，不允许旧 layout 的 offset 紧接着发 y 把 jump 拉回。这里“新”是当前请求之后的观察，不能以任意旧缓存 frame 或无关回调代替。请求不等于实现/完成；合法但未实现的同 ID 随后续几何/内容重新修正。真实拖动推进 revision，同时淘汰旧任务和等待阶段，不能只取消一个 Task 却留下旧 ID→y 阶段。
- **无变化路径也闭合**：已对齐可按当前真实 frame 结束，不为等待一个不会发生的几何变化而卡住；未对齐则仍受 D4 合并/防重复无效请求规则约束。没有用固定延迟等待布局或把一次 proxy 调用当成功。
- **公开 API 边界已核实**：[ScrollViewReader](https://developer.apple.com/documentation/swiftui/scrollviewreader) 明确禁止 content builder 执行期间调用 proxy，只允许其中创建的 actions 使用；[ScrollPosition.init(idType:)](https://developer.apple.com/documentation/swiftui/scrollposition/init(idtype:)) 的默认类型为 Never、类型用于匹配 target layout 以更新位置，不是“无内部成本”保证；[isPositionedByUser](https://developer.apple.com/documentation/swiftui/scrollposition/ispositionedbyuser) 是公开可写且明确清除非 nil edge/point，但没有取消所有 ID 求解的保证。当前设计没有越过这些契约作成功预断。

#### 4. 坐标、用户意图与体验验证覆盖

- y 纠偏保留“同一 global 坐标中的行与有效视口相对误差，加到当前 contentOffset”的原语义；不将屏幕绝对 Y 直接当 content offset，也不重复扣系统 insets/contentMargins。现有 D3/D4 已明确有效视口与误差，不需要为内部接线另改 consumer contract。[contentOffset](https://developer.apple.com/documentation/swiftui/scrollgeometry/contentoffset) 可以因 inset/rubber-banding 为负或越界；[scrollTo(y:)](https://developer.apple.com/documentation/swiftui/scrollposition/scrollto(y:)) 有 clamping，仍须依真实 geometry 判完成与避免无效循环。
- Reader 的 [scrollTo(_:anchor:)](https://developer.apple.com/documentation/swiftui/scrollviewproxy/scrollto(_:anchor:)) 显式 anchor 是目标点与视口对应点对齐，nil 不是默认 top。D3/D4 保留实际最后消息的 bottom；高于视口的末行只要求底边到达，空会话无目标、新最后 ID 或行消失使旧 completion 无效。历史未实现锚点仍按相同消息 ID 实现后恢复相对偏移，不退回透明 sentinel 或估算 extent。
- 没有新增产品入口、按钮、说明文字或视觉取舍，不需要为内部 adapter 制造新 HTML 原型。既定箭头、消息顺序、16pt 外围留边、导航稳定反馈和键盘可达性必须保持；本轮没有新画面，因此不宣称视觉协调或横向稳定已在新接线通过。
- `design.md:80` 明确保留 A 连续阅读、远距 Latest、C 动态横向、B 键盘/阅读与取消恢复；结合 D3/D4、incident 与 M1，仍覆盖无位移触碰不取消跟随、主动上翻中止旧定位、详情/前后台阅读保留、Chats 重进、动态增高、分页/清理迟到、未实现同 ID 恢复。纯策略/命令 seam 单测能检查序列与 generation，不能替代 SwiftUI 真实减速、lazy realization、双通道提交和真实末行完成的原生回归。这里没有把“尚待实现验证”改判为设计缺陷，也没有预先将新方案记为功能通过。

#### 5. Retained 范围与退出约束

- `retained_from: Round 2`：D1/D2 的 raw transport / read scope / 业务错误所有权、导航静默/稳定 slot、epoch/stop/reset、权限/发送/媒体不变量，以及完整 unit delta 的 canonical target 与未改变 Scenario。保留理由是本轮只改 View 内定位执行，不改变这些输入/恢复 owner、服务端 API、schema 或授权事实。
- `retained_from: Round 4 + retained-diff`：全部 D5 300×2 实际加载、冷暖、固定动作/样本、真实尾部与时延、CPU/内存门槛、原生 hitch 或有界 R3 校准分支、完整运动窗口/独立时间绑定和不足即 inconclusive。设计全文与 git diff 核实这些未改；不因当前功能卡死或新 adapter 实现成本豁免性能退出条件，也不要求先跑性能来批准接线设计。
- M1 的工作与 reviewer 退出范围仍合适；无部署迁移或生产操作，不需 deployment-prompt。原生资源已有具体 runbook/fixture/独占 UDID，授权或工具实际拒绝仍由主 Agent 依当前边界处理；本轮没有获取或消费额外运行授权。

### 历史问题闭环

| ID | 既有状态 | 本轮核实 | 状态 |
|---|---|---|---|
| R1-W1 | Round 2 设计层关闭 | D5/M1 测量和 fail-closed 条件未被 R5 改弱；无必要证据仍不能退出 | **closed（设计层，retained）** |
| R1-W2 | Round 2 设计层关闭 | D1/D2/raw-scope 所有权及恢复约束未变，与新定位执行通道正交 | **closed（设计层，retained）** |
| R3-W1 | Round 4 设计层关闭 | 完整运动区间、合法排除、独立校准及时间绑定条件原样保持 | **closed（设计层，retained）** |

未关闭任何尚待原生复验的实现/体验缺陷；此前静态子集无 finding 也不等于 K 或新 adapter 全树通过。

### Issues

无新增 CRITICAL / WARNING；未发现仍开放的设计 finding。

### Recommendations

无新增门禁或可选工具套餐。实施按受审边界核查 attach/detach generation、先 ID 后新几何再 y、取消与真实完成，复验受影响原生旅程；若实际必须改变这些已收口的所有权/恢复决定，应回到设计，不再以连续猜测补丁替代证据。

### Author Confirmation

Author 完整读取 Round 5 并核对当前冻结 design，接受 Approved / 0 CRITICAL / 0 WARNING。解除本轮文档冻结并沿同一 M1 实施受审的私有 adapter；H/I/G/J/K 仅为诊断证据，K 临时补丁不保留为产品方案。本确认不改变 design、incident、delta 或任何功能/性能退出要求，不把设计批准记作原生修复通过。

## Round 6

### Metadata

- reviewer：原独立 reviewer `07871190-134a-4121-bbb7-e2ac47b16be7`，未参与设计/产品实现创作；只读审查反馈不作为作者身份。运行环境不支持显式 model/effort 参数，未声称固定模型，未调用产品模型。
- review_mode：`delta`。mode_reason：R6 取代 R5 的私有物理执行与几何一致性边界，加入固定 footer endpoint 和公开 UIKit live tuple；需求、公共接口、M1、D1/D2/D5 未改。展开全部新生命周期/坐标/所有权影响，未受影响项 retained，不只核 CODE-763-L1 闭环。
- target：`/private/tmp/nano-ios-chat-continuity`，branch `unit/bugfix-763-ios-chat-continuity`，HEAD `7c3b1929ad4e2eb29f3ad120d91319adfa9e9c9c` 加冻结 design；design SHA256 `8a1763e3706b81f1ef7674d5432a53d782cbc39dc5d6f9a0fe32bd45364702b1`，两次核对一致。源码当前仍为 O/L 诊断组合，不是尚未实施的 R6 候选。
- started_at：`2026-11-13T20:13:07+08:00`；completed_at：`2026-11-13T20:16:37+08:00`；duration：`00:03:30`（首个时钟至结论冻结）。
- abilities：change-design-reviewer、codebase-design、frontend-experience-review（设计模式）、product-journey-review（方案覆盖）。不重开未变 D5 的测量方法。
- 执行边界：仅本报告追加；未改 design/incident/delta/产品/测试，未运行 build/test/模拟器/服务/GUI/录屏，未读取其他私人临时材料或扩大权限。仅静态读取本 unit 源码、文档及自有 runtime/evidence。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。R6 当前冻结设计未通过，不能以本轮作为实施批准。**

局部公开 UIKit live tuple 是消除 CODE-763-L1 跨源快照的可行有界方向，保 x、clamp、同 ancestor/window 校验和单一 coordinator 也合理；但历史时 footer 的可用性与已确定的原生 scroll-to-top 所有权尚未闭合。作者已接受需修订，未把口头拟补充当作冻结设计已解决。

### Coverage 与证据

- 完整重读当前 `design.md:1-182`，重点 D3 `72-82`、D4、接口与 M1；对照前轮已完整读取的 incident、canonical 与 unit delta，本轮再次读取新增连续性 Requirement 并通过 git diff/hash 核实其未变：incident `d101a5856fe6ed9f0320feb99e46f2dee6c4d79ce01c3aa8ba90cd34523cdb4a`、delta `f8c9a5e99a929fe1ba238ab662a336f91e68bb9c76b9a75b64c12db486aad8d9`、canonical `86250e5a24bc0e5065621315e143d4002ec4c476a5bb02f7ef1a5459c534858e`。本次 no spec delta 正确，不是取消整个 unit 原有 delta。
- 重读原 Round 5 与 Author Confirmation、M1 progress `65-95`、当前 `ConversationView.swift:1-235` 和 `ChatScrollCoordinator.swift:1-313`；实际产品仍由 RootTabs NavigationStack 创建每聊天 View，当前 Reader 包围实际 LazyVStack，footer 是其末尾 lazy item。不是仅检查设计引用行存在。现有独立 row/scroll 通知与 OR 闸门仍是待替换来源，不将其当 R6 live tuple 实现。
- 核对本 unit 自有 L/M/N/O 日志：L 294.084s failed、M 296.185s failed、N 310.375s failed；O 原 12 手势 52.286s passed；O 新 explicit Latest case 46.590s passed，但 clock case 17.299s failed，整体 functional command failed。O 有意缺历史 y，因此这些日志不证明 R6 功能完整、真机或性能通过；本轮未重提取 xcresult/新画面。
- 读取指定自有 `reader-o-clock-scroll-events.json`：tap 后 offset 实际经过上方至 `-116.667`，期间 phase 一直 idle、intent latest、revision 0；连续 `correct-final-message` / `request-message` 后在 `20:01:43.735318+0800` 出现 offset `94663.333`。因此不是只凭失败断言把一个 noop 认成抢位，现有所有权输入确实漏掉本次 native 动作；不据此推断 SwiftUI 内部挂起根因。作者新交接的 isScrollAnimating 方向尚未落冻结 design，也尚无 exact-scroll native flag trace。
- 新设计把 footer 仅作执行端点、实际 last row 作完成，两者分离不违反原尾部契约；顶部 marker、动态增高和有效视口仍保留。原子同步 row/viewport/window tuple 与同一 scroll 的 offset/insets/bounds 可消除“新 offset＋旧 row”的构造反例；不必另建滚动容器、delegate 或通用 UIKit 框架。MainActor 同步不等于布局已稳定，但后续几何驱动、代次与真实 completion 已保留，不要求在 Gate 2 先完成原生验证。
- frontend 设计模式：无新增产品入口/按钮/文案，不要求制作新 HTML 原型；footer 的约19pt尾部拓扑变化需原生实际检查，但不能只因 endpoint 不可见就阻断。当前没有 R6 画面，不宣称视觉/横向或键盘通过。
- 验证安排保留 A连续阅读、远距Latest/Earlier竞争、实际历史改高/分页恢复、C横向、B键盘/详情/前后台、账号/权限边界。新增 live marker 必须实测 lazy 回收/重挂和错误祖先 fail-closed；clock 不能以 swipe fallback 代替。两个 finding 关闭后仍须原生验证，不因设计修订缩小退出目标。
- `retained_from: Round 2` 的 D1/D2、网络/raw-scope/业务错误、权限/发送/媒体与 delta 归属不变；`retained_from: Round 4/5` 的 D5 全负载、样本、数值与校准/时间绑定/inconclusive 门槛不变。无生产迁移，不需要 deployment-prompt，不创建新 Gate。

### 历史问题闭环

- R1-W1、R1-W2、R3-W1：保持此前设计层 closed，理由为相关设计与退出规则未改，不表示运行测量完成。
- CODE-763-L1：R6 atomic live tuple **设计方向可解决**，但当前 R6 尚未实施，本轮不关闭实现 finding。footer 生命周期缺口也会使 live tuple 根本不可取得，见 R6-W1。
- CODE-763-2：本次指定 clock 事件支持原生系统滚动实际被 followLatest 修正抢回；不能仍把 native phase 漏洞仅留作独立观察而给执行方案批准，见 R6-W2。

### Issues

#### R6-W1 — 历史精确偏移依赖可被 lazy 回收的 footer marker

- severity：WARNING；位置：`design.md:80-82`。
- 证据：当前文字仅允许从 footer UIView 向上找最近 UIScrollView；footer 位于 LazyVStack 末端，远历史或详情返回后的历史重挂不能保证该 UIView 已实现。设计同时要求 marker 不可用时不写且不能搜索别处，没有描述可用的解析/恢复路径。
- 后果：恰在历史改高、分页和重入需要精确 y 时可能永远无法取得 adapter，合法稳定历史锚点无法纠偏；不能以 fail-closed 安全性代替必须兑现的历史恢复。
- Author clarification：作者确认意图并非每次依赖 footer 存活，但冻结文字未表达，接受需修订；拟将识别 marker 放在非 lazy item 的 content-root background，footer 只保留 Reader endpoint，每次 snapshot 从 live root 找最近 scroll 并校验 row/window/viewport。该方向有界；须落入修订并复审，不能据口头意图关闭。

#### R6-W2 — 原生动画滚动没有进入定位所有权，clock 已可被抢回

- severity：WARNING；位置：`design.md:73,81-82`，尤其“clock tap 独立追踪”的未收口表述。
- 证据：本次 clock 的实际 offset 序列和修正写入均维持 idle/latest/rev0，已发生真实 native 移动却未淘汰旧跟随；当前设计只明确 SwiftUI gesture pause/revision，新增 UIKit 只描述历史 y，不提供此路径的所有权输入/结束。
- 后果：即使恢复 y 和 footer 路径稳定，用户系统滚到顶部仍可被自动拉回，与主动读历史不被抢位的目标冲突。
- 必需修订：在同一局部 adapter 定义 native 动画观察何时推进 revision、暂停全部定位、如何观察结束/取消并捕获真实锚点，以及与本 adapter/Reader 程序请求的区分；不能把任意 SwiftUI `.animating` 或所有 `isScrollAnimating` 直接当用户意图。保留键盘/卡片/显式Latest的负例，避免修 clock 却破坏跟随。公开 flag 可作候选输入但存在不证明归因，exact ancestor 与实测仍须验证。作者同意本轮结束后与 R6-W1 一起修订；尚未写入冻结版本。

### Recommendations

无新增工具套餐或风格要求。先在原 design 收口上述两个具体边界，再按修订影响复审；不继续用诊断绿跳过历史 y 或原生所有权要求。

## Round 7

### Metadata

- reviewer：原独立 reviewer `07871190-134a-4121-bbb7-e2ac47b16be7`；未代写受审设计或产品实现，反馈为只读审查。环境不提供显式 model/effort 参数，不声明固定模型；未调用产品模型。
- review_mode：`delta`。mode_reason：除定向核实 R6-W1/W2 外，加入局部 UIScrollViewDelegate forwarder，实质改变原先自定的 no-delegate 技术约束，须展开其生命周期、输入归因、转发与取消影响，不能仅作两项文字 closure。产品选择、数据/公共接口、delta、M1 与 D1/D2/D5 未变。
- target：worktree `/private/tmp/nano-ios-chat-continuity`，branch `unit/bugfix-763-ios-chat-continuity`，HEAD `7c3b1929ad4e2eb29f3ad120d91319adfa9e9c9c` 加冻结 design。初始 SHA256 `de48824caaaebbbedb3ba8332c32df4520117c0e351a399fad0dbdc1929bf5cb`；本轮提出 already-top/noop 等待边界后，作者经明确解除窄冻结自行补充 `design.md:82` 最后一句，最终受审 SHA256 **`ee5a0ea8e3c4f9ac17ab3aafd8b0d2a18e296449df3b395a41e64cc7d7cfabf2`**。结论只绑定最终版本；未回写 Round 6。
- started_at：`2026-11-13T20:22:49+08:00`；completed_at：`2026-11-13T21:19:14+08:00`；duration：`00:56:25`（墙钟，包含等待作者窄修订与重新冻结；不是纯审查工时）。
- abilities：change-design-reviewer、codebase-design、frontend-experience-review（设计模式）、product-journey-review（验证覆盖判断）；未重新执行未变 D5 的性能方法评审或测量。
- 执行边界：只读本 unit 文档、真实产品接线、已有审查证据与 Apple 公开 API 文档，只向本报告追加本轮；未改 design/incident/delta/源码/测试，未运行 build/test/模拟器/服务/GUI/trace/录屏，未创建后台任务、提交或 push。当前产品仍是 O/L 临时诊断接线，不是新 adapter 实现批准对象。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。最终冻结设计在设计层通过。**

R6-W1 的 lazy footer 依赖与 R6-W2 的原生 top 输入归属均已在设计层闭合；新增 forwarder 的责任、转发、返回值、生命周期、取消与 noop 边界足以指导实施。这里批准的是局部执行方案，不是 SwiftUI 祖先拓扑保证、delegate 集成安全、卡死根因、真实功能/体验或性能通过。

### Coverage 与决定性证据

#### 1. 当前事实、落点与变更范围

- 完整读取初始冻结 `design.md:1-184`、incident `1-89`，读取 unit delta `40-79`、M1 progress `65-95` 与本报告 Round 5/6；作者补 noop 后重新读取完整 D3/D4 边界 `68-94` 并核对最终 hash。通过 git diff/hash 核实 incident、unit delta 与 canonical 未改：分别为 `d101a5856fe6ed9f0320feb99e46f2dee6c4d79ce01c3aa8ba90cd34523cdb4a`、`f8c9a5e99a929fe1ba238ab662a336f91e68bb9c76b9a75b64c12db486aad8d9`、`86250e5a24bc0e5065621315e143d4002ec4c476a5bb02f7ef1a5459c534858e`。本次 `no spec delta` 合理：只改原 unit 已定义的原生连续性实现边界，不取消既有 delta 或改写 current canonical。
- 沿真实组装入口重新读取 `App/NanoIMApp.swift:225-246,305-320`、`ConversationView.swift:1-240`、`ChatScrollCoordinator.swift:1-313`、`ChatScrollPolicy.swift:1-66`。每聊天 NavigationStack/View 持有自己的 coordinator；Reader 包围实际 timeline，真实消息行、viewport、geometry/phase、Latest、分页/restore 与 appear/disappear 接到该实例。当前 footer 的确仍在 LazyVStack 尾部，现有独立 row/offset 与 OR 闸门也仍待替换，不能把设计中的 persistent marker、atomic tuple 或 forwarder 当成已实现。
- 现有源码读取绑定：Conversation SHA256 `24e7e3b2cbf1a7bbb836474a57c05c82d69a40b1bd219c995fd56ad5b5f1c727`，coordinator `73694db3c24f8fadacd0d5a6ea31cfc623d08a0e20fbbe7433c1567ad112750d`，policy `6b3182144af8195bb4d0a9dd540354b93a460af1341be5618a1c5003f99c8b03`。它们仅用于识别本轮看到的组装与待替换边界，不作产品通过绑定。

#### 2. 历史 marker 与原子几何路径

- `design.md:80-81` 将解析根改为 LazyVStack 整体 background 的 live content-root，不再从可回收的末尾 lazy footer 找 scroll；footer 仅是 Reader 执行端点。当前 row 必须属于同一最近 UIScrollView、同一 window，并与有效 viewport 相容。远历史或详情返回不需 footer 仍在场，关闭 R6-W1 的具体缺口。
- 历史 y 在同一 MainActor 同步调用中读取当前 row/viewport 的 window rect 与该 scroll 的 offset/contentSize/bounds/adjustedInset；保 x、真实范围 clamp、校验失败不写。不再将两条独立 SwiftUI 回调拼成 tuple。ID 前后快照与当前 attach generation、revision、active/gesture pause 一起仲裁，未安装/未解析不记完成，同 ID 未实现时等待 realization/新快照，已对齐不等不存在的布局变化。
- 这些决定给出了可替换旧 OR 闸门的真实 seam，不需要新增公共 driver 框架、业务 owner、第二容器或卡片完成协议。UIKit 祖先拓扑仍是需原生验证的集成假设；设计已要求真实历史改高/分页恢复与横向证据，不成立阻止交付且不扩大为 window 搜索/私有类名/轮询。尚待验证不等于已证明设计缺陷，也不等于可提前关闭 CODE-763-L1 实现 finding。

#### 3. 原生 top 的来源、转发与结束/取消

- `design.md:82-84` 以 exact UIScrollView 的 `scrollViewShouldScrollToTop` 作为明确输入源，而非从 `.animating`、`isScrollAnimating`、offset 或同步调用栈猜用户。先保留原 delegate 决策；拒绝则不改 intent/revision，允许且确需移动才使旧恢复/pending 失效、revision++、进入 history 并暂停本方自动定位。Reader/UIKit 自有请求禁动画且不借 shouldTop 作为完成信号，键盘/动态改高不因此被当作上翻。
- [Apple shouldTop 文档](https://developer.apple.com/documentation/uikit/uiscrollviewdelegate/scrollviewshouldscrolltotop(_:))明确该方法批准/拒绝 status-bar scroll-to-top，原 delegate 未实现时默认允许；不能让“未实现”无意变成拒绝。[didTop 文档](https://developer.apple.com/documentation/uikit/uiscrollviewdelegate/scrollviewdidscrolltotop(_:))说明完成后回调，already-top 时可能立即调用；[scrollsToTop 文档](https://developer.apple.com/documentation/uikit/uiscrollview/scrollstotop)另说明 already-top 时没有动作，并说明 iPhone 多个启用的 scrollview 可使手势无效。因此本轮不从 API 名称推导所有 noop 都一定有 didTop。
- 本轮指出该边界后，作者在最终 `82` 自行补齐：原 delegate 允许后先读同 exact-scroll live tuple，已在 `topLimit+1` 内或合法 range≤1 时原样返回允许但不创建 pause/新 revision，不等待可有可无的 didTop。该句已实际重读并绑定最终 hash，不是以口头意图关闭。真正从低处向 top 的路径才进入等待；正常 didTop 结束 pause 并捕获实际阅读锚点。
- 新 drag、Latest、disappear、root/delegate 换代都会取消本方 top pause；旧 generation/旧完成不能再夺新 revision。未将原生 top 完成当成自动恢复 latest；只有明确 Latest 或实际回到底部才跟随。这与用户最新明确意图及详情/前后台不重置阅读的目标一致。
- forwarder 的职责限观察三项输入和透传：原 delegate 弱引用，adapter 持有本方 proxy，不自包或包另一聊天；其他可选 selector 的 `responds(to:)`/NSObject 转发保持原对象行为和返回值，不能吞掉 SwiftUI 的 scroll/zoom 方法。公开 [forwardingTarget(for:)](https://developer.apple.com/documentation/objectivec/nsobject-swift.class/forwardingtarget(for:))是未识别消息的重定向，不是任意已实现方法的自动透传；三个本方实现的方法仍需显式先调用原 delegate。[UIScrollView.delegate](https://developer.apple.com/documentation/uikit/uiscrollview/delegate) 本身为 weak，当前设计明确 proxy 的本方 owner，且不为掩盖生命周期而强持有外方 delegate。
- 本地 marker 生命周期重新校验实际 scroll/delegate 身份；replacement 时重绑新原 delegate，旧 generation 忽略，detach 仅在 scroll.delegate 仍为本方 proxy 时还原，不覆盖外方后续替换。root/viewport 失效也解除。这是局部系统集成，不扩大为全局 hook/swizzle/私有框架或永久 poll。改变的是作者原自定 no-delegate 技术限制，不是替用户选择新产品体验；原生 replacement/rebind 与 optional-selector 透传安全仍须实证，不能凭公开 API 或 mock 绿声称已经安全。

#### 4. 体验、旅程与 retained 边界

- 设计层没有新增可见入口、按钮/文案或信息层级取舍；仍恢复安静连续阅读，故不为内部 adapter 制造 HTML 原型。footer 尾部约19pt拓扑/空白、16pt左右留边、导航/composer/键盘与真实末行完成仍需受审原生画面。本轮未读取新实现画面，不宣称视觉或横向稳定通过。
- 验证范围仍包含 A 连续历史/远距Latest/Earlier竞争、实际历史改高与分页恢复、C 动态横向、B 键盘/详情/前后台。新增 source 必须在原生 clock **无 swipe fallback** 下完成真实 top、保留 history，再经明确 Latest 到真尾；同时覆盖新 drag/Latest/详情重挂中断及 proxy 恢复，键盘/动态改高是不应误转 history 的负例。策略/转发单测不能代替真实 UIKit/SwiftUI delegate、lazy realization 与实际几何结果。
- `retained_from: Round 6`：L/M/N/O 的受控诊断与 clock 抢回事件只沿用此前已独立读取的证明范围，本轮未重新提取 xcresult/运行日志或新增 runtime evidence。O 诊断绿没有历史 y，不是新方案功能完整；O clock 失败不是 noop 的事实已由上一轮 offset/修正 trace 支持，但不证明挂起内部根因。
- `retained_from: Round 2`：D1/D2 的传输/read-scope/业务错误所有权、静默/稳定 slot、epoch/stop/reset、权限/发送/媒体边界及 canonical delta 归属未改。
- `retained_from: Round 4/5/6`：D5 300×2 真实加载、冷暖、固定动作与失败样本保留、真实尾部/Latest时延、CPU/内存、原生 hitch 或 R3 独立校准/完整窗口/时间绑定与不足即 inconclusive 全部未减免。M1 退出条件不因 delegate 集成成本或诊断结果降级。无 schema/服务端迁移、无生产动作，不需 deployment-prompt，也不增加新 Gate。

### 历史问题闭环

| ID | Author Resolution / 本轮证据 | 状态 |
|---|---|---|
| R6-W1 | `80-81` persistent content-root 解析 exact scroll，row/window/viewport 校验；footer 仅执行端点，历史回收/重挂不依赖其存在 | **closed（设计层）** |
| R6-W2 | `82-84` 明确 shouldTop 来源、原返回值、真实位移/noop、history/revision/pause、didTop、取消及旧 generation 防护；原生 clock 与负例验证保留 | **closed（设计层）** |
| R1-W1 / R1-W2 / R3-W1 | 相关 D1/D2/D5 与完整校准/退出条件不变，按此前证据 retained | **closed（设计层，retained）** |
| CODE-763-L1 / CODE-763-2 | atomic live tuple 和 native-top source 设计覆盖原反例，但新产品尚未实施/原生验证 | **不在本轮关闭实现或体验缺陷** |

### Issues

无仍开放的设计 CRITICAL / WARNING。本轮 already-top/noop 缺口在最终冻结前由作者窄修订实际解决；不另造已失效 finding 或额外 Round。

### Recommendations

无新增工具套餐或可选门禁。按既有原生影响范围核实 marker 拓扑、proxy 转发/重绑、top 完成与中断、历史原子偏移及真实末行结果；这些是受审方案的验证义务，不是本报告预先认定已通过的实现。
