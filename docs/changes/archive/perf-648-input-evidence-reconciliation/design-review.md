# perf-648 Design Review

## Round 1

### Metadata

- reviewer: independent Codex subagent `/root/design_review`，未参与本 unit 设计或实现。
- reviewer target: `docs/changes/perf-648-input-evidence-reconciliation/`，受审基线 `cb1cfbfd816fc23abc2f8f930710978d5aaf3fd2`。
- review_mode: `full`。
- mode_reason: 首轮 Gate 2，独立覆盖需求、现状接线、决策、数据流、delta 与 milestone。
- started_at: `2026-10-23T23:12:59+08:00`（首次显式计时记录，此前已读取受审文档）。
- completed_at: `2026-10-23T23:17:25+08:00`。
- duration: `266s`（从首次显式计时记录起，不包含之前文档读取）。
- validated_at / executed_base: `cb1cfbfd816fc23abc2f8f930710978d5aaf3fd2`。共享 main 在审查中推进到 `15063908dc738f6485d7255c5798430d4f1841ab`；受审 unit 相对基线无 diff。
- 受审 Git blob：`design.md = 0cef00802a94dbb9507b2c615772a50495bde571`；`motivation.md = 70cf28fc77c15d20a20192b6b61479719b601dd8`；`M1-pending-evidence/.gitkeep` 已存在且为空。
- 工作边界：只写本报告；不改设计、产品代码或其他任务内容，不提交。开工发现 bugfix-644 staged 内容和 perf-649 untracked 内容，均保留。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 未通过。**

输入筛选、缺失证据保守处理及 delivery/receipt 分离总体成立，但设计尚未封闭“已固定逻辑证据仍被后来的物理事件改写”的既有写路径。该缺口会使永久跳过回查的行不再保存其权威最终证据，需要 author 收口后复审。

### Coverage 与证据

1. **需求与性能现状。** `single-thread.ts:194-206` 确实在 durable observe、recordEvents 之后对 `store.inputs(sessionId)` 全量串行 lookup。核读 motivation 引用的本机 `lookup-probe.mts` 和 `results.jsonl`：1000 已完成输入、零事件仍为 1000 次 lookup，1 ms 人工延迟结果为 1155 ms；这是模拟 RPC 的规模证据，不是生产延迟。SQL `(session_id,evidence_final)` 筛选 input id 能兑现本 unit 的逐输入 RPC 目标；保留交付全量遍历意味着本方案不承诺整个 drain 成为 O(K)。
2. **实际产品接线与职责。** `apps/node/src/main.ts:335-338` 真实构造 SingleThread，传入 NodeStore、runtime 与 external relay；启动、重连恢复调用 `product.recover`（同文件 114、276、393、403）。`single-thread.ts:162-170` 恢复原绑定并 reconcile。按 `SPEC.md:29-47`，输入事实选择与交付归 PA/NodeStore，执行与 logical run 投影归 integration。复用现有 RuntimePort、lookup/modelRuns 和 NodeStore 字段，优于另建共享运行协议、TTL 或事件缓存框架；无跨包 private import、第二套 Agent Loop 或新 runtime API。与 runtime replay / descendants 等并行优化无必需依赖。
3. **物理 attempt 与逻辑 run。** `dsh-integration/src/index.ts:362-366,376-381` 是真实 lookup/observe handlers；`model-fallback.ts:169-179` 将所属 input 映射到 logical turn，运行中隐藏 terminal，completed 才暴露 run.terminal。`model-fallback.ts:229-299` 负责 attempt 与 switching/completed 转换。`presentation.ts:82-90` 将物理事件映射至逻辑 turn，并屏蔽中间 turn/end。设计要求关联 run completed、明确 pending=false 且不信旧 terminal，能防止通常的中间失败收敛；遗漏的后续物理事件写入见 R1-W1。
4. **缺失证据、未消费与取消。** `input-evidence.ts:5-41` 从入队、claim、user/message 和 turn/end 重建 accepted/pending/turn/terminal；`tests/input-evidence.test.ts:13-32` 已有 claim 中断、仍排队、取消未消费的语义用例。明确缺少 pending 不收敛、旧行默认 0、无关联 run 时允许权威普通终态，均与现有协议相容。取消无 turn 行在 `single-thread.ts:208` 跳过交付，设计明确保留现状，没有另造 receipt 规则。
5. **delivery/receipt 恢复。** `single-thread.ts:212-216` 对已确认交付仍调用 receipt；`382-387` 在 relay ACK 成功后才 confirmReceipt。`store.ts:233-243,261-265` 持久化 delivery 身份和 receipt。只跳过 lookup、仍遍历所有 input 的决定能保留丢失 ACK 后的重试与同一消息身份；`tests/store.test.ts:9-31` 提供重开 DB 保留归属/交付的既有测试基础。设计把 evidence_final 与完成 receipt 解耦合理，仍须 M1 新用例证明“终态已缓存且 receipt 尚未 ACK”的组合。
6. **迁移、回滚与数据所有权。** inputs 原 schema 见 `store.ts:29-33`；普通 receive 和原生 schedule/system input 插入均显式列名（173、224），添加默认 0 字段可兼容旧插入与旧版读取。单 UPDATE 记录证据与标记可避免半写入，但 `recordEvents:205` 是另一个 terminal writer，当前方案未限制，构成 R1-W1。无须扩展成新状态机即可在本 unit 内解决。
7. **delta 与用户约束。** no spec delta 合理：`routing-delivery.md` 的原聊天恢复与 `agent-capabilities.md:40-99` 的备用模型顺序、失败提示、切换说明、最终回复保持不变。当前设计不修改客户端布局/交互，无 prototype 或多平台视觉决策要求。只读核对源码与文档，没有把测试 fixture、模拟计时或静态阅读说成产品验收。
8. **milestone 与后续验收。** 单一 M1 目录与范围匹配。1000+K、旧数据库、fallback switching/多 attempt、取消、重开 DB、ACK 故障覆盖了主要目标；需补 R1-W1 的 observe/lookup 跨轮时序。runbook 已指定隔离真栈、同一 IM API、独立身份及清理，并分别给 worker 协议检查和 reviewer 两个真实旅程。模型代理、fallback 故障触发和重连环境仍由 caller 在实施验收时准备，本轮未启动生产或 E2E 服务。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 固定的逻辑终态仍可被下一轮补录的物理 turn/end 覆写

- **位置：** `design.md:31-43`（最终证据持久化、永久筛选跳过与 recordEvents 原序）；实际冲突写路径 `packages/personal-assistant/src/store.ts:205`。
- **证据：** `recordEvents` 每见物理 `turn/end` 都执行 `UPDATE inputs SET terminal=? WHERE session_id=? AND turn=?`。它既不判断证据是否已固定，也不使用 logicalEvents。当前全量 lookup 会在同一 drain 随后用权威证据纠正它；新方案跳过 final 行后失去这一纠正。
- **可达时序：** observe 先取 events 快照，之后 await flush/toolViews（`dsh-integration/src/index.ts:378-381`），PA 再串行 lookup。某输入的 run 在该观察中尚不存在，而较晚 lookup 时已完成主模型失败及备用成功，设计允许按 fresh lookup 缓存 `turn=1,terminal=completed,evidence_final=1`。下一 drain 补录物理 turn 1 的 error 与 turn 2 的 completed；前者命中 input 的逻辑 turn 1，后者不命中该行。recordEvents 把 terminal 改成主模型 error，lookupInputIds 又永久排除该行。无关联 run 的允许分支使设计中的“观察仍 running 则推迟收敛”不能消除这个时序。
- **本轮最窄复现：** 用 `pnpm exec tsx -e` 直接实例化真实 NodeStore `:memory:`，保存输入的 `turn=1,terminal=completed`，然后 `recordEvents` 写入 turn 1 error 和 turn 2 completed。结果从 `{"kind":"completed"}` 变成 `{"kind":"error","error":{"code":"AUTH","message":"primary failed"}}`。没有修改仓库文件。该探针验证当前覆盖写；永久不修复的后果来自拟议 evidence_final 筛选，未声称已运行尚不存在的实现。
- **未修后果：** 数据库会保留“已最终确定”标记，却保存物理失败而非逻辑最终证据，并跨重启继续跳过补证据，违反本 unit 的可靠复用目标。当前交付主体还读取 logicalEvents，不能据此断言该探针已导致真实用户漏回复；问题是新设计冻结了当前会被 lookup 修正的错误事实。
- **所需收口：** 明确固定证据后各写入者的权限，保证 recordEvents 不会改写已固定逻辑证据，或采用等价的本地顺序/覆盖保护；保持未固定行与 Global 调用的原行为。在 M1 加入“观察未含该 run → lookup 已最终完成 → 下一 drain 补物理失败/成功事件 → 重开同一 DB”的用例，同时断言逻辑 terminal 不变、无历史 lookup、交付及 receipt 无重复。无需新共享 runtime API。

### Recommendations

无额外建议；修订集中处理 R1-W1，避免扩展至 runtime 重放或交付算法优化。

### Author Resolutions

- R1-W1: accepted。核实 store.recordEvents 的 UPDATE 无条件覆盖 terminal，且 session.observe 在 flush 前获取 events 快照。design 的“最终逻辑证据不再被延迟物理事件覆盖”明确写入所有权：物理事件仅更新 evidence_final=0 行；M1 加入跨 drain 延迟事件回归。原事件持久化及未定输入行为不变，不需要 runtime 协议变更。


## Round 2

### Metadata

- reviewer: independent Codex subagent `/root/design_review`，沿用 Round 1 reviewer，未参与设计修订或实现。
- reviewer target: `docs/changes/perf-648-input-evidence-reconciliation/` at `13d5a40b1ff5d9e8e9b0411add6600e1688210e1`。
- review_mode: `delta`。
- mode_reason: R1-W1 的有界设计修订增加 recordEvents 写入条件及原 M1 的针对性回归断言；没有改变需求、核心职责、共享接口、milestone 数量/范围/依赖。独立核对该条件对 final、未定与 Global 三类行的影响，其他覆盖 retained。
- started_at: `2026-10-23T23:18:22+08:00`。
- completed_at: `2026-10-23T23:19:22+08:00`。
- duration: `60s`。
- validated_at / executed_base: `13d5a40b1ff5d9e8e9b0411add6600e1688210e1`。
- 受审 Git blob：`design.md = 7a5b20c02696938878a764e96f5ff89ff58f3cfb`；`motivation.md = 70cf28fc77c15d20a20192b6b61479719b601dd8`。
- 工作边界：只追加本报告；保留 perf-649/perf-650 的其他任务变更，不修改设计或代码，不提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1 已在设计层闭环。新增写入条件直接保护已固定的逻辑证据，保留完整事件、未定输入和 Global 的既有路径，没有引入新的共享协议或状态机。此结论是 Gate 2 设计审查通过，实施与 M1 验证尚未执行。

### Coverage 与证据

- `retained_from: Round 1`：需求与规模目标、真实产品组装、fallback evidence 协议、缺失/pending/取消判据、receipt 恢复、迁移回滚、no spec delta、用户旅程及验收环境。已比较 `cb1cfbfd8..13d5a40b1`：相关 PA/integration 源码、`apps/node/src/main.ts`、`SPEC.md`、Gateway current specs 与 motivation 无变化；变更集中在受审 design 与报告，R1 源码证据和真实 NodeStore 探针仍适用。
- 本轮重新核对全部 inputs 写入口：`store.ts:173,176-180,205,224`。receive/runtimeInput 是显式列名的插入，accepted 只改 accepted；会覆盖 terminal 的现有路径是 inputEvidence 与 recordEvents。新设计 `design.md:33-37` 要求 inputEvidence 原子写入标记和证据，并将 recordEvents 的物理终态更新限于 `evidence_final=0`，覆盖了 R1 中的冲突 writer。
- 对 final 行：下一 drain 即使补录第一 attempt error，行不满足 UPDATE 条件；完整事件仍持久化并进入 logicalEvents，交付与 model notice 不丢事实。对未定/旧行：默认 0，沿用暂态投影和 fresh lookup，直到可信收敛。对 Global：`global-agent.ts:535` 的既有 inputEvidence 调用不传 final，设计默认 false，保持原回查与投影行为。
- M1 在 `design.md:67` 增加“最终 lookup 之后补录物理失败事件不覆盖逻辑终态”，并保留旧 DB/重启、0/K lookup、receipt 恢复和用户不重复回复要求。它与 R1 的跨 drain 反例一致，作为原 M1 的回归条件足以指导实施；不需要新增 milestone 或 runtime 变更。
- 本轮未重跑 R1 的未修复源码探针，因为产品代码未变；闭环依据是设计中的明确保护与验收约束，不声称产品修复已通过测试。

### 历史问题闭环

- **R1-W1 — closed（设计层）。** Author Resolution 为 accepted，新增“最终逻辑证据不再被延迟物理事件覆盖”。独立核对 `design.md:35` 的条件准确落在 `store.ts:205` 所在 writer，且明确不跳过事件持久化；M1 纳入延迟事件回归。R1 的物理 error 覆盖已固定 logical completed 的路径在目标方案中被阻断，未定与 Global 路径保留。

### Issues

无未解决 CRITICAL / WARNING，无新增 issue。

### Recommendations

无。

### Author Resolutions

R2 Approved 已核实；无实质异议，0 CRITICAL / 0 WARNING。受审设计无后续语义变化，Gate 2 通过，进入 change-orchestrator-simple。
