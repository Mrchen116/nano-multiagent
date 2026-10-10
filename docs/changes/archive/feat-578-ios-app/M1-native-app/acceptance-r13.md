# feat-578 — 发送挂起窄复验与后台恢复 R13

> Snapshot：5de8ffdb4 / 同390 UDID861AD10A-8A44-4028-8A4A-29CF1308E25D / native PID4396 / nano / base62009。独立change-reviewer，用户指定GPT-6.1 Sol。只写报告，无实现修改/commit。

## 裁决

**inconclusive / R12-01 closed，既有管理/媒体/提及范围保留。** 本轮正常多行发送、running→Home→completed恢复直接完成；长历史02/03→Latest11/12保持响应。S27后台结果补齐已完成；前台3秒banner捕捉调度超窗，点击跳转仍inconclusive。

## J52 — 发送与后台恢复closure

- 新包进入原群，R12唯一BG请求/回复500500已完成、composer为空，过程2展开思考＋bash completed13.1s；结果详情真实command/sleep12、duration13141ms、exit0/stdout500500。展开/Back正常。
- 原生菜单提及peer输入一次同类 `578-R13-BG` 请求，真实键盘输入后发现range重复逗号，未发送前selectText修正并核实完整草稿才Send。没有host paste/setValue。
- 点击发送后UI正常，用户请求已发送且composer清空；旧过程因展开仍处视口，显式Latest后直接见peer进行中、过程1、0:09–0:10。立即点击Simulator真实Home，主屏截图NanoIM图标可见，未操作其他App。
- caller辅助唯一请求b539a688eeff4cac8c9c17317c22b793，16:13:50创建；下一回复a004c20a9c1742a4817b34cfdf83236a完成500500、真实bash1次/13383ms、总17061ms，约16:14:07完成。完成后通过主屏NanoIM图标恢复同群，旧过程展开保持；唯一R13用户/唯一peer回复completed500500、14,054tokens、17.1s，输入空。
- 展开新过程1→bash completed13.4s→结果详情command/sleep12、13383ms、exit0/stdout500500直接可见，最终聊天回复与工具return分开展示；Back响应正常。本次没有重复用户或回复；API唯一性为辅助，不能冒充所有未来重放的完整计数。
- R12-01直接closure：同类多行Send已清空/正常running可见，Home后最终结果与控件恢复；CPU0.0%辅助，不替代UI。source改geometry为bottomVisible布尔，旧sample只支持布局事务忙，不能单由sample确认特定回调根因。

## J53 — geometry影响的长历史窄回归

进入既有R10 chat最新11/12可见，fresh语义click08→06→04→02，截图02全19行与03顶部，Latest按钮在历史处可见。显式Latest立即10完整19行及11/12完整可见、AX正文正常，Back响应。未新增history。新入站不抢滚动/unread1引用R10直接UI与服务辅助证据，本轮未重复入站；几何改动本轮只证明历史可达/Latest响应，无新增假想边界。

## 最新S1–S30合并表

| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | pass | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；R9 J45真实201上游已完成/客户端上传中时退出→实际旧连接中断→B身份正确/Chats空→A恢复无待发旧项。运行期未送达迟到主体；clear后transport迟到保护另有独立测试层证据，不混称UI已送达。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；R10历史02收新11不抢滚动且unread1已证；主动Latest停08/09未见11、native布局持续忙、AX无正文，但服务unread0，R11候选33b6e64f4同fixture02→Latest实际11完整可见且返回/重入响应，R10-01关闭；前台跳转见S27。 |
| S7 发送提及历史 | pass | R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；R11 J49全新群原生菜单选择e2e-peer，真实Gateway/LLM两轮均该Agent completed 42；原生配置空→578-R11保存节点确认，M2回复前显示「Agent 配置已更新」分界，再清空恢复并确认。目标回复已实证；R12 J50候选f77b34633既有M2与实时M3分界均在对应用户消息前，R11-01 closed。 |
| S8 不确定发送重连 | pass | R5 J24真实POST后端201但回执丢失，输入保留/发送锁定/明确核对；恢复手动核对后同message ID仅一条、输入清空，收件方GET两次COUNT1。 |
| S9 复制fork蒸馏 | inconclusive | R6 J27来源/执行Agent/global选择保持、生成可编辑正确草稿、不自动发送，R5-02/R6-01已关闭；长按复制/fork受现CUA动作能力限制，离线/跨Gateway限制分支未完成。 |
| S10 附件接收导出 | inconclusive | R2照片上传/比例预览；R8 TXT/PDF系统选择、取消、发送、QuickLook、Share→SaveFiles及实际bytes/hash闭环；主动图片粘贴仍缺（本轮明确禁用host paste）。 |
| S11 附件失败权限 | pass | R5撤权后清缓存/禁用/列表移除；R8新包12MiB真实server413保留/移除/禁发，9MiB正常上传发送，one-shot503逐项失败/原PDF保留/仅文字无附件/原文件重试，429倒计时禁提前重试与恢复均完成；R9 J43下载503可恢复，J44外部image接收端无IM凭据/保护GET不同端口302未follow，J45真实退出中断上传与账号隔离完成。跨origin结论限定本次本机不同端口，不扩大任意外站；迟到主体未在B送达。 |
| S12 过程统计结果 | inconclusive | R1/R2真实工具/审批/主子执行及指标、运行计时持续增长和最终耗时回看稳定已完成；R13 J52真实bash运行中→Home→完成后原生主屏返回同群，唯一请求/回复completed、工具return与最终聊天回复分开、结果详情与统计/Back正常；未知指标及所有子任务后台返回分支未完整实证。 |
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
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。R13运行中Home→结果完成后原生图标返回同群/展开状态保持、实际唯一消息与过程正常，后台补齐范围闭环。计划13因调度晚12秒未捕获3秒banner，点击跳转仍缺；不以API收到消息或源码推断出现。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |







## J54 — 前台banner一次计划（调度超窗）

Me前台fresh确认，root启动唯一peer→本次R10chat marker `578-R13-banner-13`，delay12秒，明确目标UTC08:18:40.3做一次freshAX动态click。此消息交接实际到达模型处理后clock已08:18:52，晚于3秒banner窗口；随后仅一次CUA取freshAX，未发现收到新消息按钮，未点猜测坐标，Me仍在、Chats badge4→5。因此只记录调度超窗，不能判banner不存在；不追加无目标探测消息。S27点击跳转继续inconclusive，后台补齐已有J52直接证据。

## 精确剩余资源与范围

S2真中文IME组合/软件键盘遮挡/VoiceOver，S9长按复制与fork、S10主动图片粘贴：现CUA不具可靠动作或本轮host paste明确禁止，需后置真实iPhone操作。S29/S30物理免费签名、Apple账号/协议/手机信任、Mini AltServer及拔线同网续签依用户明确安排后置，不以Simulator/archive替代。其它尚未完整分支按合并表保留，尤其S12未知指标/子任务后台顺序，S14失效关联/完整节点字段，S15历史分页，S21通道异常生命周期，S25分页/被停用机器资格，S27短banner点击；不重复已绿管理与媒体。
