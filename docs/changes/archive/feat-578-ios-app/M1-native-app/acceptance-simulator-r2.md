# feat-578 — 模拟器辅助操作与提醒窄复验 R2

> Mode targeted；change-reviewer；产品`executed_base = validated_at = aa7876fa9ab443b4cf12d1a4119fd2abc7d428d3`。390 iPhone14/iOS26.4 Simulator、原隔离IM62008/nano。2026-10-06 22:40–22:49 +08:00实际UI观察，随后停止UI并保存报告。报告时共享HEAD 4ce7a3c0f仅后续文档；共享后续HEAD可含文档，不冒称整个提交树全量已验。
> 实际安装`ADC97CD1-1079-47FD-AF3C-C4455211E8E4/NanoIM.app`；独立核binary SHA256 `8b099d40c54142e4b8ec097896cf8af15e8bf392c899e0db24030a910be489ce`、debug.dylib `673b10a07f71bad0580a3b4b49e728a0f25b719690247e249b57574a94e4be3a`。未重建/重装、启停服务、操作其它模拟器或物理手机。R1旧失败及未验事实原样保留。

## Verdict

**fail：模拟器仍未完整测完。** 本轮正文Copy辅助动作、准确clipboard及反馈实际pass；fork、离线整理新说明、修复后来源提醒尚未实际复验。没有新增产品finding；操作器窗口动作阻挡不能作为产品Back失败。R1含混英文回执与提醒未捕获事实不改写，caller修正/静态审查/35项测试不替代这三项新产品结果。

## 当前断点

当前c_zia690ag已知阅读页、统计展开、Send禁用、无消息draft/附件/表单/sheet。Copy通过后坐标返回报`noWindowsAvailable`。caller使用已暴露window Raise恢复截图，本reviewer随后实际Raise截图也成功；但fresh截图之后一次Back坐标仍报同样错误。再按caller完整顺序fresh getApp→AX已暴露window0 Raise→fresh截图→Back一次，仍被操作器入口拒绝。因此准确结果是截图可恢复、坐标未恢复，不是Mac锁屏或产品导航失败；未重启/重装/绕过系统认证，也未反复长按或猜动作。

caller随后仅一次独立环境诊断：其simCheck578绑定fresh截图成功，可见Back坐标[120,284]仍抛-10005 `noWindowsAvailable`，AX无变化、未触发导航。该caller辅助环境事实支持不是单个reviewer绑定问题，不替代产品旅程；双方停止重复UI。

已通知caller；尚未fork、生成蒸馏或发本轮新提醒marker。没有创建待发草稿/附件，不能把此阅读断点称已回Chats。后续旅程不能由动作声明/API成功/单测/源码代替。

## 实际产品旅程

- J-SIM2-01 短正文：Chats→本次受控群c_zia690ag；实际AX显示消息正文“复制正文”secondary动作后才执行。对R2唯一请求实际performSecondaryAction→截图出现“已复制正文”带勾反馈。只读Simulator clipboard完整等于`@e2e-peer 578 UX R2: Compute 31+11. Reply only the number; do not use tools.`，未host paste，未重新发送。
- J-SIM2-02 长正文：对同群明确API准备的阅读素材执行该动作。只读clipboard为可读内容，保留标题、文字A/B/C顺序、@Test User、具名链接及URL、两列表项、制表符分隔表格和`let result = 42`代码；不把Markdown符号或图片像素当正文，未截为当前可见段。画面Copy反馈已可见，clipboard确实变为该长内容。R3代码区域独立Copy精确证据retained。
- J-SIM2-03 子控件：仍实际点击42回复的13,287 tokens，展开本轮输出2、总用量13,287、上下文13,285/262,144、缓存7,296(55%)、上下文5%。新父层secondary动作没有阻挡该统计子控件。本群category group的完成回复AX只有Copy，没有fork；caller确认原条件本来不对group提供fork，不判漏。

已知可fork direct c_xuh5cshe/iOS approval acceptance具两条真实completed回复，caller建议第一条ea433beb8bd7439ba470c7d705a23aad/kernel msg_0b942daf456cb956验证截至目标、不复制后续轮次。尚未进入该会话，不能把该前置信息写成fork已操作。

## 受影响范围状态

| 范围 / 来源 | 实际结果 | 边界 |
|---|---|---|
| S2/S9 Copy正文与反馈，P1/P6 | pass该子范围 | J01/J02真实clipboard+反馈；R1真正中文软件组合retained，VoiceOver设备无入口不重试 |
| S9 fork辅助动作/取消/确认历史 | inconclusive | current工具阻挡尚未进入eligible direct；不以声明动作判pass |
| S12 原过程/统计子控件 | pass统计子范围 | J03实际展开，原过程其它范围retained未重跑 |
| S9 离线整理明确原因 | inconclusive待复验 | R1英文含混回执历史保留，本轮尚未进入c_wdnb5vv5 |
| S9 online整理草稿 | retained旧pass，本轮邻接未验 | 未重复发送/执行Skill；未生成本轮draft |
| S6/S27 真人message.sent来源提醒 | inconclusive待复验 | 本轮尚无marker；不重复旧成功marker，不把R1协议辅助诊断当本版UI结果 |

当前没有新增产品finding，只有操作器阻挡；不把窗口不可用判产品Back失败。S10设备内图片paste/VoiceOver不再重复无效尝试；S13真实pending前置保留未验，不改权限规则；S21外部、S29/S30真机按用户安排deferred。

## 最新合并Scenario矩阵

来源均spec.md对应S行；retained来自模拟器R1、R3/R4/R20，注明没有重跑。本轮只关闭正文Copy与统计子范围。S2 VoiceOver、S9 fork/离线新说明、S6/S27新提醒、S10主动图片paste及S13 Work默认展开仍未完成；S21外部、S29/S30真机分别deferred。

| Scenario | 最新结果 | 本轮增量 / 精确保留边界 |
|---|---|---|
| S1 四入口/返回 | pass | retained；本轮坐标操作器拒绝不冒称产品返回成功或失败 |
| S2 输入/辅助 | inconclusive | R1真实中文组合/两行安全区pass retained；本轮J-SIM2-01/02正文复制及反馈pass，R3代码Copy retained；VoiceOver模拟设备无入口仍未证 |
| S3 登录/注册恢复 | pass | retained；不重复登录/注册 |
| S4 暂时失败/切换 | pass | retained；无本轮新故障注入 |
| S5 找人/群管理 | pass | retained；本轮无新增会话或数据删除 |
| S6 偏好/已读 | inconclusive | R3实际>60离屏77秒→Latest/cursor闭环及R1来源列表阅读retained；修复后banner尚无本轮marker/UI证据 |
| S7 发送/提及/历史 | pass | R2直接@/slash及唯一42回复、R3分页/身份、R20配置分界、R1真实中文组合retained；本轮未发送 |
| S8 不确定发送/重连 | pass | retained；422控制fixture请求不冒充UI不确定发送分支 |
| S9 Copy/fork/蒸馏 | inconclusive | 正文Copy/反馈本轮J01/02 pass；R3代码clipboard、R6正常草稿、R1跨Gateway拒绝 retained；fork尚未进入eligible direct，离线新说明未复验 |
| S10 附件接收/导出 | inconclusive | R3 ready图片/R20导出retained；主动设备内图片paste工具缺口仍未证，不重复无效尝试 |
| S11 失败附件/权限 | pass | retained；本轮无上传/发送 |
| S12 过程/统计 | pass | retained；本轮J03实际统计子控件展开pass，未扩大其它过程/指标 |
| S13 审批提交确认 | inconclusive | R20 allow_once/Deny/等待/恢复retained；R1真实执行没有pending，Work默认展开仍缺前置，不修改规则 |
| S14 任务/回聊 | pass | R3语义/祖先及R4 N8 closure retained |
| S15 Work主子历史 | pass | R4时间显示/R20受控分页与R1真实completed retained |
| S16 节点创建 | pass | retained；无本轮Agent创建 |
| S17 完整配置 | pass | retained；不改/保存权限规则、Agent配置 |
| S18 冲突pending配置权限 | pass | retained；不替代S13真实Work人工卡 |
| S19 Skills/心跳/Cron | pass | retained；不删/改计划 |
| S20 通道凭据 | pass | retained；未输入或保存secret，无外部换密钥 |
| S21 通道生命周期 | inconclusive / external deferred | 自然stop异常重试、受限/未知权限、真实平台shadow缺口retained；不因模拟器任务操作真实飞书 |
| S22 绑定 | pass | retained；无本轮新绑定/恢复旧节点 |
| S23 节点管理 | pass | retained；本轮未启停节点或恢复离线节点 |
| S24 账号/语言 | pass | retained；本轮不改产品账号/语言或设备键盘 |
| S25 公司管理 | pass | retained；不注册/停用/审批真实他人 |
| S26 策略容量 | pass | retained；不保存策略 |
| S27 提醒 | inconclusive | R1合法唯一源投递/列表阅读retained；aa修复后新marker尚未POST，banner图/点击未证 |
| S28 后台边界说明 | pass | retained；不宣称保证后台推送 |
| S29 真机首次安装 | inconclusive / user-deferred | 用户要求先跳过真机；本reviewer未触物理手机 |
| S30 同网/自然到期恢复 | inconclusive / user-deferred | 用户要求先跳过真机；不由模拟器/构建替代拔线续签及自然到期 |

## Reference Artifacts Reviewed

spec.md S2/S9/S12/S27，design.md P1/P3/P5/P6，[模拟器R1](acceptance-simulator-r1.md)及[R4](acceptance-ux-r4.md)。J01–03实际AX/截图/clipboard对照Copy与子控件结果；fork/离线/提醒的must-match仍需恢复后实际UI，不以caller静态检查或构建代替。

## 文档同步

- [x] SPEC.md：无需更新，架构边界未改。
- [x] docs/specs/im/：最终行为由orchestrator校正归并，reviewer不提前代写通过。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## 交接边界

当前断点如上，无消息draft/附件/表单/sheet，未发送本轮新marker、创建fork或蒸馏draft。只有两个实际Copy及一次统计展开；caller要求暂停后未再触UI，操作器阻挡期间保留安全阅读页，交还caller处理窗口，不擅自重启或通过其它技术返回。仅提交本报告，不包含caller dirty文档/output。最高Required Action：继续缺前置/操作器恢复后的受影响范围复验；当前无新的fix-implementation finding。Full门槛与真机deferred保持不变。
