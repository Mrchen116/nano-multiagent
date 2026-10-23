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

## Round 2 — targeted-closure + patch verification

> Validation snapshot: `6223412809e5bdb98a741402d913e33589d686bc → e2219e12b89b581fbd1808ad768f78c72090c081`

- 时间：2026-10-23 23:37 +08；独立 verifier 不变。
- verification_mode：targeted-closure，focus R1 W1/W2，并核对 classifier effort、source unavailable 新补丁和全部 corrected delta。
- verdict：**pass（本次静态与故障验证范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- validated_issues：W1 closed、W2 closed；无新增 issue。
- requires_full_verification：false。patch 未更改 IM/PA 事务、反馈与等待链，R1 相关结论仍可保留；原 R1 缺陷的当前结论由本轮替代，历史事实保留在上文。
- outcome：**aligned**。这不是整项 M1 产品验收或最终 CI 通过结论。

### Focus closure 与新增实现核对

| 契约 / focus | 最终代码与 evidence | 结论 |
|---|---|---|
| R1 W1：局部拒绝不停止可定位的独立任务；design:46 | integration `task-execution.ts:119-124` 纳入 dependency from/to；native scope dependency 用例保护同图独立责任；相同 R1 三任务输入只持有 A/B，C 可自动 admission | closed |
| R1 W2：子树删除拒绝必须停止未变化自动重试；design:44-46 | delete 采用当前图已知责任批次，避免假设父节点必须直接负责；native subtree 用例证明另一图责任仍完成；原 child-only 输入不再自动 admission | closed |
| 原审核模型推理能力与证据/失败规则 | `policy/classifier.ts:15-36`、`policy/codex.ts:105` 都保留原 provider/model，使用该模型声明档位；Nano 仍两阶段、每阶段保留完整适用 transcript、解析器/预算/失败机制不变 | covered |
| 初次 Task 源 unavailable 不改变无已知责任的普通输入；已知责任仍有保护 | `task-execution.ts:75-80` 保持 hold/source，own-only reject；只有 previous.tasks 非空才追加 task-change。普通输入原对象保留；现有 native approval 用例保护首次无 Task 数据源仍能按真实原输入处理 | covered |

真实方法复核命令与 R1 一致：

```sh
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec tsx /tmp/nano-646-review-scope.mts
```

在 e2219e12b 的实际源码上输出：

```json
{"case":"dependency","held":["g/A","g/B"],"automaticAdmitted":1}
{"case":"delete-subtree","held":["g/child"],"automaticAdmitted":0}
{"case":"source-unavailable","known":false,"decision":"allow","messages":1,"originalPreserved":true,"interrupted":"source"}
{"case":"source-unavailable","known":true,"decision":"allow","messages":2,"originalPreserved":true,"interrupted":"source"}
```

以上是实际 driver listener/poke/pre-step seam，未替换受审判断，不是生产模型或实际删除副作用证明。自动 source admission 的拒绝分支和 poke 的 unavailable return 均未在补丁中放开。

### 证据复用与门禁边界

- 读取并复用 `/tmp/nano-646-patch-final.log`：e2219e12b 源码对应 `approval/task-execution/task-recovery`，3 文件 / 24 测试绿，23:33:37 开始，108.78 秒。scope 从旧 node 用例参数化扩到 dependency/subtree，保留无关 revision 不解锁及本节点版本变化后重新评估的旧断言；implementation 新记录保存 2 红/1 绿的回归来源。
- Nano 三档位参数化测试 `approval.test.ts:330-345` 核对两次 stream 的 provider/model/effort/transcript 和最终 deny；旧 native fixture 显式声明 low，保留原有人值守/无人值守/拒绝计数/无效 verdict 等真实生命周期断言。R1 的 Codex 8 测试与其未变源码结论继续有效。
- 前端 103 文件/963 测试、Python 65、typecheck/ios/ruff/docs 为 caller 提供的旁证，本轮未重跑、不扩大其证明范围。最终限并发后端 CI 和真实模型产品旅程仍由各 gate 提供。没有为尚未返回的外部 gate 增加 WARNING，也没有提前宣称 M1 全部退出标准完成。
- design-review.md 的并发补充设计复核由另一独立 reviewer 持有，本轮不修改该文件、不替代其结论；本轮只判断当前最终文档与实际补丁的一致性。

## Round 3 — targeted-closure + integration patch verification

> Validation snapshot: `97be7854e9956e599eea42ed9e1d9988548dc8c4 → 3a2debdd5eea8d3153fa5ae4903f67a33c9c5d92`

- verification_mode：targeted-closure + corrected-delta；focus 产品 R1 P1/P2/P3 新修订与 main 合并接线。
- 时间：2026-10-24 00:13 +08；独立 verifier 不变，未参与实现；未重新扩大为 unit full。
- verdict：**静态与本轮定向验证 pass**，0 CRITICAL / 0 WARNING / 0 SUGGESTION；outcome：**aligned**。
- requires_full_verification：false。已静态检查共享 index/PA 的实际合并交互；native stop 仅有 4f8f 编译版本边界证据；原 R2 未变化的契约证据仍有效。本轮并不认证上游 PR 全部内部实现，也不替代 caller 的最终集成 CI。
- 完整交付 gate 仍待：合并版后端全量、typecheck 与产品 R2。已知一次旧 automatic denial poll 超时未被隐去，不能将 88/89 写成全通过。

### Completeness / Correctness / Coherence

| 修订契约与现场风险 | 实际实现、验证与限制 | 结果 |
|---|---|---|
| design 新补充 SingleThread query 模式资格 | PA `global-agent.ts:491` 限 Global 注册；IM `work.ts:488-520` 已按 work_mode 分流 session 前置，保留节点、Agent、空间与会话权限；native product query 回归显式拒绝错误 Global 注册 | aligned |
| Task delta:30-33 停止事实先持久、首步可见、失败保持 pending | PA `task-execution.ts:63-74` 先 pause receipt、稳定 input ID inject，runtime `index.ts:640-660` 实际 flush 后返回；意外 notify 失败不写 intent.text、不解 fence。原生 `restore` 仅把 task-human-control 恢复 next-step；native stop 竞态含 fence 内实际拒绝与解锁后的首个模型输入对照 | aligned |
| 同场景：审批识别真实控制与原消息时序、后续新恢复有效 | 源说明与投影 `sources.ts:9,164-165`；classifier 和 codex-context 均引用该规则。stop host 内容含原 actor/message/created_at/scope，普通输入保留原消息时间；UI resume 仍为独立宿主事实，不赋予额外工具权限。approval-sources 区分 stop/resume 与普通自动提示 | aligned；真实模型对旧答复与后续新恢复的遵循由产品 R2 核实 |
| Task delta:26-28 SingleThread confirmed bound-chat send 不公开 NO_REPLY、保留审批 | PA `global-agent.ts:580-588` 从持久 tool/call 得 turn、服务端 payload 得实际聊天，限定同绑定聊天或映射后记交付。`single-thread.ts:223-231,409` 停止流式哨兵并在 final 丢弃重复泡；approvalVisible 排除丢泡，`:280` 保留审批正文语义。正常有意义 final prose 仍完成交付 | aligned |
| 发送 unknown/其他聊天不得吞掉正文 | 仅确认路径记 key；parameterized SingleThread 回归有 card/plain、found false、different chat 对照；既有可见审批回归保留 | aligned |
| merge PR393 descendant/reconcileRoot | PA task_graph/send 实际 await root drain，仍记录 source events 并提交 Inbox；child drain 独立。PA 两个 source-independent 用例直引合并 src 通过；native stop 启动 4f8f lib，仅保留为 driver 未变的既有证据 | aligned，未仅依赖 merge 无冲突 |
| merge PR394 incremental usage | 新 usage.read/UsageReadResult 在两端同步；统计 root attribution 不驱动 Task/控制来源；submit/flush/cancel keepInbox 顺序未被改动 | aligned |

design R4 的队列 WARNING 已由独立设计 R5 关闭；本轮独立检查对应实现与实际原生测试，而非把设计 Approved 当作实施证据。以上均复用原生公开接口，无额外执行循环、审批替代链或业务状态镜像。

### 有效验证与待回填证据

- caller 新窄测记录 `/tmp/nano-646-finalpatch-green.log`：**88 passed / 1 failed（89 total）**。失败为旧 automatic permission-denial 等第二模型调用的 5000ms poll 超时；新增 stop/query/交付测试均通过。记录失败原样保留，caller 将在单 worker 合并版后端全量中复跑；本轮未自行改 timeout 或测试。
- 独立合并源码工作树命令：`PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec vitest run packages/dsh-integration/tests/task-execution.test.ts packages/personal-assistant/tests/global-agent.test.ts -t 'restores a stop fence|source checks independent' --maxWorkers=1`。结果 **2 files / 3 passed / 57 skipped**，00:11:36，22.87 秒。其中 PA 两例直引 3a2 src，验证 merge 中 Task/send 的 root 源检查；native stop 使用 RuntimeClient 启动旧 4f8f lib，只证明该版本 stop 首步可见（driver 未被 main 修改）。caller 发现旧产物后停掉错误集成验证并显式 build；本次结果不证明 3a2 完整 runtime 集成，最终 build 后测试/产品证据待回填。
- PA 停止失败/恢复回归验证 pause 已成功但通知失败仍保留 pending/fence，重试相同 input ID 与内容；native stop 回归验证通知已 inject 后 fence 内并发唤醒/拒绝，解 fence 后第一个实际模型请求包含 HOST_STOP_NOTICE。
- R2 的一小时首次/续期、反馈 receipt/unknown、拒绝作用范围、supported effort、Global 收尾与 SingleThread 原正常 final 证据未失效，保留原结论。完整产品 R1 的失败历史不覆盖；须由独立产品 R2 对新栈实测修复后的 P1/P2/P3。

本轮只追加/更新两份静态报告，无新自建服务需清理；未操作 caller 的集成 E2E 或产品 R2 栈。

## Corrected Delta Reconciliation

本节为最终唯一 reconciliation，覆盖三份 delta 及 Round 3 新增 Task 场景；历史结果由各轮与 Git 保留。固定实现为 `3a2debdd5`，保留仍适用的 R2 证据。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Task:5-10 当前事实、可验证结果及合法独立工作 | driver/feature guidance；dependency 正确定位，delete 保守采用已知图批次 | R1 continuation/withdrawal；R2 native scope 三分支及直接复现 | aligned |
| Task:12-17 首次/续期 cap、普通 Schedule 不限 | IM 双阶段校验及事务回滚未变 | R1 IM cap/new/renew/unchanged graph 与 native Schedule 仍适用 | aligned |
| Task:19-24 固定聊天、实际反馈、无重复/未知诚实性 | committed feedback/receipt、deferContext、原 publication 未变 | R1 IM child/replay/later pause；native 三终态/unknown/final step | aligned；正常真实旅程另 gate |
| Task:26-28 SingleThread 已确认显式交付 | confirmed publication 的同 turn/绑定聊天键；stream 与 final sentinel 分支；可见审批不丢泡 | card/plain + confirmed/unknown + same/different chat 对照，原可见审批回归 | aligned；真实产品 R2 待回填 |
| Task:30-33 停止优先于旧排队输入 | pause receipt → stable inject/flush → terminal intent/unfence；control 保持 next-step，原消息时间/来源规则入模及入审核 | PA notify失败/相同ID恢复、审批来源测试；4f8f编译版native stop首模型步通过，main未改该driver | aligned；实际旧输入/新恢复由产品R2核实 |
| Task:35-43 失败屏障与新输入、独立工作 | R2 deny/source/error/flush 逻辑保留；新restore仅改变可信控制队列类别 | R2 scope/recovery仍有效；旧automatic denial有一次超时，待caller最终集成重跑，未计绿 | aligned（实现/契约）；最终测试gate待回填 |
| Global:5-14 空响应恢复保持、非空私有收尾、SingleThread 分支 | Global/shared/生成资产未变，复用 R1 全部检查 | 原 native communication/final step；没有更改空响应恢复策略 | aligned |
| agent-capabilities:5-10 原审核模型声明能力；保留 provider/model/证据/verdict/失败分流 | Nano/DSH classifier 与 CodexApproval 能力选择一致；personal-security 已有相同选择 | Nano 两阶段三档位 deny/transcript 回归，Codex R1 effort8 测试与生命周期证据 | aligned |

### Uncovered Observable Behavior

检查全部三份 delta 及本次 patch 后，无遗漏对外行为。SingleThread query 是既有合法会话读取/发送契约的接线修复，无新权限；stop 事实与 confirmed plain send 的新场景已明确列入 Task delta。main 的 descendant/usage 变化已有各自 current/archive 契约，本轮核实其与 Task admission、source check 和 delivery 的实际交互，不把它们冒充本 unit 新行为。source unavailable、`updated_at`、mutation `feedback` 及审核模型能力仍由原 delta/design 涵盖；没有把普通 system/定时输入提升为恢复授权。

Outcome: **aligned**。

本轮只修改本 unit 的 code-review.md 与 verification.md；未改源码/测试/配置/设计，也未启动需清理的服务。最终 CI 与真实产品闭环仍需各 gate 的明确结果，不能由本节 aligned 推断已完成。
