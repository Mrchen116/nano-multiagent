# feat-578 — 模拟器受影响复验 R4

> Mode targeted；change-reviewer；`executed_base = validated_at = aa46dbf383b8c450d5d87903963270de39617dee`。2026-10-07 01:19–01:24 +08:00实际390 UI。工作树在UI结束后已由caller前进至e99b0000c（通道文案），本报告仅验原aa46安装产物，不将后续源码视作已验。
> 390实际安装DDBEDE3A-93E2-4108-B4F3-30D9D68442C2/NanoIM.app；本轮独立核对binary SHA256 `936cf36be412e89d01e9867fb13c8d9e76bf37f98a546dbba8e828f7a9c75360`、debug.dylib `2b5a21add08a0ac701cad83b8b0422902fcf49ec73631491098644fc82d38f92`。caller原地更新、保留fixture数据，IM62008同库/config；本reviewer未构建、重装、跑测试或管理runtime，未触430/手机/主仓/生产。

## Verdict

**fail：Full仍有未完成范围；本轮三个受影响模拟器分支pass。** 实际闭环设备内图片Copy→系统Paste→可辨认待发预览→移除，关闭R3 S10未证入口；关闭SIM3-01裸英文缺少恢复方向；owned设备心跳改为可读本地日期时间。无新增产品finding。S21继续下轮受控真实通道链路，不能因已准备fixture或静态复审pass而改判。仅物理设备范围按用户后置，其余模拟器工作继续。

## 实际产品旅程

- J-SIM4-01 主动设备内图片粘贴：设备Home→设备搜索Photos→上轮同一第二花卉照片（白黄色花、绿红植株/沙地实图）→Share→实际AX“拷贝照片”，点击后share sheet关闭。设备Home→Nano→明确受控Reader/c_vpsj9y6q空composer。聚焦并double-click，实际系统菜单同时显示Paste、AutoFill，AX明确Paste。只点击这个设备内Paste，没有host paste、Simulator剪贴板传输或粘贴快捷键。实际出现`photo-1E58AF9C.jpg`按钮、可辨认同花卉缩略图、移除附件按钮，空正文但Send可用；未点击Send。点击该待发图片打开“图片”大预览，同花卉/景物清晰可辨，完成返回待发状态。点击“移除附件”，缩略图和两个附件AX项消失，composer继续空placeholder，Send恢复disabled。最后返回Chats。主动图片粘贴、识别/预览/移除pass；不宣称本轮做了粘贴图片发送、网络上传或新的导出，原有实际图片发送/接收/导出证据retained。
- J-SIM4-02 空旧来源恢复：Chats全部→整理会话知识→实际来源列表第二个同名旧`Skill distill · e2e-peer`（全列表第六switch，R3前第一旧空来源），不是本轮前新增的最顶端空chat；执行e2e-peer、范围Agent→生成待发草稿。首次同名AX click报element invalidated/multiple matches，未改变选择；fresh实图后对该唯一屏幕开关坐标点击成功，选择1明确可见。实际生成返回中文红色说明：“来源会话暂无可整理的执行记录。请选择已有 Agent 回复的会话，或先在该会话完成一轮对话。”，来源开关仍1、执行Agent仍e2e-peer、范围仍Agent，未进入新chat/未生成新draft。取消回Chats。关闭R3 SIM3-01；同名来源AX操作者定位问题不冒称产品丢失选择。正常既有binding生成、离线说明与跨Gateway拒绝由R3/R1有效证据retained，本轮不重复生成或执行Skill。
- J-SIM4-03 owned设备时间：我的→我的设备→明确578/节点wt-nano-feat578-ios-runtime-11680/在线/5Agent→详情。真实AX与截图显示“最近心跳、2026年10月7日 01:24”，设备App时钟1:24，一致为本地日期时间；不再原始UTC串。设备状态在线、5Agent、配置别名578、relay/report均on；Save/放弃修改disabled。本轮未编辑或保存任何字段。依次返回设备列表→我的→Chats全部。关闭旧heartbeat UTC side minor的显示范围，不将通道更新时间混为同一实测。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison |
|---|---|---|---|---|
| spec.md S10；design.md P1/P6 | 图片待发可辨认、可预览/移除；原生主动粘贴入口 | J01实际系统Paste菜单、花卉缩略图、同图大预览、移除后empty/Send disabled的CUA截图与AX | 390/iPhone14/iOS26.4，792×1679；已有受控Reader聊天，空正文 | match；只闭本轮待发分支，发送/接收/导出retained |
| spec.md S9；design.md整理知识失败反馈/保选择 | 来源不可用时明确原因/恢复方向，保留选择、不得假造草稿 | J02完整中文反馈、选中旧来源/e2e-peer/Agent仍在，取消回原列表 | 同viewport；empty session binding/error | match；SIM3-01 closed |
| spec.md S23；design.md P6管理状态 | 设备详情时间和状态可读 | J03本地2026年10月7日01:24、在线、5Agent；Save disabled | 同viewport；owned node未编辑 | match；heartbeat side minor closed |
| S21相关通道 | 停止失败/重试、权限诊断、更新时间及节点离线恢复原因 | 本轮未进入通道；caller后续版本/runner交接待实际验收 | 不用静态/fixture准备当实图 | inconclusive，继续下轮 |

参考[模拟器R3](acceptance-simulator-r3.md)及其逐项源证据、R20、UX R3/R4、[当前Work范围核对](verification-simulator-scope-r1.md)。caller36原生green（26 XCTest+10 Swift Testing）及独立旧入口red仅辅助，不能替代J01。后续e99静态[code review](code-review-simulator-r3.md)/[verification](verification-simulator-r3.md)只说明channel_node_offline409恢复方向已修，不证明装包/实际UI。

## 问题清单

| ID / Severity / Relation | Actual / disposition |
|---|---|
| SIM3-01 / minor / direct | **closed**：J02中文明确历史不可整理原因，给已有回复/先完成对话恢复方向，保选择；R3旧英文事实保留 |
| R3 heartbeat UTC / minor / side | **closed（心跳显示）**：J03实际本地日期时间；通道更新时间尚未走，不扩大 |
| R3 S10未证入口 | **closed（实际待发粘贴）**：J01设备Copy→实际Paste→同图预览→移除；无host clipboard |
| S21 / remaining acceptance | **inconclusive**：未知/缺失/受限权限、真实stop失败→重试/历史保留和409节点离线恢复待后续实际候选，非本轮新增finding |

## 最新合并Scenario矩阵

每行期望来源为spec.md对应Scenario；未失效行明确retained自R20、UX及模拟器R1–R3，不重跑也不宣称本轮新证。S10由本轮关闭；S21继续，不被用户真机后置吞掉。

| Scenario | 最新结果 | 证据 / 边界 |
|---|---|---|
| S1 四入口/返回 | pass | retained；J01–03实际返回Chats，无新导航阻碍 |
| S2 输入/辅助 | inconclusive | R1真中文软件组合/多行，R2正文Copy，R3具名fork/子控件AX retained；完整VoiceOver需物理设备，按用户deferred，不把AX=VO |
| S3 登录/注册恢复 | pass | retained；本轮继续原合成session |
| S4 暂时失败/切换 | pass | retained，未新注入故障 |
| S5 找人/群管理 | pass | retained；本轮未改群、删除数据或读取未知c81 |
| S6 偏好/已读 | pass | R3离屏77秒/Latest/cursor及真人来源banner点击已读retained；本轮无新增incoming |
| S7 发送/提及/历史 | pass | retained；本轮不发送图片/草稿，不算新LLM执行 |
| S8 不确定发送/重连 | pass | retained，不用fixture准备替代新重连证据 |
| S9 Copy/fork/蒸馏 | pass | R2复制、R3取消0→确认1fork截至目标/正常草稿/离线、R1跨设备guard retained；J02中文恢复关闭minor |
| S10 附件接收/导出 | pass | J01新证设备主动Copy Photo→系统Paste→待发同图→大预览→移除；文件/照片发送接收导出旧证据retained，本轮无图片发送 |
| S11 失败附件/权限 | pass | retained；本轮不触额外权限/网络上传 |
| S12 过程/统计 | pass | R3第一reply实际子控件展开retained |
| S13 审批提交确认 | pass现行可达范围 | Chat真实allow_once/Deny/等待/迟到确认retained；R3明确current global Work pending not-applicable子条件，非默认展开实测 |
| S14 任务/回聊 | pass | UX R3语义/R4标题卡片箭头retained |
| S15 Work主子历史 | pass | retained精确本地轮次日期时间/受控历史 |
| S16 节点创建 | pass | retained，本轮无创建 |
| S17 完整配置 | pass | retained，无权限/配置mutation |
| S18 冲突pending配置权限 | pass | retained，不混同Work人工pending |
| S19 Skills/心跳/Cron | pass | retained；J02不执行Skill或改计划 |
| S20 通道凭据 | pass | retained，不输入/保存secret |
| S21 通道生命周期 | inconclusive | 当前尚未走新runner；下轮继续真实可控链路及权限/历史，旧证据保留 |
| S22 绑定 | pass | retained，不恢复离线节点/新增绑定 |
| S23 节点管理 | pass | retained；J03本地心跳显示新证，未保存配置 |
| S24 账号/语言 | pass | retained，不改变账号/语言/keyboard偏好 |
| S25 公司管理 | pass | retained，未管理真实他人 |
| S26 策略容量 | pass | retained，不保存策略 |
| S27 提醒 | pass | R3真实message.sent banner图/唯一点击/正确全文/已读retained，本轮无新marker，不声称3秒自然消失计时 |
| S28 后台边界说明 | pass | retained，不宣称保证系统推送 |
| S29 真机首次安装 | inconclusive / user-deferred | 仅物理设备按用户后置，本reviewer未触Phone |
| S30 同网/自然到期恢复 | inconclusive / user-deferred | 不以模拟器代替拔USB/续签/自然到期 |

## 安全交还与文档同步

01:24 +08实际回Chats/全部筛选/空搜索；Reader待发图片明确移除、正文空、Send disabled后退出；知识整理取消无草稿，设备字段未编辑，无附件/sheet/表单dirty。UI交还caller可更换下一通道候选，停止本轮GUI，不提前写其UI结果。不删除测试记录、不保存secret、不操作生产或Phone。

- [x] SPEC.md：无需更新，架构未改。
- [x] docs/specs/im/：最终实现及Work条件由orchestrator校正归并，reviewer不代写canonical。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

只提交本报告，保留caller新报告/output，其余文件不stage，不push。本轮new issues=0，三个targeted范围pass；Full verdict fail、needs_re_review=true，继续S21实际模拟器验收；物理deferred独立保留。
