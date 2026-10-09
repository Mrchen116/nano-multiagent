# feat-578 — 最后显示批独立窄复验 R4

> Mode targeted；change-reviewer；`executed_base = validated_at = 8e03b3e78b865b494649ac565f3c4b84aac471ca`。实际390 iPhone14 Simulator/iOS26.4、隔离IM62008、既有nano合成身份。2026-10-06 21:33–21:36 +08:00。仅TaskNode标题/卡片布局和Work折叠时间；其余证据引用R3，不重新宣称Full验收。
> 实际安装容器`75CAC481-7481-4D9C-8470-A622CABB9BAC/NanoIM.app`；独立从该安装容器核对binary SHA256 `e67e5ebf0d7b549ecb939efb69ea86a56189a5adb4ca0643e30f4acf998b6dab`、debug.dylib SHA256 `7904016942b127fd819686390eef99c80f8c2dfa64059a446100494b71229505`，与交接相符。共享HEAD包含报告提交，不冒称该HEAD树全量已验。未重装、重建、跑Simulator测试或碰物理手机。

## Verdict

**本批受影响显示范围pass；Full合并判定仍fail（必验余项inconclusive）。** 本轮0新增问题，R3的UX3-01/N8和UX3-02折叠日期已在本版本实测关闭；UX3-03设备心跳技术格式side finding原样保留，未重验。R2锁屏和R3旧版本两项minor历史不改写。

## 用户旅程体验

- J-UX4-01 Tasks→578 R15 Relations：根探索图两张无描述卡实际高度约96pt（截图约166px），Candidate A待办/已选方案、Candidate B完成均清楚可读；派生箭头从A下边至B上边，端点没有因卡缩短而悬空或穿卡。点A，sheet顶部直接显示真实名称578 Candidate A，inline标题，原巨大泛称任务详情已消失；正文名称、待办、变更说明、关系/子任务和未关联聊天说明可读。进入子图，Prepare完成→Check待办两卡同样约96pt，前置/后续箭头贴合两卡边缘，祖先路径仍Relations→A可见。返回、完成、Back实际回Tasks。
- J-UX4-02 Tasks→原生探索验收：既有带描述本地方案卡约124pt（截图约216px），名称、待办、描述摘要均保留可读，没有把描述区随无描述卡一起压缩。本轮仅当前既有System font条件；没有修改字号/语言/系统偏好，不将此结果扩大为大字体全部卡、横向手势或完整图布局。
- J-UX4-03 Agent目录→明确owned 578002（ID578001，管理者Test User）→工作轨迹：同一屏主执行空闲、节点在线、关联Compute987+654子执行和两条折叠轮次。上轮次实际显示已完成/2026年10月5日10:10，下一行结束2026年10月5日10:10；下轮次实际显示已完成/2026年10月5日02:08，下一行结束2026年10月5日02:08。两个同日轮次无需展开即可从具体本地时间区分，辅助字在本viewport可读，且保持新在前。没有依靠API日期、单测或源码推断实际画面；没有种新轮次、pending审批或新消息。

以上均实际CUA截图+AX对照。完成后Work→Agent详情→目录→Chats，空搜索、无sheet/表单/附件/待发草稿，明确交还Simulator独占UI。此轮仅只读导航，没有任何产品保存、发送、配置/成员修改。

## Reference Artifacts Reviewed

复验判据为design.md P2/P3/P6、ux-correction-r1.md、[R3独立验收](acceptance-ux-r3.md)的UX3-01/02实际偏差；未受影响原型范围引用R3，不把caller静态/compile结果代替UI。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| P2 Tasks层级/关系、P6标题密度 | 实际节点身份明确、状态可读、卡与箭头位置一致 | J-UX4-01根探索/子计划截图，真实名inline sheet | 390当前System font，无描述、待办/完成、已选 | match；N8关闭于本版本 |
| P6卡片描述层级 | 描述摘要仍可读，空卡减少留白 | J-UX4-01/02约96pt/124pt实际画面对照 | 390当前System font，既有合成无描述及有描述卡 | match已走范围；大字体未重验 |
| P3 Work摘要、P6信息可辨 | 折叠时可区分真实轮次，本地开始/结束时间 | J-UX4-03两条同屏10:10/02:08，各含结束 | 390当前System font，真实completed两轮/idle | match；UX3-02关闭 |

## 问题与闭环

| ID | Severity | Regression Relation | 实际证据 / 本轮结果 | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| UX3-01 / N8 | minor（历史） | direct | J-UX4-01/02真实标题inline、无描述96pt、有描述124pt、两种箭头布局；closed | pass | 当前受影响显示期望实际出现，保留299失败历史 |
| UX3-02 折叠日期 | minor（历史） | direct | J-UX4-03具体本地开始/结束，两轮可区分；closed | pass | 未编造请求摘要，也未机械扩义未知事件名 |
| UX3-03 设备心跳格式 | minor（retained side finding） | unrelated-existing | R3 J03原始UTC微秒字符串；本轮未触设备表单 | out-of-unit / side finding | 不属于此次两文件显示范围，不以未重跑冒称关闭 |

N1–N7、U01–U03/U06–U10的R3已证范围retained；N8由本轮关闭。U04正文长按/复制反馈、U05手势/自动分页成本及真实pending权限默认展开仍inconclusive，不能由本轮时间/卡片改动关闭。

## Scenario逐项继承与增量

来源均spec.md对应S行；前轮证据完整位于[R3的增量与R20原样历史表](acceptance-ux-r3.md)。本表明确合并状态，retained代表没有重跑。R3真实>60历史离屏77秒→单次Latest见完整marker→权威read cursor闭环保留，不以旧停用peer替代；S27仍未捕捉有效banner窗口/点击。

| Scenario | 实际证据或保留来源 | 合并结果 | 本轮边界 / 剩余 |
|---|---|---|---|
| S1 四入口与返回 | R3/R20 retained，J-UX4-01/03自然返回 | pass | 未重跑全部导航 |
| S2 输入辅助 | R3 J01/R2短候选与keyboard retained | inconclusive | 中文IME组合、VoiceOver、正文选择/复制反馈未验 |
| S3 登录注册恢复 | R20 retained | pass | 不重复登录/注册 |
| S4 暂时失败切换 | R20 retained | pass | 不新增故障注入 |
| S5 建聊群管理 | R3 J02/J08、R2 retained | pass | 原两成员/偏好/私聊名称已恢复，本轮不修改 |
| S6 偏好/已读 | R3 J07当前viewport闭环 retained | inconclusive | S27前台跳转仍缺，不扩大整体通过 |
| S7 发送提及历史 | R2唯一请求/回复、R3 J07/J08 retained | inconclusive | 新AND中文组合仍缺；不再发送或请求marker |
| S8 不确定发送重连 | R20 retained | pass | 不重复回执故障 |
| S9 复制fork蒸馏 | R3代码clipboard证据/R20 retained | inconclusive | 正文/fork/离线/跨Gateway边界保留 |
| S10 附件接收导出 | R3 J01/R20 retained | inconclusive | 主动粘贴仍缺且明确禁止host paste |
| S11 附件失败权限 | R20 retained | pass | 本轮无上传/发送 |
| S12 过程统计结果 | R20 retained | pass | 限既有真实执行与受控缺失统计 |
| S13 审批确认 | R20原通过保留，R3新默认展开范围 | inconclusive | 当前无真实pending，不种伪审批；默认展开未验 |
| S14 任务与回聊 | R3 J04 retained + J-UX4-01/02 | pass | 本轮关闭显示N8，不重跑回聊或任意深层图 |
| S15 Work主子历史 | R3 J05/R20 retained + J-UX4-03 | pass | 折叠日期关闭；不扩张自然100+过程或pending |
| S16 节点创建 | R3 J06/R20 retained | pass | 无本轮创建 |
| S17 完整配置 | R3 J06/R20 retained | pass | 无本轮保存 |
| S18 冲突pending权限 | R20 retained | pass | 既有配置冲突证据不替真实Work pending默认展开 |
| S19 Skills心跳Cron | R20 retained | pass | 不改计划或删除 |
| S20 通道凭据 | R3普通草稿/R20凭据旅程 retained | pass | 未输入/保存secret，无外部平台操作 |
| S21 通道生命周期 | R20 retained | inconclusive | natural stop异常重试、受限/未知权限、真实平台shadow仍缺 |
| S22 绑定 | R20 retained | pass | 无新绑定 |
| S23 节点管理 | R3 J03/J05/R20 retained | pass | 不重复暂停/恢复节点 |
| S24 账号/语言 | R3 J03/R20 retained | pass | 无账号保存/语言修改 |
| S25 公司管理 | R20 retained | pass | 不操作审批或未知成员 |
| S26 策略容量 | R3 J03/R20 retained | pass | 无本轮保存 |
| S27 提醒前后台 | R3 J09/R20 retained | inconclusive | banner有效画面及点击未证；不判为产品fail、不再种marker |
| S28 后台边界 | R20 retained | pass | 不宣称保证后台推送 |
| S29 真机首次安装 | R3/R20 retained | inconclusive | 本reviewer未碰手机，caller签名安装不替独立物理操作 |
| S30 同网续签恢复 | R3/R20 retained | inconclusive | 拔线同网刷新/自然到期恢复不能由Simulator或构建替代 |

## 安全交还与文档同步

21:36前回Chats并交还。本轮没有启动/停止服务，无本轮fixture写入；caller集中管理的进程、数据和物理手机均未碰。只提交本报告；R3已单独提交`afa6cc44c`，其实际版本仍299。

- [x] SPEC.md：无需更新，跨包边界未改。
- [x] docs/specs/im/：最终显示增量由orchestrator校正归并，reviewer不代写；既有未验范围保留。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。
