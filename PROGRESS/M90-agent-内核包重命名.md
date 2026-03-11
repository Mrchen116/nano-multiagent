# PROGRESS (Milestone: M90)

- Milestone: M90
- Title: Agent 内核包重命名
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M90`
- Branch: `milestone/M90`
- Baseline:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q`
  - Result: `1 failed, 611 passed, 4 skipped, 246 warnings`
- Notes:
  - 已按要求先阅读 `/Users/czj/Repos/nano-multiagent/.worktrees/M90/SPEC.md` 与 `/Users/czj/Repos/nano-multiagent/.worktrees/M90/docs/内核设计SPEC.md`；目标态以 `src/agent/` 为唯一内核根包，内部保持 `core → platform/products` 的依赖纪律。
  - 已阅读 `/Users/czj/Repos/nano-multiagent/LOGBOOK.md` 与 `/Users/czj/Repos/nano-multiagent/.worktrees/M90/COMMENTING_GUIDE.md`；需特别注意“大范围 canonical path 替换后立即复查 forbidden snippets / legacy doc snippets / find_spec(None)”的零残留规则，以及 public API docstring / 注释只写契约与意图的规范。
  - 当前基线失败与 M90 scope 相关：`tests/contract/test_multi_product_architecture_acceptance.py` 仍依赖已删除的旧架构文档 `多产品架构调整建议.md`，说明 contract 尚未切换到 M90 新权威文档集。

## Roadpoints

### R90.1 重命名目标态 contract 先红
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R90.2 物理重命名包并收口 imports
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R90.3 全量门禁、main 集成、派工板更新与清理
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
