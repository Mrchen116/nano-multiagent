# feat-578 — 模拟器继续验收 R3

> Mode targeted；change-reviewer；产品 `executed_base = validated_at = aa7876fa9ab443b4cf12d1a4119fd2abc7d428d3`。开工HEAD4c7134600，后续afa1d5e74仅报告。2026-10-07 00:49–01:01 +08:00真实390 UI；隔离IM62008，caller恢复同一fixture DB/config，IM45154/Gateway45162。未重建/重装/启停服务、未触430或物理手机、主仓或生产。
> 实际安装仍ADC97CD1-1079-47FD-AF3C-C4455211E8E4/NanoIM.app；本轮独立复核binary SHA256 `8b099d40c54142e4b8ec097896cf8af15e8bf392c899e0db24030a910be489ce`、debug.dylib `673b10a07f71bad0580a3b4b49e728a0f25b719690247e249b57574a94e4be3a`。caller核main d87ffa3d1仍为祖先，本报告不将另一产物当验收对象。

## Verdict

**fail：Full仍未完整通过；可测模拟器工作继续。** 本轮实际关闭R2因操作器未能进行的fork、离线中文说明、来源banner图/点击，并补正常蒸馏草稿。R2历史`noWindowsAvailable`原样保留；本轮实际坐标返回与导航成功，不能再把旧工具阻碍当停验原因。设备内图片已主动Copy，但Nano未出现Paste，尚无待发图片/完整粘贴结果；S21受控真实停止失败及权限/历史仍待caller前置，继续后续轮。只后置物理范围，不宣称暂停所有模拟器工作。

## 实际产品旅程

- J-SIM3-01 fork取消：Chats全部→搜索明确iOS approval acceptance/c_xuh5cshe→已完成第一回复Fetched successfully（对应ea433beb8bd7439ba470c7d705a23aad），AX实际显示“从这里分支”后才执行。弹出“从这条回复创建新分支？”/“创建分支”；执行实际暴露Cancel，回同一原chat、第一回复实图，Send禁用、无draft。原聊天中后来nano_ios=2请求与deny回复可辨认，未打开未知c_81nb7o3h。
- J-SIM3-02 fork确认：第一回复过程(3)实际展开，web_fetch/completed/131.3s可再展开为已授权、https://example.com/、输入/结果详情；统计2,557实际展开本轮输出175、上下文2,382/262,144、缓存3,584(78%)、1%。辅助动作不挡子控件。再次对该第一回复执行具名分支，唯一确认点击16:52:02.878Z。实际跳新iOS Permission Check/c_t509s0a9；整页/AX恰第一human请求和第一completed回复，后来请求/deny回复均不在新chat，空composer/Send disabled，没有自动发送或运行。详情成员Test User+iOS Permission Check，pin/mute0，未编辑。caller只读ID baseline差分恰新增该会话(created16:52:03.574334Z)；实际UTC16:48以来同Agent也仅该条，取消时无新创建。其API timeline正确unwrap后恰两复制消息、sender/content与截至目标历史一致；新ID57469ad6959440c3b022b5d9b0dddfe7/49235d39550a49299a4659c2bcc377af不算新LLM消息。私有0600 receipt `/tmp/nano-feat578-sim-r3-fork-receipt.json`。caller初始未来UTC查询/未unwrap辅助读取错误均已纠正，无mutation，不当作最终证据。
- J-SIM3-03 离线整理：Chats→整理会话知识→仅ios-binding-check/c_wdnb5vv5→同名执行Agent→Agent范围→实际生成。画面/AX明确“来源设备离线，请在设备恢复在线后重试。”中文红色反馈，来源选择和执行/范围保持、无draft，不恢复节点。关闭R1 SIM-01离线含混英文回执，旧事实不改写；R1两不同node跨Gateway拒绝retained，不重复。
- J-SIM3-04 无binding来源及正常草稿：改选明确允许的第一Skill distill · e2e-peer旧空draft chat、executor e2e-peer，生成实际英文`source session binding is unavailable`、无draft；caller确认该旧空chat无binding，不能冒充有效transcript正常分支。取消，重新整理仅原c_xuh5cshe/iOS approval acceptance真实历史、executor e2e-peer、scope Agent，实际生成并跳新Skill distill · e2e-peer空chat：composer完整含`/skill:conversation-skill-distiller`、原ios-permission真实sess_8322d299169686b8.jsonl来源、execution_agent_id e2e-peer、target_scope agent、中文蒸馏指令。没有点Send或执行Skill。明确全选BackSpace后placeholder空/Send disabled，再回Chats，保留新空chat、不删除。正常草稿pass；英文无binding原因另列minor，不扩大离线已闭环范围。
- J-SIM3-05 真人来源提醒：已知Reader c_vpsj9y6q列表未静音；我的→提醒与安装实际前台提醒on，只读返回我的，未选聊天/无sheet。ready_at16:54:30.067Z；连续实际AX+截图观察started16:55:00.422Z、37samples。caller唯一API控制sender Reader u_kita0969 POST201，新marker UX-SIM3-S27-a4e2471c44bc，created16:55:15.126884Z/id5b964dda99fd47bdb7cbc61efa15e753，post_count1。16:55:15.916Z实图捕捉粉色57头像、578 UX R3 Reader、“新消息”，没有marker/body；真实AXbutton6。仅一次点击16:55:16.078Z，16:55:17.223Z实际正确Reader聊天，完整新正文可见，Send disabled。caller只读确认唯一1、事件622 message.sent/623 message.delivered、unread0且last_read精确新id、pin/mutefalse。私有receipt `/tmp/nano-feat578-sim-r3-banner-receipt.json`。来源API准备不是UI发送或LLM。实际点击前banner出现及点击后全文pass；不把主动点击后消失称3秒自然到期，没有追加marker。返回Nano前台无旧提醒重放，本轮未改时长或偏好。
- J-SIM3-06 主动设备内图片Copy/Paste：Simulator Home→设备搜索Photos→Photos。首次功能介绍继续、其意外通知请求选择不允许，不授额外通知。仅6张已有默认模拟照片，打开第二花卉实图→共享→明确AX“拷贝照片”，实际点击，sharesheet关闭。设备Home→Nano既有Reader空composer：+菜单只有文件/照片，聚焦后一次double-click实际编辑菜单仅AutoFill，无Paste；未出现待发项。无host paste、Simulator Edit剪贴板传输、键盘粘贴快捷键或API附件。caller只读simctl pbpaste为text-only，不能据无text判断无image。本轮没有能证明设备pasteboard实际图片类型的探针，不提前写根因已证；Paste入口/附件结果inconclusive，交caller独立窄回归与后续候选复验，继续其它范围不停止全部工作。

## 辅助操作与Work条件裁决

本轮实际AX可读并可操作：聊天搜索/筛选、具名Copy/fork、分支明确确认与Cancel、过程/工具/统计子控件、整理来源switch/执行Agent/范围/生成/取消、我的管理入口及提醒开关。根页Tab Bar在CUA仅为container，部分聊天返回/顶部入口采用fresh截图坐标，不把这套操作器AX呈现冒称VoiceOver手势/朗读已通过。

Apple官方[Performing accessibility testing for your app](https://developer.apple.com/documentation/accessibility/performing-accessibility-testing-for-your-app)本轮独立浏览确认VoiceOver不在Simulator，完整VO要物理设备；不是继续寻找不存在的模拟器系统入口。S2模拟器可测输入/AX部分保留已证，物理VO随用户真机安排deferred，S2整体仍inconclusive，不称所有辅助能力完整。

S13 current `docs/specs/gateway/global-agent.md`“全局未获准动作”明确不弹权限卡、不挂Future；`docs/operations/auto-permissions.md`普通global主/child不等待卡、HB/Cron走unattended。独立[scope核对](verification-simulator-scope-r1.md)进一步限定当前main/child/Workflow/HB/Cron均无人工pending生产入口；保留事件消费/旧历史不意味着前置可达。由此，本轮将当前global Work人工pending默认展开子条件标**not-applicable（现行生产条件）**，不要求改Auto规则、造pending或再发请求碰运气；不是“实际默认展开已测”或对未来版本豁免。S13原WHEN“聊天或Work”在真实单聊天审批仍有实际选项，R18/R20 allow_once/Deny/迟到确认有效证据retained，Scenario该现行可达范围pass。R1/R2当时未验的历史不删除，新增的是明确条件裁决，而非追写UI成功。

## Finding及继续范围

| ID / Severity / Relation | 期望 / 实际证据 | Recommended Action / rationale |
|---|---|---|
| SIM3-01 / minor / direct | 无binding来源应有用户可理解的原因；J04实际裸英文source session binding is unavailable，没有中文恢复方向 | fix-implementation：明确会话历史不可整理的原因，不把无binding伪造为有效来源；正常生成不受此失败影响 |
| S10入口待证 / 非确定产品finding | J06实际Copy Photo后Nano仅AutoFill，无Paste；图片pasteboard类型未独立证 | 继续受影响复验；caller独立入口回归不替代本轮实测，不能先判原生粘贴pass/根因已证 |
| S21受控停止失败/权限/历史 | 当前尚未操作本轮合法runner | 等caller明确fixture/版本/授权，实际原生删除失败→重试闭环；“natural”不是spec条件，不据此前措辞放弃可控真实链路 |

设备心跳原始UTC日期minor side finding由R3旧报告retained，本轮未进入该页、不冒称已闭环。caller后续修正未装入本候选，不能混为本轮结果。

## Reference Artifacts Reviewed

spec.md S2/S6/S9/S10/S12/S13/S21/S27；design.md P1/P3/P5/P6；[模拟器R1](acceptance-simulator-r1.md)/[R2](acceptance-simulator-r2.md)、[UX R3](acceptance-ux-r3.md)/[R4](acceptance-ux-r4.md)、R18/R20审批原证据、current global/Auto契约及独立scope核对。J01–05含实际截图/AX输出/clipboard旧证据及scope-specific caller只读对账。P3当前Work pending子条件按上述生产入口not-applicable，未用静态报告代替实际展开；P5来源名头像/无body/正确跳转match，3秒自然消失不扩大声明；P1/P6其余有效视觉范围retained。J06主动paste结果仍未证。

## 最新合并Scenario矩阵

每行来源为spec.md对应S，retained来自R20及UX/模拟器前轮，未失效范围不机械重跑。仅后置物理设备；S21及S10继续实际可测范围，不降为“用户已跳过”。

| Scenario | 最新结果 | 新证据 / 精确保留边界 |
|---|---|---|
| S1 四入口/返回 | pass | retained；本轮实际从fork、详情、整理、我的返回，旧坐标阻碍本轮不复现 |
| S2 输入/辅助 | inconclusive | 真中文软件组合/多行/长表单/字号retained；R2 Copy+本轮具名fork/子控件AX操作pass；完整VoiceOver物理设备deferred，不冒充AX=VO |
| S3 登录/注册恢复 | pass | retained；caller刷新原合成session，不重新注册 |
| S4 暂时失败/切换 | pass | retained；本轮未新故障注入 |
| S5 找人/群管理 | pass | retained；本轮仅明确受控fork/蒸馏空chat，未改群/删数据 |
| S6 偏好/已读 | pass | R3>60离屏77秒→Latest/cursor闭环retained；J05真人新源banner实际点击→全文→精确已读闭环 |
| S7 发送/提及/历史 | pass | R2 @/slash、唯一42、R3分页、R1真实Chinese软件组合retained；本轮无UI发送，fork复制历史不算新执行 |
| S8 不确定发送/重连 | pass | retained；本轮控制marker非UI重试，不扩张其他分支 |
| S9 Copy/fork/蒸馏 | pass | R2正文clipboard/代码retained；J01/02取消0新增→确认1新fork截至目标；J03离线中文说明+J04正常待发/清空，R1跨Gateway拒绝retained；minor裸英文另列 |
| S10 附件接收/导出 | inconclusive | ready图片/导出旧证据retained；J06设备主动Copy Photo后无Paste/未待发，后续继续入口复验 |
| S11 失败附件/权限 | pass | retained；本轮无图片发送/上传 |
| S12 过程/统计 | pass | retained；J02 firstreply过程→工具及统计实际可展开 |
| S13 审批提交确认 | pass现行可达范围 | Chat allow_once/Deny/等待/迟到确认retained；当前global Work pending子条件not-applicable，明确不是默认展开实测 |
| S14 任务/回聊 | pass | UX R3语义/R4 N8 closure retained |
| S15 Work主子历史 | pass | R4时间/R20受控历史与R1真实completed retained；不造pending |
| S16 节点创建 | pass | retained；本轮无Agent创建 |
| S17 完整配置 | pass | retained；未改Auto/权限规则/Agent配置 |
| S18 冲突pending配置权限 | pass | retained；不与global Work运行pending混淆 |
| S19 Skills/心跳/Cron | pass | retained；J04只待发草稿，不执行Skill或改计划 |
| S20 通道凭据 | pass | retained；没有输入/保存secret或改真实平台 |
| S21 通道生命周期 | inconclusive / 继续模拟器范围 | stop真实故障/修复及受限/未知权限/历史前置待caller，旧离线恢复删除证据retained；不要求必须自然发生 |
| S22 绑定 | pass | retained；不恢复离线节点/新增绑定 |
| S23 节点管理 | pass | retained；本轮离线明确反馈，不启停节点 |
| S24 账号/语言 | pass | retained；不改变产品账号/语言或keyboard偏好 |
| S25 公司管理 | pass | retained；不管理真实他人 |
| S26 策略容量 | pass | retained；不保存策略 |
| S27 提醒 | pass | J05完整实际banner截图+唯一click跳对应Reader+完整正文/已读；后台返回旧证据retained，本轮Photos往返无历史再提醒；未声称3秒自然消失已计时 |
| S28 后台边界说明 | pass | retained；本轮真实提醒on/说明可读，未宣称保证系统推送 |
| S29 真机首次安装 | inconclusive / user-deferred | 用户只后置物理设备；本reviewer未触Phone |
| S30 同网/自然到期恢复 | inconclusive / user-deferred | 不以模拟器代替拔USB/续签/自然到期 |

## 安全交还及文档同步

01:01 +08:00 caller要求安全点后，实际回Chats、全部筛选/空搜索；正常distilldraft已明确清空、Send disabled后退出，无附件/表单/sheet。新fork/蒸馏空chat保留，Reader marker已读，不删除数据。复制仅设备Photos用户操作，不用host clipboard；首次Photos通知选择不允许，未授权额外通知。UI交还caller后停止触碰，后续S10候选/S21合法runner准备不改变本轮aa事实。

- [x] SPEC.md：无需更新，跨包边界未改。
- [x] docs/specs/im/：由orchestrator按最终实现及Work条件校正归并；reviewer不代写接受结果。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

只提交本报告，不碰caller dirty/output，不push。最高Required Action：fix-implementation（SIM3-01 minor）；另继续S10/S21真实验收。Full未接受，needs_re_review=true，未创建外部issue。
