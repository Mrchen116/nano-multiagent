# M214 稳定 M170 fresh browser 复验脚本重复运行

## Milestone 目标
- 让 current-main 的 M170 real-browser rerun 脚本在 fresh runtime 上可重复运行，不再因为等待通用 ACK 文本或脆弱 locator 而超时。
- 保持结构化结果 JSON 产出，继续适配 current-main 单一真源 schema / UI。

### R1 锁定 rerun 成功判据并移除脆弱 ACK/locator 依赖
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M214/tests/unit/test_m170_rerun_acceptance.py && python /Users/czj/Repos/nano-multiagent/.worktrees/M214/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
