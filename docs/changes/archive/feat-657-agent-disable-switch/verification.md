# Verification Report: feat-657-agent-disable-switch

> Validation snapshot: `797b225df → 935510058d338866e2310f54c1804d6120eac51c`

## Round 1 — FULL

- unit_id: feat-657-agent-disable-switch
- review_round: 1
- verification_mode: full
- verify_worktree_dir: `/Users/czj/.codex/worktrees/unit-feat-657/nano-multiagent`
- branch: `unit/feat-657`
- requires_full_verification: false（本轮已经 FULL；修复可按下列两处及关联 delta 定向闭环）
- verdict: **FAIL — 0 CRITICAL / 2 WARNING / 0 SUGGESTION**
- validated_issues: W1/W2 均 CONFIRMED；W1 已独立临时副本复现，W2 是确定的控制结果/展示调用链。
- 产品真实旅程及原生视觉由独立 reviewer 执行；本报告不代替产品验收。最终 CI、指标汇总、delta/current 归并正在进行，不把尚未交接的这些产物判成缺代码。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 全部需求与 M1 实施落点可定位；完整 M1 门禁尚待并行产品报告和 final sync 收口 |
| Correctness | 停止结果安全边界、旧工作冻结、冷恢复与历史路径有保护；迁移源写入和失败具体原因两项需修 |
| Coherence | 每 Agent 独立官方 DSH host、control host、生命周期代次与公开依赖边界遵守；两项偏差见 Issues |

## Completeness

M1 的 tasks/progress 仍是中间记录，本轮以代码及具体证据核对，不按复选框或测试文件数量推断通过。

| M1 退出标准 | 实现与直接证据 | 本轮状态 |
|---|---|---|
| R1 入口、空闲、全部停止、其他 Agent、权限/设备 | IM lifecycle authority；Web 共享 Action/Status；iOS 三页 Controls；真实 native A/B 连续性 | 静态实现 covered；真实产品结论由 reviewer 交接 |
| R2 所有唤醒、重连重启、离线失败重试 | NodeAgentLifecycle + PA lifecycle ALS；gateway relay/output/approval fences；native cold restore、deadline/cleanupthrow | 停止安全边界 covered；具体原因受 W2 阻塞；产品门禁另行交接 |
| R3 启用新工作、旧工作不恢复、历史保留、定向真人恢复 | disabled_through_revision、ColdLifecycleBarrier、Task freezes、CronOwners.skipMissed、ColdHistory | 静态 covered；真实产品门禁另行交接 |
| R4 global/single-thread/PA 和全停管理/历史 | 分区一 Agent 一 home，零 Agent control，PA/SingleThread/Global admission；冷只读历史 | 静态 covered；真实产品门禁另行交接 |
| W1 权限/CAS/迟到/冷 inbox/Task | IM `tests/agent-lifecycle.test.ts`；Node 同名测试；PA lifecycle 测试；native cold inbox/owners 和 supervisor launch race | covered，失败诊断保护需随 W2 补齐 |
| W2 实际 OS 树、PTY、TERM、卡死、连续性 | native test: 一次性子/孙级/continuable + Bash 孙进程 TERM 忽略 + PTY；supervisor event-loop block/deadline 测试；A stop 后 B tick 继续 | 自动化 seam covered；实际延迟/资源指标最终汇总由 caller 收口，不冒充实测数字 |
| W3 独立进程/home、control-only、update、冷历史、dependency/build | `runtime-partitions.ts:40-65,103-120,188-245`；RuntimeLayout；runtime-partitions/cold-history/supervisor/layout 测试；caller build/typecheck 和 dependency contract | covered |
| W4 Web 1440/390/320 原型/操作 | 共享独立 lifecycle 区、布局 CSS、列表 sibling 按钮、detail 草稿回归；progress 记录本地受控检查 | 本轮只核实现与投影；真实对照证据由产品报告交接 |
| W5 iOS 三页原生、权限、状态、44pt、动态字体 | Controls 按配置/详情/Work 分入口，minHeight 44，完整换行；AgentContractsTests；progress iOS build/test 25 tests/5 suites | 绑定与自动化 covered；原生视觉不以编译替代，等产品报告 |
| W6 副本迁移/回退、Work游标、指标、归并 | `runtime-migration.test.ts:89,106,121,138` 覆盖内容/中断/回退/污染；product DB 原地保留；deployment-prompt | 迁移受 W1 阻塞；指标与归并属于本轮结束前 final sync，不是缺实现 |

## Correctness

| Requirement / Scenario | 实现位置 | 测试/直接证据 | 状态 |
|---|---|---|---|
| 工作视图立即停用；不保存草稿 | Web `agent-detail-page.tsx:1647`、`agent-lifecycle.tsx:22-50`；IM `agent-lifecycle.ts:66-99` | Web lifecycle/detail 测试；停用控制独立 HTTP 资源 | covered；视觉另行验收 |
| 空闲 Agent 也持久停用 | schema lifecycle trigger；Node `agent-lifecycle.ts:45-50,82-89` | Node lifecycle tests；IM持久重开 | covered |
| 跨聊天、全部后代及 Bash/PTY；其他 Agent 连续 | `runtime-partitions.ts:44`；integration `index.ts:683-745`；`client.ts:171-206` | native `agent-disable-native.test.ts:27` 和 supervisor 真实 event-loop block | covered（不超出已接受 DSH 平台范围） |
| 消息/群提及/Agent消息/Task/Heartbeat/Schedule/回报不唤醒、不补旧输出 | IM gateway/messaging/personal-actions；PA AgentLifecycleAuthority + wrappers、cancelAgent；integration ColdLifecycleBarrier | IM迟到 output/approval/Task await；PA image await/外部 admission；native cold owners/Schedule | covered |
| 重启重连/重复操作保持停用 | IM持久 snapshot、Gateway register ACK；Node sync先save，allowed需同步；机器 boot proof | IM socket+DB reopen；Node stale intent、未知cleanup跨重启、recordStopped保护 | covered |
| 离线等待确认 | IM desired与observed分离；capability旧节点stop_unconfirmed；客户端online独立 | IM old-node；Web/iOS状态fixture | covered；产品离线交接另验 |
| 清理超时/失败持续未确认、有原因、重试 | supervisor latch/deadline；Node stop_unconfirmed；UI retry且禁止enable | 真实cleanupthrow和卡死证明未确认；具体原因丢失见 W2 | **WARNING W2** |
| 显式启用只接受新工作，独立周期未来触发 | revision + disabledThrough；ColdLifecycleBarrier；CronOwners.skipMissed；Heartbeat reset；PA取消旧输入/输出 | native冷inbox一次fence、后续restart保留fresh；Schedule旧expired不补跑/新消息revision；PA lifecycle | covered |
| 真人只恢复指定旧任务 | IM task-graphs freezes/schedules + authenticated user resume_request | IM lifecycle冻结todo/paused、Agent拒绝、human指定恢复，其他保持 | covered |
| 管理权限与状态可见；Agent/node不能改 | lifecycle routes `authorize:136-140`；只owner写、只existing可见空间读；脱敏publish | IM权限回归；只通过真人HTTP改变desired | covered |
| 设备在线与Agent停用分开 | Web row/profile/detail Status；iOS controls与presence独立 | Web/iOS解码和控件测试；真实视觉由reviewer | covered |
| 旧数据/资料/游标迁移保留且不运行live源 | migration公开persistence/domain、原地product数据库、marker后启动 | 副本测试及独立legacy公开API复现；W1改变源快照 | **WARNING W1** |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| desired/observed分离，revision+processInstance拒迟到 | 是 | IM lifecycle:79-86,116-126；Node lifecycle:63-97 |
| 先关准入，再并行终止；不等普通RPC队列 | 是 | IM change:92-96；Node applyKnown:40-50；supervisor.disable同步latch；RPC独立agent.disable |
| 每产品Agent独立进程/home；零Agent control | 是 | RuntimePartitions.key/create('control')；main create partitionHome/initialize；control跳过product consumers |
| 全部DSH接入在integration且公开exports | 是 | package显式声明jobs/subprocess/terminal/persistence等；Node仅client；迁移script只调用integration公开runtime-migration export；没有runtime fork/private import |
| enable不resume，旧Task真人恢复 | 是 | task_lifecycle_freezes/schedules；冷inbox与owner fences；PA原代次与取消facts |
| 原生历史停用后只读且不恢复Agent | 是 | ColdHistory独立reader，无Agent registry和执行provider，Nano provenance复制到scratch；冷history测试比对源文件摘要 |
| 停机最终Work保留且不混内部Agent | 是 | index disable对所有native Agent清理，仅boundRoot生成stoppedSessions；GlobalAgent.recordStopped:752-771只写持久历史/Work |
| 迁移保留源快照 | 否 | plan在源domain.open触发合法legacy bootstrap；W1 |
| 停止失败给具体原因 | 否 | supervisor丢失reason，Node report不带detail；W2 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Web身份→设备→操作，停用不等配置保存 | R1/W4 | detail独立Action；list sibling按钮；独立mutation | design-evidence/progress，最终产品报告待交接 | 实现covered，真实对照不由静态审查代签 |
| stopping/disabled/offline/failed且未确认禁enable | R2/W4 | shared status/action；confirmedDisabled；owner权限 | 自动化fixture；产品失败/离线旅程待交接 | 实现covered，具体失败原因W2 |
| enable后旧任务暂停/历史可读 | R3/W4 | Task freeze、native/cold history | native/IM/PA回归；产品报告待交接 | covered |
| iOS每页单主入口、短句、动态字体/44pt | W5 | 配置Toggle（失败仅重试），详情/Work单Button；44pt/minHeight与fixedSize | Xcode结果已记录；原生动态字体对照由reviewer交接 | 绑定covered，视觉pending |

## Issues

### CRITICAL

无。

### WARNING

- **W1 — 迁移规划修改静止源目录。** `runtime-migration.ts:233`。`deployment-prompt.md` 的保护源/中断回退与 `design.md` 迁移约定要求源快照可靠；公开legacy domain读取触发bootstrap，第一遍plan新增源文件并误报外部writer。复现命令和实际输出见 `code-review.md`。建议domain数据先复制到临时只读观察副本再经公开API读取；源hash应保持原始数据且不能以重跑掩盖源被改写。补充公开single-layout源的plan/apply/verify回归并比对源摘要。
- **W2 — 停止失败原因未到达owner。** `apps/node/src/agent-lifecycle.ts:88-97`，关联 `client.ts:191-204`。`spec.md:91-94`要求具体原因；实际只有通用error_code，IM `report:125`清空detail，UI无信息可展示。建议stop result携带有界安全原因，区分timeout/cleanup错误/之前未确认；发布owner可读detail，保留非owner脱敏。复用已有真实失败测试补协议可见结果保护。

### SUGGESTION

无。

## Delta Reconciliation（全部四份）

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| gateway/service-lifecycle：停止/禁止唤醒/离线先应用/历史保留/外部已提交副作用 | Node/runtime/PA/ColdHistory与native/cold-history tests | 核心行为aligned；管理能力短句需按下方校正明确范围 |
| gateway/task-graphs：所有旧未完冻结、独立真人指定恢复、/stop不变 | freezeAgent/validate/task execution；IM lifecycle tests +既有stop tests | aligned |
| im/agents-nodes：真人独立入口、意图/观察、离线例外、新工作与未来周期 | HTTP lifecycle+Web+iOS；IM/PA/native tests | 失败具体原因漏入delta且实现缺失，见W2；其余aligned |
| im/ios-client：配置单Toggle，详情/Work单Button，未确认禁enable | AgentLifecycleControls及三个调用点，iOS contracts | 静态aligned；原生视觉evidence由reviewer交接 |

### Final sync 所需校正

1. `specs/im/agents-nodes.md:22-24` 的失败场景应保留首文档已有的“具体原因”，不能在delta中只剩通用状态来适配W2；代码修复后同时核对owner可见、非owner诊断脱敏。
2. `specs/gateway/service-lifecycle.md:22-24` 的“控制与管理仍可用”应明确为生命周期、模型设置、已保存普通配置/历史等不需执行的管理；按design:130，依赖运行时的插件操作/能力探测保持已知快照并明确不可执行，不得为其短暂启动停用Agent。该条目前过宽，不能归并成“所有管理操作均可用”的承诺。
3. 补充或链接实际新增的运维可观察边界：旧共享执行home启动须先离线plan/apply/verify，不在普通启动自动拆分；独立执行home/process属于顶层SPEC拓扑唯一权威。现有delta未写这一启动拒绝行为。归并时同时更新顶层拓扑与相关入口，沿用unit deployment-prompt作为一次性操作历史，不复制技术步骤。
4. current `SPEC.md`“Cron停机期间一次性任务补发”的通用句应增加Agent停用/重新启用的例外链接；普通Node重启保留原语义。当前代码通过disabledThrough fence只取消停用前旧触发，不能把整个Cron通用语义改成永久不补跑。

Outcome: **implementation-mismatch**（W1/W2）；delta文本校正后可定向核对全部四份最终delta及新增受影响段落，无需重复完整产品验收。

## Evidence reuse and cleanup

复用 caller 针对冻结版本交接的 IM真实WebSocket/CAS/冻结Schedule、PA 25 files/197 tests、Node controller/partition/layout、native stop 5 tests、coldhistory 4 files/7 tests、migration 4 tests。独立读取 build/typecheck/stop-fix日志的通过尾部：`/tmp/nano-feat657-build3.log`、`/tmp/nano-feat657-typecheck3.log`、`/tmp/nano-feat657-stop-fix-test.log`。不声称这些局部通过替代最终CI或原生视觉。

本轮只写本报告和code-review.md。独立复现仅用随机临时副本并在finally删除；没有创建服务、额外worktree、生产变更或提交。共享现场报告由caller提交。

## Round 2 — Targeted Closure

- verification_mode: targeted-closure（附全部 corrected delta reconciliation）
- review_round: 2
- fix_delta_range: `935510058d338866e2310f54c1804d6120eac51c..e55e5285a2ee2ab9193ebdb94680585726441ce5`
- validated_at: `e55e5285a2ee2ab9193ebdb94680585726441ce5`
- prior_verification_path: 本报告 Round 1
- focus_issues: W1/W2；产品 R1-1/R1-2 对应修复的静态实现；cleanup proof UPSERT 与恢复分区过滤的新风险。
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION（本次定向静态闭环）**
- requires_full_verification: false
- retained_from: Round 1 的全部未受影响需求、设计、架构与M1实施证据；不重新验收整个unit。M1真实产品、原生视觉、最终CI/指标及current归并仍依赖caller最终汇总，本轮PASS不能取代它们。

### Completeness / Correctness / Coherence Closure

| 项目 | 契约与实现证据 | 验证结果 |
|---|---|---|
| W1 / M1-W6 静止迁移源 | 原 deployment-prompt 保护源约定；`runtime-migration.ts` openSourceStorage在临时copy打开domain，普通domain和Schedule owner均走该路径，finally移除副本；session公开read保留 | closed。新增legacy single-layout模型domain回归覆盖plan/apply/verify、源字节和目录不变，并保留target内容验证。没有为通过测试改迁移预期。 |
| W2 / spec清理失败具体原因 | `client.ts` errorDetail已覆盖cleanup异常、截止、提前退出；`NodeAgentLifecycle.stop/publish`传持久error_detail和report；IM已有脱敏及UI显示 | closed。真实cleanupthrow断言携带真实原因；deadline的状态仍未确认，不能enable。 |
| 产品R1-1 / 新工作重新启用 | integration ensure仅按SessionBinding五个真实字段比较；字段顺序不再产生冲突 | 静态closed；native回归重排成功，owner变更仍拒绝。真实新消息恢复结果由产品reviewer追加。 |
| 产品R1-2 / 停用消息明确不接手 | Web MessagePane和iOS ConversationView按Agent participant装配readonly notice，desired=disabled时说明不处理，保留历史/发送 | 静态closed；Web lifecycle notice回归与全前端通过。真实原生可见性仍由原生验收交接。 |
| offline/restart proof更新 | 独立agent_cleanup_proofs UPSERT；main只使用该authority，launch/cleanup替换事实；无proof但IM有旧process实例时不确认 | covered。PA测试重新构造authority读取stopped更新，并验证新实例覆盖旧确认；R1 Node未知清理/recordStopped保护仍适用。 |
| knowledge/workflow恢复只选可用分区 | main集合过滤runtime.availableFor，原scoped generation/lifecycle gate保留 | covered。只缩小恢复资格，没有跨Agent恢复或副作用绕过。 |

### M1 evidence retained / 尚待外部门禁

R1 的 M1-R1～R4、W1～W6覆盖表继续作为任务全量映射。两项 WARNING 已清零；产品acceptance Round 1已记录的R1-1/R1-2只能在真实新版本产品报告完成后正式变成产品pass。本轮未把正在进行的backend task-execution-limits负载超时复核当成无关已知失败或静态代码缺陷，也没有重跑全套。最终还需caller完成SPEC/current归并、原生视觉/资源指标证据与最终CI结算。

## Corrected Delta Reconciliation

本段核对全部四份delta，而非只核文字变更行。R2受审代码为`e55e5285a`；报告本轮另作下述一处已授权delta校正。不存在需要再扩大FULL的共享边界变化。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| gateway/service-lifecycle：整Agent停止、自动恢复/输入阻断、离线先应用、历史及外部已提交动作 | R1 IM/Node/PA/native stop/cold history边界未变化；新增恢复集合仅可用分区 | R1 native/Node/PA有效证据；R2窄测 | aligned |
| gateway/service-lifecycle：管理能力明确限定不需执行操作 | RuntimePartitions对已停用configuration保存/目录和冷history走control，对执行RPC拒绝；control模型设置不启动disabled产品host | RuntimePartitions disabled配置/冷history回归沿用 | aligned |
| gateway/service-lifecycle：旧共享home离线迁移，源不变，verify后发布 | RuntimeLayout拒旧数据；openSourceStorage临时副本；verify marker | 新legacy single-layout源不变 + 原迁移中断/污染/回退测试 | aligned |
| gateway/task-graphs：全旧未完冻结、真人指定恢复、/stop不变 | task freeze表、validate/authenticated resume_request，Schedule关联冻结 | R1 IM冻结todo/doing/waiting及指定恢复证据未受影响 | aligned |
| im/agents-nodes：真人独立开关、状态/离线例外、具体原因、重新启用新工作/未来周期 | R1生命周期与客户端；R2 errorDetail传播、ensure语义比较 | native真实cleanupthrow/重排绑定/旧owner拒绝，IM/PA有效证据 | aligned |
| im/agents-nodes：聊天中明确不处理，消息保留且无生命周期操作 | AgentLifecycleChatNotice→MessagePane；未动聊天send/read | Web notice回归与108files/1028tests全套 | aligned |
| im/ios-client：三页单操作、未确认禁enable、旧任务提示 | 三处AgentLifecycleControls入口、canEnable守卫未变 | R1 iOS contract/build；原生视觉由产品验收 | aligned（静态契约） |
| im/ios-client：停用Agent聊天说明 | ConversationView按参与者Agent显示readonly notice | 代码绑定+共享语义；原生可见性由产品报告 | aligned；本轮将说明从等待确认场景拆为独立WHEN停用聊天场景，避免遗漏已确认disabled |

### Uncovered Observable Behavior

None。proof UPSERT修复停用/重启的既有事实正确性，绑定语义比较恢复既有新工作资格，availableFor过滤恢复集合兑现原禁止唤醒，均未引入新的产品策略。新增聊天说明、停用态管理范围及旧home启动拒绝已由最终delta覆盖。

Outcome: **aligned**。

### Final SPEC / current merge obligation

最终仍须把这四份已核对delta归并进current，并在顶层`SPEC.md`统一写明每产品Agent独立home/DSH host及零Agent control；Cron普通停机补发的既有句必须链接Agent停用例外，保留普通Node重启的原语义。该收尾由caller执行，不通过改delta来弱化W1/W2或产品需求。

本轮读取并复用 `/tmp/nano-feat657-last-narrow.log`（3 files/15 pass）、`/tmp/nano-feat657-typecheck5.log` 和 `/tmp/nano-feat657-frontend-green.log`（108 files/1028 pass）。只修改本报告、code-review报告及授权iOS delta文字，未提交、未启动服务或迁移live源。
