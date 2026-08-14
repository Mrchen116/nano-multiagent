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
orchestrator 判断
  |                      |
  v                      v
unit 直接闭环      worker milestone
验证/关闭                  |
  |                        v
  +----------------> commit + test strategy
                              |
                              v
                     shared unit lock + rebase
                              |
                              v
                    unit branch 集成/推送/独立关闭
```

## 模块变更

| 模块 | as-built 变更 | 理由 |
| --- | --- | --- |
| `change-orchestrator` | 用少量原则判断直接闭环或派 worker；直接闭环在 unit worktree；向 worker 提供实施现场 | 让流程成本随风险变化 |
| `change-impl-worker` | 从固定 SOP 收缩为 creator-owner、锁集成和简短交接 | 保留可交付性，移除固定过程税 |
| worker references/assets | 把 worktree、真实入口、实现记录拆成按需参考；压缩 tasks/progress 模板 | 减少预读和强制文档写入 |
| workflow 文档与相邻 skills | 对齐“可选工件、按风险验证、未知根因才调试”的术语与入口 | 让调度和执行边界一致 |
| 契约测试 | 覆盖自主路由原则、锁、unit head、测试复用和文档用词 | 防止旧的固定流程重新引入 |

## 关键决策

### 路由由交付收益决定

不维护“哪些改动必定派 worker”的分类表。调度者结合当前证据判断：当直接闭环已经可靠且独立 worker 不增加价值时直接完成；当独立 owner、隔离现场或深入实现/验证能提高交付可靠性时派 worker。范围或证据变化时重新判断，不按行数阈值机械处理。

### 工件与参考按需加载

`tasks.md`、`progress.md`、额外基线、真实入口验证和实现记录只在协作、交接、风险或证据缺口要求时创建/读取。worker 的必要 DONE 字段替代了固定过程日志的最小交接信息。

### 验证按实际变化决定是否复用

代码、命令、环境和风险未变时可以保留有效验证；发生实际变化才重跑受影响范围，避免“rebase/merge 后同 tree 再跑”的无信息重复。

### 保持 worker creator-owner，使用共享锁集成

为兼容 `feat-537` 的既定合约，worker 继续创建、恢复与清理自己的 milestone worktree。共享锁位于 `<git-common-dir>/nano-unit-locks/<unit_id>.lock`，用原子 `mkdir` 保护 unit 分支整合；发现 unit head 推进则释放锁、rebase/重新评估后重试。

## 失败处理与回滚

- 直接闭环出现验证失败或发现新信息时，重新判断是否需要 worker，而不是套用旧分类继续。
- worker 无法获得锁时不删除其他 owner 的锁；按锁协议重新评估。
- 该变更可由回滚此 unit 的提交恢复旧工作流，无产品数据迁移或运行时回滚步骤。

## 验证策略

本实现使用 skill 结构验证、change-workflow 文档契约测试、完整 contract suite、Ruff、文档完整性检查和 `git diff --check`。另对两个直接闭环和一个需要独立 worker 的场景执行了前向流程演练，结果记录在 [analysis.md](analysis.md)。
