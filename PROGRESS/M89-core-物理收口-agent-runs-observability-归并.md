# PROGRESS (Milestone: M89)

- Milestone: M89
- Title: core 物理收口：agent/runs/observability 归并
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M89`
- Branch: `milestone/M89`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `606 passed, 4 skipped, 246 warnings`
- Notes:
  - authoritative base: `origin/main` commit `028eeed`
  - 目标是将 `src/nano_multiagent` 顶层剩余 `agent/`、`runs/`、`observability/` 彻底物理归并到 `core/`，并同步收口 source/tests/docs/contracts。
  - 迁移后顶层目录只允许 `core/`、`platform/`、`products/`、`apps/`。

## Roadpoints

### R89.1 core target-state contract 先红
- Context:
  - 当前仓库仍保留 `src/nano_multiagent/agent`、`runs`、`observability` 三个真实实现根目录，与《多产品架构调整建议.md》最终目标树不一致。
- Decision:
  - 先把 acceptance / import guard / location tests 改成 M89 口径，再用 focused red batch 暴露物理归并与越层依赖缺口。
- Rationale:
  - 只有先把 contract 改红，才能避免在旧顶层 root 假设上继续修补，确保后续实现严格对齐最终目录树。
- Evidence:
  - Tests: `TBD`
- Rollback:
  - 最近稳定点：`028eeed`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 改写 M89 目标态门禁并执行 focused red。

### R89.2 迁移实现并收口 canonical imports
- Context:
  - 待 R89.1 红测固定后，需要物理搬迁代码并移除对旧根包的所有 source/tests/docs 引用。
- Decision:
  - 将顶层 `agent/`、`runs/`、`observability/` 移入 `core/`；同时通过依赖注入/协议抽象消除 core 对 platform 的越层 import。
- Rationale:
  - 仅做路径迁移不足以满足 `core` layering guard；实现与依赖边界需要一次性收口。
- Evidence:
  - Tests: `TBD`
- Rollback:
  - 最近稳定点：`TBD`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 完成迁移、focused green 与文档同步。

### R89.3 full sweep、live 验证、main 集成与清理
- Context:
  - 待 focused green 后，需要补全全量/ live 证据并完成 main 集成、board 更新与 worktree 清理。
- Decision:
  - 先回写最终证据链，再做 main merge/push、`data/dev-tasks.json` 更新与 worktree 清理。
- Rationale:
  - 先固化证据与回滚点，避免 main 集成后再补文档导致哈希、命令和结论漂移。
- Evidence:
  - Tests: `TBD`
- Rollback:
  - 最近稳定点：`TBD`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 full sweep / live / merge / board / cleanup。
