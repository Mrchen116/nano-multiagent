# perf-751 · 独立设计审查

## Round 1

- reviewer：`/root/global_descendant_design`
- reviewer target：`motivation.md`、`design.md`、`M1-incremental-descendants/.gitkeep`，源码基线 `3179cd45f`
- review_mode：`full`
- mode_reason：首轮 Gate 2，涉及 DSH 与 PA 的通知、读取、持久化和恢复边界。
- started_at：`2026-11-10T00:48:32+08:00`
- completed_at：`2026-11-10T00:51:04+08:00`
- duration：`PT2M32S`
- Verdict：**Issues Found**，1 CRITICAL / 4 WARNING。

### 覆盖与证据

- 真实组装从 [Node 初始化与 relay 恢复](../../../../apps/node/src/main.ts#L134)、[GlobalAgent 与 WorkSync 组装](../../../../apps/node/src/main.ts#L429) 到 [Global 通知订阅](../../../../packages/personal-assistant/src/global-agent.ts#L70)、[DSH 目录与读取 RPC](../../../../packages/dsh-integration/src/index.ts#L626) 和 [中心的 journal 校验](../../../../apps/im-server/src/work-records.ts#L154)。当前普通根变化会执行整树扫描，翻页从根重复寻找上一页 ID。DSH 持有可信根、父链和原生事实，PA 复用单执行持久游标和 journal 事务的职责划分合适。运行时分区会检查 `rootSessionId` 和 `sessionId`，新提示和读取应复用该入口与生命周期授权。[运行时分区](../../../../apps/node/src/runtime-partitions.ts#L194) [PA 持久游标与 journal](../../../../packages/personal-assistant/src/inbox.ts#L519)
- 范围覆盖一年历史、每 Gateway 约 50 个 Global、总体约 1,000 用户中的第一个 P0。性能审查采用真实目录消费者对比 1 千和 1 万历史项，分别测热增量和冷恢复。根、Workflow 以及旧记录仍保留在当前消费者路径。R1-W2 和 R1-W4 给出需要纳入的具体负载形状和可计数入口。设计阶段未运行实现或复现基线探针。
- [当前 Work 可见性、父子关系与恢复](../../../../docs/specs/im/agent-work.md#L197) 是消费者验收依据，设计目标保持这些语义，无 delta。此范围无模型输入变化，无待判断的界面交互，无一次性迁移。单 milestone 目录骨架已就绪，能共用一条 DSH → PA → 中心的验收链。现有 [Workflow DSH 用例](../../../../packages/dsh-integration/tests/workflow-native.test.ts#L143) 在结束后读取目录，[PA 子执行恢复用例](../../../../apps/node/tests/global-inbox-native.test.ts#L361) 关闭了通知订阅。需要用生产通知接线的组合用例覆盖以下竞争窗口，并从中心 Work 读回正确 scope、父链、在途和终态。

### Issues

#### R1-C1 · Workflow 归属的可恢复提交顺序尚未确定

[设计第 10 行](design.md#L10) 的创建上下文和持久 runs 之间存在真实间隙。锁定版本 `@deepseek-ai/dsh-subagent@0.2.1-alpha.1` 在 `ctx.subagents.start` 返回前向父 Session 追加 `subagent/catalog`，目录载荷不含 Workflow ID。`NanoWorkflowEngine` 在原生 start 返回后才发布 `workflow/agent-start` 并等待预算落盘，`WorkflowControl` 收到结果后才把 ID 加入尝试列表并保存。根目录和子 Session 活动可能已持久化，进程却在 Workflow 记录保存前中断。内存创建上下文随之消失，重启时 runs 中查无此 ID 无法区分普通 child 和这个 Workflow child。活进程也需要在归属证据变得可用时重调度，子 Agent 可能已经结束且没有更多通知。中心的 `scope` 是不可变身份，错误注册会产生 409，既有传输会暂停这一 journal。需在设计中指明持久 Workflow 身份的来源、与目录可发现性的顺序，以及归属就绪后的重调度。用暂停 Workflow 尝试持久化及在窗口内终止进程的实际路径验证，中心从第一条注册起就应得到真实 Workflow scope、run ID 和父链。[Workflow 启动](../../../../packages/dsh-integration/src/workflow/engine.ts#L394) [尝试持久化](../../../../packages/dsh-integration/src/workflow/control.ts#L199) [中心注册](../../../../apps/im-server/src/work-records.ts#L62) [冲突后的传输](../../../../packages/personal-assistant/src/work-sync.ts#L103)

#### R1-W1 · 点读缺少父目录事实的持久边界

[设计第 9–12 行](design.md#L9) 从实时自有 catalog 事件建立索引并沿用 durable barrier。现有全量扫描先观察、flush 父 Session 再遍历其目录。现有 `session.work.child` 的 barrier 只 flush 被请求的 child。若父执行在中心早已注册，点读沿用该 barrier 就可在父目录新事实仍未持久化时提交子身份。父写入失败或进程退出后，中心会永久保存一条无法从原生持久目录重建的关系。需明确实时 hint 与可用于注册的父目录证据之间的确认点，保留 child 页自身的 barrier，并验证父日志失败而子日志可读时 journal 不会先提交注册。父目录确认应以目标事实的 cut 完成，避免重新读取整份兄弟目录。[实时事件](../../../../packages/dsh-integration/src/index.ts#L294) [当前扫描顺序与 durable barrier](../../../../packages/dsh-integration/src/descendants.ts#L132) [子读取 barrier](../../../../packages/dsh-integration/src/descendants.ts#L173)

#### R1-W2 · 已知 ID 的失败恢复和 root/child 完成边界未收口

[设计第 10–11 行](design.md#L10) 保留既有重试，且允许根事件单独投影。现有重试定时器调用全 Gateway `recoverAll`，所有启用的 Global 即使 root 已确认也会请求完整子树。一条可重试的 child flush 错误足以把一个 ID 的失败扩成约 50 根历史扫描，并在持续失败时重复。现有最新 reconciliation generation 之所以能清除 `workPending`，是因为每次都等待 root 与 child 两个 drain。根单独提交后也沿用这个逻辑，会在较早的 child drain 或重试仍未完成时发出 `processing_pending=false`。需要确定已知 dirty ID 的同范围重试、升级为根发现的条件，以及 root、child、扫描及重试全部完成才清除 pending 的规则。验收覆盖一个根内失败/正常 child 与随后完成的 root 事件，以及其他根访问量为零。[重试及全局恢复](../../../../packages/personal-assistant/src/global-agent.ts#L385) [reconciliation generation](../../../../packages/personal-assistant/src/global-agent.ts#L874) [中心同步中的 pending](../../../../packages/personal-assistant/src/work-sync.ts#L93)

#### R1-W3 · 有状态目录续页的重试语义未定义

[设计第 11 行](design.md#L11) 约束每根一个迭代器并保留越界候选，但未决定消费了一部分位置后观察抛错，或者页面已生成、调用者尚未处理时如何处理该枚举位置。旧实现按 `afterId` 每次重新构造扫描，同一输入不会从上次失败后的内部位置继续。新枚举器若在旧游标上继续会跳过未交付候选，若反复从根重启会重复前缀。设计至少需明确何时可重复同一页、何时废弃整代并由 Gateway 从起始位置重建，以及重连或停止如何拒绝旧代的续页。验证在非首个页内注入失败，检查无候选遗漏、正常翻页总访问线性。正常发现中的 `unavailable` 诊断也要保持未完成状态，不能将越过该分支当作已经补齐。[现有分页与位置校验](../../../../packages/dsh-integration/src/index.ts#L626) [诊断分支](../../../../packages/dsh-integration/src/descendants.ts#L141) [PA 的分页消费](../../../../packages/personal-assistant/src/global-agent.ts#L957)

#### R1-W4 · 热点父级的历史扇出仍可能在点读中重复物化

[设计第 9–10 行与 milestone](design.md#L9) 约束候选发现和工作流查询，但没有限定 `DescendantReader.page` 复用现有 `observe` 的范围。当前 child 的任一新增事件会让缓存 cut 失效，`observe` 此时从全量 projection 物化该 Session 的直接子目录，再把整份 `children` 作为 per-record 行写入。一个运行一年的可继续 child 自身有 1 万个已结束子执行时，即使只收到这个 child 的一条事件，也会访问并写入其全部历史目录。需把事件页观察与目录物化分开，或者明确有可证明的等效增量边界。对照应增加热点非叶子和高扇出祖先，记录目录位置、projection 物化或目录行写入次数，以及 Workflow 关系表访问次数。只测旧叶子数量无法证实目标。[点读路径](../../../../packages/dsh-integration/src/descendants.ts#L124) [全量 projection 和目录写入](../../../../packages/dsh-integration/src/descendants.ts#L173) [Workflow 历史扫描](../../../../packages/dsh-integration/src/workflow/engine.ts#L184)

### Author Resolutions

- R1-C1 accepted。Workflow owner 在 awaited native agent/created 期间持久化 child→run，早于父 catalog 事实；补已有 attempts 的冷索引、catalog 重提示和遗留规则。
- R1-W1 accepted。保存 catalog seq 并确认父的持久 cut；父卸载时读原生位置。保留 child 自身的持久屏障。
- R1-W2 accepted。失败的 ID 留在本根，单根低频重试，Work pending 汇总 root、child、枚举、重试。
- R1-W3 accepted。上一页有幂等重放，失败废弃枚举代并从本根开始，拒绝前代游标；unavailable 保持 pending。
- R1-W4 accepted。事件增量单独读取，热非叶子不物化历史目录；将高扇出非叶子纳入量化。

## Round 2

- reviewer：`/root/global_descendant_design`
- reviewer target：修订后的 `design.md` 与 milestone，源码基线 `3179cd45f`
- review_mode：`delta`
- mode_reason：重新核对 Workflow 的持久化接口、点读与枚举重试。需求边界、包归属和 canonical 消费者沿用 Round 1。
- retained_from：Round 1 的需求规模、三个 P0 的拆分、无契约 delta、无原型和无一次性迁移。
- started_at：`2026-11-10T00:52:02+08:00`
- completed_at：`2026-11-10T00:54:04+08:00`
- duration：`PT2M02S`
- Verdict：**Approved**，0 CRITICAL / 0 WARNING。

### 历史问题闭环与证据

- **R1-C1 closed。** Author 将关系落盘移到匹配直接父的 `agent/created` 中，通过权威 live record 与同一 save queue 写入。核对锁定 DSH 版本的调用顺序：fork provider 等待 in-process driver 的 `agents.create`，Agent factory `publish` 等待 registry 的 `announce`，registry 串行等待 `agent/created`，之后 provider 才返回给 `SubagentRuntime.start` 追加父 catalog。监听器失败会阻止这条原生目录事实发布。与 [Workflow 先保存 run 后驱动程序](../../../../packages/dsh-integration/src/workflow/engine.ts#L529) 及 [序列化 save](../../../../packages/dsh-integration/src/workflow/engine.ts#L123) 兼容。新索引只在目录事实存在时提供 Work 身份，旧 attempts 能恢复归属。测试要求覆盖目录事实已存在而 attempts 尚未保存时的恢复，并检查中心首次注册的 scope 和父链。[Workflow 接入决定](design.md#L11) [Milestone](design.md#L24)
- **R1-W1 closed。** Author 将父目录的确认点与 child 事件屏障拆开。活父 flush 确认先前的目标事件，冷父以 public `SessionHandle.read(offset, length)` 核验记录，既有持久目录继续作为冷发现来源。验收覆盖父 flush 失败而不能提交注册，保持现有中心的父先注册规则。[父目录持久 cut](design.md#L10) [中心注册](../../../../apps/im-server/src/work-records.ts#L62)
- **R1-W2 closed。** Author 指定已知 child 只在本根重试，由 root、child、枚举、重试的汇总状态控制 `workPending`。复审时进一步核实 DSH one-shot provider 可在父目录 append 前发出 child 事件，append 失败时原生会释放该 child。修订稿明确不把尚无可信目录边的提示计入 pending，成功发布目录时重新提示并从持久 child cut 读取。对应规则涵盖创建失败无后续提示、根先结束和已知 ID 重试，避免沿用全 Gateway 定时扫描。[定向重试与通知](design.md#L12) [现有全局重试](../../../../packages/personal-assistant/src/global-agent.ts#L385)
- **R1-W3 closed。** Author 明确上一页可重放，旧代游标拒绝，枚举失败丢弃本代并从同根重开。`unavailable` 继续保持未补齐。单 lookahead 保留越界候选，PA 的持久 child cut 和 journal stable ID 支持重开时跳过已提交工作。复审仅接受正常恢复的一次线性遍历，故障后的同根重开单独记录。[分页协议](design.md#L13) [PA 提交事务](../../../../packages/personal-assistant/src/inbox.ts#L531)
- **R1-W4 closed。** Author 分离热子事件切片和目录观察。现有 root Work 已通过公开 Session range 读取有限切片并 flush，支持在 child 重用同一事件读法。冷 body 读取使用 `projectionMode: 'none'`，热门非叶子无需重写子目录。新增高扇出非叶子和基于访问量的 1 千 / 1 万对照足以区分点读成本与目录大小。[事件增量设计](design.md#L10) [现有 root bounded read](../../../../packages/dsh-integration/src/index.ts#L610) [Milestone](design.md#L24)

### 波及范围

- 以 `agent-context-review` 设计模式检查 Workflow 归属字段的实际消费者。现有 `project` 展开整个 run，模型的 `workflow read` 和 `control` 共同使用 `presentRun`，最终工具输出以 JSON 交付。修订稿在同一入口过滤新增内部字段，维持原有 Workflow 状态、run ID 和下一步可调用动作，milestone 检查模型工具结果。未改变模型可见契约，无 delta。[共享模型投影](../../../../packages/dsh-integration/src/workflow/tool.ts#L13) [模型调用和输出](../../../../packages/dsh-integration/src/workflow/tool.ts#L143) [Work 私有归属与验收](design.md#L11)
- 单 milestone 的行为验收覆盖实接通知的运行中 Workflow、旧轨迹、深层父链和停止恢复。性能对照区分热点非叶子与一次冷发现。结论限于设计与锁定依赖的源码核对，候选实现和运行数据待 milestone 验证。

### Issues

无。
