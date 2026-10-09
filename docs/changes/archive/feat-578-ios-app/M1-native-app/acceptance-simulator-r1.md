# feat-578 — 模拟器剩余分支有界补验 R1

> Mode targeted；change-reviewer；2026-10-06执行，22:32 +08:00交还。产品`executed_base = validated_at = 8e03b3e78b865b494649ac565f3c4b84aac471ca`；报告前共享HEAD `5d3c0911b`仅后续文档。390 iPhone14/iOS26.4 Simulator，隔离IM62008、nano及明确合成fixtures；未重建/重装、未切其它模拟器/生产。远端新合并范围由caller独立核对，本报告不冒称覆盖另一远端产物。
> 安装容器`75CAC481-7481-4D9C-8470-A622CABB9BAC/NanoIM.app`两项独立复核：binary SHA256 `e67e5ebf0d7b549ecb939efb69ea86a56189a5adb4ca0643e30f4acf998b6dab`；debug.dylib `7904016942b127fd819686390eef99c80f8c2dfa64059a446100494b71229505`。与[R4](acceptance-ux-r4.md)同产品版本。

## Verdict

**fail：模拟环境尚未完整测完。** 本轮关闭真正中文组合输入及跨设备蒸馏限制两个子范围；保留已证正常旅程，未重复整App。仍有操作器/模拟设备限制、真实pending前置未出现和来源banner未捕获；它们不是已确认产品失败。新增1项minor体验观察（离线蒸馏英文含混回执）。真机按用户最新安排deferred，外部平台自然分支另列deferred，不混作模拟器通过或失败。

## 实际产品旅程

- J-SIM-01 中文软件键盘：明确纯真人direct c_vpsj9y6q，进入空composer；Simulator I/O→Keyboard→Toggle Software Keyboard，从已有English切已有简体拼音，不新增系统输入法。实际点按软件n/i/h/a/o，composer出现下划线nihao未提交组合和“你好”等候选，未选择/发送。明确点“你好”，中文准确成为草稿；点键盘换行，再点n/i/h/a/o，实际为两行“你好\nnihao”（后一行下划线组合），候选保持、无自动消息或目标选择、发送按钮和composer均在键盘上方可见。手选候选后全选删除，Send禁用；最后恢复English US及软件键盘隐藏。未发送该中文草稿，不用host paste、中文typeText或API文本冒称IME组合。
- J-SIM-02 辅助/正文操作：工具文档仅click/drag/scroll/selectText及实际AX secondary动作，无按住/长按API。明确Reader阅读消息右键一次无菜单；selectText明确报`Cannot select text for an element that does not support a settable selected text range`，消息AX只有Cancel，无copy/fork secondary动作。有限尝试后停止，不猜动作名、不重复无效长按。Simulator Features无VoiceOver选项；通过主屏搜索打开本模拟设备设置→辅助功能，视觉列表实际只有悬停文本、显示与文字大小、动态效果、朗读内容，没有VoiceOver入口，未改这些偏好。普通AX名称可读不等于VoiceOver旅程完成。R3代码Copy精确clipboard证据retained，正文选择/复制反馈及完成回复fork仍inconclusive。
- J-SIM-03 真执行前置：caller授权owned global 578002/ID578001（详情管理者Test User），从Agent发消息入口单次发送唯一UX-SIM-S13-20261006，请仅web_fetch https://example.org/一次、等待权限、拒绝则结束。实际请求气泡已发送；转同Agent Work，最新轮已完成，开始22:22/结束22:23、主执行空闲。展开实际web_fetch调用完成，回复明确请求已获允许、抓取成功、只报告到请求聊天，未产生待确认卡；reviewer没批准/Deny或改规则。caller后续只读确认其当前Auto前置不产生人工卡。本轮不能证明Work待确认默认展开，不重发、不换权限造pending。已发生的是一次真实UI请求及执行，不是API伪造LLM/pending。
- J-SIM-04 图片主动粘贴边界：本次UX群c_zia690ag受控橙色图片A实际打开预览，画面仅图片及完成，无可执行Copy/Share入口；当前操作器也无长按。未取得模拟设备内图片pasteboard，不执行host paste或Simulator Edit的主机剪贴板传输。结束预览，composer空、没有附件。本轮只补有限入口检查，主动图片复制/粘贴仍inconclusive，不把R3照片ready缩略/取消/移除及R20附件导出旧通过当该分支完成。
- J-SIM-05 蒸馏限制：caller明确授权离线owned ios-binding-check（wt-feat578-bind-check）；目录→详情实际Test User、单Thread、离线及需设备恢复在线说明。从发消息入口建立空测试私聊，未发送/恢复节点。Chats整理会话知识，选该新离线来源及caller明确允许的Skill distill · e2e-peer来源，执行Agent只有ios-binding-check；生成实际回执“来源必须属于同一设备。”，两选项/执行选择保持，无草稿和消息，跨Gateway guard子范围pass。取消主节点来源只留离线空chat，生成实际英文`selected Gateway did not return a distill prompt`，未产生草稿；无历史前置与离线两条件不能由该回执区分，不主张有效历史离线分支已通过。明确取消退出，未使用列表中的未知e2e旧私聊，没打开c_81nb7o3h。
- J-SIM-06 来源提醒：我的→提醒与安装实际前台提醒on，只读退出，Reader会话未静音。caller初始fixture body遗漏sender，第一次单POST在14:26:31.354 UTC返回422，未创建消息，保留历史，不算产品fail。caller纠正必填sender并权威确认marker0条后，按同一marker唯一合法POST（含synthetic Reader u_kita0969），201创建f2db0509c6904c0395d6d92bcf22222d，sent14:30:06.943 UTC。实际连续60次完整AX采样14:30:01.239–14:30:25.762，已覆盖投递及3秒窗口，均没有Reader来源字符串；没有在窗口逐帧截图，不能排除AX不呈现overlay，因此banner画面/点击仍inconclusive，不能从AX缺失断言产品未显示。停止后我的Chatsbadge6（此前5），Chats明确Reader行22:30/唯一UX-SIM-S27-ace8c1cce3/unread1；进入已知direct实际见该完整正文，返回该未读消失。列表送达/读到正文不替代banner点击。合法投递后不再发送marker，也不修改提醒时长。

J-SIM-06控制sender是明确测试API，非reviewer UI发送或LLM。私有0600 receipt `/tmp/nano-feat578-sim-s27-receipt.json`保存422历史、合法POST一次、id/绝对时间与观察边界，不入repo。该控制投递与J03唯一真实UI请求分开计。

辅助唯一性已只读核对：`/tmp/nano-feat578-sim-s13-receipt.json` final_requests仅一条fa9c59cf3ed24b00b18ad9cb044860fb/c_ts2skl8m；真实Work最新turn_3c5acf10d8dbf736 completed、22:22:50→22:23:04，没有pending。S27合法receipt一次201/唯一上述message_id。caller另只读确认离线空私聊c_wdnb5vv5。caller协议核查报告该消息实际为message.sent/message.delivered事件，现App提醒接线不同；这是caller辅助诊断，不替本reviewer未捕捉到banner的UI事实，也不将之后修正混入8e。

## Reference Artifacts Reviewed

spec.md S2/S7/S9/S10/S13/S27、design.md P1/P3/P5/P6、[R3](acceptance-ux-r3.md)/[R4](acceptance-ux-r4.md)及R6蒸馏正常旅程。未失效R20完整历史证据继续引用R3原样表；本轮不是Full重跑。

| Reference / contract | 实际证据 | Viewport / state | 对照结论 |
|---|---|---|---|
| P1/P6输入安全区，S2/S7组合不自动发送 | J01下划线拼音→明确候选→换行→第二次组合、清空 | 390当前字号、真实简体软件键盘 | match该子范围；VoiceOver/正文选择未证 |
| P3真实权限/Work默认展开 | J03一次真实执行完成，未出现pending | owned global，同版本Work | inconclusive前置未出现；不造pending |
| S9限制及原因说明 | J05不同node实际中文拒绝；离线空来源英文回执 | 390整理页，无草稿/消息 | crossGateway match；离线原因体验deviation/有效历史未证 |
| P5前台来源提示/点击 | J06绝对时间AX窗口、后续列表未读与完整阅读 | 我的前台，提醒on，合成Reader未静音 | banner实图/点击inconclusive，列表送达已证 |

## 问题与阻挡分类

| ID / 类型 | Severity / Relation | 期望与实际 | Recommended Action / 理由 |
|---|---|---|---|
| SIM-01 离线整理回执 | minor / direct | S9中文明确原因；J05真实英文Gateway未返回prompt，不能区分离线/无历史 | fix-implementation：提供准确离线/不可用说明；不伪造有效transcript或将非空错误当成功 |
| 操作器/模拟设备 | 非产品finding | J02正文selectText不支持、无长按；设备无VoiceOver入口；J04没有设备内Copy动作 | 保留inconclusive；不使用主机paste或猜动作绕过 |
| 实际前置 | 非产品finding | J03真实普通Auto执行已完成，没有人工pending | 保留默认展开未验，原审批旅程retained |
| 提醒证据 | 非产品finding | J06合法唯一投递窗口AX未捕获来源、没有窗口连续截图 | 保留inconclusive；不把未捕获判产品fail，不重复成功marker |

caller准备后续修正不属于本8e安装实测。R4已关闭N8/日期范围retained，设备心跳原始日期minor side finding继续保留；本轮不追逐其它偏好。

## 最新合并Scenario矩阵

来源均spec.md对应S行；retained来自R3/R4/R20，注明没有重跑。模拟器内仍未完成S2、S6/S27、S9、S10、S13增量；S21外部自然平台条件和S29/S30真机另行deferred。既有pass不表示本轮再次验证。

| Scenario | 最新结果 | 本轮增量 / 精确保留边界 |
|---|---|---|
| S1 四入口/返回 | pass | retained；本轮主屏→设置只读→Nano→Work/Chats自然返回 |
| S2 输入/辅助 | inconclusive | 中文软件组合/两行安全区J01pass；VoiceOver不具入口、正文选择/复制J02未证，其余长表单/字号retained |
| S3 登录/注册恢复 | pass | retained；不重复登录/注册 |
| S4 暂时失败/切换 | pass | retained；无本轮新故障注入 |
| S5 找人/群管理 | pass | retained；J05只新增授权离线空私聊，无用户数据删除 |
| S6 偏好/已读 | inconclusive | R3真实>60离屏77秒→Latest阅读cursor闭环retained；J06新来源列表unread→见正文→消失，banner点击仍缺 |
| S7 发送/提及/历史 | pass | R2直接@/slash及唯一42回复、R3分页/身份、R20配置分界等retained；新增中文组合AND由J01关闭，未重复Agent目标发送 |
| S8 不确定发送/重连 | pass | retained；422控制fixture请求不冒充UI不确定发送分支 |
| S9 Copy/fork/蒸馏 | inconclusive | R3代码clipboard/R6正常草稿retained；J05跨Gateway拒绝pass；正文/fork操作器阻挡，离线有效历史未证/回执minor |
| S10 附件接收/导出 | inconclusive | R3 ready图片/R20导出retained；J04仅预览入口检查，主动设备内图片paste未证 |
| S11 失败附件/权限 | pass | retained；本轮无上传/发送 |
| S12 过程/统计 | pass | retained；J03真实单次completed不扩大所有工具/指标 |
| S13 审批提交确认 | inconclusive | R20 allow_once/Deny/等待/恢复原通过retained；J03无真实pending，新增Work默认展开未验 |
| S14 任务/回聊 | pass | R3语义/祖先及R4 N8 closure retained |
| S15 Work主子历史 | pass | R4时间显示/R20受控分页retained；J03只新真实completed观察 |
| S16 节点创建 | pass | retained；无本轮Agent创建 |
| S17 完整配置 | pass | retained；不改/保存权限规则、Agent配置 |
| S18 冲突pending配置权限 | pass | retained；不替代S13真实Work人工卡 |
| S19 Skills/心跳/Cron | pass | retained；不删/改计划 |
| S20 通道凭据 | pass | retained；未输入或保存secret，无外部换密钥 |
| S21 通道生命周期 | inconclusive / external deferred | 自然stop异常重试、受限/未知权限、真实平台shadow缺口retained；不因模拟器任务操作真实飞书 |
| S22 绑定 | pass | retained；无本轮新绑定/恢复旧节点 |
| S23 节点管理 | pass | retained；本轮owned离线状态只读，不启停节点 |
| S24 账号/语言 | pass | retained；只恢复设备键盘语言，不改变产品账号/语言 |
| S25 公司管理 | pass | retained；不注册/停用/审批真实他人 |
| S26 策略容量 | pass | retained；不保存策略 |
| S27 提醒 | inconclusive | J06合法唯一源已投递/列表阅读；banner图/点击未证，后台回App既有范围retained |
| S28 后台边界说明 | pass | retained；J06提醒页只读on与说明，不宣称保证后台推送 |
| S29 真机首次安装 | inconclusive / user-deferred | 用户要求先跳过真机；本reviewer未触物理手机 |
| S30 同网/自然到期恢复 | inconclusive / user-deferred | 用户要求先跳过真机；不由模拟器/构建替代拔线续签及自然到期 |

## 安全交还及文档同步

22:32 +08:00回Chats空搜索、无sheet/蒸馏/附件/消息draft，UI已交还caller。键盘恢复English US与隐藏软件键盘；设置辅助功能未修改。合法控制消息已读，原阅读素材/离线空私聊保留，不删除数据。只发送J03那一条真实UI请求，没有凭据/生产/物理手机操作。只提交此报告，不提交output/或caller其它dirty文档。

- [x] SPEC.md：无需更新，架构边界未改。
- [x] docs/specs/im/：由orchestrator根据最终实现校正归并；本reviewer不代写或提前写通过。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。
