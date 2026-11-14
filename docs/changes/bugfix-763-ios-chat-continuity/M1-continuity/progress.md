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
- 独立初审 CODE-763-1确认Pin/Mute业务重试成功不消费旧错误。将原View PATCH原样提取到Store后，新回归取得Pin/Mute两项有意义的XCTAssertNil失败。主修为按操作scope/owner及epoch消费其自身失败，并使错误行Retry重试真正失败的PATCH；不得恢复『任意读成功清业务错误』。真实focused green已执行：1 case / 0 failure / 0.075s，`preference-recovery-green.xcresult`与source hash绑定；这是带临时诊断的dirty source，不把旧219+29重标为最终树全套通过。同一原非作者已在当前dirty子集独立复核，CODE-763-1 CLOSED / Approved SUBSET / findings=[]；UserStream与新增5项握手测试亦静态通过子集审查并核对focused原始日志。此结论不包含滚动、键盘、实际网络恢复、UX/性能或最终冻结全树；临时诊断移除后仍须最终review。
- 首组baseline MarkdownColdScroll已取得5个非空App CPU、peak memory与scroll-duration样本；XCTHitchMetric没有输出hitch系列（**不是0**）。备选Animation Hitches实际record返回exit2，完整日志为 `baseline-animation-hitches-support.log`：`Hitches is not supported on this platform.`。按当前D5，性能结论inconclusive，不归档为完成。有界能力探针/真实MOV捕获链校准提案经R3修正完整运动窗口漏洞后，R4独立设计复核Approved 0C/0W；不冒称Apple hitch等价值，校准/产品事件时间绑定不足仍inconclusive。该分支尚未运行，之后因用户要求直接试模拟器而让位，未降低目标/宣称通过。其余可比指标仅作部分证据继续保留。
- 3秒/12秒故障仍未消耗。候选健康listener下出现持续raw不可用caption，是待定位实际问题；不在该前置未清时消耗故障或把旧caption归因给新fault。服务PID54838及出生时间/cwd/command/loopback监听再次核实。临时凭据和runner不入Git，原始结果须扫描实际secret后再promotion。

## 后续真实观察与当前人用交接

- 原计划基线8组全部各执行一次、每组实际1discard+5retained，无丢red/补跑。四scroll组CPU/peak-memory/scroll均非空；Markdown冷暖Latest各5/5真尾，Mixed冷暖各0/5、完成时延null，最终Text y3546/maxY3567仍屏外。`baseline-status.md`与`baseline-partial-matrix-summary.json`保留完整值/hostload，postflight核实全20项App原hash与两组300行。实际runtime26.4.1/23E254a（SDK标签26.4）。固定6历史+6向尾手势的Mixed末图在284，不把execution PASS当成功回尾；独立Latest真实尾标/时延目标不减免。
- 一次纯观察原生诊断已完成，未注入故障。键盘这次实际final Text419…439、composer477.667，三帧稳定；不能关闭原先空白问题，因为诊断改变时序。普通App连接日志只记录ticket received→resume sent，42秒内没有handshake-confirmed/catch；停在ping等待是已观察边界，Foundation接收顺序/服务端响应原因仍未知，未重试此前被拒的独立credential/WS probe。
- 数字几何日志已直接揭示adapter把系统insets重复扣除：无键盘实际ScrollView global116…779.667被算成232…685.333；有键盘实际361.667pt视口又被扣396.333而变零高。这解释了真尾仍显示Latest等错误判定；原空白的全部因果尚未复验。已准备基于真实记录的两项最窄unit regression，尚未编译/执行，产品机制未继续叠猜测补丁。
- 用户要求“打开好模拟器给我验证也可以”后，优先交实操，不再卡在自动hitch量化。通过cua-driver实际打开专用窗口`bugfix-763-chat-continuity`，候选`ed5248-geometry-diagnostic`全部安装文件hash核对，已打开B高卡片并直接读图确认最终Text `763-END`可见。持久server配置核实为本轮loopback。明确告知仍有raw不可用caption、真尾Latest按钮、初轮keyboard/3秒失败未关，大字号与短长断线未验；不是全部修好版。
- 交接前Cua末次验证该精确Simulator窗口focused/frontmost ordinary均true，结束driver session但不关App。**当前sim/fixture为人用保留**：没有测试/采集job运行，不build/install/launch/trace/录屏/自动驱动与用户争抢该sim；只可整理已有日志/源码。待主Agent转回实际反馈和恢复自动操作时机，不把人用交接当用户验收或整个unit完成。

## 人用样本纠正（不是修复通过）

- 用户指出旧示例“没有UI消息，只有markdown，没有说服力”。直接读旧source确认虽走WK，但只是Title+32个Text；不能用卡片数量反驳视觉代表性不足。新增独立C试用会话，不改原A/B600条冻结source/checksum。
- 在用户明确“切啊”交还空档后，通过真实Messaging/Interactions注册24短历史+1张真实OpenUI看板；没有启动第二server/Delivery、重启服务、重装App、读token或网络probe。准备阶段创建扩展脚本曾被拒，实际新空档授权后才沿同事项恢复正常工具检查执行，未换法绕拒绝。receipt：`/private/tmp/nano-ios-763-runtime/visual-extension.receipt.json`。
- 当前C `c_yyvwpn3r`“763 · C 可交互看板 · 点击展开变高”，看板有双列状态、标签、分段控件、清单、展开三路线panel及大块布局切换，全部本地@Set。8种初始状态经真实parser/evaluator验证；随后实际App点展开→panel出现/变高→收起恢复，直接读图确认。`ui-sample-handoff.png`、`ui-sample-expanded-actual.png`、`ui-sample-collapsed-actual.png`在本轮evidence保留。实际主题按钮黑色，不把设计文字“蓝色”当画面事实。
- 已立即再次交还精确Simulator窗口focused/frontmost ordinary均true，driver session结束，当前人用保留。旧连接/Latest/键盘等失败仍未关闭。
- C初版另发现同毫秒created_at导致iOS用随机id打平局，native次序末组22/24/UI/23；因此旧UI-763-TAIL不作为全聊天真尾验收。用户随后明确要求“消息列表里有多个UI消息我才能测”，主Agent批准C扩展与最小刷新，不重装App/重启服务/长测。现在C已44条＝10张独立真实OpenUI＋34普通消息，卡片涵盖看板、清单、表格、SVG、活动步骤、图表、人数计算、方案与检查；全部独立可展开，穿插普通消息，可连续跨屏滚动。原C旧card同ID进行明确的synthetic fixture重注册（非产品改卡API），去掉蓝色按钮文字和易被误解为原生滚动设置的radio；所有C时间戳严格1秒递增，44条created事件DTO已对齐，最后普通消息明确763-C-CHAT-END。原A/B冻结hash仍不变。回执`/private/tmp/nano-ios-763-runtime/evidence/C-multi-ui.receipt.json`。
- 10卡初始/展开20状态通过真实parser/evaluator/schema验证。随后实际App普通Chats重进加载新C，直接读图确认09/10与完整末条END；实际向历史滚过08/09两个独立UI及中间普通消息，点击08展开出现A户外/B室内两个panel并变高，再收起恢复。实际图`multi-ui-crossscreen-actual.png`、`multi-ui-expanded-confirmed.png`、`multi-ui-loaded-actual.png`、`multi-ui-handoff.png`保留在本轮evidence。精确Simulator窗口再次验证focused/frontmost ordinary均true，driver session结束但不关App，当前人用保留，已通知主Agent立即交用户试。该样本更正不替代300×2冻结性能负载、异步动态尾部或修复通过；连接caption、真尾Latest等旧失败仍未关闭。

## 人用反馈后继续诊断（当前状态）

- 主 Agent 已结束上一段人用保留并交还专用模拟器。用户实际反馈“虽然能滚动到底下……也会一直闪……界面稍微被放大，左边都凸出去了”。已直接读用户截图：原生头像、Markdown 与 WK 卡片共同左移，归一化后卡片宽度不变，不能当成 Web 卡宽或 App 缩放问题。
- 真实几何输入对应的两项 adapter regression 先取得 red（重复扣键盘 inset、真尾已可见但 Lazy extent 导致 Latest 不消失），随后仅修有效视口与可见尾判定。focused 18 项通过（10 scroll、3 continuity、5 WS handshake），不替代最终全套。`viewport-regression-red.xcresult` / `viewport-green-a.xcresult` 留存本轮 evidence。
- WS 普通 App 路径先已观察 ticket→resume 后无确认；修为先启动唯一 receive pump，再等待可取消、有上界的 pong readiness，收到确认前缓冲事件。候选普通 App 实际出现 receive-start→handshake-confirmed、旧持续不可用 caption 消失；SDK 行为仍不等于已证明 Foundation 内部因果，未绕过此前被拒的独立凭据/WS probe。
- 横向 trace 证明内容宽度恒定 402、左右 inset 为零，但 contentOffset.x 在 0/16 之间改变，且第一次偏移发生在任何显式 correction 之前。修有效视口后仍有永久 16pt 左移，尚未关闭。单独更改 bottom→bottomLeading、单独将 scrollTargetLayout 移到 padding 之前均未修复，已分别回退；目前独立验证无初始 ScrollPosition edge 的单变量版本，不把猜测补丁叠成最终方案。
- 用户进一步纠正“闪动就是横向偏移的问题，一会偏移一会不偏移”：按同一消息区域左右横跳处理，不再另开亮灭/独立闪屏调查。具体 anchor/layout 竞争机制仍待工程证据，不由用户症状描述证明。
- D（不持有初始 edge）普通 C 实测54事件：首次显式 edge 请求前x0，之后动态布局发生x16，尾左缘0；故只移除初始edge不足修复。E仅将两个edge请求换为尾部id，112次请求仍停在同一y，消息加载后的真实尾未实现；x0不是通过。E2仅将尾部改单项ForEach后原生入口case通过且真实尾可见，但trace与同代AX证明仍永久左偏：消息共同wrapper宽370/x0，对402屏幕左/右gutter为0/32，内容root宽402/x−16。静止x-range=0不等于对齐正确，未接受此候选；已据同一真实共同祖先补初始margin对称判据，后续单独验证targetLayout与padding的目标边界。
- 新 C 原生测试直接观察精确最后一条普通消息，禁止用 Latest/手势修入口；记录至少 13 个、至少 2.4 秒 AX 样本及展开/收起后的同一参考坐标。它验证横向稳定样本，不宣称样本间绝对无瞬态。
- 强判据在 E2/E3 真实 native 均 red（13 样本各 L0/R32、中心偏16），modifier 顺序不足修复。F 将 target layout 的普通 padding 迁到公开 ScrollView contentMargins；首次入口真实 green（13 样本 L16/R16、真尾可见、Latest0），但另一独立入口出现 sentinel 几何最后1057 与 AX 真实末条在屏内不符，Latest误现；保留失败，不以随后5次入口全绿消除它。
- G 将同一有序最后消息 ID 同时作为定位/到达判据，删除透明 sentinel；实际 row trace 曾与 AX 末行位置吻合，完成语义不依赖另一个可回收尾标。12项 scroll unit green；旧历史测试的 B 末行原在视口内却期望仍读历史，修为视口下方后原5项锚点断言保持并通过，原失败留存。原非作者静态滚动子集 CLEAN / findings=[]，不是最终全树或体验审批。
- G 真实 C 两 case / 0 failure：untouched初始、持久expanded状态后的真实收起归一化、展开、收起共5阶段，每阶段13个AX样本，L/R全部16/16、横向range0、Latest0；末条一直可见，Y range分别0/0/0/0/0.667pt，采样持续3.8–5.0s。直接读展开/收起真实截图，原生头像、Markdown/WK/气泡共同正常留边，末条在composer上方；不以该样本推全量无帧停顿。证据 `final-message-g-cards.xcresult`、`final-message-g-cards-observations.json`及对应attachments；键盘、历史导航、网络故障仍待本候选实际执行。

## 新发现的原生阅读阻塞与实际运行限制

- G 的 B 旅程取得 3 项真实 green：6 次历史手势后详情/前后台保持同一 anchor（4pt 内）、Chats 重进回真尾；真实软件键盘及三行 composer 增高后真尾可见；公开大字号参数下详情可达。`final-message-g-reading.xcresult` / `.log` 保留对应结果与截图；其中最后一项纯 Markdown Earlier case 失败，因此整次 test command exit65，不称整套通过。键盘测试删除草稿后的后续大字号截图仍有 `line one`，清空草稿的 harness postcondition 尚须核实，不能据测试 green 宣称清理成功。
- A 的 Earlier case 在第 3 次上翻后 App 主线程不再响应，尚未点 Earlier。原始无 trace 的 run 与随后仅启用本地诊断的同一产品 G 均出现；`final-message-g-earlier-diagnostic.xcresult` / `.log` 及 `final-message-g-earlier-main-thread.{receipt.json,sample.txt}` 记录后者。已核实只 sample 本轮专用 Simulator App PID；34 个有效 main-thread 样本均在 SwiftUI/AttributeGraph lazy placement/layout 事务，AX 等主线程。不是已证明的 Apple bug，不把短 sample 当 CPU 定量。
- `final-message-g-earlier-scroll-events.json` 共 2266 事件，前两次手势回 idle，第三次进入 decelerating 后停止回调；末 content height 32290→31738。仅 2 次 `correct-final-message`，均早于首手势，0 次 `correct-history-y`。这不支持当前现场的 history-y 纠正自反馈假说；未单独 trace 的历史 ID restore/realize 分支不能由日志绝对排除。具体触发机制仍未知，旧基线同类 12 手势曾完成，因此本次滚动修改仍有回归嫌疑，候选不可交人试用。
- 仅为隔离 target registration，H 单变量将 `.scrollTargetLayout()` 改为 `isEnabled:false`，build exit0，revision `7c3b192-target-layout-h` 的正常 App artifact 已绑定并安装，证据 `target-layout-h-build.log` 与 `/private/tmp/nano-ios-763-runtime/artifacts/target-layout-h/binding.json`。随后同一 Earlier XCTest 调用被工具明确拒绝（引用早期只读/原生 UI 运行限制），未返回 job ID/运行输出，不把它记为执行。已停止、不换工具/runner/child 绕过；已通知主 Agent 对照实际人类原话处理。源代码一行已回退 G，**未 rebuild/reinstall G，当前 derivedData 和已安装 App 仍 H 诊断版**；H 无测试结论、不作产品修复。现存 G 正常 artifact 在 `/private/tmp/nano-ios-763-runtime/artifacts/final-message-g/NanoIM.app`；恢复安装也尚未执行。
- 之后主 Agent 向用户实际送达具体问题“允许在该专用隔离模拟器里启动 App，执行本 unit 的上翻、跳底、键盘和重连原生回归测试吗？不涉及生产环境或手机”，用户明确答“允许”。沿同一事项恢复，未扩大到生产/手机或独立 token/WS 探针。恢复前核实唯一 booted 的专用 simulator、源 G 及安装 H 的全部 20 个 App 文件 hash；本轮 fixture 原 PID/出生时间/cwd/loopback listener 均保持。回执 `target-layout-h-resume-state.json`。随后按正常工具检查重新提交同一 H Earlier 单变量回归，实际获得 job；结果仍须按真实运行判定，不把许可当作通过。
- 恢复后的 H Earlier 真实 exit65，仍第 3 次上翻后主线程不可响应；因此单独禁用 target layout 不足消除卡死。新 bounded 原生诊断保持同一 A/同一手势（6 次向历史、6 次向尾，不注入 scroll hook），I 仅从 G 移除 `.scrollPosition` 绑定，实际 12 手势与两端 AX/截图均完成（54.332s，exit0）；I 有意失去程序定位职责，不能作为修复。随后原样恢复绑定的 G 对照在同一 bounded case 再现卡死（294.283s，exit65）。`target-layout-h-earlier.xcresult`、`position-binding-i-twelve.xcresult`、`position-control-g-twelve.xcresult` 与各自 build/App/source binding 全保留。这将必要交互边界收窄到绑定位置参与的路径，仍不证明内部 ID resolver 原因。随后 J 首次确认 reading 位移后仅写 `isPositionedByUser = true`、K 重建自动 String position，两次原生均 exit65/同第3手势阻塞；超时重启后的0-test suite不算成功。它们均不保留为产品补丁。公开 user-positioned 契约只保证用户定位语义及清除非 nil edge/point，不保证取消所有 ID 求解。
- D5 revision2 准备已静态完成，但公开 actual XCTest event→product MOV 的 ≤X/3 时间绑定 producer 实际缺失，validator 不等于 provider；有限 Game Performance probe 也未执行。依原 design 只能 inconclusive，不能归档完成。性能探索/新样本准备当前让位给可用功能候选，不再先跑校准掩盖原生卡死。

## R5 adapter 实施及未通过的原生验证

- Round5 独立 Gate2 为 Approved / 0 CRITICAL / 0 WARNING（design SHA256 `fc8264f365bb19de2732079f2c45c5adce80e6119f42d0599b9ed9871da45423`）。L 实现将四类 ID 请求全部汇入 timeline-local Reader action，默认 Never 的 ScrollPosition 仅留 y；attach/detach generation、缺 adapter 重调度、point 清理及实际拖动取消均纳入同一 coordinator。原14项 scroll 单测实际全绿（`reader-adapter-l-unit.xcresult`），不作为真实 SwiftUI 接线通过。
- L 的108份产品/Tests/UITests/scheme源在 build 前冻结、后核实完全未变，并绑定实际 UITest executable；正常App全部20文件安装后hash匹配、无unit plugin。回执 `reader-adapter-l-{source-before-build,build-binding}.json`、`artifacts/reader-adapter-l/binding.json`。原生同 A / 同12手势 case 仍在第3历史手势卡死，XCTest实际 exit65（`reader-adapter-l-twelve.xcresult` / `.log`），不能交试用。这推翻了“只撤掉String ID跟踪即可解除现场”的修复预期，仍不证明私有框架根因。
- 独立review给出 `CODE-763-L1` MEDIUM / PLAUSIBLE：ID后offset与row frame的独立通知可能混代，当前OR闸门允许先新offset+旧row或先新row+旧offset，发错误y；未在native证明该顺序是此次卡死根因。不能以窄单测绿关闭此风险，也不能机械改AND而阻塞合法仅row改高。
- 当前 M 只从 L 移除 `.scrollPosition` 绑定，仍保留同一 Reader ID adapter，作为必要条件诊断；有意不兑现历史 y，因此不是完整候选。通过同一 bounded case 区分“任何 position binding”与“Reader 程序请求本身”参与，不据一次诊断绿交付。若需要改变执行边界，将先修订受审技术方案，不继续堆未证实小补丁。键盘清理harness已改为真实 Select All/删除并严格空值，但新菜单路径尚未原生验证。

## R5 后续必要条件对照（均非完整产品候选）

- M 完全去掉 ScrollPosition 绑定但保留 Reader，N 再去掉 target-layout registration，均在同第3历史手势后失败/exit65。故“绑定是挂起必要条件”“只删targetLayout就足够”都不成立。N 的确切专用 App PID26332/revision/hash核实后 sample exit0，258个main样本仍以 SwiftUI lazy measure/phase/layout事务为主，自有代码未见定位写入栈，不能下私有框架根因结论。
- O 从 N 改为向额外固定1pt footer发 bottom请求；coordinator completion仍取实际最后消息 ID/row frame，history y有意不生效。原样12手势case真实通过（52.286s/exit0）。这是“固定尾端拓扑+目标路径”的可操作差异，不仅是ID改名：额外约19pt间距、末行不再是last child、惰性估算extent也改变；不以此声称已精确归因。
- 精确PID的本sim事件已导出：L/M/N首次手势前实际末行相同、global tail bottom均763.667、有效viewport116…779.667，estimated extent32290；O同5个末尾row身份、tail bottom744.667、extent31498。O后来经过N挂起时全部8个缓存row，最近一帧各row globalY一致相差5pt（revision10）；仍不声称私有layout状态相同。`reader-n-o-oslog.json`、`reader-{n,o}-scroll-events.json`、`reader-l-m-n-o-trace-summary.json`及`reader-n-o-nearest-row-window.json`记录来源。I无对应事件导出且旧case无initial true-tail断言，不把I过推成严格同起点/必要因果。
- 新增独立原生功能case保护“初始真尾→实际上翻→history稳定/Latest可操作→明确点击Latest→真实尾部/入口消失”，另有clock无任何swipe fallback的所有权case；旧12手势与strict Select All helper不变。Reading tests SHA256 `8e469ef8927b40ed14b87f807538cf4aa3b83815d0976bfac7e8fe09a3109538`。O-functional重新冻结108源/scheme并绑定UITest executable，正常App安装20hash匹配、无unit plugin：**A六次上翻后H763-289的实际Y保留706.667，tail不在viewport、Latest可点；明确Latest后真tail连续3样本可见且入口消失，46.590s/0failure**。这证明O不是默认定位/no-op替代程序Latest；仍不证明任意历史y。另clock case真实失败（17.299s），tap(80,30)后未见Earlier/001；直接读before/after截图视觉仍在相同末行，不把它自动归因“coordinator抢回”，需trace或对照分类。整次command exit65，不记全套通过。证据 `reader-endpoint-o-functional.xcresult` / `.log` / `-attachments/`。
- 用户系统重开后明确“继续，刚刚重开了系统，agent中断了”。已重新核对同branch/HEAD、fixture原PID54838出生时间/cwd/listener、专用373sim booted、installed O 20hash，均保持；没有遗留bash jobs。旧授权不扩大，沿同一事项接续；不新建副本或重跑有效基线。

## R6 原子原生几何与系统 top 所有权

- 精确自有sim/PID89581的clock事件已核：offset确实上移至-116.667，SwiftUI全程idle/latest/rev0，随后本方correct+request拉回94663。故旧截图相同不是noop，CODE-763-2有真实事件支持；不据此推断私有layout挂起根因。`reader-o-clock-oslog.json`及`reader-o-clock-scroll-events.json`保留。
- Round6指出lazy footer依赖和native top来源未闭合；Round7在persistent content-root、局部公开delegate透明forwarding/weak/rebind/detach、真实shouldTop来源、noop/代次取消补全后Approved0/0。设计最终SHA `ee5a0ea8e3c4f9ac17ab3aafd8b0d2a18e296449df3b395a41e64cc7d7cfabf2`；设计批准不关闭实现finding。
- P已移除全部ScrollPosition/targetLayout，Reader使用私有固定footer端点而actuallastrow判完成；historical y通过同MainActor同步UIKit live tuple、同ancestor/window/viewport校验，保x/clamp。局部forwarder观察允许的nativeTop请求，原delegate返回值与其他optional方法透传；Latest/drag/解绑取消旧top暂停。17项scroll单测实际全绿（`native-adapter-p-unit.xcresult`/log），包含混cache顺序不写、live tuple实际原生y恢复、foreignrow、clamp/x、原delegatefalse/optionalforward、noop/replacement/latecompletion。不是原生App接线通过。P Journey build-for-testing exit0，109源/scheme前冻后核、UITest executable绑定 `native-adapter-p-{source-before-build,build-binding}.json`；正常artifact准备及原生测试待执行。
- 新D专用120条合成会话 `c_afqtkn0l`，消息360秒间隔保证prepend不消失061 timestamp；真实Messaging创建/insert，不改A/B/C，全部旧messages+card-source hash保持。receipt `D-pagination.receipt.json`。Earlier harness仅新增正确的第一旧row061非零Y恢复→无fallbackclock001，不清AppDB/改原A/B性能语料；错误08卡下方ordinary固定Y case已删，因已定策略合法保存更上方可见卡top而非下方ordinary。D首次运行仍需cache0→60→120与实际trace核对，未宣称已通过或两物理分支必执行。
- P functional 实际2例全绿：A untouched真尾→6次上翻→稳定history→明确Latest真尾；clock无fallback直达001、同一anchor Y209.667观察不变→明确Latest真尾（22.318s）。`native-adapter-p-functional.xcresult`/log为2tests0failure/exit0。命令中误写的12手势selector没有实际case执行，**不能记12手势绿**。
- 独立P静态review仍给出两项MEDIUM：P1为已live且Reader/top合法noop时pending快照相等永久阻挡所需相对y；P2为didTop早于SwiftUI最后几何时缓存判底/capture可能误切latest或拉回。新增两项确定性回归在P产品实际2tests/9断言失败/exit65；分别观察A0未恢复−20、cachedtail400误latest、cached610保存−20并把live native0拉20。`native-adapter-q-red.log`保留；其后的simctl诊断收集PATH error72不是已执行断言失败原因。不把受控排序证明升级为平台真实回调顺序证据。
- Q按原R6职责修实现：已live history直接coherent y，不发不必要Reader；真正unrealized仍保留ID后live tuple/代次门。bound时actualtail判底与captureAnchor均只读live marker，无live不退回旧cache；coalesced校正刷新button。旧mix-cache回归改为B先unrealized，仍覆盖两缓存顺序不写→live实现actualy1210。19项scroll单测全绿/exit0（`native-adapter-q-unit.xcresult`/log）。同原非作者完整读受影响delta并核hash后 `Approved SUBSET / findings=[]`，P1/P2在源码/受控排序层关闭；不是原生全路径或最终全树批准。
- Q Journey build exit0，109源/scheme前冻后核、UITest executable绑定 `native-adapter-q-{source-before-build,build-binding}.json`；正常artifact全部20文件安装373后hash一致、无plugin，revision `7c3b192-native-adapter-q`。D首次进入前只读cache确实0条，独立0600 runner仅新增四项D合成输入；真实D原生测试与只读0→60→120 observer运行中。A12、Q clock/Latest、C/B、网络及性能仍不记通过。

## 待执行

1. 先解除纯 Markdown 连续阅读卡死并核实可复核的触发边界，完成 Earlier→Latest、当前树远距 Latest/状态栏定位所有权及短/长断连两 surface 旅程。具体隔离sim运行限制已有用户明确允许，仅沿本unit/专用373 simulator继续；不扩到生产/手机或此前独立token/WS探针。
2. 独立静态review已派原非作者reviewer；真实体验/旅程/性能证据齐后补同一review收口。归并delta与本地CI、归档、PR develop/远端CI；不merge/部署。
