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


## Round 2

### Metadata

- reviewer: `/root/usage_design_review`，与 R1 相同的独立 reviewer；未参与设计修改或实现。
- target: `perf-650-incremental-usage` motivation、修订后 design、M1 骨架及 Author Resolutions (R1)。
- review_mode: `full`
- mode_reason: R1 两项问题引入冷 child 持久读取分支、NodeStore 索引和 M1 范围/退出条件变化，故按 skill 做 full；结合本轮实际 delta 复核，不仅根据 author 的 accepted 声明放行。
- started_at: 2026-10-23T23:18:43+08:00
- completed_at: 2026-10-23T23:20:21+08:00
- duration: 98.8 seconds
- validated_at: `1e7430e4a7a3f7d98f6bf2effd8f2dbd1864370b`
- executed_base: `1e7430e4a7a3f7d98f6bf2effd8f2dbd1864370b`
- reviewed blobs: design `73389e1f24be9e115fac451c134240fedf7bc4e1`；motivation `490d14ef7dcbe660913d551c08138fdbc2633804`。
- workspace: 开始时 main clean；本轮只向本报告追加 R2，不改受审文档、实现或索引，不提交。
- effective_base / effective_through: 留待最终同步后的失效判断；本轮没有替未来版本背书。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

两项 WARNING 均已在设计层闭环。此结论表示方案足以进入实施；没有将设计 probe 当成已实现性能结果或真实产品验收。

### Coverage 与证据

1. **基线与需求。** 对照 `15063908d..1e7430e4a`，相关 integration/PA/contracts/Node/IM 源码、pnpm-lock、SPEC 和 current specs 没有变化；motivation blob 未变。本轮重新读完整 motivation/design，准确计量、fork 继承、稳定 run id、RPC/ACK 重放、runtime/PA 重启和排除另两 unit 的要求继续完整覆盖。R1 对实际组装、旧行为、计量 helper、IM receipt 事务和审计 fixture 能力边界的证据仍适用。
2. **持久读取与公开 API。** 重读安装版 `dsh-session-query` 的公开 SessionObservation 声明：source 区分 live/prepared，cursor 是 immutable cut，prepared 有 durable source revision。修订后的决策 2 明确只对 changed cold child 重新 observation，按已处理 seq 消费；排队终态超过持久 cut 时保留 pending 并失败，不发布/前移 cursor；live→cold 竞态采用同一规则。这与 R1 核实的 flush live-only 和 best-effort teardown 约束相容，既保留可靠性，也不恢复全体冷 child 扫描。
3. **增量 owner、通知与初始化。** 公开 readUsage 按 Context 保留 reader，在首次 recovery 的第一个 await 前注册 session/event，初始化之前的历史由冷恢复覆盖；随后用 cut/seq 排除重放。决策 4 与 usageRoot(ctx,sessionId) 现在明确把 descendant 映射接到 `index.ts` 实际 session.event 的 rootSessionId fallback。再次核对 `index.ts:187-193` 当前 live parent 链：新增映射解决的是这个真实入口的缺口，未另设路由或放松 binding 校验。原有根串行化、own-event 过滤、未完成 turn 保留和原生 helper 决策继续成立。
4. **outbox 与复杂度。** NodeStore 在已有表上新增 partial index，属于 PA 持久交付职责，不增加数据库或持久游标 owner。本轮使用实际 `node:sqlite` DatabaseSync 内存数据库，建立原表后插入 10,000 条 acknowledged 历史和 2 条 pending，再执行两次 `CREATE INDEX IF NOT EXISTS usage_reports_pending ON usage_reports(acknowledged) WHERE acknowledged=0`。原查询计划从 `SCAN usage_reports` 变为 `SEARCH usage_reports USING INDEX usage_reports_pending (acknowledged=?)`，未出现临时排序；返回顺序为 pending-a、pending-b。确认 pending-a 后仅返回 pending-b，原表仍有 10,002 行。此 probe 证明原表补索引、幂等初始化、待确认过滤和旧历史保留的可行性，不代表成品吞吐测试。首次建索引扫描成本及旧代码回滚兼容已写明。
5. **传输与故障恢复。** report envelope/epoch cursor 的边界没有变化：完整 saveUsage 后推进 PA cursor，ACK 后确认，缺失/失效 cursor 重放紧凑历史，原生稳定 ID 与 IM receipt 保证重试幂等。新增索引不删除 acknowledged 行，不改变去重权威。读取与 ACK 的同一 drain owner、失败等待后续 recover、通知到达退出窗口的处理保持原方案。没有跨包 DSH import、新协议权限或数据格式迁移。
6. **delta、用户验收与 milestone。** no spec delta 仍合理；客户端面、消息 token 展示和租户权限不变。重新核对 `apps/im-server/src/work.ts:827-850`，runbook 的 agent_id 过滤实际可用，限定单一 scope 的前后差值并按原生 turn 对账避免多 scope 重计。单 M1 明确纳入 PA store、已初始化 child 卸载/final flush 失败、大量 confirmed 历史的索引查询，原有 400 child、根子并发、初始化竞态、fork、RPC/ACK、重启及冷热量化退出条件全部保留。骨架和分工没有引入并行文件冲突；真栈仍按 worktree-runtime 隔离执行。本轮未启动栈，未执行实现测试或 reviewer 用户旅程。

### 历史问题闭环

| 原问题 | Author Resolution | 本轮核验 | 状态 |
|---|---|---|---|
| R1-W1 | 决策 2 新增 cold prepared cut、失败保留、live→cold 分支；M1 增加卸载与 final flush 失败 | 公开 observation source/cursor/revision 支持该路径；只消费确认持久的 seq，保留未持久终态，且不再依赖 detached flush | closed |
| R1-W2 | 决策 6 在原 usage_reports 上建立 pending partial index；M1 补存量/查询计划 | 实际 Node SQLite 10,000 confirmed + 2 pending probe 证实使用索引、按 rowid 返回、ACK 后移出 pending 且保留历史 | closed |
| R1-R1 | runbook 明确 metrics agent scope 差值与原生 turn 对账 | 实际 IM route 支持 agent_id 过滤；修订明确不跨 scope 累加 | closed |

### Issues

无新增 CRITICAL / WARNING，无未闭环历史 WARNING。

### Recommendations

无新增建议；实施按已收口的 M1 退出标准验证即可。

### 本轮结束时的 main 推进核对

报告写入期间共享 main 推进到 `1ef49808ffd2618c275b6e38683f93f74ff8455d`。检查 `1e7430e4a..1ef49808f` 仅新增 perf-648 的 design-review.md；本 unit motivation/design blobs 仍与上述记录一致，相关实现、公开依赖和契约无变化。本轮结论 retained；`validated_at` / `executed_base` 保留实际开始审查基线，`effective_base` / `effective_through` 均为 `1ef49808ffd2618c275b6e38683f93f74ff8455d`。后续推进仍由收尾 owner 再作失效判断。

### Author Resolutions (R2)

作者核对 R2 evidence 与公开 API，接受 Approved 及 R1-W1/W2 closed；无实质异议或未处理建议。受审 motivation/design/M1 骨架未再修改。Gate 2 满足 0 CRITICAL / 0 WARNING，进入默认简化实施。
