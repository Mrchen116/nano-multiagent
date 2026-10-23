# M1 实施与证据

执行方式：change-orchestrator-simple，主 Agent 在独立 managed worktree `/Users/czj/.codex/worktrees/unit-perf-650/nano-multiagent`、`unit/perf-650` 实施；主仓已有 dirty 未修改。本次由 Codex create_worktree 管理路径，未在共享主仓切实施分支。

## 实现

- runtime 按 Context 保留增量 reader；原生日志重建、实时 own events、flush cut 与 changed-cold observation 统一输出完整 turn 用量。epoch cursor 只用于传输，原始数据与 ID 不变。
- PA 保存 reports 后才推进内存 cursor，ACK 等待期间新通知继续 drain；现有持久 outbox/IM receipt 负责重试幂等。既有表新增 pending partial index，旧库兼容。
- 部分 catalog 暂不可读时保留已恢复事实并重试 discovery，不将诊断分支静默冻结为永久已完成；正常完整恢复后不再遍历。
- 未改 input-evidence、model-fallback、SingleThread 或 session.descendants。no spec delta。

## 测试归属与处置

- `packages/dsh-integration/tests/usage.test.ts` 新增：真实 readUsage + 公开 DSH seam fixture，保护 400 cold child 热成本、fork 排除、初始化/并发、持久屏障、卸载、runtime epoch 与暂不可用分支恢复。这是用量性能/投影的最低层；既有 workflow-native 没有足量 cold/故障调度覆盖。计数断言对应本 unit 明确的冷观察性能目标，不读取 reader 私有状态。
- `packages/dsh-integration/tests/workflow-native.test.ts` rewrite-merge：保留真实 DSH workflow 4 child、15 token 和重启测试，适配 envelope，在启动工作前首次 usage.read 并验证热空增量/重启 epoch，覆盖实际事件/catalog/RPC 接线。
- `packages/personal-assistant/tests/usage.test.ts` rewrite-merge：原 ACK 丢失 test 增强为实际关闭/重开 Node SQLite；新增 ACK 等待竞态、部分写入失败 cursor 不前移、20,000 acknowledged 旧库索引迁移/去重。无重复高层覆盖。
- 临时 benchmark 脚本/原始输出在 `/tmp/nano-perf650-evidence/`，不进入永久测试或提交原始日志。

## 窄验证

Node v24.22.1，pnpm 11.7.0。

- Red：新 usage tests 在旧 reader 上 5 failed；另真实旧 readUsage 重复调用 401 observations × 2 的性能失败已复现。
- Green：usage 两文件全部通过（随后新增的 unavailable branch 用例纳入最终完整验证）。
- `pnpm build`：通过。
- `pnpm exec vitest run packages/dsh-integration/tests/workflow-native.test.ts`：1 passed，25.64 秒测试耗时；真实锁定 DSH 子进程 + fixture provider，不声称真实模型/产品验收。

## 性能证据

Claim：正常稳定读取不再打开不变的冷子会话或派生全部历史。Baseline：main `15063908dc738f6485d7255c5798430d4f1841ab`；候选为本 M1 同提交的源码。Method：Node 24.22.1、真实 readUsage、root + 400 child，每会话 100 个完整 turn（5 events/turn，15 tokens/turn），内存 observation fixture；串行单次冷/热样本，未采样生产。单 child 变化通过公开事件 seam 输入 5 个新事件。

| 读取 | catalog 遍历 | 显式 observe | observation events | 返回 reports | tokens | 耗时 ms |
|---|---:|---:|---:|---:|---:|---:|
| 基线首次 | 1 | 401 | 200,500 | 40,100 | 601,500 | 25.222 |
| 基线不变重复 | 1 | 401 | 200,500 | 40,100 | 601,500 | 25.513 |
| 候选冷恢复 | 1 | 401 | 200,500 | 40,100 | 601,500 | 68.712 |
| 候选不变重复 | 0 | 0 | 0 | 0 | 0 | 0.049 |
| 候选单 child 新 turn | 0 | 0 | 0 | 1 | 15 | 0.069 |
| 候选再次不变 | 0 | 0 | 0 | 0 | 0 | 0.012 |

Locator：`/tmp/nano-perf650-evidence/{baseline,incremental}.mts` 与同名 jsonl；上游审计 `/Users/czj/.codex/reports/nano-performance-audit-20261023-2247/runtime/usage-count.mts/jsonl`。Limit：观察次数与实际 JS 函数计时，内存 fixture 不模拟磁盘，首次 listDescendants 内部真实存储遍历不在 fixture 时间内。不能推断生产占比、端到端延迟或磁盘提速。冷重建仍线性，当前样本冷恢复更慢；runtime 紧凑 reports 内存随已完成轮次数线性增长。


## 持久 outbox 测量

真实 NodeStore、20,000 条 acknowledged 旧行、既有库重开初始化后：建索引初始化 6.439 ms；1,000 次 pending 查询有一条待投递时合计 20.882 ms，空队列合计 14.328 ms，EXPLAIN 使用 `usage_reports_pending`。同一临时库删除该索引后，空查询 1,000 次合计 5309.891 ms，EXPLAIN 为 table scan。Locator：`/tmp/nano-perf650-evidence/outbox.mts/jsonl`。这是本地 SQLite 样本，不推断生产延迟；acknowledged 历史行仍保留幂等去重。
