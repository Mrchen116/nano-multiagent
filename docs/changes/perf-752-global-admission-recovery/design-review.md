# perf-752 · Gate 2 设计审查

## Round 1

- reviewer: `/root/global_admission_design`（独立审查）
- target: `3179cd45f`，`motivation.md`（`dd7b821c`）、`design.md`（`5a726f50`）与 `M1-global-admission/` 骨架
- review_mode: `full`
- mode_reason: 首轮审查，覆盖接单索引、恢复顺序、模型输入、契约和验收
- started_at: `2026-11-10T00:49:55+08:00`
- completed_at: `2026-11-10T00:53:00+08:00`
- duration: `3m05s`
- verdict: **Issues Found**（0 CRITICAL / 4 WARNING）

### 覆盖与证据

- 从普通 Global 的真实装配核对了 `relay.message → GlobalAgent.receive → session.ensure/lookup/submit`，以及 `RuntimeSupervisor.initialize/onReady` 和 Relay 重连。`initialize` 的全 binding 子执行检查确实在 DSH 接单之前。Relay 的入站回调可并行，supervisor 在 `onReady` 前开放内部 RPC，节点仍在 `onReady` 和重连路径等待产品恢复后才发布相应的生命周期状态。因此需要分别验证运行时可接收 RPC、节点真实接到首个交办以及该根执行前的恢复条件。 [Node 装配](../../../apps/node/src/main.ts#L114) [真实 Relay 入口](../../../apps/node/src/main.ts#L289) [Relay 重连](../../../apps/node/src/main.ts#L313) [并行入站回调](../../../packages/channels/src/index.ts#L300) [Supervisor](../../../packages/dsh-integration/src/client.ts#L148)
- 职责划分成立。按 Session 实例缓存纯身份投影和 ModelRun 查证属于 DSH integration，产品接单与 Work 队列排序属于 PA，Node 持有进程就绪与真实 Relay 装配。既有提交去重、原生持久屏障、绑定身份、通知账本和分根 drain 都有可复用落点。`snapshotEvents` 在锁定版本是公开的半开区间 API，非全区间只复制指定范围。它带上游弃用标记，宜收敛已有生产调用并复用公开 `session/event` 订阅，避免扩大对此读取面的依赖。公开 `agents.resume` 仍激活原生历史，本单元不以热证据推断冷首次激活也变成常量成本。 [架构边界](../../../SPEC.md#代码归属) [已有事件订阅](../../../packages/dsh-integration/src/index.ts#L294) [已有区间读](../../../packages/dsh-integration/src/index.ts#L572) [原会话恢复](../../../packages/dsh-integration/src/owned-sessions.ts#L158)
- Agent Context 设计审查以 Global 根的第一个正常模型请求为消费点。现有 hook 在 `enter` 且有实际输入时，在正常输入前交付含子会话 ID、异常退出和无结尾内容的系统事实。角色、来源、顺序和消费屏障可以复用。受控 provider 捕获实际首个请求及后续请求足以验证装配和去重，结合强杀及主动停止验证事实选择。没有新前端视觉决定或待对齐交互，原型与 must-match 不适用。设计和现状均保留原生日志，未发现一次性迁移需求。本轮为静态审查，未运行实现或性能实验。 [现有通知装配](../../../packages/dsh-integration/src/subagent-recovery.ts#L29) [真实 DSH 测试](../../../packages/dsh-integration/tests/trajectory-runs.test.ts#L148) [原型边界](../../../.agents/skills/frontend-experience-review/references/prototype-and-runbook.md#原型的判断范围)

### Issues

#### R1-W1 · 前台恢复没有划出 Inbox 的持久事实切面

`design.md` 第 11 行只说待办根先做「安全所需操作」。现行 `recoverAll` 在 `wake` 前等待同时含 root 和 child 的 `reconcile`。其中 root 页同时提交原生 `tool/result` 对应的完整 Inbox 内容及部分读片段，并据逻辑 `turn/end` 持久化回执。一次常见的崩溃切面是原生读取结果已落盘、产品未标已读。若先 `wake` 再让整个 root drain 补齐，`unreadAttention()` 仍会把该输入算作未读，可能补发已消费的冷重启交办。若保留对原 drain 的等待，子执行和展示回放继续在前台。还需考虑同一根的新 Relay 请求和首个原生触发可与全局恢复并行。请明确在什么持久位置、用哪些既有事实查证，在同一根的冷恢复 wake 与新触发之前处理待查读片段和必要控制，终态回执按什么顺序补记。可借鉴 `session.publication` 对已持久原生结果的有界读取。保留待办同根围栏，让纯 Work 展示和后代补齐独立推进，并明确与 perf-751 的 drain 归属和合并顺序。 [现有恢复顺序](../../../packages/personal-assistant/src/global-agent.ts#L393) [原生页中的业务提交](../../../packages/personal-assistant/src/global-agent.ts#L897) [冷唤醒查证](../../../packages/personal-assistant/src/global-agent.ts#L284) [已有持久读取复用点](../../../packages/personal-assistant/src/global-agent.ts#L791)

#### R1-W2 · 延迟发现中断缺少稳定取证切面与明确的待处理状态

`design.md` 第 11 行将中断发现放到根 `pre-step`。`interruptedChildren()` 目前只采最新边界且忽略已 live 的 child，而 `schedule.deleted.notify` 能在没有任何根模型 step 时走 `resolveManaged()` 激活原 child。因此现行启动时可查证并排队的中断，在按需读取时可能已经被后来的状态覆盖。另一个可复现的差异是单个 child 的 `SessionQueryError` 会被记录后跳过，函数仍返回部分结果。initialize 当前只记警告，没有可直接继承的 per-root 重试完成状态。请固定对应的恢复取证切面，例如在相关原生 child 被首次接续或改变该事实前按根查证，或提供等价的有界稳定证据。说明部分失败、取消或持久写失败何时继续重试，已有 durable pending 在同一轮仍可按现有规则交付，并且仅在 flush 证实 native `user/message` 后退休。建议用已有强杀轨迹测试补入先激活 child、空/拒绝 step、部分读失败再成功及二次崩溃中与新方案直接相关的场景。 [当前检查与部分失败](../../../packages/dsh-integration/src/descendants.ts#L79) [可先激活 child 的产品入口](../../../packages/dsh-integration/src/index.ts#L846) [当前消费屏障](../../../packages/dsh-integration/src/subagent-recovery.ts#L63)

当前 canonical Scenario 明确承诺重启时持久排队，下一次正常触发后交付。基线测试在首个触发前读取 durable pending，并再重启确认仍存在。选用新的按需发现时机时，需要对该 Scenario 给出 `MODIFIED`，保留本节其他场景及通知的 ID、去重、被动触发和处理责任。若设计仍兑现原来的排队时机，请说明机制并据此保留无 delta 裁决。 [现行契约](../../specs/gateway/global-agent.md#requirement-全局输入的持久接收与工作记录上传独立) [待通知测试](../../../packages/dsh-integration/tests/trajectory-runs.test.ts#L159)

#### R1-W3 · 索引等价的测试需要独立于候选 reducer 的基准

`design.md` 第 5、7、15 行允许候选和「现有纯函数的验证路径」共用新 reducer。生产复用合理，但如果逐前缀对照两端都是同一个新 reducer，就无法识别语义漂移。例如同 ID 已在 A 轮终结，后被 B 轮 claim 且未写 transcript 时，旧实现同时保有 A 的 `terminal` 和 B 的 `turn`，直到 B 终结或取消覆盖。仅从当前归属反查轮次终态会改变结果。`inputIdsForTurn` 另有首次入队顺序和只返回曾入队 ID 的语义。ModelRun 则在 `turn/end` 才给旧 run 增加 inputs，补入较早 run 的映射不能覆盖后插入且同样拥有该 input 的 run。请保留冻结旧 reducer 的测试参照或独立的固定预期，覆盖上述事件前缀、恢复后的 sidecar 插入顺序以及 `submit`/`lookup` 的真实 durable 结果。 [旧查证与轮归属](../../../packages/dsh-integration/src/input-evidence.ts#L5) [ModelRun 顺序](../../../packages/dsh-integration/src/model-fallback.ts#L175) [迟到输入归属](../../../packages/dsh-integration/src/model-fallback.ts#L290) [RPC 持久结果](../../../packages/dsh-integration/src/index.ts#L537)

#### R1-W4 · M1 需要把规模目标转成真实入口可判定的退出标准

`design.md` 第 15 行已有 4 万/40 万热后缀与双根并发，适合定位机制，但缺少 milestone 表和能区分「后台扫盘提前开始」与「无关根确实更早接单」的实栈对照。需要在 M1 固定同一 Gateway 的代表性 50 Global、长年历史和子执行扇出，说明 1000 账号从何进入负载或为何它不是本地性能的自变量。指定基线/候选、冷/热切面、旧根正文读取计数，以及用可控阻塞的旧根 Work/中断读取验证独立根通过真实 Relay 获得可恢复输入并启动执行。记录首个真实接单、后台完成与总读取，分别记录按需检查对目标根首个模型请求的成本。可复用仓库隔离 Node/DSH 强杀 fixture 和真实 Relay 旅程，不需要新前端或生产环境。若共享日志固定后缀只测提交查证，验收结果限定到该路径，普通模型轮次的历史访问量另行标明。 [规模需求](motivation.md#原始诉求) [现有 M1 验收描述](design.md#验收与回退) [既有 Relay 恢复旅程](../../../apps/im-server/tests/e2e/relay-recovery.test.ts) [Milestone 规范](../../development/change-workflow.md#阶段-2设计)

### Author Resolutions

- R1-W1 accepted。保留同根的前台 root 证据与控制、回执，不把 reconcileRoot 整体异步化；只拆子执行核对。
- R1-W2 accepted。检查改在对应 OwnedSessions 首次根/历史 child 激活前，在已授权父链后且先于覆盖证据。保留旧 pending，partial 保持可重试，补 canonical timing delta。
- R1-W3 accepted。独立旧折叠 oracle 覆盖逐前缀与迟到 ModelRun 归属。
- R1-W4 accepted。补真实 Relay、SIGKILL、50 根规模验收和分段指标。

## Round 2

- reviewer: `/root/global_admission_design`（独立复审）
- target: `57b2200d`（相对 R1 的受影响产品源码未变），`design.md`（`512d5813`）、Gateway delta（`4746fe5a`）及 M1 骨架
- review_mode: `delta`
- mode_reason: 恢复时机移到共享激活边界，新增 canonical delta 与 M1 验收标准，需要沿受影响入口复查
- retained_from: Round 1 的职责划分、公开 DSH 边界与冷原生激活限制、无界面原型和无一次性迁移仍适用
- started_at: `2026-11-10T00:54:39+08:00`
- completed_at: `2026-11-10T00:55:50+08:00`
- duration: `1m11s`
- verdict: **Issues Found**（0 CRITICAL / 2 WARNING）

### 历史问题闭环

| ID | 核实结果 | 状态 |
| --- | --- | --- |
| R1-W1 | 保留同根 `reconcileRoot`、控制和终态回执作为 wake 前台事实，旧后代 Work 使用原分根 drain 异步补齐，结算空闲根不激活，状态仅在真实补齐后更新。设计明确新 Relay 同根也走同一前台工作。实施验收应覆盖恢复期间并发到达的同根 Relay 或状态回调，因为 `lifecycle.run` 仅传播 epoch，本身不做互斥。 [修订设计](design.md#恢复) [现有并行入口](../../../packages/personal-assistant/src/global-agent.ts#L70) [生命周期 scope](../../../packages/personal-assistant/src/agent-lifecycle.ts#L45) | closed |
| R1-W2 | 成功路径的前置钩子可以覆盖正常根恢复、原生 Schedule 和 `schedule.deleted.notify` 的历史 child 恢复。与现有 durable pending/flush 兼容，delta 锚定现行 Requirement 并完整保留其他 Scenario。部分失败遇到原生子执行重新激活时仍缺决策，见 R2-W1。 [前置钩子设计](design.md#恢复) [根与原生 Schedule](../../../packages/dsh-integration/src/owned-sessions.ts#L158) [已校验 child 恢复](../../../packages/dsh-integration/src/owned-sessions.ts#L77) [Gateway delta](specs/gateway/global-agent.md) | still-open |
| R1-W3 | 旧纯折叠保留作独立 oracle，ModelRun 明确按首次插入顺序而非迟到输入的最后更新时间归属。RPC 仍以 flush 后证据返回。 [热路径设计](design.md#热路径) | closed |
| R1-W4 | M1 已增加真实 Relay、50 根、SIGKILL 及分段指标。尚未定义可以排除全量读取移到后台的负载和验收，见 R2-W2。 [Milestone](design.md#milestone-与能力) | still-open |

### Issues

#### R2-W1 · 首次检查部分失败后，原生 child 可绕开 OwnedSessions 再次激活

`design.md` 第 11 行要求延后重试，却没有明确部分失败时是否准许当前根/子激活。若允许根进入正常模型请求，Global `send_message(agent_id, ...)` 会直接执行 DSH 原生工具。锁定版本公开 `SubagentRuntime.sendMessage` 明确可以冷恢复缺席的直属 continuable child，该路径不调用 Nano `OwnedSessions`。一个 child 首次观察失败、根继续、模型给它发消息后，即使下一次观察成功，现有检查也可能因 child 已 live 或最新轮次已更新而漏掉通知。若决定等根检查完全成功才激活，也应明确故障时同根的可观察结果和重试入口，避免实现把既有 durable pending 与新发现成败一起丢掉。请收口暂不可读、可证实缺失和记录写失败时的策略，让可能改变证据的接续等到相应取证完成或有等价稳定证据，并用实际 native 路径验证。受控 provider 需要检查首个符合条件请求；若确实只能晚于该请求交付，delta 要明确何时可见。 [原生工具分流](../../../packages/dsh-integration/src/global-mode.ts#L65) [当前最新边界与 live 过滤](../../../packages/dsh-integration/src/descendants.ts#L79) [现有 pending 消费](../../../packages/dsh-integration/src/subagent-recovery.ts#L63)

#### R2-W2 · 冷启对照还缺可控竞争条件与总读取口径

`design.md` 第 17、23 行增加了规模与真实入口，但仅并发两根并报告就绪时间/RSS 无法区分是旧后代读取移出前台，还是冷启立即派发了同样的全量 I/O。请固定代表性冷子执行扇出，以及可暂停 A 根旧 Work/中断检查的对照点，直接以 A 尚未完成时 B 的真实 Relay 接单与持久结果判定。分别记录首个接单、旧根待办完成和相同观察窗口的旧根正文读取量，说明 1000 账号怎样代表为真实来源或为何该本地链路主要受事件与子执行规模影响。该补充可以落在现有 M1 单行或证据安排内。 [现有验收](design.md#验收与回退) [规模目标](motivation.md#原始诉求)

### Author Resolutions

- R1-W2 accepted for R2 residual。根级核对失败/部分时，先保留已核实 notice 并阻止该根进入第一次模型 step，确保任何 native 路径不会先冷启未知 child。隔离为该根的可重试错误，其他根可继续。
- R1-W4 accepted for R2 residual。增加持有 A 的受控阻塞、B 的真实 Relay 提交和 ready 前后日志正文总数/字节。

## Round 3

- reviewer: `/root/global_admission_design`（独立复审）
- target: `57b2200d` 产品基线，`design.md`（`c3a4d989`）、Gateway delta（`4746fe5a`）及 M1 骨架
- review_mode: `closure`
- mode_reason: 本轮收口两个既有发现，公开接口、需求范围与 canonical delta 保持 R2 已审版本
- retained_from: Round 1 的公开 DSH 与原型判断，Round 2 的 root 前台事实、独立索引 oracle 和 delta 锚点。并行 perf-751 实施工作树不作为本单元运行证据。
- started_at: `2026-11-10T01:02:01+08:00`
- completed_at: `2026-11-10T01:02:25+08:00`
- duration: `24s`
- verdict: **Approved**（0 CRITICAL / 0 WARNING）

### 历史问题闭环

| ID | 核实结果 | 状态 |
| --- | --- | --- |
| R2-W1（R1-W2） | Author Resolution 已写入第 11 行。已验证的子中断先持久化；部分读取不放行该根首次激活，原输入和旧 pending 保留为同根重试。`OwnedSessions` 根恢复走 coalesced resolve，直接管理的历史 child 要先通过父链校验并取得同一根。既然部分失败时根无法开始模型 step，原生 `send_message` 就没有可用于冷唤醒未知 child 的 live 根。恢复后仍从已有通知入口向首个符合条件的请求交付，现有 flush 后退休规则适用。 [修订设计](design.md#恢复) [根与历史 child 顺序](../../../packages/dsh-integration/src/owned-sessions.ts#L77) [原生发送分流](../../../packages/dsh-integration/src/global-mode.ts#L65) [已持久通知消费](../../../packages/dsh-integration/src/subagent-recovery.ts#L63) | closed |
| R2-W2（R1-W4） | M1 指定在 A 根子观察处受控暂停，经真实 Relay 验证 B 在 A 放行前持久接单，释放后验证 A 通知和回执。对照固定历史规模下的访问量，并测 readiness 前后的正文读次数、字节、就绪时间和 RSS，能区分可并发接单与迁移同等历史 I/O。中心 1,000 账号的授权与 Web 读取规模交由 perf-753，当前路径仍使用真实 Relay 用户授权。 [M1](design.md#milestone-与能力) [perf-753 规模验收](https://github.com/Mrchen116/nano-multiagent/blob/56c5083770805182832fc52543b0c35aef5a430c/docs/changes/perf-753-bounded-work-reads/design.md#milestone) | closed |

本轮裁决限于设计。实际原生激活、故障重试、模型请求和性能结果由 M1 取证。

## Round 4

- reviewer: `/root/global_admission_design`（独立复审）
- target: `f8892a95` 装配基线，`design.md`（`0cc94e43`）新增注册屏障与补齐调度，Gateway delta（`4746fe5a`）未变
- review_mode: `delta`
- mode_reason: 修改 Node 启动等待链、恢复任务归属与冷 Work 调度，需复查实际注册与关闭路径
- retained_from: Round 3 的同根前台事实、原生 pre-activation 中断检查、索引 oracle 与中断时机 delta。此次不复审索引实现。
- started_at: `2026-11-10T01:26:43+08:00`
- completed_at: `2026-11-10T01:28:15+08:00`
- duration: `1m32s`
- verdict: **Issues Found**（0 CRITICAL / 2 WARNING）

### 覆盖与证据

- 当前启动链的发现成立。`relay.message` 等 `lifecycleSync`。初次同步先保存所有 lifecycle intent，再等待每 Agent 的 `applyKnown`。首次 `startAgent` 经 Supervisor 启动，等 `onReady` 返回。由此当前 Global、外部入口和其他产品恢复都可能从 `onReady` 传递到入站等待。按 Node 权威等待生命周期/原生围栏、按根合并接单恢复，符合现行断线重连与停用契约。 [入站等待](../../../apps/node/src/main.ts#L195) [初次注册](../../../apps/node/src/main.ts#L300) [同步权威](../../../apps/node/src/agent-lifecycle.ts#L29) [Supervisor](../../../packages/dsh-integration/src/client.ts#L148) [现行重连契约](../../specs/gateway/service-lifecycle.md#requirement-断线后自动重连且保持投递与权限边界)
- 逐根后台目录发现可以复用 perf-751 的持久游标、续页与 catalog witness。现有 DSH witness 先匹配受信任 header 与 event count/size，命中且已覆盖才避免读取正文。串行冷目录发现限制启动并发，独立根的前台恢复继续使用自己的 native 事实。设计继续保留缺证明时的待补齐状态，方向满足 IM Work 现行契约，无需新增 Work delta。Node 组装验证要使用 `main.ts` 的同一注册路径。现有 A/B 测试草稿用 `WebRelayConnection.onFrame` 直接调用 `GlobalAgent.receive`，能验证真实连接与 DSH 隔离，不能单独证明 `lifecycleSync` 与 `onReady` 的等待已解除。 [已覆盖证据](../../../packages/dsh-integration/src/descendants.ts#L169) [Work 契约](../../specs/im/agent-work.md#requirement-已保存工作记录直接读取节点恢复只补缺口) [A/B 草稿装配](../../../apps/node/tests/global-relay-scale.test.ts#L125)

### Issues

#### R4-W1 · 注册前置还有会激活旧根或扫描后代的传递路径

第 29 行提出只等待 lifecycle 与 native fence，明确移走 `globalProduct.recover` 与 `external.recover`。实际 `onReady` 还等待 `tasks.recoverStops`、`scheduleDeletions.recover` 和 `tasks.recover`。前者写 `task.execution.block` 后执行 `session.ensure`，会进入本单元的冷根中断核对。Schedule 通知直接经 `schedule.deleted.notify` 恢复原子会话。Task 已有责任恢复也对 Global 执行 `session.ensure`。初次 lifecycle 同步还通过 `start` 等同一 `recoverStops`，通过 `disable` 在原生清理确认后等 `globalProduct.recordStopped` 全量旧 Work。这些路径即使移走两条显式恢复调用，也能让有待办的 A 挂住 B。请区分前台持久禁用/停止围栏与按根恢复的动作、通知、终态 Work 补齐，保持同根动作原有顺序和真实 stop/deletion 证明，并明确哪些路径必须离开共享等待链。Node 组装用至少一种真实待办控制/恢复触发 A 再验证 B，防止只覆盖无控制的空闲配置。 [Supervisor 回调](../../../apps/node/src/main.ts#L134) [enable/disable 回调](../../../apps/node/src/main.ts#L578) [Task 恢复与停止](../../../packages/personal-assistant/src/task-execution.ts#L85) [Schedule 删除通知](../../../apps/node/src/main.ts#L441) [停止后后代补齐](../../../packages/personal-assistant/src/global-agent.ts#L1038)

#### R4-W2 · 后台恢复需要可收拢的 owner 与实际隔离的外部重试

第 29–31 行写由 `admitted` 生命周期追踪并按根重试。现有 `admitted` 仅增减更新屏障的计数，不记录或等待 promise。`ExternalChannels.recover()` 按 DB 行串行调用 `admit`，未把恢复操作放进 `external.stop()` 所等待的 `admissions`。若脱离回调只 `void admitted(...)`，首条 A 入站失败会终止整个外部恢复，后面的 B 即使根可用也得等再次调用。此外节点关闭可能与仍在操作 SQLite 的恢复交叠。请明确用哪一已有 owner 持有/收拢脱离就绪的任务，并让外部持久入站保持同根顺序、失败只留该根待恢复。后台冷 Work 的排队、重试和停止同样应走既有可收拢的 drain 状态，失败/取消时继续保留真实未确认状态。 [admitted 计数](../../../apps/node/src/main.ts#L38) [节点关闭顺序](../../../apps/node/src/main.ts#L620) [外部顺序恢复](../../../packages/personal-assistant/src/external.ts#L109) [外部 stop 等待范围](../../../packages/personal-assistant/src/external.ts#L397) [既有 Work drain](../../../packages/personal-assistant/src/global-agent.ts#L912)

### Author Resolutions

- R4-W1 accepted。实际 Relay 等待已写入的注册快照和目标 Agent 的 transition；共享 host ready 不等待能激活 Global 或历史 child 的恢复，原生 stop/schedule fences 和同 Agent transition 仍先于该 Agent 接单。
- R4-W2 accepted。由 Node 跟踪同 partition/generation 的后台任务至关闭，外部重放按 Agent 隔离并保持各自顺序、失败状态及重试。

## Round 5

- reviewer: `/root/global_admission_design`（独立复审）
- target: `f8892a95` 装配基线，`design.md`（`1750fb9f`）第 27–35 行，Gateway delta（`4746fe5a`）未变
- review_mode: `closure`
- mode_reason: 复核 R4 的注册等待与后台恢复归属两项发现
- retained_from: Round 3 的接单及中断设计，Round 4 的串行冷 Work 目录发现、正文 witness 和现行契约判断
- started_at: `2026-11-10T01:30:30+08:00`
- completed_at: `2026-11-10T01:31:02+08:00`
- duration: `32s`
- verdict: **Approved**（0 CRITICAL / 0 WARNING）

### 历史问题闭环

| ID | 核实结果 | 状态 |
| --- | --- | --- |
| R4-W1 | 第 29 行明确三个不同条件。完整生命周期快照先持久写入，host ready 确认基础可用性及原生围栏，入站按已认证目标等待对应 transition。Task stop/recover、Schedule 删除通知、Global/外部重放均脱离共享 `onReady`；停用后旧 Work 仍跟随目标 transition。NodeAgentLifecycle 已有按 Agent 记录的 `applying` Promise 和同步保存所有快照的阶段，可复用这两处来拆共享等待。整节点 `connected` 可以等控制收口，B 的真实入站及模型开始可先观察，原生禁用/停止权威保持。 [修订设计](design.md#注册屏障与补齐调度) [现有每 Agent transition](../../../apps/node/src/agent-lifecycle.ts#L59) [初始 native fences](../../../apps/node/src/main.ts#L116) | closed |
| R4-W2 | 第 31–33 行将更新计数与真正的后台 promise owner 分开。Node 持有同 partition/generation 的恢复并合并，关闭先停止调度和 I/O，再等待受管任务后关闭存储，过期 generation 不贡献新结论。外部重放按 Agent 持久输入顺序执行，失败只留该根待重试，其他 Agent 继续；既有 durable inbound 行和 lifecycle revision 可复用。冷 Work 仍按既有分根状态提交真实完成，队列未完成时继续提示待补齐。 [修订设计](design.md#注册屏障与补齐调度) [现有持久入站和 scope](../../../packages/personal-assistant/src/external.ts#L105) [现有待补齐契约](../../specs/im/agent-work.md#requirement-已保存工作记录直接读取节点恢复只补缺口) | closed |

设计阶段确认方案成立。M1 仍应让真实 Node 注册入口遇到 A 的待办控制或旧历史阻塞，区分 B 的已持久接单与整节点 `connected`，并核对外部重放失败隔离和关闭收拢。本轮未执行运行验证。
