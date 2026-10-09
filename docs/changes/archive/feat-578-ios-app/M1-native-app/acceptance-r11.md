# feat-578 — Latest修复窄复验与提醒续验 R11

> Validation snapshot:2505c9772→33b6e64f4，caller原地安装保数据/PID97409，390同UDID/base62009。独立change-reviewer，用户指定GPT-6.1 Sol；只写报告，无实现修改/commit。

## 裁决

**fail / R11-01 major：配置分界锚定顺序错误。** R10-01 closed；S6可见域/Latest闭环，整体提醒跳转仍依S27未验。S7有效mention已绿，但配置分界在M2用户消息后，与before_message_id=M2合同不一致。S12暂停等待此窄修复，S27计划banner未捕获，不误判不存在。

## J47 同fixtureLatest直接closure

freshAX与截图显示正常恢复nano聊天列表，进入578 R10 Read and Banner初始直接见10完整19行及11完整文本。沿已验证semantic bringIntoView用freshAX08→06→04→02，截图02完整/03顶部，Latest可见。点击Latest立即截图10全19行与11完整标记/正文，产品AX完整仍正常；Back回列表响应，再进入同chat响应正常，没有unknown或持续卡住。重入后早期01–03位置本轮只记现状，不据此追额外假想边界。没有新增history或改服务未读。

本轮同触发条件直接消除R10-01可见失败，caller只声明最小去显式动画；不由声明代替结果。CPU辅助尚待caller，不用CPU正常替代真实11可见。结合R10收新11保02/03+unread1实证和本轮Latest11可见/控件响应，S6可见域/显式最新旅程闭环；前轮偏好/静音及历史保持证据保留。

## J48 一次计划前台banner（时序不足）

本人真实退出目标聊天到Me tab，caller提前交接专用peer→同本次chat的生产者脚本。仅一次helper578-R11-banner-12/delay1秒/yield250ms启动后立即CUA freshAX动态找banner按钮并截图；未抓到收到新消息/marker按钮，截图Me仍在，Chats badge由4→5。未点击猜测坐标、未反复发探测消息。3秒UI窗口与工具调度无法据此证明不存在，S27仍inconclusive；实际消息唯一性/receipt待caller辅助。没有LLM/外部真人。

## 最新S1–S30合并表





本表取R6及本轮最新实证，替代旧状态用于交接。inconclusive仅代表列明剩余分支未完成，不等于产品已确认失败。已经完成的注册、群管理、节点离线、绑定异常、容量及策略失败不再留作欠账。
| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | pass | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；R9 J45真实201上游已完成/客户端上传中时退出→实际旧连接中断→B身份正确/Chats空→A恢复无待发旧项。运行期未送达迟到主体；clear后transport迟到保护另有独立测试层证据，不混称UI已送达。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；R10历史02收新11不抢滚动且unread1已证；主动Latest停08/09未见11、native布局持续忙、AX无正文，但服务unread0，R11候选33b6e64f4同fixture02→Latest实际11完整可见且返回/重入响应，R10-01关闭；前台跳转见S27。 |
| S7 发送提及历史 | fail | R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；R11 J49全新群原生菜单选择e2e-peer，真实Gateway/LLM两轮均该Agent completed 42；原生配置空→578-R11保存节点确认，M2回复前显示「Agent 配置已更新」分界，再清空恢复并确认。目标回复已实证；R11-01 major：分界实际在M2用户消息后，应按before_message_id锚在M2前，待窄修直接复验。 |
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





## J49 — 真实群提及与配置分界

- 创建全新 `578 R11 Mention`（`c_3e3xk4sp`），仅 nano 与本次 owned e2e/e2e-peer；没有打开旧 Agent 私聊。原生提及菜单选择 e2e-peer，M1 `578-R11-M1: Compute 17 + 25. Reply with the result only.` 显示明确目标，e2e-peer 从进行中到已完成，正文42、过程1、13,410 tokens、2.0s可见。
- caller辅助真实wire有 `target_id=u_3zfa6xso` 的mention；唯一Agent回复sender=e2e-peer、completed42，另一Agent没有回复。这是实际Gateway/LLM证据，非mock。
- 原生Agent配置展开自定义指令，空值改为 `578-R11`，保存显示「配置已由节点确认；聊天在下一轮采用新配置」。caller按实际字段custom_prompt核对精确7字符、version10，节点不变。其早期helper错误键读取不是产品失败。
- 同群M2 `578-R11-M2: Compute 19 + 23. Reply with the result only.`，UI在M2用户消息与e2e-peer回复之间显示「Agent 配置已更新」；回复已完成42、13,484 tokens、2.0s，旧M1仍可见。直接UI证明分界位置；仅凭数学结果相同不能独立证明prompt内容被采用，真实wire/版本另列辅助证据。
- 再进配置可见578-R11持久化，清空并保存后节点确认可见，恢复baseline待caller辅助核对。
- 输入时首次光标位于mention中间，错误草稿始终未发送，真实键盘全选重输并核实正确draft才Send；End未移到末尾。曾误用Simulator的旋转快捷键，恢复竖屏后继续，不把操作问题当产品缺陷。没有host paste、setValue后直接发送、secret或私人剪贴板。

## R11-01 — major / 配置分界迟到后落在新用户消息后

- Expected：分界的before_message_id指向M2用户消息，分界应在M1回复与M2用户消息之间，解释M2这一轮配置。caller的真实API顺序为M1用户、M1回复、boundary、M2用户、M2回复；当前Web契约按该锚显示。
- Actual：J49运行中与完成后截图都为M1用户、M1回复、M2用户、boundary、M2回复；恢复配置后仅一次fresh重入同群，截图与AX再次明确此顺序。不是缺少分界，而是新配置所属轮次标识位置错误。
- Evidence层级：两次直接原生截图/AX显示顺序；caller只读API提供before_message_id与服务器顺序；caller源分析NativeTimelineMerge迟到追加为辅助机制说明，不代替UI。
- Acceptance：S7 fail，真实mention目标和两轮实际Gateway/LLM回复保留pass子范围；先前临时S7 pass裁决已修正。未新增消息或群来重复追边界。
- Safe handoff：当前仍nano/578 R11 Mention，空composer、Send disabled，无上传或待提交表单，已交还caller安装窄修。原配置清空保存已获节点确认，后台baseline核对另待caller。
