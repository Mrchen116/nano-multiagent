# Worktree 创建、集成与清理

本文件只在创建/恢复 milestone 现场和 DONE 集成时读取。worker 是自己 milestone
worktree/branch 的 creator-owner；orchestrator 只提供精确路径、branch 和 `base_head`。

## 创建或恢复

- 新现场从派发的 `base_head` 创建 `branch` 与 `worktree_dir`，不从主 checkout 的当前 HEAD 猜起点。
- 已存在现场时，核对它已注册到精确路径、checkout 的 branch 正确、HEAD 可解释且没有来源不明的
  dirty；任一不符就报告，不 reset、覆盖或另建同名现场。
- `unit_worktree_dir` 必须 checkout 派发的 `unit_branch`；主 checkout 只做只读发现。

## 共享 unit 集成锁

所有并行 worker 使用同一个 Git common dir 下的锁目录：

```text
<absolute-git-common-dir>/nano-unit-locks/<unit_id>.lock
```

`<absolute-git-common-dir>` 由
`git rev-parse --path-format=absolute --git-common-dir` 取得。先创建
`<absolute-git-common-dir>/nano-unit-locks/`，再用原子 `mkdir` 获取本 unit 的锁。

- 锁已存在：说明另一个 creator/adopter 正在集成；等待或与 orchestrator 协调，不触碰
  `unit_worktree_dir`，也不得删除或接管该锁。
- 获锁后：重新 fetch `unit_branch`，核对它仍是 milestone 最近一次 rebase 的 unit HEAD。若已
  前移，不触碰 `unit_worktree_dir`，释放锁，回到锁外 rebase 并重新判断 gate 有效性，然后再竞争锁。
- unit HEAD 未变：核对 `unit_worktree_dir` clean、branch 正确且可安全同步，再合入并 push。
- push 成功且 unit worktree 回到 clean、可解释状态后释放锁。失败时先保存现场并报告；不能用
  reset 或删锁伪造清理。

## 清理

先证明 milestone commits 和 durable evidence 已从 pushed `unit_branch` HEAD 可达，再只对派发的精确路径
和 branch 执行清理：移除 milestone worktree，删除已合入的本地 branch；HANDOFF 时若曾 push
milestone branch，正常 DONE 后一并删除对应远端 branch。

禁止通配删除 `.worktrees/` 中的其他目录。HANDOFF/BLOCKED 保留精确现场，并把 owner、path、head
和恢复条件交给 orchestrator；接管者成为 adopter-owner，完成后承担同一清理责任。
