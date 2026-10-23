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
