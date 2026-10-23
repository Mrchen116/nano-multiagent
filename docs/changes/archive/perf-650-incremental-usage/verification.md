# Verification Report: perf-650-incremental-usage

> Validation snapshot: `40deea7f19794b73614e56c339fd02a88dd1ae7c → cc091e4b9a396e87a659fedadb296c5a924d80e4`

## Round 1 metadata

- reviewer: `/root/usage_static_review`，未参与实现；明确派发的独立静态组合职责另有 `code-review.md`。
- review_round: `1`
- verification_mode: `full`（同时核对 no spec delta）
- branch / workspace: `unit/perf-650`；`/Users/czj/.codex/worktrees/unit-perf-650/nano-multiagent`
- executed_base: `40deea7f19794b73614e56c339fd02a88dd1ae7c`
- validated_at: `cc091e4b9a396e87a659fedadb296c5a924d80e4`
- 原派发 `63e9c73b7f5cd352dfa4a28f6b910fd2f3b27483` 到上述版本仅增加 `update(): Promise<void>` 类型注解；caller 明确追加，已核对差异，运行语义未变。
- effective_base / effective_through: 尚未声明后续同步的 retained 结论，由收尾 owner 核对。
- requires_full_verification: `false`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 全部静态可核对退出标准有实现及对应证据；两项用户旅程由独立产品 reviewer 承担 |
| Correctness | 两项 Requirement / Scenario 实现映射与回归保护齐全 |
| Coherence | Followed；符合 design 和 DSH/PA 公开依赖边界 |

**PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION。静态一致性门禁通过。** 最终全 CI 与独立产品旅程仍是各自适用交付门禁；本报告不把它们提前判为通过。

## Completeness

- Tasks: 简化流程单 M1；不强制 tasks.md。实施块、测试归属和性能证据在 `M1-incremental-usage/progress.md`，可从最终源码和测试逐项复核。
- M1 的 400 cold child 热读、单 child 增量、fork inherited prefix、根子并发、初始化竞态、卸载与持久失败、RPC response replay、ACK 丢失、PA/runtime 重启和既有数据库索引均有直接覆盖，详见下表。
- M1 性能处理量和耗时已经分开报告冷/热阶段；读取原始 benchmark jsonl，数据与 progress 一致。内存 fixture 不证明生产磁盘或端到端占比。首次重建线性，当前样本候选冷读 68.712 ms 比基线 25.222 ms 慢，符合明确允许的一次性重建边界。
- 窄测试：共享最终源码证据 `pnpm exec vitest run packages/dsh-integration/tests/usage.test.ts packages/personal-assistant/tests/usage.test.ts`，10 passed；仅后续类型注解不同，运行证据保留适用。
- 真实 DSH：共享证据 `pnpm exec vitest run packages/dsh-integration/tests/workflow-native.test.ts`，1 passed，测试 25.64 s；已读 `/tmp/nano-perf650-evidence/native.log`，测试覆盖实际 4 child、15 tokens、usage RPC 和 runtime 重启。该 fixture provider 不是实际模型或产品验收。
- 构建：已读 `/tmp/nano-perf650-evidence/final-build.log`，`pnpm build` 完成，installer candidate 明确为 `cc091e4`。最终本地 CI 正由 caller 执行，不重复全量，也不将构建成功当作全 CI。
- Prototype / Reference: N/A。没有客户端布局或视觉变化，无前端原型 contract。

## Correctness

| Requirement / Scenario 或 M1 风险 | 实现位置 | 测试 / evidence | 状态 |
|---|---|---|---|
| 完成工作按实际用量计量：普通与后台工作 | `packages/dsh-integration/src/usage.ts:145`，既有 deriveTurnTokenUsage；`packages/personal-assistant/src/usage.ts:46` | integration usage test:70、88、106；workflow-native:125；独立产品旅程另验 | covered |
| fork 继承不重复计量、稳定 run id | integration usage:31、136；PA usage:47；NodeStore:268 | integration usage test:70；PA usage test:9；workflow-native 重启一致性 | covered |
| 恢复不重计或漏计：ACK/断线/重启 | integration usage:103、164；PA usage:45、53、57；store:268、275；IM gateway:769 | usage test:84、140；PA usage test:9（真实 SQLite 关闭重开）、70；workflow-native:146 | covered |
| 初始化和并发根/子完成不丢事件 | integration usage:29、48、95、123、141 | integration usage test:88；PA usage test:40（ACK 等待中的 child 完成） | covered |
| live flush 失败和卸载后必须有持久证据 | integration usage:109、127、134 | integration usage test:121；读取锁定 DSH flush 和 live/prepared observation 实现核对 seam | covered |
| 未变的 400 child 不重新 observe/list；新增 child 单次重建 | integration usage:62、73、79、95 | integration usage test:70、106；progress 性能表及 `/tmp/nano-perf650-evidence/incremental.jsonl` | covered |
| 部分 catalog unavailable 后可恢复，不丢旧投影 | integration usage:79 | integration usage test:147 | covered |
| 持久 outbox 后 cursor 前移；部分写入失败可重放 | PA usage:45、53、54 | PA usage test:70，第二次请求仍无 cursor，已保存事实由 INSERT OR IGNORE 去重 | covered |
| acknowledged 历史不增加每次 pending 查询扫描成本，旧库兼容 | store:18、271 | PA usage test:89，20,000 acknowledged 旧行、真实 EXPLAIN QUERY PLAN 使用索引、历史去重保留 | covered |

Current 契约核对：`SPEC.md:7`、`:40`、`:50` 的唯一 DSH runtime/公开边界成立；`docs/specs/gateway/relay-protocol.md` 的既有中继和 token 口径未改；`docs/specs/im/response-metrics.md` 的消息气泡计数链路不受内部 usage RPC 影响；`docs/specs/im/auth-tenancy.md` 的 owner metrics 过滤与授权链保持原样。unit diff 未修改 IM 入站协议、权限、scope 或计量 receipt。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| runtime 内增量投影，重启从原生日志重建，不新增持久游标库 | 是 | integration usage:25、48、162 |
| flush 前捕获 cut，成功后消费；卸载使用 prepared 持久 cut | 是 | integration usage:109-142；无新增 deprecated snapshotEvents/eventAt 调用 |
| own seq / inherited count 排除继承，保留未完成 turn，完成后释放原始 turn | 是 | integration usage:31、136、145 |
| catalog 和 live parent 链发现新 child；已发现 mapping 补 root 通知 | 是 | integration usage:34、73、187；index:192 |
| epoch cursor 仅传输；全部 outbox 落库后前移；ACK 不承担读 cursor | 是 | integration usage:103；product-contracts:99；PA usage:45-59 |
| pending partial index，保留 confirmed 去重历史 | 是 | PA store:18、268-275 |
| PA ACK 期间继续接收 dirty；退出时无 running promise 窗口 | 是 | PA usage:27、38、61、63 |
| 不越出原授权 usage scope，不改并行优化文件、DSH 或通用缓存框架 | 是 | 完整 diff 仅 integration usage/RPC、PA usage/store、contracts 及所属测试和实施记录 |

独立读取锁定 DSH 包确认 session/event 在 log.push 之后同步发布；Session.seq 为日志长度；sessions.flush 拒绝 detached 对象并等待所有 durability listeners；sessionQuery.observeSession 返回不可变 live/prepared cut。实现的捕获上界、fork 排除和卸载恢复没有依赖 fixture 独有语义。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Corrected Delta Reconciliation

**no spec delta，aligned。** 独立核对整个 unit diff；UsageReadResult 和 cursor 是同一节点成套发布的内部 RPC 变化。统计值、稳定 run identity、IM node.report/receipt、既有存储格式、owner/conversation/agent scope、权限、消息气泡和外部消费者可观察行为均保持原契约。没有遗漏需要写入 canonical specs 的新行为，不创建空 delta 文件，也不以修改 current spec 适配实现。

### Uncovered Observable Behavior

无新增对外行为。motivation 两项真实旅程的独立产品观察由产品 reviewer 报告，本报告不代替该结论。

Outcome: `aligned`

## Handoff

报告文件可从共享 unit worktree 读取；遵派发只写 `code-review.md` 与本文件，未提交、未改源码/测试/设计、未启动或接管服务。`report_commit` 由 caller 提交后记录。top_concern: 无静态阻塞；保留冷恢复线性、紧凑报告内存线性和 microbenchmark 非生产性能证明的已知限制。
