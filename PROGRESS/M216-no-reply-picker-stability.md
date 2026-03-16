# M216 进展：NO_REPLY 完成态泄漏与 fresh picker 复验稳定性

## Baseline
- Context: M216 只处理 NO_REPLY 完成态泄漏与 fresh picker rerun 不稳定，禁止修改 `data/dev-tasks.json` 与 `scripts/acceptance/**`。
- Decision: 在独立 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M216` 上执行，并共享主仓 `data/dev-tasks.json` 与 `data/locks/`。
- Rationale: 避免碰用户 worktree，同时保证任务状态文件不分叉。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M216/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build && pytest /Users/czj/Repos/nano-multiagent/.worktrees/M216/tests/unit/test_m170_rerun_acceptance.py`
  - Entry: frontend test 入口因环境缺少 `vitest` 失败，记录为基线依赖缺口，不直接代表代码回归。
- Rollback:
  - `3d12ffb`
- Commits: C1=, C2=, C3=
- Next:
  - 建立 R1/R2 红测并定位真实显示源与脚本脆弱 locator。
