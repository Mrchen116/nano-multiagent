# feat-578 — 原生受影响 UX 独立复验 R2

> Mode: targeted；Skill: change-reviewer；指定候选 `ba261e12f5c5bba36e8f513d7a3cce74d3f417cc`。实测为 iPhone 14 Simulator 390、iOS 26.4、普通字体，隔离 IM `127.0.0.1:62008`，合成账号 nano。无物理手机、生产、飞书或未知私聊操作。
>
> 安装身份由实际安装容器读取：`54544043-A121-4742-9AF4-1794D7918233/NanoIM.app/NanoIM`；SHA-256 `1b28020c68cc7c948f66f06b401aa3f3bbe61f18ab3af16cfd0b747c72c5e12f`。不以可能被后续构建覆盖的 build 目录替代安装身份。caller 后续源码修改不属于本候选 UI 证据。

## Verdict

**fail：已完成旅程通过，受影响范围尚有 inconclusive，整体 Full 门禁继续未通过。** 20:51 左右 Mac 锁屏，CUA 明确返回自动解锁失败；此后没有绕过锁屏或替代为 API/源码验收。caller已向用户请求解锁，用户尚未回复；caller明确要求在此安全断点保存本轮报告并交还UI，不继续操作。以下按实际覆盖逐项保留。

本轮仅关闭由候选实际证明的旧 UX 问题；此前 R20 未完成的中文组合输入、VoiceOver、复制/fork、粘贴、通道分支、前台提醒、物理安装与续签不得凭单测或新包安装宣称完成。

> Validation snapshot: executed_base = validated_at = `ba261e12f5c5bba36e8f513d7a3cce74d3f417cc`；实际交互窗口 2026-10-06 20:47–20:51 +08:00。报告提交时共享工作树已进入后续修正，不能把报告提交所基于的树冒称UI受审版本。

## 用户旅程体验

### J-UX2-01 建聊、身份与唯一目标发送

20:47–20:49：Chats 的 + 直接进入新建聊天。输入 `zz578-no-match` 得到明确「没有匹配的联系人」，再搜索 `e2e-peer`，唯一结果显示 Agent、Test User、设备 578、在线状态及缩写头像。选择 owned e2e-peer，打开群聊、保持名称为空，顶部创建仍可用；只创建一次，生成标题 e2e-peer 的空群。caller 只读确认本次专用群 `c_zia690ag`，创建时间 `2026-10-06T12:48:06Z`。

在新群直接输入 @、继续 e2e，显示当前成员 e2e-peer 单项候选。通过 Simulator 菜单显示实际软件键盘：候选贴近输入，面板约80pt，单项没有原 R1 220pt 空白；聊天阅读区仍可用。实际点选成员后键盘继续保持，草稿为 `@e2e-peer `。补入唯一标记 `578 UX R2: Compute 31+11. Reply only the number; do not use tools.`，确认目标后只点击 Send 一次。human 显示 Test User、20:49、已发送；e2e-peer 从进行中0:01变为已完成，正文42、13,287 tokens、2.0s。画面只有一条 user 请求与一条 Agent 回复；持久唯一性辅助待 caller receipt，不能将 API 准备 fixture 算作 UI 发送。

随后只输入 `/eff`，单项 /effort 候选约110pt、包含目标及说明；选择后草稿 `@e2e-peer /effort `。补入 high，按 Return 后继续文字形成两行草稿，未触发发送；全选删除，composer空且 Send disabled。

### J-UX2-02 群成员与名称/偏好组合

20:50–20:51：本次专用群详情中，把名称改为 `578 UX R2 draft`，不保存名称。依次打开置顶与静音，名称草稿每次回执后仍在，保存名称仍可用；再分别恢复置顶/静音为关闭，名称草稿继续保留。

添加成员进入独立搜索多选页，按名称顺序显示 578 Paging 01/02 等合成人员，并标注真人。选01和02，顶部按钮显示「添加(2)」；搜索 e2e 后看到 Agent·e2e·Test User·578，既有 e2e-peer 不列入可添加项。清搜索回到原列表，两项选择仍在。点取消，不添加成员；回到群详情仍只有 Test User/e2e-peer，名称草稿不丢。

返回触发「放弃未保存的名称？」与明确「放弃并返回」。先取消提示继续编辑，确认草稿仍在；再次返回选择放弃后回到聊天，标题仍e2e-peer。最终 composer空、Send disabled、偏好都关闭，无待提交名称/成员选择。

### 当前安全断点

CUA 锁屏失败发生在尝试从该群返回 Chats 时。没有启动自己的服务，未删除数据、未改账号/配置、未保存 secret、未使用宿主剪贴板。caller 可以在此安全断点继续：本次唯一请求已完成42，slash草稿已清，群名称草稿已明确放弃，偏好已恢复，多选已取消。

caller之后确认阅读fixture已种入同群：`36d9a732826c4ea78c79ee64a9b469a0`，私有辅助receipt `/tmp/nano-feat578-ux-r2-reading.json`。正文明确「通过测试接口准备」，预期文字A→橙图A→文字B→linked蓝图B→文字C，含self提及/具名链接/列表/表格/Swift代码。只读核对素材不计UI阅读、复制、发送或LLM执行。长历史 `c_1p4zrncj` 已准备但未进入，caller未发送新marker；owned节点未暂停。Work 578001（显示578002）目前两轮completed，无真实waiting_permission；不种伪审批代替实际分支。

## Reference Artifacts Reviewed

来源为 design.md 的 P1–P6 原型对齐契约、prototype.html/visual-review.html 设计说明、ux-correction-r1.md，以及三份 UX R1 报告。旧 390/430、大字体九页视觉 R3 的未受影响证据保持原范围；此次只对新候选实际截图/AX进行受影响对照，不冒称再次完成所有 viewport。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| P1 / 聊天输入，design 输入增量 | 键盘下可编辑、直接 @/slash、保留目标及换行 | J-UX2-01 CUA实际软件键盘同屏与单次发送/两行未发草稿 | 390普通字、群聊 | match（实际覆盖）；中文组合输入仍inconclusive |
| P2 / Tasks | 关系语义、祖先、选中、回聊保留 | 本轮尚未进入 | 390 | inconclusive；旧S14证据保持 |
| P3 / Work | 可理解执行摘要、主子/授权待确认 | 本轮尚未进入 | 390 | inconclusive；旧S12/13/15证据保持 |
| P4 / 管理及群详情 | 常用主动作可达、草稿保护、权限 | J-UX2-02成员筛选/取消与群名称偏好组合 | 390群详情/多选sheet | match（群部分）；管理表单仍inconclusive |
| P5 / 提醒安装 | 具名来源、前后台/安装边界 | 本轮尚未捕获banner或操作真机 | N/A | inconclusive；旧S28说明保持 |
| P6 / 密度身份与主操作 | 单项面板紧凑、身份头像、顶部创建、多选操作可达 | J-UX2-01/02实际截图；选择页显示数量/身份 | 390普通字 | match（建聊/群部分）；其他页与430/大字未重验 |

## N1–N8 与 U01–U10 受影响覆盖

结果只取 pass/fail/inconclusive/not-applicable；inconclusive 是本轮无法证明，不等同功能失败。

| Issue | 期望来源 | 实际证据 | 结果 | 精确剩余 |
|---|---|---|---|---|
| N1 单项候选过高 | ux-audit-native-r1 / correction输入 | J-UX2-01 @/slash短面板与软件键盘同屏，点选保持键盘 | pass | 未扩张中文组合输入 |
| N2 群成员入口成本 | native-r1 / correction群 | J-UX2-02搜索、身份、双项选择数量、清搜索保选择、取消无添加 | pass | 不主张本轮实际一次提交添加成功 |
| N3 Tasks搜索假空 | native-r1 / correction任务 | 未进入 | inconclusive | 查询无结果、清除恢复 |
| N4 Work技术首屏 | native-r1 / correction Work | 未进入 | inconclusive | 语义标题/本地时间、信息折叠、权限默认展开 |
| N5 账号悄悄丢草稿 | native-r1 / correction管理 | 未进入 | inconclusive | dirty返回继续编辑/放弃、确认未保存 |
| N6 建聊查询全空白 | native-r1 / correction列表 | J-UX2-01没有匹配联系人实际提示 | pass | 无 |
| N7 账号字段无标签/技术信息优先 | native-r1 / correction管理 | 未进入 | inconclusive | 固定标签、本地时间和身份层级 |
| N8 任务图/标题密度 | native-r1 / correction任务 | 未进入 | inconclusive | 节点、sheet标题与图首屏对照 |
| U01 交错图片顺序 | web-r1 / correction内容 | caller已准备fixture，未阅读 | inconclusive | 图/正文/链接内图片真实顺序 |
| U02 待发图片辨认 | web-r1 / correction附件 | 未选择图片 | inconclusive | 缩略图、取消/移除、不发送 |
| U03 消息缺时间 | web-r1 / correction身份时间 | J-UX2-01发送与回复时间、user已发送 | pass | 跨页/私聊改名头像另列风险 |
| U04 正文复制格式与反馈 | web-r1 / correction内容 | 未长按复制 | inconclusive | 实际正文及代码clipboard内容、反馈 |
| U05 历史分页读行成本 | web-r1 | 未进入长历史 | inconclusive | 实际顶部自动/手动分页状态；correction未承诺自动分页，不默认为关闭 |
| U06 探索与箭头 | web-r1 / correction任务 | 未进入 | inconclusive | 可见关系说明、已选状态 |
| U07 深层祖先定位 | web-r1 / correction任务 | 未进入 | inconclusive | 真祖先跳父层与回聊 |
| U08 建聊强制名/弱搜索 | web-r1 / correction建聊 | J-UX2-01搜索owned联系人身份、空名创建成功 | pass | 设备/ID搜索尚未独立实测 |
| U09 加成员单选难查 | web-r1 / correction群 | J-UX2-02 | pass | 不冒称提交添加 |
| U10 Work难懂 | web-r1 / correction Work | 未进入 | inconclusive | 待fixture与真实入口 |

## 商业表单、状态、身份与已读风险

| 范围 | 本轮实际证据 | 结果 | 未完成项 |
|---|---|---|---|
| 群名draft与置顶/静音 | J-UX2-02：回执保draft、恢复偏好、返回先继续后放弃 | pass | 移除成员邻接行为未操作，不以caller静态发现作为本轮UI复现 |
| 账号/节点/策略dirty | 未进入 | inconclusive | 继续/放弃、不保存及顶部动作 |
| 通道secret | 未进入、没有写/保存secret | inconclusive | 取消保护及内存secret清除只按可观察范围 |
| 新建/备用模型折叠 | 已证建聊顶部创建；Agent配置未进入 | inconclusive | Agent顶部创建/保存、备用折叠 |
| 运行/Agent详情状态 | 群请求可见进行中→已完成42 | inconclusive | 列表状态、Profile实际读新状态/最后已知 |
| 跨页/私聊改名身份 | 目录搜索与消息 e2e-peer缩写已见；未临时改私聊名 | inconclusive | 不变目标头像/身份与跨页颜色对照 |
| Work权限展开 | 未有本轮实际待授权fixture | inconclusive | 真实pending轮次首屏与可达动作 |
| Latest/真实viewport未读 | 尚未进入授权c_1p4zrncj，未通知caller READY | inconclusive | 离屏新消息仍未读、Latest见新消息后已读 |
| 前台来源提醒 | 尚未捕获 | inconclusive | 具名授权来源/头像与点击正确聊天 |

## 问题清单与阻挡

| # | Severity | Regression Relation | 期望/实际/证据 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| ENV-UX2-01 | blocking（验收环境） | unclear / 非产品失败 | Mac锁屏，CUA实际报告自动解锁失败；中断余下真实旅程 | out-of-unit：由caller/用户解锁后继续同包 | 无法以源码/单测/API替代UI。未将阻挡误报为产品bug |

本轮已走范围没有新增实际产品 fail；剩余 inconclusive 本身使 targeted不能pass。caller报告的移除成员草稿及头像hash静态问题不混入本轮独立真实UI；最终新修候选须另有版本复验。

## 上层文档同步

- [x] SPEC.md：无需更新（包边界未改）。
- [x] docs/specs/im/：最终原生体验增量需由orchestrator按最终实现校正/归并；本轮不代写。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## 本轮交还与后续边界

caller接回390 Simulator独占UI。最后实际状态是本次专用群内，返回Chats的点击因Mac锁屏未执行；已完成请求42、composer空、名称草稿放弃、偏好off、成员多选取消。后续 `2992200b9` 的两项修正不属于此报告安装候选，不改写本轮事实；解锁后从该断点继续窄复验。

## Full 场景继承规则

以下完整保留 R20 S1–S30 表，未声称全部重跑。上方本轮证据是附加受影响验证，不覆盖旧失败经过与精确剩余。S2的软件键盘范围有新增证据，但中文组合/VoiceOver/复制仍未完成；S6仍未完成新viewport已读复验；S29/S30不由Simulator通过。

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
