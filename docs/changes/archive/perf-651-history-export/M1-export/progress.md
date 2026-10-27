# M1-export 实施记录

- 方式：change-orchestrator-simple，主 Agent 自主实施；独立设计审查 Round 3 Approved 后开始代码修改。
- 触及：history.ts 的派生输出与队列；不改 DSH、PA/RPC schema、配置快照或 fork 创建。
- 实现：live Session 生命周期内的 WeakMap 水位、可读 JSONL 增量写、原始按显式请求原子发布、pending/raw/rebuild 合并、持久上界、同队列恢复和失败重建。
- 测试策略：保留 history.test.ts（真实 DSH 子进程的 fork、compaction、来源和 restart 接线）、PA history.test.ts（提炼与路径编排）；新增 history-export.test.ts，仅承担最低层文件系统、持久屏障、并发、写入量风险，不复制产品高层场景。使用真实文件 I/O，故障注入在 fs 与公开 DSH 服务 seam，无私有函数断言。
- Red：旧实现新测试 5 failed / 1 passed；持久切面测试因旧 path 只检查已有文件而无法进入 flush，产生 ENOENT/timeout；暖轮测试明确复现超量写入。
- Green：代码 `6fe274eb6`；7 个导出测试通过；既有 DSH/PA 3 个测试及临时 benchmark 通过。构建/typecheck 使用 Node 24.22.1。
- benchmark：见 evidence/benchmark.md，计逻辑 payload，非物理磁盘字节或生产时延。一次性脚本已删除，不纳入长期套件。
- 本任务独立 worktree 中运行 fixture，使用 mkdtemp home/cwd，无生产服务或外部消息；主仓未修改。

## 最终集成与交付检查

2026-10-25，final sync 合入 main `d5b3577923e3dff74de47d947e49c1f963ef91e0`；集成受测 HEAD `2cedfb1e6f9e464c872a57229fc5ad0df60d66b7`。主干新增能力依赖、默认 Codex 审批和任务同步，导出实现、低层测试、PA 消费者及依赖锁未变；history 既有 fixture 按主干增加关闭无关能力。对这次集成执行独立产品与静态定向复验，acceptance、code-review、verification Round 2 均 Pass、0 issue/finding；canonical/delta aligned。保留原报告的 executed_base/validated_at；effective_base 为上述 main，effective_through 为上述集成 HEAD。后续收尾仅追加证据与整体归档，PR body 记录最终文档提交 SHA。

同一套顺序本地 CI 使用 Node 24.22.1，不并发启动另一套全量：

| 检查 | 结果 |
|---|---|
| pnpm build / pnpm typecheck / pnpm check:ios-runtime | Pass |
| pnpm test --maxWorkers=2 | 131 files / 684 tests passed |
| pytest -m "not e2e" -q | 65 passed / 31 deselected |
| ruff check . / ruff format --check . | Pass |
| ./scripts/docs-check | Pass |
| frontend npm ci / npm audit --audit-level=critical | Pass |
| frontend shared contracts tsc（CI 同命令） | Pass |
| frontend npm run test -- --maxWorkers=2 | 104 files / 987 tests passed |

日志位于本机 `/tmp/perf-651-final-ci-*.log`；不提交日志、运行数据或构建产物。此前旧基线集成的全量曾有 3 个时间上限失败：knowledge-review 两项单独复跑通过，workspace-tools 几次触及原 90 秒上限。旧实现对照 88.75 秒通过，一次性诊断副本 80.26 秒通过，原测试不改断言/上限最终 73.68 秒通过；不能据此声称根因已证明。该诊断副本已删除，受版本控制测试未为超时调整。最新集成上述全量一次通过，作为最终检查依据。

已完成 canonical routing-delivery 归并及 gateway Requirement 计数 22→23，保留 main 的其他计数。独立验收 fixture 与失败运行的任务自有临时目录已清理，没有操作生产服务或历史。交付只创建 PR，不合并或部署。
