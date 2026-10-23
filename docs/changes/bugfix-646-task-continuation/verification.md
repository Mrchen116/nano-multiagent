# Verification Report: bugfix-646-task-continuation

> Validation snapshot: `e7f8249d26287dbaccde298365323c70e3cd5fc8 → 6223412809e5bdb98a741402d913e33589d686bc`

## Round 1 — full + corrected-delta

- 独立 verifier：`/root/static_review_646`，使用 `change-verifier`；未参与实现。
- verification_mode：full，附全部 corrected-delta reconciliation 及 diff 对外行为核对。
- 时间：2026-10-23 23:28 +08。
- verdict：fail；**0 CRITICAL / 2 WARNING / 0 SUGGESTION**。
- outcome：**implementation-mismatch**。
- requires_full_verification：false；本轮已覆盖 full，无需因发现问题再扩大全量范围。修复后应按实际共享影响决定复验范围。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现落点均存在；拒绝作用范围有两处缺陷；产品旅程/最终 CI 由对应 gate 待回填 |
| Correctness | waiting/反馈/模式分支与契约一致；部分 Task 拒绝操作未满足独立推进及停止无效重复 |
| Coherence | IM/PA/integration 职责与 DSH 公开 API 边界符合；design 决策 5 存在实质偏离 |

两项 WARNING 修复前不能判定本 unit 静态验证通过。产品旅程尚未返回及 CI 正在执行属于证据待补，未计为实现缺陷；本报告不宣称 M1 已整体完成。

## Completeness

- M1-continuation 是唯一 milestone（`design.md:84`）。IM cap/反馈、PA 最小责任字段、integration admission/提示、生成源与资产及其回归均有实现，没有第二 Agent Loop、运行时 fork/private import、Task 业务状态镜像或新调度器。
- 可信复用证据：`implementation.md:9-11`，7 文件 34 测试绿、红测具体失败、构建/typecheck 已通过；额外 Codex effort 生命周期 8 测试绿。读取 `/tmp/nano-646-narrow-final.log` 复核 7/34 汇总；未重复全量运行。
- 本轮补充两个真实 driver 方法的最小故障入口复现，版本/命令/输入及精确输出见 `code-review.md`。现有 native Task 测试仅覆盖直接 update_task 的局部作用范围，未覆盖依赖端点与非责任父节点子树删除，故未挡住本次两个缺陷。
- caller 负责最终 CI，独立产品 reviewer 负责 `design.md:78` 的真实模型旅程及自建服务清理。本轮不运行或接管其服务，不采纳其他 worktree 的日志为证据。
- Prototype / Reference：N/A，无客户端布局变更。catalog.tsx 仅模型文案生成源；生成 Skill 和 integration prompt 已同步模式规则。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| incident:47-53 多任务、事实优先、合法替代、验证结果 | integration `task-execution.ts:148-160`；feature `task-graphs.ts:14-19` | native Task 执行/withdrawal/schedule 测试；真实模型旅程另 gate | 提示覆盖；独立责任受 W1 影响 |
| incident:55-64 首次/续期一小时、到期重估、提前恢复 | IM `task-graphs.ts:500-524,804-812`；feature `task-graphs.ts:14-16`；既有 Schedule/watch | IM Task `:38-56,71-91`，native Task `:307`；正常模型重估另 gate | 静态 covered |
| incident:66-71 固定聊天与 Agent 派发反馈 | IM `task-graphs.ts:815-825`；feature `task-graphs.ts:23-38`；PA `global-agent.ts:440-460` 透传 | IM `:58-69` receipt replay；task-feedback `:7-50` waiting/in_review/done、unknown 后确认 | covered；实际聊天可见性另 gate |
| incident:73-75 Schedule/写入/send 失败诚实性 | feature `task-graphs.ts:15,17,31`；既有 PA publication/request_key | IM 原子与 stale revision 测试、task-feedback unknown 不注入成功提醒；未改 PA publication 状态机 | covered，实际未知交付处理复用旧链路 |
| incident:79-81 参数可修正、读取/flush/model 故障停止与恢复 | integration `task-execution.ts:47-82,176-215` | task-feedback 第一次 ok:false 后继续；task-recovery source/flush；task-execution throw/finish/config/new-input | covered；不改业务 phase |
| incident:83-85 拒绝不因无关唤醒/同名成功清除、独立工作继续 | integration `task-execution.ts:34-44,116-137` | native automatic/human deny、heartbeat 不同动作、图 revision/本节点更新、同图独立 B；本轮作用范围复现 | **偏离：W1/W2** |
| incident:87-91 Global 私有收尾、SingleThread 静默 | integration `global-mode.ts:17-19`、`task-execution.ts:149-151`、intelligent-ui；生成器/Skill/catalog | 原 native communication 及 task-feedback final step；静态逐源检查 | covered；无空响应策略变化 |
| 停止、不重开、无新授权（贯穿场景） | 既有 PA durable stop；integration block/pre-step 与 Task prompt | native stop fence/restart、withdrawn A + B、schedule replacement | covered；本次不豁免审批 |

## Coherence

| design 决策 | 遵守？ | 证据 |
|---|---|---|
| 1 事实推进、Global 结语与共享文案按模式区分 | 是 | driver prompt、global-mode 单线程显式 sentinel、catalog 与生成物一致 |
| 2 IM 双阶段一小时 cap，普通 Schedule 不加限 | 是 | 新校验只在 prepareWaits 与同步事务；超限在 save/receipt 前失败回滚 |
| 3 提交事实反馈，固定聊天，最终 tool result 后 deferContext | 是 | feedback 生成于 IM 规范化 wait 后/save receipt 前；integration 仅 ok:true apply 注入；公开 DSH ToolRunContext.deferContext |
| 4 精确动作拒绝与运行错误分离、普通参数可修 | 是 | actionKey 参数与 tool 名组成，成功只删相同 key，普通输入不清 denied，error/source/flush 分开；原生 turn-stopping 文档限定正常停止边界 |
| 5 局部责任抑制，其余 doing 继续；未知影响不能假装无影响 | **否** | W1/W2；未完整解释 task_graph 各动作作用范围 |
| 5 节点 updated_at 排除图 revision | 是 | product-contracts、PA 保留字段，IM list 节点时间；IM `task-execution.test.ts:20` 与 native paired regressions |
| 6 复用幂等/发送状态与原生 Schedule，不改 Task 状态假装恢复 | 是 | PA publication 未变，feedback 提醒明确 unknown/replay/较新状态；无额外 timer 或持久 phase |
| Changelog 同模型 supported effort、保留独立审查 | 是，限 Codex 路径 | `policy/codex.ts:105,172-203`；未改 reviewer identity、证据供应、预算、parser 与失败分流。默认 Nano classifier 的同类修订由 caller 另补，不在当前固定版本结论内 |

### Prototype / Reference Contract

N/A。无 UI must-match；未以主观视觉判断代替独立产品验收。

## Issues

### CRITICAL

无。

### WARNING

- **W1 / CONFIRMED：依赖操作拒绝会停住同图独立责任。** 契约：`incident.md:52,85`、`design.md:46`。实现：integration `task-execution.ts:119-125` 未解析 dependency from/to。真实 IM 操作 `task-graphs.ts:285-294` 能确定 A/B 端点；driver 反而因 ids 为空持有整图 A/B/C，C 没有后续自动 admission。修复动作定位并为同图独立 C 增加长期回归，保护持续推进公开行为。精确复现见 code-review 第一项。
- **W2 / CONFIRMED：非责任父节点子树删除拒绝后没有屏障。** 契约：`incident.md:77-85`、`design.md:44-46`。实现：同一筛选器用父 node_id 精确匹配直接 doing 子任务，结果为空便不记录 denied；真实 delete 会递归子树（IM `task-graphs.ts:718-738`）。拒绝后未变化的子任务立即再次获得 automatic admission。对最小投影无法核实的子树影响保留合适屏障，不能把未命中当作无影响；增加对应回归。精确复现见 code-review 第二项。审批仍会执行，不声称已绕审或发生删除副作用。

### SUGGESTION

无。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Task:5-10 当前事实、可验证结果及合法独立工作 | driver prompt/feature guidance | native continuation/withdrawal + 本轮 W1 复现 | implementation-mismatch |
| Task:12-17 首次/续期 cap、普通 Schedule 不限 | IM 双阶段校验及事务回滚 | IM cap/new/renew/unchanged graph，native 一小时 Schedule | aligned |
| Task:19-24 固定聊天、实际反馈、无重复/未知诚实性 | committed feedback + receipt，deferContext，原 publication | IM child/replay/later pause；native 三终态/unknown/final step | aligned，正常真实旅程另 gate |
| Task:26-34 失败屏障与新输入、独立工作 | error/source/flush/denied 分离；task_graph scope 提取有缺口 | native deny/recovery + W1/W2 直接复现 | implementation-mismatch |
| Global:5-14 空响应恢复保持、非空私有收尾、SingleThread 分支 | global-mode、shared guidance 与生成源/产物 | 代码逐源及 native final-step；未改空响应恢复实现 | aligned |

### Uncovered Observable Behavior

检查完整 diff 后，新增的 `updated_at` 最小投影与 mutation `feedback` 已被 design:54-55 及 Task delta 的责任恢复/固定聊天行为涵盖；不是独立用户设置或新发言旁路。Codex reviewer effort 参数从硬编码 low 改为同模型声明能力选择，是本 unit 实施中新发现的请求兼容性修复，已写 design Changelog 与 implementation:11；符合 current `agent-capabilities.md:225-240` 的按已选模型分类、失败不换模型既有保证。无需将 low/default/首档这一内部选择算法新增为用户契约，也不能据此声称全部 Nano 规则已修复。未发现其他需要补写却遗漏的用户可观察契约。

Outcome: **implementation-mismatch**。

本轮只新增本 unit 的 code-review.md 与 verification.md，无源码/测试/配置/设计改动，也未启动需清理的服务。独立复现临时脚本在 /tmp；其输入和结果已持久记录于报告。
