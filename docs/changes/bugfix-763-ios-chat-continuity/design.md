# bugfix-763: iOS 聊天连续体验 — 技术方案

> 对齐: [incident.md](incident.md)

## Changelog

## 现状分析

### 涉及范围

核实基线 `45babb2b49e314754c6ca390f4ca3da61fe9f107`：

- `Features/Chat/ChatPhases.swift`、`ChatStore.swift`：内容 phase 已与连接 state 分离，但状态文字仍直接映射原始重试；HTTP sync 后提前 online / attempt=0，WebSocket 尚未建立。
- `ChatListView.swift`、`ConversationView.swift`：连接文字是可插拔内容行；读取错误与业务操作错误混用 `errors`。
- `ConversationView.swift`：`bottomVisible` 同时决定按钮和跟随；初始缓存没有显式定位，count / 最后正文才 scrollTo；分页完成无条件 top、清理恢复 center。用户滚动与渲染长高没有区分。
- `InteractiveWebView.swift` 已接通 ResizeObserver → 原生 frame；`MediaViews.swift` 异步图片也改行高。不需要另造卡片专用完成协议。
- `MarkdownView.swift`、`ChatModels.swift`、`CommonViews.swift`、可见已读回包是性能候选，无原生测量，不能预定全部优化。
- `UITests/` 已有 `NanoIMJourney` 真实登录/缓存旅程；PBX 文件同步目录可发现新增 Swift。原生最低 iOS26，可以使用 ScrollPosition、滚动几何与滚动 phase。

### 既有约束

仅原生客户端与相应测试/行为契约；不改 IM API、存储 schema、跨包架构或 DSH。维持 local-first、实时权限核实、账号/服务隔离、撤销清理、发送幂等和私人编辑语义。不得缓存实时授权或受保护媒体字节来加速。

用户已选择 Chats 重进到最新，详情返回和前后台保留当前阅读。只用模拟器，不部署/合并。必需模型限定 Sol6.1，普通合成渲染输入不调用模型。

### 可复用能力

- **用**现有内容 phase、本地 repository、`TimelineMerge` 与权限 fence，不新增聊天数据源。
- **改**现有 UserStream 建连完成点，使 sync 与实时链路各自真实；不 fork WebSocket 协议。
- **用**原生滚动几何和 phase 控制用户意图；卡片/图片只需真实改高，宿主统一处理。
- **改**清理阅读恢复的旧 id 链：继续保留跨 revision 补历史能力，但 UI 恢复由当前意图和请求代次仲裁。
- **用**独立 NanoIMJourney scheme，不在生产 App 加测试后门，不以 Web 窄屏代替原生。

### 相关历史

714/716 已实现生命周期清理/本地优先与卡片语义；本 unit 保留其权限和发送不变量，不重开旧事项。旧只读报告只提供线索，未有原生 App 截图/性能结果可复用。

## 架构总览

```text
内容 phase（本地/网络） ──────────────→ 现有消息/列表
原始连接状态 → 稳定展示策略 ──────────→ 导航辅助反馈（不插内容行）
用户手势 / 最新按钮 / 新会话 → 滚动意图与代次
                              ↓
内容尺寸 / 视口 / 可见锚点 → 单一定位仲裁 → 原生 ScrollPosition
旧分页 / 清理恢复 ─────────────↑（必须代次仍有效）
```

把『想看哪里』和『当前几何在哪里』分开；视图只管理当前导航实例的滚动，不把位置永久保存到数据库。

## 关键决策

### D1. 连接展示采用五秒静默与稳定故障反馈，不再把重试状态作为消息行

- 已有内容时，普通 starting/syncing/offline/unavailable 从首次连续不可用起静默5秒。这个值是工程初值，不是用户指定或行业标准；原生短3秒/长12秒演练校正。
- 同一不可用期间的 syncing/offline/HTTP成功但WS失败不重置静默时钟，也不轮播文案；只有完整恢复或终止账号状态结束该期间。
- 持续不可用后只有一处『连接暂不可用，自动重试中』辅助反馈，可点击查看上次更新时间/重试。Chats 现有 nanoRootTitle 实为 inline 自绘 principal，并非 large title；两页统一用同一 principal 内的标题与辅助 slot，默认约44pt高并按Dynamic Type适配、同字号下状态切换高度固定；标题/slot始终保留布局，静默slot无文字/图标且不可访问。持续故障仅填充slot，不改列表/消息可用高度与输入。长标题截断/大字号保持返回与主操作可达，详情可完整读；不能仅凭navigationSubtitle API存在就宣称其不会重排。不插 List / VStack 内容行。
- 首次无缓存失败由现有内容区错误状态独占反馈，不再叠加全局连接状态；撤销/登录失效/发送失败仍按各自对象提示。
- 将读取错误和业务操作错误分清：后台校正失败按 list / detail(id) / timeline(id) / access scope 保存失败种类与连续失败起点，不写实时传输健康、不复用 `errors`。导航仅合成当前surface相关读取scope与实时传输故障；仅HTTP校正失败时文案为『暂时无法更新，轻点重试』，点击重试实际失败的读取，不宣称后台存在自动重试。对应成功读取仅清自己的scope；full sync可清其实际覆盖的list/access scope，不能清尚未校正的timeline。无缓存失败由内容phase读取专属错误；业务发送/上传/访问错误仍在原对象，forbidden/access/stale-write不伪装网络。
- 拒绝『小图标代替文字』『每次重试插入不同状态行』『所有错误静默』。

### D2. online 与退避归零推迟到 sync 完成且实时传输确认可用

`ConnectionState`只由run的实时连接生命周期（以及明确terminal账号结果）拥有；读取成功/失败不得把健康socket改offline或把未恢复socket改online。UserStream在ticket / socket resume之外等待一次WebSocket ping成功确认握手；随后ChatStore才online并归零attempt。HTTP同步完成仍更新内容/lastFullAt，不借此宣称实时恢复。失败保留指数退避（1/2/4…30秒与Retry-After取大）；取消、账号失效、epoch保持原有语义。不会等待有业务消息才算在线，也不新增服务端ack API。

后台读取的scope故障与raw传输正交：① healthy WS + HTTP失败，保留rawonline，仅该surface的scope在静默后显示『暂时无法更新，轻点重试』；同scope成功重试立即清除，不残留offline。② HTTP sync或scheduleAccessRecovery成功只清它们覆盖的scope，即使rawWS仍失败也不能结束raw不可用时钟；检查所有online写入点，不只改run。③ raw故障由run实际退避自动重连，scope故障由显式导航重试、该读取下一次正常校正或已有有界access recovery恢复；文案据真实owner表达，不为此新增通用网络coordinator。④ stop取消展示timer和旧任务；新run重新注册当前仍相关的展示deadline；reset/退出清除全部scope、时钟与恢复任务，旧epoch回包不能清/写新owner的状态。禁止catch业务发送错误改变raw或静默处理。

### D3. 单一滚动策略保存用户意图、目标代次和当前可见阅读锚点

私有值类型策略（可直接单测）隐藏：followLatest / readingHistory、操作 revision、用户滚动阶段、底部距离、历史可见 id+相对有效视口偏移、布局修正状态。View 使用小接口消费用户操作和几何结果，不在多个 onChange 中各自决定强制定位。

- 新建会话 View 默认 followLatest；显式初始 anchor 到 bottom，缓存未变化也定位。详情 push/pop 与前后台不创建新滚动意图；不能在每次 onAppear 无条件 reset。
- tracking（可能只是触碰）先暂停自动定位；只有 interacting 且实际发生用户滚动才推进 revision、提交 readingHistory 并淘汰旧任务。tracking→idle 无位移要恢复原意图，不能点一下卡片就永远停止跟随；滚动结束若实际在底部恢复 followLatest，否则 readingHistory。程序定位/动态长高本身不算主动上翻。
- 点击最新立即切到 followLatest，推进 revision，清除旧阅读恢复意图，发出不带长动画的到底请求。不等网络、不加载全部历史。
- 底部按钮显隐由真实几何距离与意图决定；执行 scrollTo 不算完成。最新消息尾部在扣除 safe-area / composer / keyboard 的有效视口内才算到达，容差只作按钮显隐，不用掩盖大幅不到底。

### D4. 尺寸变化统一参与定位，历史读取保持锚点

- 使用 ScrollPosition、初始 bottom anchor 与滚动几何（content size、container、insets、offset）处理惰性布局。尺寸变化后若 followLatest 且非用户交互，再向 bottom 定位；回调驱动，不用固定延迟500ms。
- 对惰性远距跳转，允许布局稳定期间继续纠正到尾部；同一布局代次合并请求，避免重复无效 scrollTo 循环。任务取消与新 revision 使旧修正失效。
- readingHistory 时保存最上方可见稳定消息与其相对视口偏移；分页/异步增高导致该锚点移位时按偏移差校正。用户拖动期间不反向纠偏，结束后重新选锚点；卡片内部增高不无条件拉底。
- 分页捕获当前 revision 和锚点；await 后只有 revision 未变且仍读历史时可恢复。点最新/新手势淘汰旧恢复；清理后的 store anchor 同样不能覆盖更晚用户操作。锚点被权威删除时允许取仍存续的最近阅读目标，不复活旧内容。
- 拒绝只对生成UI追加延迟、等待所有远程媒体完成后再显示、为修定位强行收键盘。

### D5. 先测量实际阅读路径，只做有证据的局部性能修复

冻结以下可比较协议，不以更小加载范围或未渲染卡片换快：

| 条件 | 固定值/判据 |
|---|---|
| 环境 | 同一本轮iPhone17Pro模拟器/iOS26.4.1（23E254a；SDK/xctestrun标签26.4）、默认字号/竖屏、键盘关闭；同Xcode26.4.1、同Debug配置/优化级别、同fixture数据库/图片/卡片source。原生UI基线产品树45babb2b49e3；允许在两版共用无行为变化的测量harness/signpost，绑定各自实际SHA。 |
| 负载 | 两会话各300消息，完全相同base Markdown文本量；控制组纯文本，混合组在相同消息附2张nano-iui-1卡片/2受保护PNG，末卡有唯一真实尾标。初页241–300，实际通过Earlier加载181–240、121–180、061–120、001–060，UI见001且API页边界对账才算300历史已加载。 |
| 冷/暖 | 冷为进程终止后，同已预热本地300消息窗口重启，renderer/AST是新内存，不把首次空库等同暖重开；暖为同进程立即重访相同范围。两版均从同样已确认的SQLite窗口开始，远程媒体无持久缓存承诺。首次无缓存进入另作功能旅程，不混入性能样本。 |
| 动作 | 各组从已确认真实尾部开始，6次同方向/速度的fast swipe读历史，再6次向尾方向手势；逐次及终点真实frame保留，不能仅凭反向6次就宣称成功回尾。另从同一历史marker范围点击Latest一次，必须按下列真实尾部与时延标准完成；Latest/动态尺寸跟随的终点要求不减免。重置起点与等待已知卡片完成在测量区间外，不用长途程序动画制造表面流畅。 |
| 样本 | 每组先1次discarded warmup，再5次measured，冷/暖分列；保留每次值、中位和min/max，不给5样本伪p95，失败样本不丢。达到下述边界但受噪声影响时只追加一组5次等条件复核，仍不确定则inconclusive，不无限挑好样本。 |
| 尾部完成 | 唯一最终尾标的完整frame位于nav.maxY到composer.minY有效视口内，3次间隔约200ms观察均在内且相对Y漂移≤4pt；随后卡片/图片或输入区再次改高仍恢复尾部。这个稳定窗口仅用于测试判定，不是产品固定延迟。 |
| 操作时延 | 同步记录Latest handler→尾部几何可见signpost（不是触摸→屏幕呈现）与XCTest命令→稳定尾部外部墙钟（含automation同步开销，分列不混算）。已加载/渲染内容的handler→tail中位≤500ms、最大≤1s；新挂载卡片的最终tail≤3s、最后height revision后的纠正≤1s。按钮即时取得跟随且旧定位不抢回是独立必过行为。 |
| 滚动代价 | 主要指标为App定向XCTHitchMetric的hitch duration ratio（ms/s），辅以scrollingAndDecelerationMetric、XCTCPUMetric(application:)与XCTMemoryMetric(application:)；必要时用本轮sim的Animation Hitches/Time Profiler解释与请求时序的相关性。不能把runner CPU或空metric当App结果。 |

**原生 hitch 退出规则（平台支持时）**：原生连续旅程必须全部通过。滚动候选hitch ratio中位不得超过基线中位加`max(1ms/s, 基线的10%)`；若基线中位>5ms/s（本轮明显停顿工作阈值，不是行业标准），候选须至少降低20%且≤5ms/s。App CPU/峰值内存中位不回归超过15%，超界须解释并以对照证明不增加阅读停顿/内存压力，否则不能退出。基线未复现hitch时，只能给『此负载下未复现真实帧停顿』的限定结论；候选仍须取得非空原生metric且hitch ratio≤5ms/s、操作时延达标、无上述回归，不能声称找到用户手机版本卡顿根因。

#### R3：本机 hitch 不支持时的有界验证分支（待独立复核）

实际同机基线的5个CPU/内存/scroll样本非空，但XCTHitchMetric没有hitch系列，不能记作0。Animation Hitches真机具备的能力不能推到模拟器：本轮实际`record`退出2，原始日志`/private/tmp/nano-ios-763-evidence/baseline-animation-hitches-support.log`明确`Hitches is not supported on this platform.`；命令、exit receipt和App/corpus hash见同目录`baseline-native-measurement-binding.json`。以下是主Agent在既有工程授权内批准探索的**验证方法变更**，不是用户新要求、不是性能通过，也不把可见停滞伪称Apple hitch等价值。

1. **一次能力探针**：基线测量helper释放独占sim/CPU后，只做一次最长15秒的`Game Performance`（如模板实际不支持则结束，不连换模板）的本轮App采样，检查原始track/schema和非空行。只有能绑定本轮App/Simulator画面、实际present时刻及预期显示deadline的track，才可另交原非作者判断是否保持原生hitch规则；GPU命令提交、SwiftUI update、FPS均值或空表不成立。探针不能取得这三项就转下一分支，不无限寻找trace。
2. **独立真实捕获链校准**：不改产品renderer、不用私有hook，也不靠分析器人工复制帧作唯一positive。临时无网络校准App在同一sim实际绘制匀速标尺/至少3个可追踪纹理区、逐帧序号与单调时钟；negative持续运动，positive在真实主线程按已记录单调起止时间各注入3次50/100/200ms冻结。使用与后续产品相同的`simctl io <UDID> recordVideo --codec=h264`原始MOV、像素分辨率/窗口设置/host条件；不转固定fps、不用文件标称fps作源帧率。保存每个原始sample的PTS、duration、尺寸、分析器版本及冻结事件时间。
3. **在看任何候选可见停滞分析前冻结精度**：只从校准结果按50→100ms顺序选择最小合格档`X`；档位合格要求同档及以上全部3次positive均检出、时长误差不超过`max(1个实际采样间隔,25ms)`，且negative不存在任何≥X的假停滞。200ms只检出而100ms不可靠不够评价本目标，本分支失败。PTS必须严格递增，无倒退；活动画面样本间隔p99≤X/3且最大≤X/2，至少3个纹理区位移一致。捕获间隔缺口不算产品停滞，造成区间不可判定，必须保留失败样本。误差、eligible window算法、ROI/patch规则、X及采集/分析hash形成独立校准receipt，由原非作者复核后才可分析候选；不能按候选好坏调整档位/阈值。
4. **完整预期运动区间、采集扰动与正常静止**：同校准App交错不录制/录制各3次等长运动，从其单调display-link回调间隔和冻结日志检验录制扰动；录制不得新增≥X源回调停顿，回调间隔p99中位回归不得超过15%，否则校准失败。产品每次12个swipe的完整预期活动/减速区间，必须在候选分析前由独立XCTest实际输入event及预先冻结的边界规则定义，并与原MOV PTS建立≤X/3误差绑定；不是从候选哪些帧已在运动反推区间。开始未响应、中途停住、停后继续都在完整应评估区间内，不能因其没有位移就剔除。所有应评估区间须逐段全覆盖，任何一段采样/分类/追踪不明使整sample无效；“每swipe至少有一个平滑片段”不算覆盖。静止等候、反向过渡、首尾边界和自然减速低于追踪分辨率的合法排除，须有独立输入/几何边界及冻结规则支撑，逐段列明，不能因像素停住循环推断“已减速结束”。校准App除匀速冻结外，必须用**同一窗口算法**覆盖预定开始不响应、运动中冻结、冻结后继续、匀速→减速及触界/窗口边界positive/negative，证明≥X positives未被eligibility切掉；缺公开event精度或独立边界依据就校准失败，而不是缩小区间。正文运动由至少3处patch的一致位移验证；局部card/caret/spinner变化不算正文运动。原始帧索引与PTS必须能回查所有区间、合法排除及每个检出段。
5. **产品同负载比较与独立门槛**：仍保留上表300×2真实加载、冷暖、12次同轨迹swipe、1discard+5retained、真实尾部/Latest时延与CPU/内存15%门槛。视频组与既有CPU/内存组分开等条件执行，基线/候选都录像，禁止并发构建等重活；记录真实host负载而不宣称绝对空闲。以明确命名的`Simulator captured visible stall (≥X ms)`报告每次有效运动秒数、停滞次数/时长/最长段及原始PTS，不沿用5ms/s hitch阈值。候选每个保留样本在全部合格窗口内均不得有≥X停滞；基线若有停滞则报告是否改善，基线无停滞只能说此负载/精度下两版均未观察到，不能声称优化根因。不得以均值掩盖单个候选长停顿。一个样本采样/追踪无效即保留为无效；只可按原协议追加一组5次复核，仍无效或候选真实停滞未消除则不能通过。
6. **失败及证明边界**：有限探针/校准/事件时间绑定任一不能成立，必要流畅性证据仍inconclusive，阻止以“已完成”归档；向主Agent带回实际已完成功能、未证明部分和建议，由其负责产品交付取舍。校准成立也只支持本Mac/本sim/该负载≥Xms的捕获可见停滞判断；不能推出iPhone呈现、16ms单帧hitch、Apple hitch ratio≤5ms/s、用户原手机卡顿根因。原生连续功能、尾部/时延及CPU/内存不得由此豁免。

依据边界：[Apple hitch定义](https://developer.apple.com/documentation/xcode/understanding-hitches-in-your-app)、[WWDC2020 hitches](https://developer.apple.com/videos/play/wwdc2020/10077/)、[CMSampleBuffer PTS](https://developer.apple.com/documentation/coremedia/cmsamplebuffergetpresentationtimestamp(_:))。`simctl recordVideo`只承诺display QuickTime capture，不承诺逐vsync；本分支必须靠真实校准而不是引用PTS名称补足保证。

优先核实重复日期/时间分隔计算、Markdown解析、可见已读请求/回包投影以及WebView挂载。仅在同负载测量支持时改该私有路径，可采用消息内容键的有界/视图生命周期缓存、聚合幂等已读等；授权/状态更新不能缓存掉。若性能修复需要改业务语义或新公共边界，先修订受审设计再实施。无稳定收益的候选不合入，不把正确定位等价于无掉帧。

## 接口与数据流

- 连接展示策略：`updateTransport(state, now)`与`readFailed(scope, failure, now)` / `readSucceeded(scope)`保留各连续故障起点；`presentation(surface, now, hasContent)`按当前页面相关scope返回静默或稳定辅助文案。原始健康不被读取scope回写；clock/timer可注入测试，只在最早未显示deadline调度一次，不每帧/每秒改内容。Store生命周期取消旧timer、防止退出后回填。
- 原生连接反馈组件只消费展示结果与 retry action，错误详情按需展开；Charts/会话共享策略，不共享重复错误行。
- 滚动策略输入为 initial / userInteraction / latest / geometry / visibleAnchor / pendingRestore；输出 latest 或 anchorCorrection，revision 包含定位所有权。SwiftUI adapter 独占 `ScrollPosition` 调用。
- 清理阅读锚点沿用 repository 的 revision fence；用户切最新时同时使旧 pending/restore 无效，网络补页仍只按合法消息合并，不应为了位置取消必要权限校正。
- 无模型可见信息、工具/Skill/Prompt 或 Context 生命周期变化；无需 Context 专项。

## 界面方案与画面边界

保留现有 Chats 搜索/分类/会话层级和会话正文/输入层级，去掉连接行；最新箭头沿用右下角、补具名辅助标识。持续故障只占导航辅助反馈，不抢正文主操作。当前没有 App 内基线画面，**视觉对照尚未验证**；实施首先取得基线/候选原生画面，再核对持续反馈是否清晰、不遮挡/跳位。

本次恢复已明确的连续体验，不设计新业务流程或以HTML模拟原生布局，故不另造原型。原生截图/连续操作是必须证据；若导航辅助反馈无法稳定容纳真实长标题/大字号，局部调整后必须补独立体验复核，不能用『平台适配』豁免信息遮挡。

## 本次审查安排

| 必须回答的问题 | 能力与阶段 | 方法与范围 |
|---|---|---|
| 根因/状态机/竞态修复是否完整，权限发送不变 | change-code-review，实施后独立 | 冻结SHA对incident/design/delta核查；窄单测、现有清理/本地优先/发送回归 |
| 短重连安静、持续不可用如实，读历史/动态尾部/最新可靠且视觉协调 | frontend-experience-review + product-journey-review，设计与实施 | 独立读真实原生截图/连续旅程视频或XCTest附件/结果，关键不足补操作；只iOS，不复制Web矩阵 |
| 大滚动卡顿是位置失效还是计算/挂载/请求代价，局部改动有无回归 | performance-review，实施 | 同设备/fixture/样本前后对照；记录metrics、请求和主线程证据。零测量不得pass |

独立review可由同一非作者执行多能力；author组织fixture/构建并共享可信证据，不要求重复全量。最终报告保留 validated_at / executed_base / effective_base / effective_through。

## 契约层增量

仅 [specs/im/ios-client.md](specs/im/ios-client.md)：修改『断线及前后台』『离线反馈』时机，新增『原生聊天阅读连续性』。不把5秒/类名/性能偶然数字写成长期契约。

## 风险与回退

惰性尺寸估算可能导致二次布局，需实测真实尾部，不仅断言请求。手势识别与程序滚动混淆可能抢位，phase/代次测试及连续旅程覆盖。连接静默可能掩盖读取失败，故无缓存/真实发送/失效独立保留。性能缓存可能泄漏跨账号数据，只可视图生命周期/内容型有界计算缓存，不存凭据与媒体。

回退为撤销本 unit 客户端提交；无schema或服务端迁移，不操作生产。

## 一次性部署迁移

无。

## Runbook for Reviewer

常驻产品服务无改动；为实测新建独占 IM 服务，不需 Gateway/模型。主执行者核实PID/出生时间/cwd/端口/DB合成对象后交接fixture manifest与0600凭据路径。只用本轮专用模拟器，不复用旧714/716。

| 服务 | 停止 | 启动 | 健康检查 |
|---|---|---|---|
| 本轮IM | 对manifest中核实出生时间的自有PID发送SIGTERM并等待退出 | `IM_JWT_SECRET=<本轮secret> node <worktree>/apps/im-server/lib/main.js serve --host 127.0.0.1 --port <本轮高位端口>`，cwd为本轮runtime，同DB同端口恢复 | `/health` + lsof + DB只读对象核对 |

原生：`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`；`NANO_IOS_BUILD_ROOT=<独占目录> ./src/IM/ios/scripts/build.sh build` 构建随包渲染；`xcodebuild -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIMJourney -destination 'platform=iOS Simulator,id=<新UDID>' -derivedDataPath <独占目录> -jobs 2 -parallel-testing-enabled NO build-for-testing`，将真实合成输入写入同目录0600 xctestrun副本，`test-without-building` 仅选本unit case。授权来源为用户明确『所有的真实隔离测试…不需要我给你权限』『只用在模拟器测』及本轮改动请求；实际工具拒绝仍遵从，不拆换绕过。

必验资源：本机Xcode26.4.1/iOS26.4 SDK已核实；新模拟器和高位端口可创建；依赖已独立安装；只需新合成账号/文本/卡片/图片，不需要外部账户或手机。fixture负责人核实后交接；短3秒与长12秒各一次本轮专用IM断开/恢复，不影响生产/共享栈。结束提取脱敏证据，回收服务、模拟器、临时凭据/DB/build，PR未合并保留开发worktree。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-continuity | 连续聊天状态与原生验证 | 无 | 串行集成 | ChatPhases/ChatStore/UserStream、ChatList/Conversation及私有策略、测量支持的局部呈现、Tests/UITests、ios-client delta | [reviewer] 短重连零反馈且不位移，持续失败一处诚实可恢复；Chats重进尾部、动态增高/键盘跟随、上翻/详情/前后台不抢位、旧定位不覆盖最新；原生信息层级协调；D5冻结负载/样本的真实尾部、时延、CPU/内存与平台支持的hitch规则或经独立校准复核的R3可见停滞规则全部成立，缺决定性测量不退出。[worker] 策略边界、timer取消/epoch、WS失败退避、healthyWS+HTTP失败再成功、HTTP-only成功不清WS故障、操作错误单测；真实UI连续旅程含缓存重入/高卡片/分页竞态/历史上下文；300实际加载边界、冷暖5样本metrics/请求/必要profile绑定SHA；原生build+受影响单测、CI等价检查；不更改权限/发送/媒体持久边界。 |

## 交付路径差异

工具实际拒绝首文档直推共享 develop，完整命令未执行。主Agent决定遵守该边界：首文档、设计与实现均保留本轮独立 `unit/bugfix-763-ios-chat-continuity` 分支，最终 PR → develop，不重试直推/不 force-push。主checkout已有dirty不碰。
