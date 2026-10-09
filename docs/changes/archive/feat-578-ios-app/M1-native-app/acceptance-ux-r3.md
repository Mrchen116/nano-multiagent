# feat-578 — 原生受影响 UX 独立复验 R3

> Mode targeted；change-reviewer；产品源码 `2992200b9`，实际390 iPhone14 Simulator iOS26.4，隔离IM62008/nano。R2锁屏报告原样保留。执行2026-10-06 21:03–21:27 +08:00。executed_base = validated_at = `2992200b994e0c24b72a481b5af031c8c6aed942`；提交报告的共享HEAD可含之后修正，不冒称已验后续树。
> 实际安装容器 `D6F3BF6F-FA00-4ED8-986C-940A769F0F97/NanoIM.app`，binary SHA256 `9eb92c27c4daa5c58468c861c51190ccb598edabe439eba517500bbb5532bbc9`，debug.dylib `74a393367c8fa42d6967f653c0ccd2cce4776e8eab97b562be51973efcf030a2`。两项均独立从安装容器核对。不以caller后续源码/构建冒称UI版本。

## Verdict

**fail：必验余项仍inconclusive，N8视觉问题仍未关闭。** 本轮已证范围有效，3项minor实际观察，无新增关键功能失败。R2的锁屏事实不被覆写；后续候选的显示修正不混入299实测。

## 已完成用户旅程（实际CUA截图/AX）

- J-UX3-01 阅读/照片：本次群c_zia690ag恢复后，阅读素材实际文字A→橙图A→文字B→linked蓝图B→文字C；self mention为@Test User，具名链接、列表和表格正确可读。代码区域独立Copy操作，simulator clipboard只读得到`let result = 42\n`；没有使用host paste。反馈未捕获，正文长按操作器不具已知可执行动作，保留未验。API阅读素材不计UI发送/LLM执行。图库取消→无附件且Send禁用；再次选系统合成花卉样图→ready待发区为可辨认花卉缩略图→点缩略图看同花卉预览→完成→移除→无附件/Send禁用。未发照片；未受控复现上传中/失败缩略。
- J-UX3-02 群名/成员回执：本次群真实只添加合成578 Paging01一次，列表三成员；未保存改名578 UX R3 removal draft→只确认移除刚新增Paging01→回执仍保draft/SaveName启用、恢复原TestUser/e2e-peer两成员、pin/mute均off。明确放弃名称后退出，标题e2e-peer、composer空。关闭299版本专门修正的移除邻接草稿问题；不碰其它原成员。
- J-UX3-03 管理dirty：账号固定显示名称标签、用户名先行、账号信息默认折叠；展开创建日期本地2026年10月5日01:25。名称draft→Back明确提示→取消仍draft→再Back明确放弃→重开TestUser。设备578 alias draft同样继续/放弃→列表578原别名，relay/report保持on；策略保留天数31→32draft同样继续/放弃→重开31，其它14/45/15未变。全部没有保存。顶部Save原始禁用/dirty启用实际可见。
- J-UX3-04 Tasks：zz578-no-match→没有找到任务/试试其它名称或关键词；清搜索原3任务恢复。578 R15 Relations探索图说明箭头派生、CandidateA显示已选方案；A详情→进入子图说明前置后续依赖，真实breadcrumb Relations→A，点击Relations实际回根探索图。此fixture已解除聊天关联，界面正确无回聊，未替换成新关联或自动发。N8仍有巨幅任务详情标题及约120pt节点空卡，单列minor。
- J-UX3-05 Agent状态/Work：578002(ID578001)管理者TestUser，同页在线→caller受控SIGSTOP owned Gateway21704→心跳超时后同页灰点离线+需设备恢复在线说明→callerCONT→同页恢复在线绿点、离线说明消失；无页面重入。caller contacts只读5agents全offline辅助，不以暂停推测离线。Work空闲、收到新消息已完成、Compute987+654子执行；turn/model/human/trigger只显式展开执行信息后出现，本地详细时间2026年10月5日10:10。当前真实两轮completed、无pending，不种伪审批。折叠开始/结束仅10/5，两轮无法从时间区分，事件仍有原始runtime_config_applied/model_round_end；单列minor。
- J-UX3-06 主操作与通道：578002配置备用模型0默认折叠→展开见添加备用模型；name草稿顶部Save启用→明确离开放弃→详情仍578002。新Agent必需ID/name草稿令顶部Create启用→取消明确放弃→目录未创建。通道当前暂无，Add仅AppID普通草稿→Cancel提示放弃通道配置→取消提示保draft→再次Cancel明确放弃→暂无通道→重开AppID/Secret均空，再取消。未输入secret/保存/打开外部平台；不将普通草稿保护扩大为secret生命周期。
- J-UX3-07 长历史：旧c_1p4zrncj peer原已suspended，caller纠正不恢复旧账号；本轮改新approved合成Reader u_kita0969纯真人群c_yqmwvyrl，共70条API阅读素材，不算UI发送。初始实际viewport68–70。scroll/drag没有移动当前Simulator画面，AX聚焦已加载文字64→60→56→…12实际逐段到早期；点击更早的消息加载01–10，当前实际03–05与Latest入口。不以这些动作声称手势/自动顶部分页完成。收到本轮唯一marker `UX-R3-OFFSCREEN-88d34a1f6e` (`d957099cf3ac444c9385e408224a1551`)，实际03–05画面未跳、marker不可见。caller在POST后77秒只读unread仍1/cursor70th；随后Latest只点击一次，marker全正文实际在composer上方可见，Latest消失，UI可返回。最终只读unread0/cursor新marker。独立只读receipt `/tmp/nano-feat578-ux-r3-incoming-receipt.json`已核对三个时点；API控制sender不算本reviewer UI发送。证明此>60历史fixture的单次离屏新消息真实viewport保护，不扩张物理手机/自然全部分页/手势。

- J-UX3-08 私聊身份：caller明确新专用direct c_vpsj9y6q，nano/新Reader两人，避免任何未知旧私聊。临时保存Alias Test R3（中文typeText只得到R3，未以此冒称中文输入通过）；列表标题已改，头像仍粉底57，与原Reader成员及群消息相同。随后保存恢复原578 UX R3 Reader，pin/mute均off，空composer、无发送。
- J-UX3-09 提醒控制：停我的前台，caller单次新direct消息UX-R3-BANNER-bd7e6b671b，实际sent21:25:45.413，msg94bd482f6df8438dad71cbc6ad4fb910。CUA35次短AX观察20秒未捕捉可点来源banner，未记循环起点，不能证明观察完整涵盖3秒展示窗口，结论inconclusive而非产品fail；不请求重复marker。随后Chats实际专用Reader摘要/未读1→从已知direct行进入，实际见唯一完整素材与粉底57来源→Back Chats无该unread。API送达/列表未读不替代banner画面或点击。私有receipt `/tmp/nano-feat578-ux-r3-banner-receipt.json`已只读核对。

R2唯一UI发送持久辅助本轮已独立读取：`/tmp/nano-feat578-ux-r2-send-receipt.json`，request88160244dd06468ea424cd49c5015e7d/replya06fccf5160d46f0b60b13545d1ca227各1，replycompleted42，另1API阅读素材。本轮未再次发送该请求或其它消息。

## Reference Artifacts Reviewed

design.md P1–P6、原型相关页面、ux-correction-r1.md和三份UX R1报告；R2为prior targeted。实际CUA截图/AX是本报告对应J编号的产品证据，不是caller成功叙述。原九页390/430/大字visual-r3未失效范围继承，不称本轮全部重跑。

| Reference / contract | 实际产品证据与viewport/state | 对照结论 |
|---|---|---|
| P1 输入与返回/安全区，design增量身份 | 390普通字；J01附件预览/取消、J08私聊改名头像、R2直接候选+software keyboard retained | match已走范围；中文组合/VoiceOver仍inconclusive |
| P2 Tasks层级/语义/回聊 | 390普通字；J04探索selected、前置说明、真实祖先导航，解除关联无回聊 | match功能范围；N8标题/密度deviation |
| P3 Work/主子/审批 | 390普通字；J05真实completed主执行+子执行/信息收纳 | match摘要信息层级；具体折叠时间deviation；真实pending inconclusive |
| P4 全管理入口与主动作/草稿 | 390普通字；J03/J06账号/节点/策略继续和放弃、配置/创建顶部主操作、通道普通草稿取消 | match实际覆盖；未保存密钥/未新增真实通道、不扩大该生命周期 |
| P5 提醒安装 | J09唯一direct源控制；无banner实图/点击，未操作手机 | inconclusive；S28既有说明retained |
| P6 层级/颜色/密度/可达 | J01有识别性照片缩略；J02/J08统一身份；J03/J06固定标签/折叠/顶部动作 | match已走范围；N8和Work日期2minor deviation；430/大字体未重跑 |

## N1–N8 / U01–U10逐项结论

| Issue | 期望来源 | 实际证据 | 结果 | 精确边界 |
|---|---|---|---|---|
| N1 短候选/键盘 | native-r1 / correction输入 | R2 J01 retained | pass | 299两项delta不改变输入；不称重验IME |
| N2 搜索多选身份 | native-r1 / correction群 | R2多选取消retained，R3 J02实际单项提交/移除保draft | pass | 原两成员恢复 |
| N3 Tasks查询空态 | native-r1 / correction任务 | J04 noresults+clear恢复 | pass | 本轮3真实测试图 |
| N4 Work原始首屏 | native-r1 / correctionWork | J05语义标题/空闲/子执行、显式展开technical IDs | pass | 折叠日期粗另列minor，pending未验 |
| N5 账号丢草稿 | native-r1 / correction管理 | J03 continue/discard/reopen原值 | pass | 没保存任何账号更改 |
| N6 新建查询空白 | native-r1 / correction列表 | R2 retained | pass | 不称新建全部分支重跑 |
| N7 标签/账号身份层级 | native-r1 / correction管理 | J03固定标签、默认折叠ID/本地创建时间 | pass | 设备心跳原始格式另列minor |
| N8 Task密度 | native-r1 / correction任务、P6 | J04巨幅标题、120pt两行卡下空白 | fail | minor，299真实未关闭；后续包待窄复验 |
| U01 图片交错顺序 | web-r1 / correction内容 | J01 A橙B蓝C及linked图片、列表表格可读 | pass | 受控API准备的阅读素材 |
| U02 待发照片识别 | web-r1 / correction附件 | J01 ready缩略/preview/移除、picker取消 | pass | 没捕获上传中/失败缩略，不称失败分支重跑 |
| U03 消息时间 | web-r1 / correction身份 | R2发送/回复retained；J01/J07/J09可见本地时分 | pass | UI发送仅R2那一次 |
| U04 正文/代码复制 | web-r1 / correction内容 | J01代码clipboard正确；正文长按/反馈未能证明 | inconclusive | 操作器无已知长按动作；不以单测代UI |
| U05 历史读取成本 | web-r1；correction未承诺自动分页 | J07真实更早按钮加载01–10、Latest见marker | inconclusive | 手势/自动top分页/加载end反馈未完成，不默认为关闭 |
| U06 探索已选与箭头 | web-r1 / correction任务 | J04 selectedA与探索/计划关系说明 | pass | 未修改选中结果 |
| U07 真实祖先路径 | web-r1 / correction任务 | J04 Relations→A及点击祖先实际回根 | pass | 本次真实一层子图，不扩张任意深链 |
| U08 空群名与搜索 | web-r1 / correction建聊 | R2空名实际创建及owned身份搜索retained | pass | ID/设备搜索未在本轮再验 |
| U09 群成员多选可查 | web-r1 / correction群 | R2双选取消retained+J02一次添加再恢复 | pass | 只操作明确本次合成新增人员 |
| U10 Work可理解摘要 | web-r1 / correctionWork | J05首屏可理解/信息层级 | pass | 具体日期和未知过程名另列minor；审批默认展开inconclusive |

## 问题与限制

| ID | Severity | Regression Relation | 期望 / 实际 / 证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| UX3-01 (N8 retained) | minor | direct | P6应紧凑；J04 TaskNode巨幅泛标题/无描述120pt卡留白 | fix-implementation | 当前299实图未关闭旧N8，任务功能可用 |
| UX3-02 Work日期 | minor | direct | 折叠应可区分轮次；J05两轮标题收到新消息、开始结束都10/5 | fix-implementation | 无须编造请求摘要，用已有本地时分消除歧义；原始未知事件可保留准确名 |
| UX3-03 设备心跳技术格式 | minor | unrelated-existing | J03仍完整UTC微秒字符串占状态区域 | out-of-unit / side finding | 账号已改本地日期，设备dirty功能可用；不是本轮管理返回保护失败 |

CUA scroll/drag未移动和中文typeText省略字符仅作操作边界，不自行定位产品根因。正文长按/feedback、真实pending权限默认展开、banner点击、中文组合/VoiceOver缺实际证据。任一必验inconclusive使总体不可pass；不自动把minor升级成blocking。

## 受影响Scenario与Full继承

来源均feat-578 spec.md对应S行；真实方式/证据为上方J或精确prior acceptance。下表是本轮增量，完整R20表附后，不把所有旧通过项说成重跑。

| Scenario | 验证方式与证据 | 本轮合并结果 | 精确剩余 |
|---|---|---|---|
| S2 键盘长内容辅助 | R2software keyboard；J01代码copy；J03/06顶部动作 | inconclusive | 中文组合/VoiceOver/正文选择复制 |
| S5 建聊群设置 | R2空名/搜索；J02新增再确认移除保draft、群仍群；J08私聊别名恢复 | pass | 未失效其余R20范围retained |
| S6 偏好/真实viewport | R2偏好恢复；J07未读77秒保护→单Latest见全文→0/newcursor，J09列表未读可感知 | inconclusive | 真实viewport子范围已关闭；前台banner点击仍S27inconclusive，不将整体扩大 |
| S7 目标/命令/历史/头像 | R2单次发送42/命令草稿；J07分页/Latest；J08头像稳定 | inconclusive | 新增AND中文组合未完成；R20历史通过原范围retained |
| S9 Copy/fork | J01代码copy准确 | inconclusive | 正文/fork及跨Gateway/离线既有剩余 |
| S10 附件 | J01阅读顺序/ready预览取消移除 | inconclusive | 主动粘贴明确禁止host paste；其余旧范围retained |
| S14 任务 | J04selected/关系/真实祖先 | pass | 未失效R20引用与解除关联范围retained；N8视觉另列 |
| S15 Work | J05主/子completed摘要可读与信息折叠 | pass | 原真实主子范围retained；真实pending展开放S13增量inconclusive |
| S16/17 新建配置 | J06主操作/备用折叠/dirty启用后不提交 | pass | 原创建及完整保存范围retained，不冒称本轮新增Agent |
| S20 通道凭据 | J06普通AppID草稿continue/discard重开空 | pass | 旧S20credential范围retained；本轮没有输入/保存secret或外部连接 |
| S23 节点 / S24账号 / S26策略 | J03各dirty，J05节点状态 | pass | 原保存/权限范围retained，新的草稿保护实际已证 |
| S27 前台提醒 | J09单次消息实际送达/列表未读，没有banner图或点击 | inconclusive | 不认定观察窗口覆盖3秒，不判产品fail |
| S29/30 物理安装续签 | 本reviewer未碰手机 | inconclusive | 不将Simulator/caller签名安装直接替独立操作与自然到期 |

## 安全恢复与交还

21:27回Chats，无搜索/表单/待创建Agent/配置/附件/消息draft；群恢复原两成员与偏好off，专用私聊已恢复原名与偏好off。owned Gateway21704已经CONT并同页实际online。两条控制incoming/API阅读素材原样保留、没有重复发送或删除。UI独占已明确交还caller，后续8e安装不属于R3事实；报告只提交这一文件，生产/物理iPhone/未知旧私聊未操作。

## 上层文档同步

- [x] SPEC.md：无需更新，包边界未改。
- [x] docs/specs/im/：最终增量由orchestrator校正归并，本reviewer不代写。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## R20完整历史表（原样继承）

上方增量优先描述本候选新范围；下面保留历史表包括失败经过与未完成精确范围，不称全量重跑。S6真实viewport已新增关闭子范围，S2代码复制也新增证据；S27/S29/S30和其余未验继续开放。

## 最新S1–S30合并表

| Scenario | 当前状态 | 已完成证据 / 精确剩余范围 |
|---|---|---|
| S1 四入口与返回 | pass | R1/R2四入口及任务/Work/账号导航；R3–R6反复跨页自然返回，原生管理无需Safari。 |
| S2 输入与辅助操作 | inconclusive | P6已完成390/430普通及大字体、三行composer、长配置滚动/主按钮可达；真正中文IME组合输入、软件键盘遮挡、VoiceOver导航、正文代码复制仍需支持的操作方式/真机。 |
| S3 登录注册恢复 | pass | R20 J67同版本/证书在exact域名代理bypass环境差异后真实HTTPS登录成功；R19 TLS失败保留，未冒充手机。 R7 J35真实注册→只见本人待批准→普通成员批准后刷新空聊天；b8f9保数据重启恢复相同有效账号，结合前轮错误登录/停用状态。 |
| S4 暂时失败与切换 | pass | 前轮A→B隔离/停用踢出/真实断线恢复；R7 429倒计时、503区别密码错误、字段保留及正常恢复均完成，中文窄修已闭环；R9 J45真实201上游已完成/客户端上传中时退出→实际旧连接中断→B身份正确/Chats空→A恢复无待发旧项。运行期未送达迟到主体；clear后transport迟到保护另有独立测试层证据，不混称UI已送达。 |
| S5 建聊群管理 | pass | R7 J29搜索真人/建私聊，专用群添加成员→确认移除→两人仍为群→确认解散后撤销访问/列表消失；前轮Agent私聊/群改名证据保留。 |
| S6 偏好已读 | inconclusive | R1改名置顶、R5静音保存重开、静音不丢消息、历史阅读不被新消息强拉底已完成；R10历史02收新11不抢滚动且unread1已证；主动Latest停08/09未见11、native布局持续忙、AX无正文，但服务unread0，R11候选33b6e64f4同fixture02→Latest实际11完整可见且返回/重入响应，R10-01关闭；前台跳转见S27。 |
| S7 发送提及历史 | pass | R20 J68同一HTTPS原生新群单次目标请求→进行中→42 completed，caller持久仅2消息辅助；不扩张真机。 R1文字/slash；R5 65条分页加载001–005保持早期位置、实时066不抢滚动、按聊天隔离草稿与真人发送收件方可见完成；R11 J49全新群原生菜单选择e2e-peer，真实Gateway/LLM两轮均该Agent completed 42；原生配置空→578-R11保存节点确认，M2回复前显示「Agent 配置已更新」分界，再清空恢复并确认。目标回复已实证；R12 J50候选f77b34633既有M2与实时M3分界均在对应用户消息前，R11-01 closed。 |
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
| S21 通道生命周期 | inconclusive | R4实际connected→停用applied/实际停用→确认删除空列表完成；R18 J63单次重连后已连接/报告更新时间；J64真实节点offline最后已知说明、确认删除pending及一次停止重试conflict；J65恢复后真实停止确认/原生暂无通道闭环。natural stop异常重试、受限/未知权限及真实平台shadow历史保留未触发，仍inconclusive；R18-01为通用草稿文案和旧冲突横幅留存minor。 |
| S22 绑定 | pass | R2双端接受→等待→设备确认→完成；R7当前账号/测试设备检查、明确拒绝后归属不变、过期清秘密输入并提示重新发起。caller确认两测试operation未造node。 |
| S23 节点管理 | pass | 前轮别名/节点创建/非owner边界；R7中继与上报off保存重开→恢复on，真实第二节点offline与主online并存→恢复online，未动生产。 |
| S24 个人资料语言 | pass | R1/R2中英与中文错误修复，R6 J28显示名及默认设备保存退出重开保持，再恢复原值；只读身份字段可见。 |
| S25 公司管理 | pass | R1批准/停用/最后admin拒绝、R2普通成员限制及客户端被停用；R14 J55真实51名human成员原生首50→加载更多追加末页17、旧页02/35保持、最终无更多按钮；R15 J58指定普通owner原生确认停用→已停用，caller真实旧runtime WS101→403、旧browser nodes401、第三节点offline/owner suspended/epoch2/清runtime hash，前两owned节点仍online，机器资格撤销闭环。 |
| S26 策略容量 | pass | 前轮管理员全部策略保存/普通成员只读；R7服务与owner容量UI和实际API一致，精确单次503保32草稿→放弃回31，真实policy全字段仍baseline。 |
| S27 提醒前后台 | inconclusive | R1轻提示、R5静音，R6总开关off保存重开并恢复on；本轮未捕捉可点击banner，不能判失败。R13运行中Home→结果完成后原生图标返回同群/展开状态保持、实际唯一消息与过程正常，后台补齐范围闭环。计划13因调度晚12秒未捕获3秒banner，点击跳转仍缺；不以API收到消息或源码推断出现。 |
| S28 后台边界说明 | pass | R1帮助和权限边界有效，未声称免费签名具备保证后台推送。 |
| S29 真机首次安装 | inconclusive / 按用户安排后置 | 未用Simulator、Release archive或未签名IPA冒充物理iPhone免费签名安装。需用户Apple账号/协议/手机信任与实际主屏幕打开。 |
| S30 同网续签恢复 | inconclusive / 按用户安排后置 | Mini AltServer、手机配对Wi-Fi sync、同网拔线刷新及自然过期恢复未完成；不能由文档/构建替代。 |
