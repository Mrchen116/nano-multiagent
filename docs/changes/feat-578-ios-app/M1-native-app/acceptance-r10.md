# feat-578 — 原生已读、提及与提醒窄验 R10

> native2505c9772未变；独立change-reviewer，GPT-6.1 Sol由用户指定。仅补S6/S7/S12/S27，保留R9已绿范围；无实现修改/commit。

## 当前裁决

**fail / R10-01 major blocking。** Latest后实际未到最新消息、native持续忙且产品AX不可用，S6不能通过。S7/S12/S27未执行，保留inconclusive。

## J46 专用真人可见域已读

caller真实API创建仅nano与本次iosr9late的direct chat `c_1p4zrncj`，标题578 R10 Read and Banner，10条每条19行合成历史标记，初始unread10/is_muted=false。原生打开确见history10全部19行及09尾部。CUA coordinate scroll/drag未移动；随后freshAX click较早消息文本触发原生bringIntoView，依08→06→04→02逐段上移，每次重取AX，截图最终02全19行+03顶部，最新10不在视口。未读页面或修改scroll状态，未调用实现。

READY后caller用对方真实身份唯一发送578-R10-unseen-11，message_id dbc2440a9dc64bc5a56a51520f226cd0；原生fresh截图仍02/03位置，11未在视口，Latest仍可见，没有抢滚动。caller发送后1.5秒权威列表unread1（07:18:18.072UTC）。此结合证明新未见消息未被读历史吞掉。

主动点击freshAX Latest后直接截图仅到08末尾/09，11尚未可见；随后AX为Window unknown仅Simulator工具栏，截图保持该位置。重新getApp Simulator结果相同。没有lock错误；没有自动解锁/重启或猜新索引。UI暂停交接caller只读native PID/Simulator响应及unread辅助检查。不能宣称Latest已settle或11实际读到，S6整体先保留inconclusive。

## 最新S1–S30合并表




本表取R6及本轮最新实证，替代旧状态用于交接。inconclusive仅代表列明剩余分支未完成，不等于产品已确认失败。已经完成的注册、群管理、节点离线、绑定异常、容量及策略失败不再留作欠账。
| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | pass | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；R9 J45真实201上游已完成/客户端上传中时退出→实际旧连接中断→B身份正确/Chats空→A恢复无待发旧项。运行期未送达迟到主体；clear后transport迟到保护另有独立测试层证据，不混称UI已送达。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；R10历史02收新11不抢滚动且unread1已证；主动Latest停08/09未见11、native布局持续忙、AX无正文，但服务unread0，R10-01 major未修，不能关闭可见域门禁；前台跳转见S27。 |
| S7 发送提及历史 | inconclusive | R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；有效群提及及配置分界线未完整实证。 |
| S8 不确定发送重连 | pass | R5 J24真实POST后端201但回执丢失，输入保留/发送锁定/明确核对；恢复手动核对后同message ID仅一条、输入清空，收件方GET两次COUNT1。 |
| S9 复制fork蒸馏 | inconclusive | R6 J27来源/执行Agent/global选择保持、生成可编辑正确草稿、不自动发送，R5-02/R6-01已关闭；长按复制/fork受现CUA动作能力限制，离线/跨Gateway限制分支未完成。 |
| S10 附件接收导出 | inconclusive | R2照片上传/比例预览；R8 TXT/PDF系统选择、取消、发送、QuickLook、Share→SaveFiles及实际bytes/hash闭环；主动图片粘贴仍缺（本轮明确禁用host paste）。 |
| S11 附件失败权限 | pass | R5撤权后清缓存/禁用/列表移除；R8新包12MiB真实server413保留/移除/禁发，9MiB正常上传发送，one-shot503逐项失败/原PDF保留/仅文字无附件/原文件重试，429倒计时禁提前重试与恢复均完成；R9 J43下载503可恢复，J44外部image接收端无IM凭据/保护GET不同端口302未follow，J45真实退出中断上传与账号隔离完成。跨origin结论限定本次本机不同端口，不扩大任意外站；迟到主体未在B送达。 |
| S12 过程统计结果 | inconclusive | R1/R2真实工具/审批/主子执行及指标、运行计时持续增长和最终耗时回看稳定已完成；未知指标与全部后台返回顺序/最终性分支未完整实证。 |
| S13 审批确认 | pass | R2真实allow_once、Deny、暂停节点后等待确认/禁重复、恢复已处理及实际回复。 |
| S14 任务与回聊 | inconclusive | R1/R2 DAG/探索/子层级/非成员私聊隔离/回聊引用，R3清除搜索无需Return已关闭；失效关联与完整节点关系字段覆盖仍需补，不能把S7聊天分页替代此项。 |
| S15 Work主子历史 | inconclusive | R2真实主执行→子执行1641及统计、普通成员可读但不能配置/回私聊；历史轮次及分页明细未完整完成。 |
| S16 节点创建路径 | pass | R1/R5正常创建/模式双节点保持/目录确认/唯一性/重复ID/草稿保护；R7普通空文件路径被拒、真实离线说明并禁创建、新普通成员无设备引导且不能用他人节点，全部创建欠缺已补。 |
| S17 完整配置 | pass | R5各字段保存重开、备用顺序、工具/特性、显式空Skills与默认发现、只读归属和稳定预览；R7离线能力目录明确不可用/保留既有配置/提供重读，不虚构在线模型。预览不主张逐字节比对。 |
| S18 冲突pending权限 | pass | R1/R2非owner/冲突，R3暂停后pending→重读确认；R5 J19真实IM版本409保草稿/重读服务器值/选择继续/保存确认且反馈自动入视口，R4-01关闭。 |
| S19 Skills心跳Cron | pass | R2真实Skill来源/用量/会话toolcall标识展开，R3指定Cron确认删除/文档，R5心跳开关间隔时段保存重开；R7 Cron离线不等于空任务、HEARTBEAT无法读取说明补齐离线区别。 |
| S20 通道凭据 | pass（本轮凭据旅程） | R4专用飞书新增、已保存Secret不可读、保留、同现有Secret替换、改AppID强制替换/空值禁止提交均真实完成；不冒充平台换密钥。 |
| S21 通道生命周期 | inconclusive | R4实际connected→停用applied/实际停用→确认删除空列表完成；离线/停止失败重试、重连、受限/未知权限以及聊天历史保留分支未完成。 |
| S22 绑定 | pass | R2双端接受→等待→设备确认→完成；R7当前账号/测试设备检查、明确拒绝后归属不变、过期清秘密输入并提示重新发起。caller确认两测试operation未造node。 |
| S23 节点管理 | pass | 前轮别名/节点创建/非owner边界；R7中继与上报off保存重开→恢复on，真实第二节点offline与主online并存→恢复online，未动生产。 |
| S24 个人资料语言 | pass | R1/R2中英与中文错误修复，R6 J28显示名及默认设备保存退出重开保持，再恢复原值；只读身份字段可见。 |
| S25 公司管理 | inconclusive | R1批准/停用/最后admin拒绝、R2普通成员限制及客户端被停用；分页与被停用成员名下机器资格未完整实证。 |
| S26 策略容量 | pass | 前轮管理员全部策略保存/普通成员只读；R7服务与owner容量UI和实际API一致，精确单次503保32草稿→放弃回31，真实policy全字段仍baseline。 |
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。跳转、后台重放去重及回前台一致性仍缺；不再额外发无目标探测消息。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |




## R10-01 — Latest长历史跳转后持续忙（major / blocking）

期望：用户点击最新消息后实际看到最新11，客户端可继续操作，未读以真实可见结果推进。实际：在19行×10条历史的02处收唯一11后，点击Latest画面停08末/09头至13行，11未见；15:19与单次15:21截图时钟变化但相同消息位置，产品AX变unknown。caller只读native92311正确目标仍运行/SimulatorBooted/无crash，CPU持续99%；2秒sample主线程1421/1421处于SwiftUI/AttributeGraph事务与LazyStack layout，非网络等待。样本仅支持滚动布局忙，不单独证明根因。权威unread已0，明确记after-latest-ui-unsettled，不替代实际可见性。

Regression relation: suspected-regression / unclear具体因果；Recommended action: fix-implementation，验证同一专用聊天早期02→Latest可到11且继续操作，并与真实未读核对。caller拟最小A/B去Latest显式动画；尚未安装/受验，不在本报告称修复。截图在本轮CUA输出可复核，未提交截图缓存。不能用服务unread0关闭S6。

## 安全安装交接

旧受验native2505c9772/PID92311卡在专用合成历史，无待提交输入/附件，无在途写入。UI交还caller，仅待同数据新包安全terminate/install；本人不自行安装或并行操作。不会重建重复fixture；S7/S12/S27需待可操作候选后继续。无源码修改/commit；仅本报告，凭据未输出。保留原scoped视觉/已绿管理证据，完整S1–S30门禁仍fail。
