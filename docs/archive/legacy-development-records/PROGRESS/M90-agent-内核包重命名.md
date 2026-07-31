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
  - 基线失败暴露出架构验收仍绑旧文档与旧根包假设，且 `agent` 新根包尚未存在。
- Decision:
  - 先把架构 acceptance、canonical import guards、location tests 改写到 M90 口径，并用 focused batch 固定 `ModuleNotFoundError: agent` 红测。
- Rationale:
  - 只有先把 contract 切到 `src/agent/` / `src/coding_cli/` 目标态，后续物理迁移才不会继续被旧路径验收牵制。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/unit/test_core_agent_location.py` → `ModuleNotFoundError: No module named 'agent'`
  - Entry: focused red batch 成功暴露“新 canonical root 尚未落地”的缺口。
- Rollback:
  - 最近稳定点：`dcbe921`
- Commits: C1=`ede19bf`, C2=<pending>, C3=<pending>
- Next:
  - 进入 R90.2：物理重命名包根目录、迁出 CLI 顶层包，并收口源码/测试 imports。

### R90.2 物理重命名包并收口 imports
- Context:
  - 新 contract 已固定后，需要一次性完成 `src/nano_multiagent/ -> src/agent/`、CLI 顶层包外移以及全仓 import 替换。
- Decision:
  - 物理将内核根包重命名为 `src/agent/`，把 `apps/coding_cli` 迁到 `src/coding_cli/coding_cli/`，并同步更新源码、测试、打包配置与架构验收断言。
- Rationale:
  - SPEC §3 要求 `agent` 与 `coding_cli` 为独立顶层包；若只改 import 不改物理布局，会继续违背顶层结构与包发现目标态。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q` → `612 passed, 4 skipped, 246 warnings`
  - Entry: `python3 - <<'PY' ... find_spec('agent') / find_spec('nano_multiagent') ... PY` 显示 `agent` 可发现、`nano_multiagent` 为 `None`；`grep nano_multiagent` 在 `.py` 中仅剩两处负向断言测试。
- Rollback:
  - 最近稳定点：`ede19bf`
- Commits: C1=`ede19bf`, C2=<pending>, C3=<pending>
- Next:
  - 进入 R90.3：补齐文档记录、提交实现/文档，再执行 main 集成与派工板更新。

### R90.3 全量门禁、main 集成、派工板更新与清理
- Context:
  - 实现已全绿，待把证据、哈希、merge / board / cleanup 操作固化。
- Decision:
  - 先提交实现与文档，再 rebase/merge 到 `main`，用脚本更新 `data/dev-tasks.json`，最后清理 worktree。
- Rationale:
  - 先固化证据和回滚点，避免 main 集成后再补文档导致命令结果和哈希漂移。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M90 && PYTHONPATH=src pytest -q` → `612 passed, 4 skipped, 246 warnings`
  - Entry: `src/agent/` 成为唯一内核根包，`src/coding_cli/coding_cli/` 承载 CLI 实现，`src/nano_multiagent/` 已删除。
- Rollback:
  - 最近稳定点：`<pending C2>`
- Commits: C1=`ede19bf`, C2=<pending>, C3=<pending>
- Next:
  - 待提交实现/文档后执行 main 集成与收尾。
