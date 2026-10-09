# feat-578 — 缺失统计与真实后台返回 R17

> Snapshot：冻结107290abe / iPhone14 390 / native10990 / nano / Debug base62009。用户指定GPT-6.1 Sol的独立change-reviewer，只写报告，无实现修改/commit。

## 裁决

**本轮窄旅程pass，S12按实际覆盖范围关闭；整体完整验收仍inconclusive。** R16任务closure保留。未新增LLM执行、未重扫已绿Work/管理、未打开旧来源聊天或复制内容。

## J61 — 主usage缺失与部分usage字段

caller临时work_missing_usage只针对GET /im/v1/agents/578001/work（展示名578002）：删去最近主usage，并把真实轮usage只保留原output3330/1911。两轮、39/38真实过程、状态/时间、parent/child与聊天投递均未改。这是受控缺失metadata条件，不能称自然provider缺报；执行本身沿用R2/R14真实Gateway/LLM历史。控制只由caller管理。

原生Agent目录→578002详情（ID578001/全局模式）→Work，展开「最近已报告的主上下文」，实际显示「尚未报告；主、子执行统计分别展示。」。展开最新已完成轮turn_ce3de545467ef9fa及「本轮统计」，屏幕显示最近一次输入的上下文未报告、上下文窗口未报告、本轮累计输出3,330、累计缓存读取未报告、缓存统计输入总量未报告，耗时26.50s。主/子分别统计且不代表计费总量的说明可见。未出现将缺失值补为0、0%或上下文进度条的显示。通过原生semantic点击Disclosure带入视口，未猜测长页面滚动。

## J62 — 后台返回、调用完成与投递分界

同一最新真实轮仅一个「Compute 987+654、已完成」后台卡；点击展开后实际结果「987+654=1641」，并显示「后台结果不代表已向聊天发送。」。展开执行归属后可读agent/task id a89252049259b5fb5、task_type subagent、completed、result1641，output归属父sess_fd35bc3ed629df6d下子sess_410e171e8ee013af；1106ms/tool_use_count0属于该后台结果元数据，未把其当主执行统计。

此卡前后保留独立agent/task_graph等「调用完成」事件与时间。稍后send_message独立「调用完成」展开显示结果/ok/1055ms，以及「工具调用完成不代表子执行完成，也不代表已向聊天发送。」与「实际投递确认」和来源入口。没有点击来源聊天；最终主文本另列子执行1641与合成探索记录，未把后台返回卡、工具完成卡与最终文本当重复结果卡。结合R2主→子/普通成员隔离、R13后台返回最终聊天/唯一消息和R14过程分页证据，S12本次定义行为已覆盖；不宣称每一种子任务、未知模型统计均自然发生并通过。

## 安全交接与证据层级

已Back到578002 Agent详情，无草稿/上传/编辑表单，明确交还UI并请caller清除唯一work_missing_usage控制。caller在安全交还后清除唯一控制：真实62008/62009均200，latest_main_usage恢复原11 keys，两轮usage恢复全部8 keys，两个原owned节点online；私有600恢复receipt /tmp/nano-feat578-r17-restoration.json。此为辅助恢复证据，不能代替上面的直接UI。无source变动、无新增source测试、无commit；本轮真实条件由caller受控HTTP投影提供，而产品显示来自直接Simulator观察。

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
| S12 过程统计结果 | pass（本次真实执行与受控缺失统计） | R1/R2真实工具/审批/主子执行及指标、运行计时持续增长和最终耗时回看稳定已完成；R13 J52真实bash运行中→Home→完成后原生主屏返回同群，唯一请求/回复completed、工具return与最终聊天回复分开、结果详情与统计/Back正常；R17 J61缺失主usage与部分usage字段实际显示未报告/保留output3330；J62真实后台subagent completed1641、执行归属与调用完成/实际聊天投递分别展示。未知统计为受控metadata条件，不主张自然provider缺报；仅本次真实子执行返回，不扩大每种子任务。 |
| S13 审批确认 | pass | R2真实allow_once、Deny、暂停节点后等待确认/禁重复、恢复已处理及实际回复。 |
| S14 任务与回聊 | pass | R1/R2 DAG/探索/子层级/非成员私聊隔离/回聊引用，R3清除搜索无需Return已关闭；R15派生B→A与Prepare后续Check/Check前置Prepare、记录结果/change_note真实可见；R16候选107290abe直接根详情todo/result/已选A/reason/change_note、最深Check一次引用关闭sheet直接本群唯一草稿未发并清空，R15-01/02 closed；J60真实DELETE后重读B/A显示未关联且回聊入口消失，图/子图/依赖保持，无自动发送或执行。 |
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
| S25 公司管理 | pass | R1批准/停用/最后admin拒绝、R2普通成员限制及客户端被停用；R14 J55真实51名human成员原生首50→加载更多追加末页17、旧页02/35保持、最终无更多按钮；R15 J58指定普通owner原生确认停用→已停用，caller真实旧runtime WS101→403、旧browser nodes401、第三节点offline/owner suspended/epoch2/清runtime hash，前两owned节点仍online，机器资格撤销闭环。 |
| S26 策略容量 | pass | 前轮管理员全部策略保存/普通成员只读；R7服务与owner容量UI和实际API一致，精确单次503保32草稿→放弃回31，真实policy全字段仍baseline。 |
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。R13运行中Home→结果完成后原生图标返回同群/展开状态保持、实际唯一消息与过程正常，后台补齐范围闭环。计划13因调度晚12秒未捕获3秒banner，点击跳转仍缺；不以API收到消息或源码推断出现。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |
