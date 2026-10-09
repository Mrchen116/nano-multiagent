# feat-578 — 原生下载与账号隔离窄验 R9

> Validation snapshot: native2505c9772，沿用R8媒体已完成范围。本轮仅S11下载失败/受控off-origin凭据边界、S4在途上传后退出切换。独立产品reviewer，只改报告、不改实现、不commit。

## 当前裁决

**inconclusive / 整体产品门禁未收口。** 本轮窄旅程完成，S4与S11产品路径合并通过；其它继承未验项保留。新增直接原生产品缺陷0。最终nano/578review空composer、发送禁用，无在途写入。

## 判据与证据边界

spec.md S4/S11及current docs/specs/IM/conversations-messages.md的受保护附件契约：下载失败应明确可恢复；退出清除旧账号页面/附件/草稿，迟到响应不能在新账号重新展示；外部origin不接收IM登录凭据。每条以真实原生旅程和对应本机受控请求收据分别记录，不以源码/单测或HTTP200替代可见结果。

## 继承 S1–S30 状态



本表取R6及本轮最新实证，替代旧状态用于交接。inconclusive仅代表列明剩余分支未完成，不等于产品已确认失败。已经完成的注册、群管理、节点离线、绑定异常、容量及策略失败不再留作欠账。
| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | pass | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；R9 J45真实201上游已完成/客户端上传中时退出→实际旧连接中断→B身份正确/Chats空→A恢复无待发旧项。运行期未送达迟到主体；clear后transport迟到保护另有独立测试层证据，不混称UI已送达。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；精确可见域已读推进仍缺；前台跳转见S27。 |
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



## J43 未缓存附件下载失败与同按钮恢复

2026-10-05 14:56，freshAX定位578804 cooldown recovered中此前未打开的52bytes TXT，READY后caller只匹配该保护资源GET一次503。点击文件按钮后错误就近显示在原消息下方，红色 `Attachment temporarily unavailable. Please retry.`；留在聊天，没有打开QuickLook或伪造内容，文件按钮仍可操作。再次点击同按钮（未重选/未重新发送）正常下载，QuickLook实际显示 `Synthetic upload cooldown fixture: 578-COOLDOWN-R8.`。关闭后错误消失且分享按钮可见，空composer/发送禁用。

caller只读receipt确认目标GET一次503未转发、incoming_authorization_present=true，control已消费自动解除。英文detail来自本次注入文案，仅记录实际可见内容，不据此单独判新本地化缺陷。下载失败可恢复分支完成；跨origin及迟到响应隔离待后续精准夹具。

## J44 外部合成图片与off-origin保护附件redirect

caller真实API在本次真人chat新增578905 external image probe，带独立loopback端口62010的64×48绿黄棋盘PNG；无Agent/LLM。原生live消息内图片正确显示，点击后原生图片Sheet完整棋盘、4:3比例，完成关闭。receiver只记录布尔值，对/fixture.png唯一1hit，Authorization/Cookie/credentialQuery均false。

另一未缓存的46bytes retry TXT保护GET在READY后精确单次302→同独立端口/redirect-probe.png。点击后原消息红色found（注入body），仍在聊天，无QuickLook/无外域PNG充当附件；同按钮正常重试后QuickLook原TXT正确578-RETRY-R8，关闭错误消失/分享可用。caller receipt确认保护GET Authorization=true、302未转发上游，receiver /redirect-probe.png为0hits。

证据仅限定本次不同loopback端口origin及此次redirect：外部原生图片读取未带IM凭据，受保护下载此次未follow off-origin重定向。不扩大为所有外站/任意协议安全证明。S11下载失败/外部凭据分支与R5撤权及R8上传失败合并已有直接证据；账号迟到响应隔离仍待J45。

## J45 真实在途上传、退出中断及账号隔离

只用本次47bytes `578-upload-late-r9.txt` 与真人chat，正确Files picker READY后caller匹配单次POST真实转发，捕获上游201但延迟真实JSON主体；header与合法JSON空白保活仅harness，不修改App。原生确实显示文件名/spinner上传中，附件与普通发送禁用。caller确认真实上游201/47bytes、response_captured=true、released=false后，原生Back→Me明确Test User/@nano→退出明确确认（本地session与待发清除）→登录页空字段。

使用600私有测试凭据文件只读到CUA内存/真实keyboard输入SecureField，无打印/paste/密码截图，用后变量null。B `iosr9late`真实登录后Chats No conversations、Me iOS Late Upload R9/@iosr9late/Active，无nano聊天/附件/错误/身份回退。通知caller释放时caller如实发现旧连接已closed、未timeout且真实201主体从未released；没有把未送达宣称late delivery。caller另层源码观察signOut明确cancel tracked HTTP，记录07:04:52.299UTC connection_closed；这说明与产品退出中断机制一致，不由reviewer读实现定位。

B随后再检查身份与Chats仍正确空；退出B、正常恢复nano，578review历史仍到external probe，输入为空/Send disabled，无late文件待发/失败/spinner。退出A前最后一次聊天截图为上传中；离开后Me/确认/登录路径没有看到成功或失败回填。UI单独不能判定cancel原因；后台真实连接关闭收据补充运行层事实。clear后不可取消transport迟到不回填属于已有独立26项测试层证据，不冒充本轮送达主体。无需强造不cancel客户端重复。

S4的产品要求是退出立即清除旧内容、B仅见自身资格数据，实际正常机制通过中断旧请求达到此结果；结合前轮登录429/503/断线恢复/停用切换，判S4 pass，明确上述运行期送达限度。S11结合R5撤权、R8超限/逐项失败/仅文字/重试/冷却与本轮下载/凭据，判pass；不主张任意网络/任意外站覆盖。

## Reference / 同步 / 安全交接

保留acceptance-visual-r3 scoped 390/430普通与大字体36图；本轮native2505c9772/390/iOS26.4真实CUA截图和AX输出对应失败、恢复、外部PNG、B空聊天/身份与A无待发，系统picker坐标仅依fresh截图。未改或提交截图缓存。SPEC.md与docs/specs/原生产品文档最终归并仍由caller收口，AGENTS/CLAUDE及文档规范无需本轮改变；本reviewer只报告。

报告仅本文件无commit，截图/秘密/配置均未提交。未触碰iPhone Mirroring/生产/外部人，没有Agent或LLM。proxy/receiver/账户/Files夹具均由caller管理。当前控制无fault/hold，nano在578review空composer/Send disabled，UI可交还。剩余S2/S6/S7/S9/S12/S14/S15/S21/S25/S27及用户后置S29/S30继续保留inconclusive，不因S4/S11完成宣布全功能ready。
