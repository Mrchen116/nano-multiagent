# feat-578 — 原生产品功能续验 R7

> 2026-10-05 13:16起；沿用R6最新S1–S30表，仅补未验分支。实际native6155e1b86 / 390 Simulator，HEAD2ebafe27b，IM62008；服务由caller管理。用户授权继续后fresh AX确认可操作，未沿用旧索引。

## J29 群成员、人数变化与解散

R6未提交草稿恢复为群名称578 Group R7，成员仅nano与专用578review。创建成功进入同名群，无消息。详情添加专用iOS History Check后名单三人；点该成员移除出现“移除此成员？”明确确认，再确认后恢复两人。群任务、添加成员和解散仍存在，未因人数回到两人变私聊。

点击解散显示“解散此群聊？所有成员都会失去此群聊入口。”，确认后App清掉标题，显示无法访问，附件/输入/发送禁用。返回聊天列表无本群。截图`output/feat578/reviewer-r7/group-created.jpg`、`group-added-member.jpg`、`group-two-members-still-group.jpg`、`group-dissolve-confirm.jpg`、`group-dissolved-inaccessible.jpg`。本次仅可丢弃测试群，无外部消息/LLM。

结合R1创建/改名与R5真人双向，S5群管理欠缺已补齐；真人新建入口的独立实证仍需核实，暂不扩大整体pass。

## J30 第二节点配置开关

我的设备→wt-feat578-bind-check，启用中继和上报初始on/on。关为off/off保存显示“配置已保存；设备状态以实际心跳为准”，退出列表重开两值仍off。截图`node-switches-reopened-off.jpg`。随后恢复on/on并保存成功。没有把保存状态当作设备心跳状态；caller正准备独立第二Gateway真实离线/恢复，后续追加。

## 当前结论

进行中，保留R6合并状态；没有新增已确认产品缺陷。只写报告/不提交截图，无实现修改。

## J31 附件容量与策略失败草稿（进行中）

系统策略下半页真实显示整个服务已用0.1MiB/预留0/上限10240MiB；nano已用0.0/预留0/上限1024，ioshistory已用0.1/预留0/上限1024，并解释预留代表进行中上传。截图`attachment-owner-capacity.jpg`。已请求caller只读API辅助核对。保留天数31→32仅留原生草稿，保存启用，尚未提交；待精确失败夹具后再验证失败保留，不把客户端数值校验冒充网络提交失败。

J29补充：新建聊天保持群开关off，搜索578review准确筛到真人；选中后关闭搜索仍保留选择，点击创建进入标题578review的空真人会话，composer/附件可操作且空发送禁用，无自动消息。截图`human-direct-created.jpg`。结合既有Agent私聊/群改名证据，**S5 pass**。

## J32 绑定拒绝与过期

使用caller本次专用的两条0600链接，仅CUA内存读入/typeText SecureField，未打印链接或截图token、变量随后清除。有效请求显示当前Test User/@nano、设备iOS R7 decline / wt-feat578-r7-decline、尚无Agent。点拒绝再明确确认，结果“已拒绝绑定，设备归属未改变”。点绑定另一台设备输入已过期请求，检查后SecureField清空/检查禁用，明确提示链接无效、已取消或已过期，请在设备重新发起。

截图`binding-declined.jpg`、`binding-expired.jpg`。caller过期夹具仅对本次新operation调过期时间，先走真实start/prove/inspect，未改现有节点。结合R2双端接受确认，**S22 pass**。

J31辅助核对：caller实际API service used124584/reserved0/limit10737418240 bytes，nano22131/0/1073741824，ioshistory102453/0/1073741824，与UI四舍五入MiB一致。策略32草稿已主动放弃，恢复31/保存禁用，待离线/绑定结束后才切单故障proxy。

## J33 非目录路径与真实离线节点

主节点选择自定义workspace为caller仅本次创建的普通空文件`/private/tmp/nano-feat578-ios-runtime/.gateway-workspace/ios-invalid-path-r7`，唯一ID ios-invalid-path-r7、名578700。提交后明确`Workspace target exists but is not a directory.`，留在可恢复表单；随后取消并确认放弃，没有创建。截图`create-path-not-directory.jpg`。英文错误为minor语言覆盖缺口，不妨碍理解路径失败原因；未改用户目录。

caller清理本次绑定fixture遗留重复进程/KeepAlive后，真实GET第二节点offline、主节点online才交接。原生Agent列表、详情及我的设备均显示第二节点离线。创建选第二节点，输入测试ID/名后，默认路径等待设备报告，模型和备用禁用，说明“节点未连接或未能返回能力数据”，预览/创建禁用，随后放弃未提交草稿。截图`offline-create-disabled.jpg`、`node-offline.jpg`。

第二Agent配置仍可读既有名称/description/工具数/心跳off，能力目录明确不可用、保留已有配置、重新连接再改，并提供重读；没有虚构在线能力选项。Cron页明确“节点离线；任务空列表不能代表设备没有任务。”；点击HEARTBEAT.md明确“节点离线，无法读取”。截图`offline-capability-preserve.jpg`、`offline-cron-distinguishes-empty.jpg`、`offline-heartbeat-unavailable.jpg`。没有在离线状态提交配置/创建/删除。已请求caller恢复第二节点，待原生online验证。

S16路径失败/离线分支已补，仍缺无设备创建；S17不可用能力说明分支已补；S19在线/离线/空数据区别已有实证。不能把本次没有真实记录的第二Agent Skills空表误认作实时节点读取失败。

J30/J33恢复闭环：caller将第二节点恢复为本次专属单实例，实际API两节点online。原生退出再进入我的设备，两条均在线，截图`node-restored-online.jpg`。**S23 pass**，不把之前仅SIGSTOP、仍有fixture重复进程的阶段算离线证据。

J31完成：退出nano→原生连接地址62009→nano重新登录，在同策略31→32留草稿。caller仅arm一次匹配PATCH retention32返回503/不转发，其余HTTP/WS正常。点保存一次，页面自动把“服务暂时不可用，请稍后重试。”显示在顶部，32及其它字段保留，保存仍可用。截图`policy-503-draft-retained.jpg`。没有第二次提交，点放弃修改后31/保存禁用；等待caller全字段baseline核对。此夹具只测失败反馈/保草稿，不能用于跨origin凭据安全证据。

J31后端辅助：caller确认真实policy所有字段仍等于baseline、retention31，单次503未转发。容量显示与真实数据一致、保存失败保留/放弃恢复完成；结合R1全字段保存和R2普通成员只读，**S26 pass**。

## J34 登录限流与临时不可用（进行中）

仍在62009窄proxy，退出nano后填写正确既有凭据等待arm。caller单次返回与IM限流同JSON detail=`temporarily rate limited`/retry_after20及Retry-After20，不转发、不记录password。点登录一次后按钮disabled，AX显示请稍后重试21s、紧接截图为20s，字段保留且出现恢复/清除本机登录入口；没有误报密码错误。截图`login-429-cooldown.jpg`。正文英文保留为minor语言缺口；中文倒计时与禁用语义清楚。等待独立503后继续。

J34续：倒计时结束后登录恢复可用，caller另arm单次503，无Retry-After/不转发。点登录一次显示`Service temporarily unavailable`，正确凭据保留、按钮可再次使用，没有密码错误。截图`login-503-retryable.jpg`。下一次正常登录成功进入原有聊天。此两项英文错误由caller准备窄修auth本地化；本报告尚未将新包写为通过。

## J35 原生注册与待批准（进行中）

从proxy正常退出后原生连接设置改回62008。新建本次专用账号iosr7new，随机测试密码仅CUA内存，不输出，显示名IOS R7 New；真实点击创建后进入仅本人名称、“账号正在等待管理员批准”、刷新状态与退出，没有四入口或nano旧公司缓存。截图`registration-pending-only-self.jpg`。已请求caller只批准为普通成员，随后由原生刷新验证准入与无设备边界。

J35续：caller只批准iosr7new为普通成员（非admin、node_count0）；原生点刷新立即进入四入口，聊天为空，无nano旧数据。截图`registration-approved-empty-chats.jpg`。进入新建Agent显示“没有已绑定设备。请先在‘我的’绑定设备”，设备菜单仅选择设备无其他人的节点；默认路径等待报告，模型/预览/创建均禁用。截图`create-no-owned-device.jpg`。没有填创建草稿，取消返回。结合R1/R5/J33，**S16 pass**。

13:46已在新普通成员Agent列表安全断点交还caller安装auth本地化窄修，新包尚未验；无在途写入。S3注册/待批准/批准刷新已完成，安装保留有效session的恢复将补验。本段后台服务与代理均由caller管理，绑定token内存清除，注册测试密码仅临时CUA变量用于必要回登。

J35恢复完成：caller原地安装b8f9a9bc6 / PID85072、未清数据。启动无需再次登录，聊天仍为空，我的显示IOS R7 New/@iosr7new/有效成员。截图`valid-member-session-restored.jpg`。结合本轮注册/待批准/批准与既有停用状态证据，**S3 pass**。退出后注册临时密码变量清除。

## J36 auth中文窄复验（进行中）

本段仅新native b8f9a9bc6，修订范围caller声明为429/503错误本地化；实际结果以下追加，不能以声明替代验收。已切62009、nano字段填写，尚未提交，等待一次429。

J36完成：b8f9实际429显示“请求过于频繁，请稍后重试。”、20s倒计时和登录禁用；结束后单次503显示“服务暂时不可用，请稍后重试。”，凭据保留、可再登录。随后真实正常登录成功聊天列表。截图`login-429-zh-b8f9.jpg`、`login-503-zh-b8f9.jpg`；**J34发现的auth英文minor关闭**。本段没有重跑已完成路径。

## J37 合成文本附件与导出中断

caller只为本次390安装独立可卸载的578 Test Files夹具容器（没有改NanoIM配置/启动夹具UI），Files我的iPhone出现该目录，只有本次83byte TXT、2页2038byte PDF和16MiB TXT。真实文件选择器可打开，先前空目录时取消后没有附件/消息、发送禁用。

在578review测试真人会话，从Files选中83byte `578-synthetic-r7.txt`→打开，原生待发区出现文件名与移除，发送可用。填写`578710 file acceptance`，点击发送，Test User/已完成、文字与文件顺序正确，待发附件与输入清空。点击已发文件进入系统Quick Look，正确显示三行合成文本和标记`578-TXT-R7`，截图`txt-native-preview.jpg`。

主动打开分享面板，实际可见Copy/Print/保存到“文件”。点击保存到文件这一调用于13:55明确返回`The Mac is locked and automatic unlock could not unlock it.`，立即停止，未再次UI尝试。该调用是否已发送点击不能证明，当前可能仍分享面板或保存Sheet；**未把文件导出宣称成功**，PDF/16MiB尚未选择，没有进行本轮上传失败/冷却故障。

caller在源码核对发现固定10MiB与当前15MiB策略不一致、上传失败逐项恢复不足，正在按原S11补实现。这是caller提供的实现发现，不是本轮已经操作16MiB/故障后的直接UI观察；待新包定向实证，不能把计划写为已修或通过。

## 本轮当前裁决与问题

**inconclusive / 全功能门禁未收口**。新增加通过：S3、S5、S16、S17、S19、S22、S23、S26；保留原有通过与36幅视觉证据。S17以完整配置逐项保存/重开、能力不可用保留说明、真实稳定提示预览和作用域说明构成产品旅程通过，不要求对预览逐字节比对；未将此扩大为全文与服务器字节一致的证明。S19结合R2真实Skills来源/用量/会话标识展开、R3指定Cron确认删除与HEARTBEAT.md、R5心跳读回、本轮离线区别完成。

本轮没有新直接观察的major。J34两条auth英文已窄复验关闭；非法workspace错误正文英文为minor，R5详情旧名称/R4通道satisfied矛盾/P6节点留白minor沿用，未为这些扩大修复循环。锁屏是明确环境阻碍，不能据此判产品失败。S11 caller发现的实现缺口待独立UI验收。

## 最新 S1–S30 合并表

本表取R6及本轮最新实证，替代旧状态用于交接。inconclusive仅代表列明剩余分支未完成，不等于产品已确认失败。已经完成的注册、群管理、节点离线、绑定异常、容量及策略失败不再留作欠账。
| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | inconclusive | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；退出后迟到附件响应隔离仍缺。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；精确可见域已读推进仍缺；前台跳转见S27。 |
| S7 发送提及历史 | inconclusive | R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；有效群提及及配置分界线未完整实证。 |
| S8 不确定发送重连 | pass | R5 J24真实POST后端201但回执丢失，输入保留/发送锁定/明确核对；恢复手动核对后同message ID仅一条、输入清空，收件方GET两次COUNT1。 |
| S9 复制fork蒸馏 | inconclusive | R6 J27来源/执行Agent/global选择保持、生成可编辑正确草稿、不自动发送，R5-02/R6-01已关闭；长按复制/fork受现CUA动作能力限制，离线/跨Gateway限制分支未完成。 |
| S10 附件接收导出 | inconclusive | R2照片上传/比例预览，R7真实Files选择TXT/文字+文件发送/Quick Look内容与分享入口完成；保存到Files时Mac锁屏，导出结果/PDF/主动粘贴仍缺。 |
| S11 附件失败权限 | inconclusive | R5打开图片撤权后清缓存/禁用/列表移除已通过；本轮16MiB未操作即锁屏。caller发现限额/逐项失败恢复实现缺口并在修，待新包真实超限/上传失败/冷却/仅文字/下载失败验证；外站凭据边界亦缺产品实证。 |
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

## 安全交接与下一步

实际最后受验native b8f9a9bc6 / PID85072，390 Simulator，nano通过本次62009代理登录；原IM62008/主Gateway与第二节点已恢复online，caller报告无暂停进程。当前578review聊天的已发送TXT原生分享/保存Sheet处，Mac锁屏后未重试。仅发送本次合成TXT及测试说明，无外部平台消息、无本轮LLM调用；注册iosr7new仅普通成员，群578 Group R7已解散，测试绑定两operation由caller清理，临时秘密变量均清除。

先待用户解锁后fresh AX确认Sheet状态，不沿用旧index；完成正常导出/PDF，再按caller新包补16MiB/逐项失败恢复窄验。文件夹具App与proxy由caller清理；保留到后续所需实证完成，不能当作产品发布依赖。手机/签名/Mini/VoiceOver等后置不变。报告未commit，截图output下不提交。UI已交还caller，在解锁前不再操作。
