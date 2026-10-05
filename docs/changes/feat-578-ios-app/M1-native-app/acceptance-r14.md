# feat-578 — 成员及真实Work分页窄验收 R14

> Snapshot：5de8ffdb4 / 同390 / nano / base62009 / native4396。独立change-reviewer，用户指定GPT-6.1 Sol；只写报告，无实现修改或commit。R13挂起/长历史closure、R12分界closure保留。

## 裁决

**inconclusive / 已绿范围不重跑。** S25成员分页与S15受控分页条件下真实历史/过程追加通过；手动刷新触发未独立证明，精确限度保留。

## J55 — 公司成员分页

原生Me→公司成员，首屏Paging44/31/14及待批准/0设备/0Agent可见；原生Form secondary ScrollDown至第一页末，Paging02/35与旧MemberCheck仍可见，加载更多与刷新成员可操作。点击加载更多直接追加Paging17，旧02/35保持；下一次ScrollDown到末页仅刷新成员，无更多按钮。没有点击批准/停用。

caller真实API辅助51名human，50+1无交集、最后cursor=nil。额外45隔离测试成员中5为实际HTTP注册，其余40用既有UserRepository创建pending数据夹具；没有禁用既有限流，不把repository夹具称注册入口证据。当前分页结果真实读API，不主张生产自然大公司或被停用owner机器资格已验。

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
| S15 Work主子历史 | pass（受控分页条件） | R2真实主执行→子执行1641及统计、普通成员可读但不能配置/回私聊；R14 J56同真实global Agent两轮按新→旧加载、更早最终游标nil；真实过程3→39追加后初始事件保留、时间顺序与主/子归属可辨、最后事件详情可展开，无更多过程。限定减小分页条件，未主张自然100+；drag后2轮保持，caller该段真实refresh重读首＋旧页辅助，不能区分manual与3秒自动触发。 |
| S16 节点创建路径 | pass | R1/R5正常创建/模式双节点保持/目录确认/唯一性/重复ID/草稿保护；R7普通空文件路径被拒、真实离线说明并禁创建、新普通成员无设备引导且不能用他人节点，全部创建欠缺已补。 |
| S17 完整配置 | pass | R5各字段保存重开、备用顺序、工具/特性、显式空Skills与默认发现、只读归属和稳定预览；R7离线能力目录明确不可用/保留既有配置/提供重读，不虚构在线模型。预览不主张逐字节比对。 |
| S18 冲突pending权限 | pass | R1/R2非owner/冲突，R3暂停后pending→重读确认；R5 J19真实IM版本409保草稿/重读服务器值/选择继续/保存确认且反馈自动入视口，R4-01关闭。 |
| S19 Skills心跳Cron | pass | R2真实Skill来源/用量/会话toolcall标识展开，R3指定Cron确认删除/文档，R5心跳开关间隔时段保存重开；R7 Cron离线不等于空任务、HEARTBEAT无法读取说明补齐离线区别。 |
| S20 通道凭据 | pass（本轮凭据旅程） | R4专用飞书新增、已保存Secret不可读、保留、同现有Secret替换、改AppID强制替换/空值禁止提交均真实完成；不冒充平台换密钥。 |
| S21 通道生命周期 | inconclusive | R4实际connected→停用applied/实际停用→确认删除空列表完成；离线/停止失败重试、重连、受限/未知权限以及聊天历史保留分支未完成。 |
| S22 绑定 | pass | R2双端接受→等待→设备确认→完成；R7当前账号/测试设备检查、明确拒绝后归属不变、过期清秘密输入并提示重新发起。caller确认两测试operation未造node。 |
| S23 节点管理 | pass | 前轮别名/节点创建/非owner边界；R7中继与上报off保存重开→恢复on，真实第二节点offline与主online并存→恢复online，未动生产。 |
| S24 个人资料语言 | pass | R1/R2中英与中文错误修复，R6 J28显示名及默认设备保存退出重开保持，再恢复原值；只读身份字段可见。 |
| S25 公司管理 | inconclusive | R1批准/停用/最后admin拒绝、R2普通成员限制及客户端被停用；R14 J55真实51名human成员原生首50→加载更多追加末页17、旧页02/35保持、最终无更多按钮；被停用成员名下机器资格仍未完整实证。 |
| S26 策略容量 | pass | 前轮管理员全部策略保存/普通成员只读；R7服务与owner容量UI和实际API一致，精确单次503保32草稿→放弃回31，真实policy全字段仍baseline。 |
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。R13运行中Home→结果完成后原生图标返回同群/展开状态保持、实际唯一消息与过程正常，后台补齐范围闭环。计划13因调度晚12秒未捕获3秒banner，点击跳转仍缺；不以API收到消息或源码推断出现。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |








## J56 — 真实Work历史与过程分页

- 身份澄清：搜索578001实际匹配当前展示名578002；初次不确定目录缺失只是名称与ID未对齐。原生详情直接可见display578002/id578001/global实验，Work执行归属Agent578001与主节点在线，未访问旧私人e2e聊天。
- caller受控proxy仅本Agent Work路径给真实上游turns加合法limit1；首轮02:10已完成，点击更早轮次追加旧18:08已完成，最新在前、原首轮保持，最终无更早按钮。不是mock执行，也不是自然100+历史证据。
- 展开最新真实turn_ce3de545467ef9fa/model deepseek-v4-flash/human触发，初始runtime_config_applied、inbox时间/工具完成、真实3项；caller仅缩小嵌入过程为前3并保留真实游标74。点击加载更多过程调用真实items(after_seq74)，直接AX追加后续36项、初始3仍保留。时间从02:10:01.964895顺序至02:11:06.744131，主请求、agent调用、子返回、task_graph、send_message、final/run_status/skills等可辨，末尾不再更多过程。
- 实际展开self_evolution_review详情，completed=true、seq141、turn_ce3…/session主fd35…对应本轮可见；关联执行Compute987+654/child410…与parentfd35…均真实可见，R2已验main→child1641和普通成员边界引用保留，不为本轮重发LLM。
- 长展开过程容器未提供Scroll动作，wheel未移动；语义文本click曾带来额外展开及关联执行导航，Back响应正常，未由这些不可靠动作声称已刷新。安全Back详情→重入Work会重新第一页，不当成同页保页。
- 重入后仅再点一次更早，fresh页首截图两轮可见；基于当前截图真实drag[393,425]→[393,1150]一次，下次AX/截图仍两轮/无更多按钮，未捕捉spinner。产品原生List.refreshable和3秒前台刷新为caller source辅助，若网络请求不可区分，不将此动作强称独立manual触发证据。
- 已安全返回Agent详情，通知caller清除唯一work_paging并核对正常API；未改proxy/source/配置，没有secret、host paste或commit。

### 清理与刷新辅助闭环

caller已清除唯一work_paging；直连62008与62009正常Work均2轮、items39/38、cursor=nil。受控请求日志该段存在首limit1→before_turn=turn_ce3de545467ef9fa&limit1重读首/旧页重复，最近写UTC08:46:40，支持真实refresh发生且已有页面未丢；不能区分手动drag与3秒前台自动刷新，没有独立spinner证据。S15按本次受控分页真实历史/过程与刷新保持范围pass，不扩展自然100+或手动触发独立证明。UI已交root，未留下control或待提交动作。
