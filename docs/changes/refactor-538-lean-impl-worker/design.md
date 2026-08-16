# refactor-538 as-built design

## 变更定位

- **Base:** `bf8b3cb108764536dba5db94dfd9f0623d60ff88`
- **范围:** 本 unit 最终提交相对 Base 的差异；精确提交见 Git history。
- **权威文档:** [change-workflow.md](../../development/change-workflow.md) 及相关 skill。

这是一次开发流程重构，不改变产品运行时或 current product spec。

## 结构与流向

```text
任务请求 + 已有证据
        |
        v
design 拆分的独立 milestone ──> worker milestone
                                    |
                                    v
                         commit + test strategy
                                    |
                                    v
                    tasks/progress + shared lock + rebase
                                    |
                                    v
                         unit branch 集成/推送/独立关闭

未形成 milestone 的自包含小闭环 ──> orchestrator 直接完成 + 独立关闭
```

## 模块变更

| 模块 | as-built 变更 | 理由 |
| --- | --- | --- |
| `change-orchestrator` | 调度 design 拆分的独立 milestone；在 unit worktree 直接关闭未形成 milestone 的小闭环 | 保留专注与并行，只移除无价值的交接成本 |
| `change-impl-worker` | 收缩为 creator-owner、自主实施、短记录和锁集成 | 保留可交付性，移除固定过程税 |
| worker references/assets | 只保留 worktree、真实入口参考和极简 tasks/progress 模板 | 减少预读和冗长文档写入 |
| workflow 文档与相邻 skills | 对齐短记录、按风险验证、未知根因才调试的术语与入口 | 让调度和执行边界一致 |
| 验证 | 运行 skill 结构校验、既有 workflow contract tests 与文档完整性检查 | 确认本次文档和 skill 结构仍可用 |

## 关键决策

### 设计拆分保留独立 owner

design 已拆出的独立 milestone 交给 worker，使 orchestrator 保持全局调度、集成和门禁注意力，worker 专注
实现、验证和自己的现场。未形成 milestone 的自包含小闭环才由 orchestrator 判断是否值得另派 owner；不按
行数阈值机械处理。

### 固定短记录，按需内容

已派发 worker 的每个 milestone 都创建 `tasks.md` 和 `progress.md`，但模板只留下实施块、进展和验证。额外基线、真实入口验证和文档内容仍由风险和证据缺口决定；不要求 roadpoint、台账字段或专门回报格式。

### 验证按实际变化决定是否复用

代码、命令、环境和风险未变时可以保留有效验证；发生实际变化才重跑受影响范围，避免“rebase/merge 后同 tree 再跑”的无信息重复。

### 保持 worker creator-owner，使用共享锁集成

为兼容 `feat-537` 的既定合约，worker 继续创建、恢复与清理自己的 milestone worktree。共享锁位于 `<git-common-dir>/nano-unit-locks/<unit_id>.lock`，用原子 `mkdir` 保护 unit 分支整合；发现 unit head 推进则释放锁、rebase/重新评估后重试。

## 失败处理与回滚

- 小闭环发现超出原范围的信息时，重新判断是否应形成独立 milestone，而不是套用旧分类继续。
- worker 无法获得锁时不删除其他 owner 的锁；按锁协议重新评估。
- 该变更可由回滚此 unit 的提交恢复旧工作流，无产品数据迁移或运行时回滚步骤。

## 验证策略

本实现使用 skill 结构验证、change-workflow 文档契约测试、完整 contract suite、Ruff、文档完整性检查和 `git diff --check`。另对两个直接闭环和一个需要独立 worker 的场景执行了前向流程演练，结果记录在 [analysis.md](analysis.md)。
