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

### R1.1 静默 NO_REPLY 完成态并修正 picker 复验 locator
- Context:
  - fresh runtime 仍看到 NO_REPLY turn 的成功态文案，且 rerun 脚本等待旧 option accessible name 超时。
  - `tests/unit/test_m170_rerun_acceptance.py` 实际 import 主仓 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`，因此修复必须落到真实共享脚本路径。
- Decision:
  - 对 `message-pane` 增加护栏：agent 且 `delivery_status=completed` 但正文为空时不渲染状态块。
  - 将 rerun mention locator 改为基于 current-main picker 可见文案 `label + label mention` 的 `role=option` 文本过滤。
- Rationale:
  - 泄漏源在真实运行态 message bubble 状态块，而不是仅事件过滤；空正文 completed placeholder 必须彻底静默。
  - picker accessible name 已不再含 handle，脚本继续等旧名必然在 fresh rebuild 后不稳定。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M216/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build && pytest /Users/czj/Repos/nano-multiagent/.worktrees/M216/tests/unit/test_m170_rerun_acceptance.py`
  - Entry: 68 个 frontend 测试通过，`npm run build` 通过，`tests/unit/test_m170_rerun_acceptance.py` 9/9 通过。
- Rollback:
  - `19e4fbb`
- Commits: C1=19e4fbb, C2=03004a4, C3=
- Next:
  - 提交文档并准备整体集成到 `main`。
