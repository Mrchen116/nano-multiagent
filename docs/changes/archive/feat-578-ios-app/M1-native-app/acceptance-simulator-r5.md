# feat-578 — 通道剩余分支实际验收 R5

> Mode targeted；change-reviewer；`executed_base = validated_at = e99b0000c13676319797f111af7247cfcb4b9f49`。2026-10-07 01:27–01:39 +08实际390 UI（caller随后要求安全点交还修正反馈）。原地更新、无清数据；实际bundle34596BCD-233E-40C2-B014-17385541DBE9/NanoIM.app，本轮独立核对binary SHA256 `b8c78babf1bd27b6f0367a048a782be66208d7bb458648d9c141e1d78906363d`、debug.dylib `e525c9c7662fedbc067e45ae64657b2d12103ad0ac99e575abd1c12a42e5d6f5`。
> 本轮仅e2e/owned节点wt-nano-feat578-ios-runtime-11680/专用隔离通道ch_b9279f22fb2a4d9cbcb415774963b739。caller管理IM45154/Gateway runner53159，同DB/config，fixture只控制该专用Bot探针及一次stop异常，reviewer不改源码/服务/真实飞书权限，不发送外部消息。原36native绿/R4三项UI pass只保留原scope，不替代本轮通道结果。

## Verdict

**fail**：S21离线重连具体失败反馈未保持至可读，新增SIM5-01 minor；节点最后已知状态、unknown/受限/实际权限更新和本地更新时间已实际证明。caller要求安全点交还更新反馈候选，下一轮仅闭本问题并继续同一通道删除失败/重试/历史，不当作全部模拟器停验或假称已完成。物理S29/S30仍按用户后置。

## 实际旅程与边界

- J-SIM5-01 删除前历史：Chats全部→明确授权`578 Simulator Channel History`/c_0kwwnqvh。实际完整正文两条：`UX-SIM4-S21-HISTORY-01 — 这是隔离IM创建的通道历史验收素材。`和`UX-SIM4-S21-HISTORY-02 — 删除通道后这两条记录应仍可读取。`，Test User/01:22/已发送，正文空/Send disabled。caller使用真实repository种子，非真实平台收发或LLM；本轮仅实际阅读，不伪造平台历史来源。未打开未知旧c_81nb7o3h。删除后仍待实际再读及caller权威同ID/hash核对。
- J-SIM5-02 unknown：Agent→e2e详情，明确管理者Test User/在线578/单Thread→外部通道。实际期望启用、配置版本1 applied、实际连接reconnecting分开；更新时间`2026年10月7日 01:22`可读为本地时间，和R4heartbeat闭环分别记录。实际中文“权限状态暂时无法确认。可重连后重试诊断。”；前七条checks visible均unknown，不将caller八条unknown当作本轮已读第八条。展开receive_group_message实际英文说明未@Bot不进group background context，Grant recommended scope/publish app。这个展开提供实际解释，但不是实际平台scope已确认。caller明确底层WS opening handshake timeout，不能据applied写自然已连接。
- O-SIM5-01 操作器可达诊断及解决：该长通道页只显示前七checks，重连/删除在viewport外。container scroll down1、fresh图右侧drag、坐标scroll down3均无AX/实际位移；收起/展开check正常。fresh getApp确认390，中央空白drag3951400→395550仍无位移。I/O菜单真实Input仅Send Keyboard Input to Device及Keyboard/Audio/External Displays，无触摸滚动选项，Cancel退出不改设置。PageDown keyNotFound未发键，Tab无焦点/viewport变化。未点击屏幕外猜测按钮，不把这组操作器限制判原生List不可滚动。caller随后仅对实际暴露container Scroll Down执行performSecondaryAction，实图底部出现重连/删除，第八read_chat unknown及凭据节点存储/历史保留脚注；未点重连或mutation。交还后reviewer独立执行实际暴露Scroll Up/Down，均有viewport和AX变化，再继续实际原生操作；无需新包/其它UI技术，旧wheel/drag无效事实保留但障碍已解除。
- J-SIM5-03 受控group_missing：caller只切dedicated Bot探针推荐scope集合减im:message.group_msg，不改平台权限、stop disarmed。01:31在实际底部AX“重连”只点一次；上报后本地更新时间01:31、期望启用/config1 applied、实际连接中→reconnecting分开。全部八check实际可读：receive_group_message/group_history missing，其余六satisfied。展开receive_group_message显示英文功能说明、中文“未 @Bot 的普通群消息不会进入 Agent 上下文。”、grant recommended scope/publish app；向下实际辅助滚动后明确“建议权限: im:message.group_msg”与可接受group_msg/readOnly列表。实际缺失原因/影响/修复方向pass，未点击开放平台权限入口或更改真实权限。caller私有group-missing快照只辅助实际UI核对。
- J-SIM5-04 实际平台探针：caller切回actual_platform，不预设grant；01:33只点一次native重连。即时上报checks实际清空，不沿用之前六satisfied/两missing；本地更新时间01:33、中文“权限状态暂时无法确认。可重连后重试诊断。”，期望启用/1 applied与连接中→reconnecting仍分开。01:34再只读实际观察前四satisfied，收起展开并辅助Scroll Down后后四亦satisfied，完整八项新实图确认。即时unknown为空历史保留，最终actual scope complete由真正更新闭环，不依赖callerAPI改写早期观察。checks complete不等于自然WS连接，actual仍reconnecting。等待active节点离线重连前置。
- J-SIM5-05 active通道节点离线重连：caller首次SIGSTOP+90秒恢复guard，68秒bounded窗口未取得权威offline，已CONT恢复；不把未达前置当产品失败、不点击尚未offline的通道。改为caller正常退出同owned53159（真实worker stop/锁释放），17:36:13.804820Z节点权威offline，desired/history不变、fault disarmed。实际UI把连接状态改“最后已知连接状态、reconnecting”，明确“节点离线或状态已过期；此状态并非当前连接确认。”。一次native重连后底部/随后顶图均无具体错误；caller只读server日志确认前两次200权限重连、此次真实409，排除未提交假设。caller明确授权一次无副作用短重试：started17:38:46.719Z，fresh完整AX19重连与immediate AX/截图同call（1.05s），视口内容短暂下移、没有中文error可读；随后实际Scroll Up顶图（1.13s）也无“恢复在线后重试”提示，仅一般最后已知/离线状态。**具体失败原因/恢复反馈未保持至可读，SIM5-01 direct minor，S21该分支fail**；不是断言逐帧从未出现，也不将caller提出poll清error推测当独立根因证明。停止该失败分支重复，通知caller恢复节点/安排修复，原desired/config/history未删除。

## 问题与Reference Artifacts Reviewed

| ID / Severity / Relation | 期望 / 实际 | Required Action / rationale |
|---|---|---|---|
| SIM5-01 / minor / direct | spec S21失败原因/修复方向应清楚。J05两次真实离线409后，具体错误未保持到实际可读，只有一般last-known说明。即使瞬时出现也不足以让长页用户读到 | fix-implementation：后台读成功不能当作操作失败已解决；明确手动重读/操作成功/撤销时再清，复验保留与恢复。不直接采用caller推测作已证根因 |
| 删除失败/Retry/历史 | 未执行；本轮fault disarmed、通道仍active，节点offline | 继续下轮同资源真实链路；不得把fault计划、已seed历史/平台权限成功变成删除已通过 |

spec.md R8/S21、design.md P4全部通道和错误恢复及P6状态/主操作可达是本轮期望。J01–05均有真实CUA截图/AX（390/iPhone14/iOS26.4、792×1679；owner/active/unknown/missing/actual/offline）。期望与连接分开、诊断影响/建议scope、last-known及本地更新时间**match**；具体失败反馈保留**deviation**；删除失败/Retry/历史**inconclusive**。原型其余有效范围引用[UX R4](acceptance-ux-r4.md)、[模拟器R3](acceptance-simulator-r3.md)/[R4](acceptance-simulator-r4.md)、R20，不无效重跑。e99静态[code review](code-review-simulator-r3.md)/[verification](verification-simulator-r3.md)只证明映射实现，不替代失败反馈实测。caller私有scope/节点/历史receipts辅助UI结果，不是平台收发或LLM执行；不提交凭据/log/数据库/截图缓存。

## 最新合并Scenario矩阵

逐行期望来源spec.md对应S；retained引用R20及UX/模拟器R1–R4，原未失效证据保持其精确版本/scope。下轮反馈修正未装在此产物，不能在这里追写pass。

| Scenario | 最新结果 | 实际新证 / retained边界 |
|---|---|---|
| S1 四入口/返回 | pass | retained；本轮Chats→受控历史返回→Agent详情/管理实际路径，工具滚动已解决 |
| S2 输入/辅助 | inconclusive | 中文软件组合、多行/长表单/大字体、Copy/fork AX retained；本轮暴露Scroll Up/Down辅助操作实际可达；完整VoiceOver随物理设备deferred，不等于AX已覆盖VO |
| S3 登录/注册恢复 | pass | retained；原合成nano session |
| S4 暂时失败/切换 | pass | retained；本轮通道具体action反馈另由S21失败计 |
| S5 找人/群管理 | pass | retained；未读未知c81/管理真实他人 |
| S6 偏好/已读 | pass | R3离屏/Latest/cursor和真人banner点击已读retained，本轮仅专用历史阅读 |
| S7 发送/提及/历史 | pass | retained；本轮无UI/外部发送，API历史种子不算用户发送 |
| S8 不确定发送/重连 | pass | retained聊天scope，不能拿通道重连代替 |
| S9 Copy/fork/蒸馏 | pass | R2实际Copy/R3 fork取消0→确认1截至目标、正常蒸馏/离线/跨node，R4中文无binding反馈retained |
| S10 附件接收/导出 | pass | R4设备Copy Photo→真实Paste→同图待发预览→移除及旧发送接收导出retained，无host paste |
| S11 失败附件/权限 | pass | retained；本轮未新附件/upload |
| S12 过程/统计 | pass | retained真实子控件展开 |
| S13 审批提交确认 | pass现行可达范围 | Chat allow_once/Deny/等待/迟到确认retained；R3current global Work pending not-applicable子条件，非默认展开实测 |
| S14 任务/回聊 | pass | UX R3/R4语义/标题/卡片箭头retained |
| S15 Work主子历史 | pass | 精确本地轮次时间/实际历史retained |
| S16 节点创建 | pass | retained，无新创建 |
| S17 完整配置 | pass | retained，无Agent配置/Auto修改 |
| S18 冲突pending配置权限 | pass | retained，与通道action错误不同 |
| S19 Skills/心跳/Cron | pass | retained，不执行Skill/改计划 |
| S20 通道凭据 | pass | retained；本轮只读masked/已有App ID，没有输入读取secret或编辑 |
| S21 通道生命周期 | fail | J02unknown/J03limited/J04实际complete、desired/observed分开、J05offline last-known及时间pass；SIM5-01反馈保留fail；删除失败/Retry/历史仍未验 |
| S22 绑定 | pass | retained，无新绑定/恢复旧停用用户 |
| S23 节点管理 | pass | R4local heartbeat retained，本轮只caller集中退出Gateway，未保存节点配置 |
| S24 账号/语言 | pass | retained，无语言/账号修改 |
| S25 公司管理 | pass | retained，未操作真实他人 |
| S26 策略容量 | pass | retained，无策略写入 |
| S27 提醒 | pass | R3真实message.sent来源banner截图/唯一click/正确正文+readback retained；无新marker，不称3秒自然消失已计时 |
| S28 后台边界说明 | pass | retained，未承诺免费系统推送 |
| S29 真机首次安装 | inconclusive / user-deferred | 用户只后置物理设备，本reviewer未触Phone |
| S30 同网/自然到期恢复 | inconclusive / user-deferred | 不用模拟器/controlled runtime代替真实续签/自然到期 |

## 安全交还与文档同步

caller收到finding后要求交还。实际安全断点：e99 active通道、owned Gateway offline，页面顶部last-known及离线说明，故障stop disarmed；没有Delete、draft/附件/secret/字段dirty/sheet，未操作真实平台权限或外发。reviewer停止CUA，caller负责修/构建/原地更新并恢复同configGateway；下轮给新版本/PID再闭反馈并继续delete失败→Retry→历史。UI此轮未回Chats，不能虚写安全列表。

- [x] SPEC.md：无需更新，架构未改。
- [x] docs/specs/im/：由orchestrator按最终实现及Work条件校正归并；reviewer不写canonical。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

只提交本报告，保留caller toolchain-readiness/output等dirty，不push。问题1minor/direct，最高Required Action fix-implementation，needs_re_review=true。Full未接受；继续模拟器，不将物理后置扩大为其它范围豁免。
