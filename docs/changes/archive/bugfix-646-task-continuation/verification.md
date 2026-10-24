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

## Round 4 — narrow patch + corrected-delta

> Validation snapshot: `a9e0f38ff → 1fbacfe3d89f842424fa5e6a7d57707dc02971f7`

- 时间：2026-10-24 00:27 +08；同一独立 verifier，未参与实现。
- verification_mode：delta + corrected-delta，单一新增 Scenario“直聊 Task 系统通知的静默收尾”，以及 PA stream/final 受影响边界。
- verdict：**pass（本次代码/契约范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION；outcome：**aligned**。
- requires_full_verification：false；本 patch 不改 native integration、Task 执行/停止、审批判定、Global 或同轮 confirmed-send 算法，无需重开 R3 未变范围。

| 范围 | 实现与直接证据 | 结论 |
|---|---|---|
| 新 Task delta:30-34 纯宿主 Task 通知的静默收尾 | PA `single-thread.ts:233-246` 从本 turn 的持久输入同时核对 system/task_graph，进入既有自动交付路径；不读取旧 turn 送达标记 | aligned |
| 不误吞真人/其他通知/混合轮次 | sender_type 与 kind 双条件、all-inputs 范围；新增参数化测试分别覆盖伪带 Task notice 的 user、other_notice、混入真人 | aligned |
| 有意义正文、实际任务与审批保留 | 只改变展示归类，receive/submit/native 执行不变；有意义 final 继续交付；pending/visible 审批保护与 final 剔 sentinel 逻辑不变；notice/native 两种审批回归都检查 permission_request/resolved 与完成泡 | aligned |
| 通知 stream 不污染已生成审批 bubble | `:405` 过滤纯 task_execution/宿主 Task 自动输入的 transient text；正常 final 仍作权威交付，mixed/human/other notice 不新增过滤 | aligned |
| RelayInput 可选字段来自真实既有链路 | IM Task metadata → system insert → system_notice 投影 → 整体 Relay message → PA JSON 持久输入均存在；仅增加可空 optional TS 字段，不新增协议 | aligned |

有效证据复用 `/tmp/nano-646-task-notice-green.log`：两文件 / 24 测试全绿，00:24:33，4.09 秒；代码测试直接 import PA src，受审实现为 1fbacfe3d，不外推为 native runtime 或完整产品验收。三 case 红证据记录在 implementation。设计 R6 的 0C/0W 仅提供设计状态，本轮从实际 producer/consumer 与测试独立核对实现，没有用设计批准替代验证。

R3 的 stop/query/confirmed-send/merge 源审与仍适用测试继续保留。caller 已提供产品 R2 对 P1/P2/Global 的实际通过及剩余 P3 来源归因；本轮没有接管产品现场，**产品 R3 尚待，未写入本轮通过证据**。build 后最终后端全量和旧 native 环境超时复核仍属 caller gate，不能从 PA 24 tests 推断通过。

本轮没有新增代码 finding 或 delta drift；仅更新两份报告，未运行全量、未修改任何被审源码/测试/配置/设计，未启动服务。

## Round 5 — final-main targeted integration delta

> validated_at: `defa49f2db762ab7e0e0415b4a10312f0dcaf764`；executed_base / effective_base: `55376c111`；reviewed integration delta: `e53e488e5..defa49f2d`。

- 同一独立 verifier；2026-10-24 00:39 +08；verification_mode：targeted delta，重点 perf-648 evidence_final 与 Task notice/plain delivery、perf-649 输入归属与 stop/control/fallback。
- verdict：**pass（集成静态与定向验证）**；0 CRITICAL / 0 WARNING / 0 SUGGESTION；outcome：**aligned**。
- requires_full_verification：false；已核实新增共享边界和实际编译运行时，没有重新改变本 unit 的 Task/发送/审批契约。R4 之前不受影响证据保留，不重新执行全量。

| 主线增量与本 unit 关联 | 实际证据 | 结论 |
|---|---|---|
| evidence_final 收窄 lookup，不能删除 Task 来源或错误静默真人/混合输入 | PA drain 查询仅改用 lookupInputIds；后续分类仍来自全部 store.inputs 的原 payload/逻辑 turn；Task pure-notice/normal text/forged notice/mixed/visible approval 原保护未改 | aligned |
| 逻辑终态固定不能吞未送达正文/receipt，迟到物理失败不能重开已交付泡 | final 要 accepted、pending=false、terminal 与完成 logical run；lookup final 与 delivery/receipt 分离；recordEvents 只阻止覆写 final terminal | aligned；input-reconciliation 的迁移/重启/receipt故障/late event 测试通过 |
| confirmed plain send 的同轮去重保持 | 原 publication 命令键及 turn/chat 限制不变；final evidence 不跳过交付循环，实际消息和回执可独立补发 | aligned；SingleThread/interactive 既有完整用例通过 |
| inputIdsForTurn 不改 stop 控制的消息/队列/来源 | helper 与旧 inputEvidence 逐前缀结果一致；ModelFallback 仅替换 run.inputs 收集方式，排除 sentinel 和去重保留；Task stop next-step/flush 代码未变 | aligned |
| fence 内 claim 的旧排队输入不可提前固定，首个解锁模型步必须看到 stop | 被拒后恢复到 next-turn/next-step 的输入仍 pending，不能 evidence_final；原生 native stop 竞态在最终完整 build 后实际通过 | aligned |
| 新 main 与当前三份 delta 无对外行为冲突 | 上游 perf-648/649 均 no spec delta；本 unit Task/Global/reviewer delta 不变，无 Task 执行、审批授权或公开回复语义替换 | aligned |

### 独立验证与版本

读取 `/tmp/nano-646-final-sync-build.log`，确认完整 build 为 defa49f2d、installer `bca4d1524c5d`；收到 caller 构建成功通知后执行 native 测试，明确区别 R3 的旧编译版本限制。

- 直接源码 suite：PA single-thread / interactive-replies / input-reconciliation 与 integration input-evidence，`pnpm exec vitest run` 指定这四文件、`--maxWorkers=1`：**4 files / 34 passed**，00:37:50，14.12 秒。
- 最终 runtime suite：integration task-execution，仅 `-t 'restores a stop fence' --maxWorkers=1`：**1 passed / 12 skipped**，00:38:02，26.30 秒。实际在新编译 native runtime 下检查 fence 内控制恢复与首个模型输入，填补本次 merge 的关键运行接缝。
- 上述均使用 `/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin` Node24。未重复 caller 正在定位的 workspace-tools/knowledge-policy 旧全量失败文件；完整 CI 结论仍待 caller 汇总，不将 629/631 或本轮 35 项通过改写为全量绿。

### 产品与保留证据

已读取本 unit regression.md Round 3：在 1fbacfe3d 真实产品中，分配/完成通知独立轮次均 completed 而无哨兵/空 running，真人 23×8=184 与6+5=11正常交付；P1/P2/Global 依明确图/消息/时间证据保留并最终 open issues=0。本轮 perf-648/649 按设计保持该对外语义，源码交互与窄测未发现使之失效的变化，故保留其产品结论；**本轮没有重新运行或伪造新产品/生产验收**。

仅更新两份报告，未更改受审源码、测试、配置、设计；没有新服务或需移交的运行现场。

## Round 6 — P4 targeted closure / corrected-delta retained

> Validation snapshot: `b0d107309 → 00ffba95923751b2ef04cc561158f85cb66adfa0`。

- 同一独立 verifier；2026-10-24 00:49 +08；verification_mode：targeted-closure + corrected-delta，唯一 focus 为产品 Round 4 P4 混合自动输入静默遗漏。
- verdict：**pass（该实现纠错范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION；outcome：**aligned**；requires_full_verification：false。
- validated_issue：P4 implementation defect closed；实际混合输入产品复验待独立 reviewer，不能以本报告代签。

| 核对目标 | 最终实现与证据 | 结论 |
|---|---|---|
| Task notice + native task context 混合 turn 仍是自动轮次 | drain 的 `every(A||B)` 与既有允许类别/stream一致；没有跨 turn 旧 send 标记或来源推测 | aligned |
| 普通真人/other notice/mixed-human 不新增静默 | A/B 每项条件不变，任意普通真人 false；原反例矩阵保留，测试仍确认其 final 可见 | aligned |
| 自动混合场景有意义正文与审批继续交付 | 只改 automaticOnly 输入集合判断，final text 与 approvalVisible 分支未动；mixed-native 正常正文新增绿测，既有 native/notice 审批用例保留 | aligned |
| design / delta 是否需要扩展 | 实现恢复既有 Task/native 自动类别混合后的预期表现，未新增静默来源、权限或功能；三份 delta 无变更、无遗漏新行为 | aligned，Gate 2 有效设计保留 |

有效红绿证据已读取：旧判定下 mixed-native 两例提前生成 bubble，**2 failed / 19 passed**；新源码下 SingleThread + interactive **2 files / 26 passed**，00:47:34，3.80 秒（`/tmp/nano-646-mixed-notice-red-direct.log`、`/tmp/nano-646-mixed-notice-green.log`）。本轮无需重复全量；caller 提供 PA tsc 已完成。R5 完整 build 与其余 35 项有效窄证据按未修改范围保留，不能将旧版本 full gate 迁移成新版本全绿。

产品 Round 4 已证明 stop 优先、新明确恢复、普通新回复/显式 send 与纯通知仍有效；P4混合轮次是新增必验失败。本报告关闭的是实现问题，产品 gate 仍须修后窄复验。turn14 仅旧真人输入选择 NO_REPLY 是单独范围外观察，本次没有借修复扩大为吞掉普通真人输出。只改本 unit 两份报告，未改受审源码/测试/设计或运行真实服务。

## Corrected Delta Reconciliation

本节为最终唯一 reconciliation，覆盖三份 delta 及通知/native 自动输入混合纠错；历史结果由各轮与 Git 保留。最新固定源码为 `00ffba959`；Round 5 的 effective_base `55376c111` 和已验证主线交互保持，Round 6 只修 automaticOnly 集合判定。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Task:5-10 当前事实、可验证结果及合法独立工作 | driver/feature guidance；dependency 正确定位，delete 保守采用已知图批次 | R1 continuation/withdrawal；R2 native scope 三分支及直接复现 | aligned |
| Task:12-17 首次/续期 cap、普通 Schedule 不限 | IM 双阶段校验及事务回滚未变 | R1 IM cap/new/renew/unchanged graph 与 native Schedule 仍适用 | aligned |
| Task:19-24 固定聊天、实际反馈、无重复/未知诚实性 | committed feedback/receipt、deferContext、原 publication 未变 | R1 IM child/replay/later pause；native 三终态/unknown/final step | aligned；正常真实旅程另 gate |
| Task:26-28 SingleThread 已确认显式交付 | confirmed publication 的同 turn/绑定聊天键；stream 与 final sentinel 分支；可见审批不丢泡 | card/plain + confirmed/unknown + same/different chat 对照，原可见审批回归 | aligned；真实产品 R2 待回填 |
| Task:30-34 直聊 Task 系统通知的静默收尾 | 当前turn每项输入满足既有native自动类别或system/task_graph；stream/final一致；不跨turn借旧send；final缓存不裁payload | R6 mixed-native红2→PA26绿，mixed-human/meaningful/approval保护；P4修后产品复验待 | aligned（实现）；产品gate待复验 |
| Task:35-38 停止优先于旧排队输入 | pause receipt → stable inject/flush → terminal intent/unfence；control 保持 next-step，原消息时间/来源规则入模及入审核 | PA失败恢复/审批来源；产品R2旧队列与新恢复通过；R5最终build native stop单例通过 | aligned |
| Task:40-48 失败屏障与新输入、独立工作 | R2 deny/source/error/flush 逻辑保留；restore保持可信控制队列类别 | R2 scope/recovery证据保留；R5输入归属/native stop通过；完整CI的既有环境失败另由caller gate汇总 | aligned（实现/契约）；最终测试gate待回填 |
| Global:5-14 空响应恢复保持、非空私有收尾、SingleThread 分支 | Global/shared/生成资产未变，复用 R1 全部检查 | 原 native communication/final step；没有更改空响应恢复策略 | aligned |
| agent-capabilities:5-10 原审核模型声明能力；保留 provider/model/证据/verdict/失败分流 | Nano/DSH classifier 与 CodexApproval 能力选择一致；personal-security 已有相同选择 | Nano 两阶段三档位 deny/transcript 回归，Codex R1 effort8 测试与生命周期证据 | aligned |

### Uncovered Observable Behavior

检查全部三份 delta 及本次纠错后，无遗漏对外行为。R6 只是使两种既有自动输入类别的混合满足 all-inputs 自动判定；不新增单条输入的允许类别、不影响普通真人混合轮次，不需为同一既有行为另加功能 delta。R5 evidence_final/inputIdsForTurn 的行为不变集成结论保留，Task通知 Scenario 与其他 delta 仍完整；没有把普通 system/定时输入提升为恢复授权。

Outcome: **aligned**。

本轮只修改本 unit 的 code-review.md 与 verification.md；未改源码/测试/配置/设计，也未启动需清理的服务。regression R3与R4未失效产品证据保留，但R4新增P4须修后窄复验；最终CI仍由caller汇总，不能由aligned推断产品P4已通过、全量绿或生产部署完成。

## Round 7 — quiet stop / mutation synchronization delta verification

> patch base: `a22ee9043`；effective main: `503c98e93`；validated source: `503498e1f94ec05ee99e5ef6367a7ae8bd28bbee`；metadata count correction: `752af9f86`。

- reviewer：同一独立 verifier，未参与实现；2026-10-24 03:01 +08。
- verification_mode：delta + corrected-delta；覆盖用户新授权的 stop只inject不唤醒、在线Task修改同步、UI恢复、冷空责任及正常dispose后最新停止事实恢复。
- verdict：**fail — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**；outcome：**implementation-mismatch**。
- requires_full_verification：false；本次范围已实际覆盖，问题机制与输入时序明确，可按修复影响做targeted closure。随后 caller 的主线集成尚未冻结，不在本轮结论内。
- 现场开始时只有 caller 的未跟踪测试配置；审查途中有共享现场 main merge，源码证据按固定 Git object读取，未把后续实现或未合并文档算入本轮。

### Completeness / Correctness / Coherence

| 用户契约 / 决策 | 实现与证据 | 结果 |
|---|---|---|
| stop完成不因解除fence/旧队列/通知自行启动 | driver block(false) 无followup；pause本次生成的actor relay仅context_only；真实native stop测试检查解锁后零调用、未来新输入首步含stop | covered |
| 父子同Agent的stop协作消息不重新唤醒；同行正常接收 | IM persistTaskNotice optional actor参数只由pauseExecution传递；enqueueRelays仅同agent_id追加context_only。PA attention、SingleThread buffer/inject及Global attention gate沿用 | covered，未扩大为所有system静默 |
| 后续UI明确resume/新责任不被pending控制挡住 | poke reconsider的两处pending检查同时调整，runnable/cancelled责任变化/denial仍生效；native UI_RESUMED请求含stop与独立resume事实 | covered |
| 普通/委托/系统Task变化通知原新负责人 | execute与PA委托按事务提交后notify；改派/删除before+after并集；pause独立post-commit；群解散新post-commit hint；Gateway→Node→PA→driver接线逐入口确认 | covered |
| 空闲无可执行责任不只为同步开模型，运行中下一步重读 | changed在running时steer既有task-change，idle poke仍需runnable；quiescent无followup | covered |
| 离线撤回后首ordinary明确空责任 | pre-step在shown缺席且普通输入存在时注入当前成功snapshot；native回归确认旧历史确实含OLD_RESPONSIBILITY而最新reminder含tasks=[] | covered |
| normal disposal取消pending后只补最新未消费可信stop，不回溯旧stop | restoreStopContext逆扫最后一次inserted；blocked恢复会逆序重新插入同一消息，双stop后选择错误older | **WARNING W1，implementation-mismatch** |
| 架构与来源 | 恢复保留原source/id，不调用followup/steer、不重放普通取消输入；仍通过公开runtime history和inputEvidence，无新存储/Loop或审批豁免 | 除W1的事实选择外符合 |

### WARNING W1 — 最新停止事实被旧消息重新入队顺序覆盖

契约：本unit design R9“先选最近可信停止通知，再判断其资格；不能因较新已消费而回溯旧停止”，以及 canonical Task `停止后的上下文同步 SHALL 不自行启动执行` 的最新未消费可信停止事实保证。位置：冻结 `packages/dsh-integration/src/task-execution.ts:184-190`。

两条stop按真实接受顺序older→newer，fence内并发普通唤醒被reject后，restore按逆序prepend产生older,newer,newer,older插入事件；normal shutdown取消pending，冷恢复逆扫最终插入选older且return。独立真实RuntimeClient/native profile复现确认首次未来模型请求仅有旧stop，最近stop未进入请求。执行命令与原始输出已持久写在同轮code-review；临时profile已关闭清理。该证据证明最新事实丢失，不外推为已发生错误Task恢复/外发。

可执行建议：以产品stop稳定身份的**首次接受顺序**确定最新通知，重复入队不能改变停止发生顺序；选定最新后才检查consumed/pending/current-batch，最新已消费时不得再回溯旧通知。增加两条stop、受拒恢复、normal dispose/restart的原生回归，以及较新已消费不补旧通知的反例。现有32绿/完整656绿都未覆盖该顺序条件，不能消除finding。

### Corrected Delta Reconciliation — Round 7

依本次明确append-only要求，以下为新增续修范围的独立reconciliation，不修改R6历史结论。

| Delta / canonical item | 直接证据 | Outcome |
|---|---|---|
| 原Gateway Task4项ADDED及原10场景中未改部分、Global与reviewer模型能力delta | 实现落点未被本patch改动，R1–R6适用source/test/真实产品证据保留 | aligned（retained） |
| 新第5项ADDED Requirement：停止后的上下文同步不自行启动；停止通知延迟消费 | 无解除fence followup；actor自身notice context_only；futurewake首步；UI resume pending处理 | aligned，最新停止恢复部分见下一行 |
| 同Requirement normal restart保留**最新**未消费可信stop、已消费不重复 | 双stop重新入队原生复现：只恢复older，newer丢失 | implementation-mismatch |
| 外部变更与冷恢复Scenario | 全写入入口commit后hint；群解散新增通知；native首ordinary tasks=[] | aligned |
| canonical与delta完整性/索引计数 | 固定canonical18 Requirements/37 Scenarios；unit Gateway Task delta5 ADDED/10 Scenarios；752af9f86入口索引18 | aligned，无漏归并行为 |

Outcome: **implementation-mismatch**。没有为了适配错误实现修改契约；后续主线63724d53f的Task工具/Feature拆分与canonical19要求不属于当前冻结对象，须下一轮独立集成delta核对。

### 验证与门禁边界

已读取可信32项窄测与128文件656项全量绿日志（Node24，02:56本轮），复用full build/typecheck事实；本轮仅追加一个独立原生latest-stop复现，没有重复全量。新产品旅程由另一独立reviewer在caller隔离栈进行，本轮不占用其数据或服务，不将其未返回结论当作代码缺陷，也不提前代签。

前序feedback事务/receipt、waiting一小时、Global非空结语、SingleThread普通/卡片/混合通知交付、supported-effort与原审批链结论保留。旧“解除fence后启动以消费队列”的停止语义被用户本次授权取代，必须采用本轮passive新基准。仅追加两份报告，未更改实现或共享merge内容。

## Round 8 — R7 P2 closure / main integration delta

> validated source: `3bdcdc546a073c9503eadda6c57573547ceb45db`；patch base: `503498e1f`；R7 report: `7983dcac5`；effective main: `63724d53f`，merge: `d44a48792`。

- 同一独立 verifier；2026-10-24 03:06 +08；verification_mode：targeted-closure + integration delta + corrected-delta。
- verdict：**pass（本次静态/故障与集成范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION；outcome：**aligned**。
- validated_issues：R7 W1/P2 closed；requires_full_verification：false。已按真实共享边界检查upstream与本unit交互，不将“无冲突”当证据；未重新代验feat-645全部产品与其他Feature内部细节。
- 自有报告append-only；未跟踪配置和两文件纯“对齐”元数据修改为caller所有，保留不动。

### Correctness / Coherence 与闭环

| 契约 / 合并风险 | 最终证据 | 结论 |
|---|---|---|
| 最新可信stop按发生/首次接受顺序，重复入队不改变顺序 | 正序事件+稳定ID Set；选最新后才检查资格；不循环回溯已消费最新后的旧通知 | R7 P2 closed |
| 冷恢复normal dispose后最新控制可见且不额外wake | 原真实双stop回归红1→绿、normal teardown与future ordinary输入请求内容；原单stop/不重复测试保留；block(false)仍无followup | aligned |
| Task Feature完整指导不丢，tool独立但不启动自动行为 | Feature guidance完整保留；registerTool与Feature拆分；driver和PA自动snapshot/recover门控未撤销，IMexecution分支仍校Feature | aligned |
| apply feedback依实际Agent当前Feature选择 | registerTool enabled回调为ConfigurationScopes.forAgent；未直接捕获preset配置。Featureoff手动工具实际2次apply成功而无deferContext/send；on状态三终态测试保留 | aligned |
| 配置撤回与责任更新竞态不丢doing/waiting | IMactiveTaskCount跨会话、withdrawsTask gate与save pending withdrawal防护；Taskpause/stop保持可操作，paused等不假作doing | aligned，canonical新增第19项已覆盖 |
| Schedule/配置变化与passive stop的交互 | TaskFeature依赖Cron及工具，实际active Schedule保持运行；waitinspect继续核ownership/session/time；prepare/reservation与tool选择不改cancel/inject/flush/no-wake顺序 | aligned |
| API/Agent/委托/系统写入到Agent同步 | R7全入口追踪保持；main修改Task工具资格但不删post-commit notifyChange、before/after负责人并集或cold空责任补充 | aligned，retained |
| 主线query同修复、Task测试双边并集与规范计数 | SingleThread不注册Global、现有IMACL保留；IM/get vs execution及nativeFeatureoff反馈用例均存在；45cap/19Task正文与索引一致 | aligned |

### 有效证据与独立性

已读 `/tmp/nano-646-stop-order-red.log`：原生older/newer顺序用例在旧实现收到older，1 failed/3 passed，03:00:49，5.94秒。已读 `/tmp/nano-646-followup-integrated.log`：七相关文件 **39 passed**，03:01:56，20.04秒；包括latest-stop、passive/empty/UIresume、Featureon/off反馈及IM/能力接缝。修复直接覆盖上一轮独立真实复现，未靠mock内部函数或提高timeout消除finding。caller已确认集成build/typecheck成功；本轮不重复已有效覆盖的测试，不将上一轮503源码的656全绿冒充当前main集成全量。

当前产品reviewer在同worktree隔离栈实测3bd；本轮未操作其身份/数据/进程，真实产品最终结论与后端全量由各gate提供。静态通过不能替代这些结果。先前一小时waiting、反馈事务/receipt、Global非空结语、SingleThread正常/混合通知交付、原审批与supported-effort未受此merge实质改变，适用证据保留。

### Corrected Delta Reconciliation — Round 8

依本轮append-only要求新增闭环段，R7的implementation-mismatch作为旧版本历史保留。

| Delta / canonical | 最终实现与证据 | Outcome |
|---|---|---|
| 本unitTask原四项ADDED+Global/reviewer模型delta未改范围 | 原646完整指导和事务/来源/交付实现保留；前序适用门禁保留 | aligned（retained） |
| Task新第五项ADDED：passive停止、未来有效触发、同Agentnotice被动 | R7源审与39项有效native/IM回归；main不改no-wake语义 | aligned |
| 同项：normal restart只补最新未消费可信stop、已消费不重复 | first accepted unique ID顺序修复，原生两stop逆序恢复红→绿；最新选定后单次资格检查 | aligned，R7 P2 closed |
| 外部修改/群解散与冷空责任 | 所有提交后通知入口保留，原生首ordinary当前tasks=[]；active责任门控的主线调整未删同步 | aligned |
| 新mainTask工具/Feature独立、Task占用保护 | canonical普通工具与自动责任分开；Featureoff手动tool/无反馈真实runtime用例，IMactiveTask gate+save竞态防护 | aligned |
| canonical/delta归并及入口计数 | 冻结Agent Capabilities45req/168scenario、Task19req/39scenario；gateway索引45/19；本unitTask5ADDED标题全部在canonical，主线占用Requirement与passiveRequirement并集保留 | aligned，无delta-mismatch |

Outcome: **aligned**。未发现遗漏的新对外行为或新架构偏离；两canonical后续仅“对齐”头部元数据变化已逐行核对，不需因此重开功能验证。新full/product门禁仍待对应明确结果，不从本报告推出生产部署或全部交付完成。
