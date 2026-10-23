# perf-650 Design Review

## Round 1

### Metadata

- reviewer: `/root/usage_design_review`，独立审查者；未参与受审设计或实现。
- target: `perf-650-incremental-usage` 的 motivation、design、`M1-incremental-usage/.gitkeep`。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖需求、实际装配、DSH 公开能力、存储与恢复、性能证据、delta 和 milestone。
- started_at: 2026-10-23T23:12:22.797000+08:00
- completed_at: 2026-10-23T23:16:42+08:00
- duration: 259.4 seconds
- validated_at: `15063908dc738f6485d7255c5798430d4f1841ab`（main；审查对象为本次读取的 unit tree）。
- executed_base: `15063908dc738f6485d7255c5798430d4f1841ab`
- reviewed blobs: design `43faf5b99c518a5033451e0efaa058129a5fdd03`；motivation `490d14ef7dcbe660913d551c08138fdbc2633804`。
- workspace: 保留共享主仓原有 bugfix-644 staged changes 和 perf-649 untracked changes；仅新增本报告，不修改设计、实现，不提交。
- effective_base / effective_through: 本轮不作后续同步后的有效性认定。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

增量 reader + 内存传输 cursor + 既有持久 outbox 的职责划分可行，且不需要新数据库或上游 patch；但正常子会话卸载后的持久 cut 获取方式和 PA 热路径对已确认历史的扫描成本尚未收口。

### Coverage 与证据

1. **需求与现状。** `motivation.md` 的准确性、稳定 run id、fork 不重计、ACK/断线/重启恢复、400 个冷 child 和冷/热分开测量均已进入 design/M1。实际 `packages/dsh-integration/src/usage.ts:7-25` 的 listDescendants → 全部 observe → 全历史 derive，与审计结论一致。读取了审计的 `runtime/usage-count.mts`、`usage-count.jsonl`、`findings.md` R1：该脚本调用真实 readUsage，但下游 observation 是空事件 fixture，两次显式观察次数为 401/802；它证明调用放大，不能证明生产 I/O、真实耗时或 token 正确性。设计正确保留了这一证据边界。本轮未重复执行原审计、未做实现性能测试。
2. **实际组装链。** `packages/dsh-integration/src/index.ts:187-193,368-375` 负责 session.event 通知和可信 binding 校验后的 usage.read；`packages/personal-assistant/src/usage.ts:21-51` 负责 turn/end → recover → saveUsage → node.report → confirmUsage；`apps/node/src/main.ts:102-117,264-279,368` 在真实 Node 初始化及 reconnect 路径装配和恢复。设计的 runtime 生命周期 reader 和 PA 每根 cursor 可落在现有 owner 内。现有 `rootSessionId` 只沿 live parent 链解析，实施必须按设计第 4 项把 descendant→root 映射接入实际通知路径，不能仅在 reader 内维护它。
3. **公开 DSH 边界。** 核对已安装且锁定的 `0.2.1-alpha.1` 包的 package exports 和公开声明：`dsh-session` 的 session/event、seq、isOwnSeq、sessions.flush；`dsh-session-query` 的 observeSession/SessionObservation（immutable cursor、prepared durable revision）；`dsh-subagent` 的公开 catalog 事件类型与 listDescendants；`dsh-token-meter/client` 的 deriveTurnTokenUsage。这些足以支持设计主干；无需导入 lib 私有路径。为核实生命周期，另只读检查安装包实现，不构成允许生产代码 private import。snapshotEvents/eventAt 已 deprecated，设计禁止新增调用是正确约束。
4. **计量与恢复。** 现有 helper 按完整 turn/start 到 turn/end 的 attempt lifecycle 计量，设计保留未完成 turn 并只在完成后调用，可保持供应商口径。fork 按 inheritedEventCount/isOwnSeq 排除继承前缀。内存 cursor 只有在全部同步 saveUsage 成功后推进；PA/runtime 重启重放同 run id 可复用 `store.ts:267-274` 的 INSERT OR IGNORE，以及 `apps/im-server/src/gateway.ts:762-778` 的 `(node_id, run_id)` receipt 与 metrics 同事务幂等。ACK 等待期间重新 drain 的决定确实覆盖当前 `UsageReports` 的退出窗口。仍缺已初始化 child 在下一次读取前变冷时的持久性处理，见 R1-W1。
5. **职责与复杂度。** DSH 原生日志是计量来源，integration 派生 runtime 内存事实，PA 持有交付 outbox，IM 做产品计数，符合 `SPEC.md`。复用现有 helper/outbox 优于再设持久游标库或通用缓存层。每根紧凑报告序列的线性内存开销已明确接受。PA pending 查询仍全表扫描，违背热成本只随增量的目标，见 R1-W2。
6. **delta 与真实验收。** 对照 `docs/specs/gateway/relay-protocol.md`、`docs/specs/im/response-metrics.md`、`docs/specs/im/auth-tenancy.md`，内部成套发布的 RPC 返回 envelope 变化不改变外部计量、权限或消息气泡，`no spec delta` 合理。`apps/im-server/src/work.ts:827-850` 确有 owner 认证、按 conversation_id/agent_id 过滤的 `GET /im/v1/metrics/usage`，因此可通过真实 IM 入口核验，不需用 usage.read 冒充产品验收。API 同时返回 owner/conversation/agent scope，验收需选定一个 scope 比较前后，不能累加各 scope。当下只确认 runbook 可行性，未启动真栈、未声称用户旅程通过；无客户端改动，不要求原型。
7. **milestone 与测试面。** 单 M1 骨架仅 `.gitkeep`，符合设计阶段规则；范围不依赖 input-evidence/model-fallback/SingleThread 改动。既有 `packages/dsh-integration/tests/workflow-native.test.ts:124-143` 已有真实 workflow 子任务 usage 汇总与 runtime 重启断言，可随 envelope 变化保留；PA `tests/usage.test.ts` 已有 ACK 丢失/重启幂等入口。M1 已要求根子并发、初始化竞态和 flush 失败；需补入本轮两个问题的退出条件，不能只验证 400 个冷 observation 次数。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — 已初始化 child 结束并卸载后，增量事件的持久 cut 获取方式未定义

- 位置：`design.md:38-40,47`（关键决策 2–4、UsageReader 接口）及 M1 退出条件。
- 证据：设计明确首次恢复用 observation，热路径只捕获 live session 上界并 flush。公开 `dsh-session` 声明要求 flush 使用 live Session；安装包 `lib/index.js:1832-1854` 经 liveEntryFor 检查后，对 detached 对象抛出 `is not live in this store`。DSH subagent 的正常自然结束路径 `lib/index.js:1155-1178` 会 flushFinalState 后 dispose；`1270-1275` 明确该 final flush 是 best-effort，失败只记录 warning。因此不能把 `turn/end` 或 disposed 当成已持久的证明。
- 具体场景：父会话一次 usage.read 已初始化仍运行的 child；child 后续完成，事件已排队，但 PA 经 stdio 发出的下一次 usage.read 到达时 child 已自然卸载。此时它既不是“首次访问 child”，也不再有可 flush 的 live Session。按现有文案，直接派生会失去持久性证明；坚持 live flush 则该 root 的读取可能一直失败到重启。
- 未修后果：正常后台任务可能漏交付最终用量，或为绕过失败而提前计入未持久事实；不是只在异常测试中出现的生命周期。
- 收口要求：明确已初始化但当前变冷的 changed session 的持久边界获取、增量去重与失败保留语义。可复用该 child 的一次 prepared observation 并按已处理 seq 取新增事实，无需重扫其他冷 child；若采用其他公开生命周期机制，也须说明它如何确认 flush 成功。补“初始化过的 child → 新 turn 完成 → read 前已卸载”以及 final flush 失败的验证。

#### R1-W2 — PA pending outbox 仍随全部已确认历史线性扫描，热路径目标未覆盖到存储

- 位置：`design.md:25,37,41-42,72`（复用 outbox、常态复杂度和 M1 范围）。
- 证据：`packages/personal-assistant/src/store.ts:17` 只有 run_id 主键；`:270-274` 使用 `SELECT run_id,payload FROM usage_reports WHERE acknowledged=0 ORDER BY rowid`，确认仅置 acknowledged=1，历史行持续保留，未创建该筛选对应索引。实际 PA drain 在每次恢复/turn 后调用 pendingUsage。本轮在内存 SQLite 用同一 CREATE TABLE 和 SELECT 执行 EXPLAIN QUERY PLAN，结果为 `SCAN usage_reports`，即使没有 pending 记录也需扫描历史。
- 未修后果：runtime 和 RPC 已增量后，正常 PA 热路径仍随累计完成轮次增长，与 motivation 的“正常持续运行成本跟新完成轮次/变化会话相关”和设计的常态复杂度承诺不符。只测 400 child observe/catalog 次数无法发现它。
- 收口要求：把既有 NodeStore 的 pending 查询访问路径纳入方案与 M1，例如在同一表上增加兼容旧库的适当索引，保留 acknowledged 行和既有去重，不引入新数据库。补大量 acknowledged 历史、零或少量 pending 的 PA 热读取处理量/查询计划证据，并明确其可回滚/旧库初始化行为。

### Recommendations

- R1-R1：真栈 runbook 可补明确的 `/im/v1/metrics/usage` 查询 scope，以及用完成前后差值和持久原生 turn 事实对账的方法。现有接口和隔离说明已足以执行，此项仅减少验收歧义，不单独阻断。

### Author Resolutions (R1)

- R1-W1: accepted。已对照原生 flush liveEntryFor 与 subagent best-effort final flush；关键决策 2 明确 changed child 变冷后 prepared observation、持久 cut、失败保留及 live→cold 竞态，M1 增加卸载/final flush 失败验证。只读取该变化 child，不遍历其他冷会话。
- R1-W2: accepted。关键决策 6 增加原表 pending partial index、旧库幂等建立及回滚兼容；M1 覆盖大量 acknowledged 历史与实际查询计划。
- R1-R1: accepted。Runbook 明确单 agent scope 差值和原生 turn 对账，避免重复累加各 scope。
- Coverage 2 接线提醒已落实到决策 4：通知 rootSessionId 使用 reader 的已知 child 映射兜底。接口段说明 reader 在首个 read await 前订阅，已有工作由冷重建覆盖；无上游 patch 或同步历史私有入口。
