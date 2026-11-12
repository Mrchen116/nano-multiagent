# M1-continuity — 实施记录

## 实际起点

- 默认简化实施，主执行者端到端集成；连接scope/传输子系统在独立worktree交局部helper，主执行者实现滚动；另一helper只维护共享原生harness/执行基线。不是机械分层milestone拆分，最终审查另交未参与实现者。
- baseline product `45babb2b49e314754c6ca390f4ca3da61fe9f107`；独立worktree `/private/tmp/nano-ios-chat-continuity`，分支 `unit/bugfix-763-ios-chat-continuity`（遵主Agent在直推拒绝后确认的同一分支路径）。主checkout用户dirty保留。
- Gate2 R2 `Approved / 0 CRITICAL / 0 WARNING`，受审 `aab91da798f8`；仅报告确认后进入实施，尚未改产品代码。

## 准备与测试处置

- 独立pnpm frozen install、frontend npm ci及原生baseline build / NanoIMJourney build-for-testing通过。Xcode26.4.1，iOS26.4，专用新iPhone17Pro模拟器`37326699-6680-4108-8319-D751AD931579`；尚未App内登录/截图/滚动，不能宣称体验通过。
- 300×2专用合成IM fixture经真实API与只读DB核对，消息/卡片不是模型生成；helper正在将停进程/重启耗时不稳定的短断方式替换为仅本轮listener关闭/重开的可控演练，准备完成后才能使用。主执行者接手清理责任。
- 保留已有权限、清理revision、本地库和发送测试；`ChatPhaseTests`原始连接描述辅助函数测试可保留，`ChatLocalFirstTests`中『离线立即显示文字』『HTTP sync成功即online』预期将按新的静默和完整实时健康语义改写，原本地先于网络的保护不删。
- 新滚动状态/异步定位风险没有现有owner，拟新增针对可观察滚动目标的最低层策略测试；真实原生harness只承担SwiftUI实际布局/生命周期和性能，避免复制内部状态断言。既有UITests私有helper不可直接复用，新共享合成fixture helper服务连续旅程与性能case。临时测量脚本/截图不进入永久测试。

## 已核实的原生基线与实施

- `NanoIMBuildRevision=b5d150a0b-baseline` 的未改产品App，真实UI登录/初次进入通过。原生截图显示屏幕落在H763-292…296，Latest可见，300及终尾不在屏内；主执行者直接读图确认。这是首次进入未到尾的真实红证据，不以prime的渲染成功冒充连续性通过。附件：`/private/tmp/nano-ios-763-evidence/baseline-prime.xcresult` 与 `baseline-prime-attachments/D43643FE-DF3D-4D6B-937B-10D7A4B34B68.png`（收尾须promotion到稳定证据路径）。
- 独占fixture runner已ready，同一个createServer/HTTP listener经本轮专有SIGUSR1/2执行3秒/12秒关闭恢复，记录真实monotonic downtime；未修改协议/代理/权限/DB。故障演练尚未消耗。
- 滚动实现单一`ChatScrollPolicy`+小型Observation adapter独占ScrollPosition，像素级几何不发布到timeline body。跟随由意图而不是末行可见推断，tracking暂停/实际手势才失效旧restore；懒布局与行高/视口更新驱动合并纠正。历史保留稳定行+有效视口偏移；Older await不再无条件scrollTo top。尚待编译/实测，不能据代码宣称通过。
- 300实际加载证明与同负载metrics尚在执行。基线harness修正LazyVStack回收期间的XCUI查询竞争时，完整冻结基线App bundle并以所有文件hash校验恢复；不能将候选App混入基线。

## 当前实施与有效证据（2026-11-12）

前文为按时间保留的准备记录，以下更新当前状态，不把当时的『尚未』当作最终缺口。

- 产品冻结 `ed5248dc1fa74358ac74b65f9a98589cc4142d8d`：scroll intent/coordinator、真实WS ping恢复、读取scope与业务错误拆分、两surface固定导航slot已集成。未实施日期/Markdown/已读等猜测性性能优化。
- 全量原生单测：219 XCTest / 0 failure / 1既有真机保护skip，另29 SwiftTesting / 0 failure。`candidate-unit-green.xcresult`及`.log`绑定该SHA。新增非网络协议读取失败回归先在7fb8740d产品+新测试取得7项真实断言失败，再在ed5248通过；不误称该red为最初基线。
- 真正原生加载300边界已验证：两会话均实际Earlier四页，UI181→121→061→001与只读App SQLite各300条对账。共享harness冷/暖各1 discard+5 retained；原始基线App整体冻结并恢复全部20项hash，避免候选混入基线。
- 未改产品基线远距Latest：Markdown通过；混合卡片在001→一次Latest后最终尾标仍Y3513，输入框上界779.67，是真正未到底。该次有其他构建负载，只作功能red，不作D5定量性能样本。原始 `baseline-far-latest-diagnostic.xcresult` / attachments / installed-proof.json留存。
- 候选Journey构建通过，`NanoIMBuildRevision=ed5248dc1fa7`且无单测plugin；0600候选runner仅继承同一fixture环境，产品路径保持候选，所有App文件SHA单独记录。首轮原生smoke实际4项/3失败：远距Mixed最终tail已到，但3秒内未取得3个稳定frame；缓存重入case在首次tail稳定窗口失败，尚未走详情/前后台；真实键盘显示后消息视口确实空白，尾标不存在。`candidate-functional-smoke.xcresult` / attachments保留全部失败，不能宣称功能通过。
- 首轮Large Type case虽然green，启动参数常量错误，实际是默认字号，**不计大字号覆盖**；一次性harness已改为UIKit公开enum.rawValue，待真实画面重验。同一混合卡片末尾实际上有Title/Text两枚同名marker，共享observer已修为选实际最末叶Text并记录全部候选，避免第一枚可见就当最终tail完成；冻结fixture不改。
- 独立初审 CODE-763-1确认Pin/Mute业务重试成功不消费旧错误。将原View PATCH原样提取到Store后，新回归取得Pin/Mute两项有意义的XCTAssertNil失败。主修为按操作scope/owner及epoch消费其自身失败，并使错误行Retry重试真正失败的PATCH；不得恢复『任意读成功清业务错误』。真实focused green已执行：1 case / 0 failure / 0.075s，`preference-recovery-green.xcresult`与source hash绑定；这是带临时诊断的dirty source，不把旧219+29重标为最终树全套通过。finding仍待最终独立复核。
- 首组baseline MarkdownColdScroll已取得5个非空App CPU、peak memory与scroll-duration样本；XCTHitchMetric没有输出hitch系列（**不是0**）。备选Animation Hitches实际record返回exit2，完整日志为 `baseline-animation-hitches-support.log`：`Hitches is not supported on this platform.`。按当前D5，性能结论inconclusive，不归档为完成。有界能力探针/真实MOV捕获链校准提案经R3修正完整运动窗口漏洞后，R4独立设计复核Approved 0C/0W；不冒称Apple hitch等价值，校准/产品事件时间绑定不足仍inconclusive。该分支尚未运行，之后因用户要求直接试模拟器而让位，未降低目标/宣称通过。其余可比指标仅作部分证据继续保留。
- 3秒/12秒故障仍未消耗。候选健康listener下出现持续raw不可用caption，是待定位实际问题；不在该前置未清时消耗故障或把旧caption归因给新fault。服务PID54838及出生时间/cwd/command/loopback监听再次核实。临时凭据和runner不入Git，原始结果须扫描实际secret后再promotion。

## 后续真实观察与当前人用交接

- 原计划基线8组全部各执行一次、每组实际1discard+5retained，无丢red/补跑。四scroll组CPU/peak-memory/scroll均非空；Markdown冷暖Latest各5/5真尾，Mixed冷暖各0/5、完成时延null，最终Text y3546/maxY3567仍屏外。`baseline-status.md`与`baseline-partial-matrix-summary.json`保留完整值/hostload，postflight核实全20项App原hash与两组300行。实际runtime26.4.1/23E254a（SDK标签26.4）。固定6历史+6向尾手势的Mixed末图在284，不把execution PASS当成功回尾；独立Latest真实尾标/时延目标不减免。
- 一次纯观察原生诊断已完成，未注入故障。键盘这次实际final Text419…439、composer477.667，三帧稳定；不能关闭原先空白问题，因为诊断改变时序。普通App连接日志只记录ticket received→resume sent，42秒内没有handshake-confirmed/catch；停在ping等待是已观察边界，Foundation接收顺序/服务端响应原因仍未知，未重试此前被拒的独立credential/WS probe。
- 数字几何日志已直接揭示adapter把系统insets重复扣除：无键盘实际ScrollView global116…779.667被算成232…685.333；有键盘实际361.667pt视口又被扣396.333而变零高。这解释了真尾仍显示Latest等错误判定；原空白的全部因果尚未复验。已准备基于真实记录的两项最窄unit regression，尚未编译/执行，产品机制未继续叠猜测补丁。
- 用户要求“打开好模拟器给我验证也可以”后，优先交实操，不再卡在自动hitch量化。通过cua-driver实际打开专用窗口`bugfix-763-chat-continuity`，候选`ed5248-geometry-diagnostic`全部安装文件hash核对，已打开B高卡片并直接读图确认最终Text `763-END`可见。持久server配置核实为本轮loopback。明确告知仍有raw不可用caption、真尾Latest按钮、初轮keyboard/3秒失败未关，大字号与短长断线未验；不是全部修好版。
- 交接前Cua末次验证该精确Simulator窗口focused/frontmost ordinary均true，结束driver session但不关App。**当前sim/fixture为人用保留**：没有测试/采集job运行，不build/install/launch/trace/录屏/自动驱动与用户争抢该sim；只可整理已有日志/源码。待主Agent转回实际反馈和恢复自动操作时机，不把人用交接当用户验收或整个unit完成。

## 待执行

1. 完成真实模拟器连续旅程与D5冻结对照；只对测量支持的代价做局部优化，不丢失败样本。
2. 独立静态review已派原非作者reviewer；真实体验/旅程/性能证据齐后补同一review收口。归并delta与本地CI、归档、PR develop/远端CI；不merge/部署。
