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
orchestrator 分类
  |           |              |
  v           v              v
纯工件      有界闭环       实质性实现
unit直接    unit直接        worker milestone
验证/关闭    验证/关闭         |
  |           |                v
  +-----------+       commit + test strategy
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
| `change-orchestrator` | 明确三条互斥路由；直接闭环在 unit worktree；向实质性 worker 传递 unit branch 信息 | 让流程成本随风险变化 |
| `change-impl-worker` | 从固定 SOP 收缩为 creator-owner、锁集成、测试策略和 DONE 契约 | 保留可交付性，移除固定过程税 |
| worker references/assets | 把 worktree、真实入口、实现记录拆成按需参考；压缩 tasks/progress 模板 | 减少预读和强制文档写入 |
| workflow 文档与相邻 skills | 对齐“可选工件、按风险验证、未知根因才调试”的术语与入口 | 让调度和执行边界一致 |
| 契约测试 | 覆盖路由、锁、unit head、测试复用和文档用词 | 防止旧的固定流程重新引入 |

## 关键决策

### 三类路由以风险和证据为准

纯工件不触及实现或行为；有界闭环要求 delta、影响层和验证命令已知，且不改用户可观察/稳定产品行为；其余或不确定的改动都是实质性实现。没有行数阈值，避免将小而高风险的改动错误降级。

### 工件与参考按需加载

`tasks.md`、`progress.md`、额外基线、真实入口验证和实现记录只在协作、交接、风险或证据缺口要求时创建/读取。worker 的必要 DONE 字段替代了固定过程日志的最小交接信息。

### 测试结果按 Git tree 有条件复用

worker 在测试策略中记录 `tested_head` 和 `tree`。集成后只有代码 tree、命令、环境或风险变化时才需要重跑，避免“rebase/merge 后同 tree 再跑”的无信息重复。

### 保持 worker creator-owner，使用共享锁集成

为兼容 `feat-537` 的既定合约，worker 继续创建、恢复与清理自己的 milestone worktree。共享锁位于 `<git-common-dir>/nano-unit-locks/<unit_id>.lock`，用原子 `mkdir` 保护 unit 分支整合；发现 unit head 推进则释放锁、rebase/重新评估后重试。

## 失败处理与回滚

- 直接闭环出现验证失败或发现行为/风险扩大时，升级为实质性 worker，而不是在错误分类下继续。
- worker 无法获得锁时不删除其他 owner 的锁；按锁协议重新评估。
- 该变更可由回滚此 unit 的提交恢复旧工作流，无产品数据迁移或运行时回滚步骤。

## 验证策略

本实现使用 skill 结构验证、change-workflow 文档契约测试、完整 contract suite、Ruff、文档完整性检查和 `git diff --check`。另对纯工件、有界闭环和生产认证/协议三个场景执行了独立前向流程演练，结果记录在 [analysis.md](analysis.md)。
