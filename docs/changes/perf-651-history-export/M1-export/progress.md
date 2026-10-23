# M1-export 实施记录

- 方式：change-orchestrator-simple，主 Agent 自主实施；独立设计审查 Round 3 Approved 后开始代码修改。
- 触及：history.ts 的派生输出与队列；不改 DSH、PA/RPC schema、配置快照或 fork 创建。
- 实现：live Session 生命周期内的 WeakMap 水位、可读 JSONL 增量写、原始按显式请求原子发布、pending/raw/rebuild 合并、持久上界、同队列恢复和失败重建。
- 测试策略：保留 history.test.ts（真实 DSH 子进程的 fork、compaction、来源和 restart 接线）、PA history.test.ts（提炼与路径编排）；新增 history-export.test.ts，仅承担最低层文件系统、持久屏障、并发、写入量风险，不复制产品高层场景。使用真实文件 I/O，故障注入在 fs 与公开 DSH 服务 seam，无私有函数断言。
- Red：旧实现新测试 5 failed / 1 passed；持久切面测试因旧 path 只检查已有文件而无法进入 flush，产生 ENOENT/timeout；暖轮测试明确复现超量写入。
- Green：代码 `6fe274eb6`；7 个导出测试通过；既有 DSH/PA 3 个测试及临时 benchmark 通过。构建/typecheck 使用 Node 24.22.1。
- benchmark：见 evidence/benchmark.md，计逻辑 payload，非物理磁盘字节或生产时延。一次性脚本已删除，不纳入长期套件。
- 本任务独立 worktree 中运行 fixture，使用 mkdtemp home/cwd，无生产服务或外部消息；主仓未修改。
