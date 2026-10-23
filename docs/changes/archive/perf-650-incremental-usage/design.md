# perf-650: 增量用量计量 — 技术方案

> 对齐 motivation.md；Full，默认简化实施，单 M1。

## Changelog

## 现状分析

### 涉及范围

`packages/dsh-integration/src/usage.ts` 每次 listDescendants 后 observe 根及全部 child，并重新派生全历史完成轮次；`src/index.ts` 的 usage.read 检查可信 binding。`packages/personal-assistant/src/usage.ts` 在 turn/end 和恢复时读全部 reports，NodeStore.saveUsage INSERT OR IGNORE，pendingUsage 经 node.report ACK 后 confirmUsage。run id 为 sessionId:turn。

### 既有约束

DSH 仅通过公开 exports 使用，PA 只依赖 product-contracts。保留持久性屏障、fork inheritedEventCount、原生 token-meter deriveTurnTokenUsage、稳定 turn ID、IM 幂等及审批链。禁止新调用已标记 deprecated 的同步 snapshotEvents/eventAt；不 patch 上游。

Current grounding：gateway/relay-protocol.md、im/response-metrics.md、im/auth-tenancy.md 保持现有计数展示与权限；本 unit 仅改变内部 usage.read 获取方式，消息 token 展示不走此 RPC。

### 可复用能力

- 用 DSH session/event 同步有序增量事件、Session.isOwnSeq、session.seq 和 sessions.flush；新建 listener 早于运行中的 Agent 工作。
- 用 sessionQuery.observeSession 在首次恢复获取不可变 cut、inheritedEventCount；冷会话不激活 Agent。
- 用 subagents.listDescendants 仅首次恢复发现存量 child；运行中使用公开 subagent/catalog 事实和实时 session 的 parentSession 链发现新 child。
- 用 deriveTurnTokenUsage 保持供应商计数口径；不自行实现计量公式。
- 用既有 usage_reports 作为唯一持久 outbox，不新增数据库、通用缓存框架或原生日志格式。

### 相关历史

refactor-581-dsh-personal-assistant 建立 DSH/PA 职责及恢复链路；本 unit 延续边界。审计 R1 在最新 main 仍成立。并行轨迹全扫修复、输入证据和 fallback 优化均非依赖，本 unit 仅在 index.ts 增加自身局部接线。

## 架构总览

原生日志仍是真实来源。runtime 内一个用量 reader 持有每根会话的增量投影：首次加载可达会话；之后 listener 缓存新 own events，读取只 flush 并处理变化会话。完成轮次转换成紧凑 UsageReport，追加到按根排列的报告序列。PA 在 outbox 写入后记住该序列的游标；未变化读取返回空增量。

## 关键决策

1. **重启重建，运行中增量。** runtime 内存状态可丢弃，每个根初始化最多一次成功的 catalog/history 重建；失败不标为完成。缓存只保留紧凑用量事实、每会话当前未完成轮次及尚未处理的增量事件，完成轮次原始事件释放。重启首次 O(可达会话+历史事件)，常态 O(新增事件+新增报告)，存量报告占 O(已完成轮次) 紧凑内存。拒绝持久游标数据库：现有日志和 outbox 已提供恢复与幂等。
2. **持久事实之后才发布报告。** listener 只排队；每次读取捕获某 live session 的事件上界，再 await flush，成功后只处理该上界前事实。flush 中新到事件留给后续 drain。冷 observation 自身是持久来源；首次 live observation 也只消费屏障前捕获 cut。已初始化 child 若在读取前卸载，只对该 changed child 获取 prepared observation，按已处理 seq 消费其持久新增事实；不信任卸载时 best-effort final flush 或仅有的排队 turn/end。排队终态超出持久 cut 时失败并保留 pending，不能发布未持久报告或推进游标；不把 detached Session 传给 flush。live flush 中发生卸载时同样回到该 child 的 prepared observation 核验。没有屏障就失败，不能推进游标。
3. **初始化与增量无缝衔接。** 初始化前建立 root/session 状态并开始收集事件；observation cut 以内只重放一次，cut 之后排队。仅处理 inheritedEventCount 之后的 own events，未完成 turn 保留，遇 turn/start 重置，turn/end 使用既有 helper。根读取串行化；根与子并发事件按各自 seq 保留，不用 dirty boolean 覆盖中途到达。
4. **新 child 通过运行中事实接入。** subagent/catalog 的 childId 以及 live parentSession 链将新 child 归到已知 root；首次访问该 child 可有一次自身重建。已有 descendant→root 映射支撑父会话卸载后的通知；index.ts 实际 session.event 通知也使用该映射兜底 rootSessionId，确保 PA 对正确 binding 发起恢复。catalog/turn 事件在冷初始化期间也进入队列，读取 drain 处理新发现会话；无变化不重复 listDescendants。
5. **传输游标不承担持久真相。** usage.read 改为返回 `{reports,cursor}`，cursor 为 runtime/root epoch 加报告位置。缺失或失效游标返回该 root 全部紧凑报告；有效游标仅切新增尾部。PA 内存 cursor 在全部 saveUsage 成功后推进；ACK 前 outbox 已持久化。PA 重启无游标重放，runtime 重启 epoch 变化重放，同一 run id 被现有 INSERT OR IGNORE 和 IM 去重。旧原生日志及 usage_reports 无迁移。RPC 是本仓成套发布的内部边界，不新增混合版本协商。
6. **outbox 只查询待确认行。** NodeStore 初始化在原 usage_reports 上 CREATE INDEX IF NOT EXISTS 建立 acknowledged=0 的 partial index（键 acknowledged，行内 rowid 顺序支持原 ORDER BY rowid）。保留 acknowledged 历史作为去重真相；旧库启动自动加索引，回滚旧代码仍可使用原表。首次建索引按历史规模扫描一次，之后 pending 查询随待交付条目而非全部历史增长；用实际 SQLite EXPLAIN QUERY PLAN 与大量 confirmed/少量 pending 记录核验。
7. **恢复与实时排队共用同一 owner。** PA recover 继续标记绑定根；每次请求带根 cursor。drain 包含读取和 ACK 交付，ACK 等待期间到达的 dirty roots 仍在同一循环中消费；失败保留 outbox，后续 recover 再试。避免已有 running promise 与 drain 退出竞态吞掉新通知。

## 接口与数据流

- product-contracts 定义 UsageReadResult（reports: UsageReport[]，cursor: string），不引入 DSH 类型。
- readUsage(ctx,rootId,cursor?) 使用按 Context 持有的 reader，首个 recovery 的第一个 await 之前订阅公开 session/event；内部串行处理 root dirty sessions 并返回一页增量。usageRoot(ctx,sessionId) 为实际通知接线提供已知 descendant→root 映射。首次 recovery 前的工作由冷重建覆盖，状态属于 runtime 生命周期而非每次 RPC 新建。
- index.ts 保留可信 root binding 校验，usage.read 仅转交 reader 和可选 cursor；missing-root 恢复仍可得到空结果且允许后续再次恢复，不把缺失当永久已初始化。
- PA 请求 → runtime 先持久再投影 → 新 reports + cursor → PA saveUsage 全部同步落库 → 内存 cursor 前移 → node.report → ACK 后 confirmUsage。
- RPC 应答丢失：PA 仍用旧 cursor 重读相同事实；PA 中途保存失败：cursor 不前移，重试幂等。网络恢复不需要重开全部冷子会话；runtime 重启需要冷重建。

## 契约层增量 (delta-spec)

no spec delta。内部 RPC 在同一节点发布单元内调整，不改变用户功能、统计口径、IM 协议、数据格式或权限。

## 风险与回退

重点防止：初始化竞态漏事件、flush 失败提前计量、fork prefix 重计、晚到 child 遗漏、ACK 重试重复收费。通过真实函数的足量冷 child、根子并发、故障与重启测试覆盖。冷重建和紧凑事实内存与历史规模线性增长是明确限制，不声称冷启动常数成本。回退代码即可，数据无迁移；任何准确性问题不得以“性能优化”为由放行。

## Runbook for Reviewer

涉及 node 内 PA 与 DSH 子进程，产品回归使用隔离 IM + node 真栈。停止：`./scripts/e2e-down.sh`；启动：按 `docs/development/worktree-runtime.md` 执行 `./scripts/e2e-up.sh`，通过输出地址的 health 和 node connected 检查。本 unit 不接管生产或其他 worktree 服务。

**Review 驱动方式**：不改客户端面；用客户端实际 IM 接口发起普通及后台子任务工作，读取实际用量统计；断线/重启后再次读取，最终不漏计、不重计。可观察旅程保持不变，独立产品 reviewer 执行。使用 GET /im/v1/metrics/usage?agent_id=<id>，选定单一 agent scope 比较完成前后差值，不累加 owner/conversation/agent 多 scope；以实际完成的原生 turn 事实对账。不能用内部 usage.read 替代产品验收。

**验收前置**：隔离脚本、现有测试账户与模型配置来源遵循 worktree-runtime；reviewer 检查受审构建版本与隔离端口，不输出凭据。性能 microbenchmark 只用隔离 fixtures，不能声称生产占比。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-incremental-usage | 增量读取与可靠交付 | 无 | 单组 | integration usage/index、product-contracts 用量类型、PA usage/store 与相关测试 | [reviewer] motivation 的普通/后台工作、断线重启两场景保持准确且恰好一次；[worker] 真实 readUsage，400 不变 child 冷恢复后重复读取零冷观察/零 catalog 遍历；单 child 新 turn 不遍历其他 child，热事件派生仅增量；[worker] 根子并发、初始化竞态、fork 继承、已初始化 child 完成并卸载、final flush 失败、flush 失败、RPC/ACK 丢失、PA/runtime 重启恢复正确；[worker] 大量已确认历史下 pending 查询使用索引且仅返回新增项；[worker] 分别记录冷/热处理量与耗时，窄测试、构建及适用 CI 通过 |
