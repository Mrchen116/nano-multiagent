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
- 持续不可用后只有一处『连接暂不可用，自动重试中』辅助反馈，可点击查看上次更新时间/重试。Chats 现有 nanoRootTitle 实为 inline 自绘 principal，并非 large title；两页统一用固定44pt高 principal 内的标题与辅助 slot，标题/slot始终保留布局、静默slot无文字/图标且不可访问。持续故障仅填充slot，不改列表/消息可用高度与输入。长标题截断/大字号保持返回与主操作可达，详情可完整读；不能仅凭navigationSubtitle API存在就宣称其不会重排。不插 List / VStack 内容行。
- 首次无缓存失败由现有内容区错误状态独占反馈，不再叠加全局连接状态；撤销/登录失效/发送失败仍按各自对象提示。
- 将读取错误和业务操作错误分清：传输/服务不可用的后台校正错误进入连接策略，不把 `errors` 通用文本过滤来隐藏发送失败。没有内容的错误仍使 phase 进入 needsConnection/failed；forbidden/access/stale-write 不伪装网络。
- 拒绝『小图标代替文字』『每次重试插入不同状态行』『所有错误静默』。

### D2. online 与退避归零推迟到 sync 完成且实时传输确认可用

UserStream 在 ticket / socket resume 之外等待一次 WebSocket ping 成功确认握手；随后 ChatStore 才 online 并归零 attempt。HTTP同步完成仍更新内容/lastFullAt，不借此宣称实时恢复。失败保留指数退避（1/2/4…30秒与 Retry-After 上限取大）；取消、账号失效、epoch 保持原有语义。不会等待有业务消息才算在线，也不新增服务端 ack API。

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

比较同一模拟器、相同历史规模和正文负载的基线与候选：纯文字/高卡片、冷/暖进入、上翻/远距最新。先保留基线构建，再用 XCUITest 连续旅程截图/计时与 `XCTOSSignpostMetric.scrollingAndDecelerationMetric`、适用的 CPU / wall-clock 指标；需要归因时用 xctrace Time Profiler 对齐主线程和本轮请求计数/时间。模拟器图形指标不可用时明确工具限制，改用实际可取得的原生 CPU/主线程和操作时序，不虚报FPS。

优先核实重复日期/时间分隔计算、Markdown解析、可见已读请求/回包投影以及 WebView挂载。仅在同负载测量支持时改该私有路径，可采用消息内容键的有界/视图生命周期缓存、聚合幂等已读等；授权/状态更新不能缓存掉。若性能修复需要改业务语义或新公共边界，先修订受审设计再实施。没有稳定收益的候选不合入；性能调查仍报告实测结论与限制，不把正确定位等价于无掉帧。

## 接口与数据流

- 连接展示策略：`update(state, now)`保留连续不可用起点；`presentation(now, hasContent)`返回静默或稳定辅助文案；clock/timer可注入测试，不每帧重算/每秒改内容。Store 生命周期取消旧timer、防止退出后回填。
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
| M1-continuity | 连续聊天状态与原生验证 | 无 | 串行集成 | ChatPhases/ChatStore/UserStream、ChatList/Conversation及私有策略、测量支持的局部呈现、Tests/UITests、ios-client delta | [reviewer] 短重连零反馈且不位移，持续失败一处诚实可恢复；Chats重进尾部、动态增高/键盘跟随、上翻/详情/前后台不抢位、旧定位不覆盖最新；原生信息层级协调；实测卡顿因果与性能对照及限制清楚。[worker] 策略边界、timer取消/epoch、WS失败退避与操作错误单测；真实UI连续旅程含缓存重入/高卡片/分页竞态/历史上下文；相同fixture基线候选metrics/请求/必要profile；原生build+受影响单测、CI等价检查；不更改权限/发送/媒体持久边界。 |

## 交付路径差异

工具实际拒绝首文档直推共享 develop，完整命令未执行。主Agent决定遵守该边界：首文档、设计与实现均保留本轮独立 `unit/bugfix-763-ios-chat-continuity` 分支，最终 PR → develop，不重试直推/不 force-push。主checkout已有dirty不碰。
