# M214 稳定 M170 fresh browser 复验脚本重复运行

## Milestone 概览
- Goal: 让 current-main 的 M170 real-browser rerun 脚本在 fresh runtime 上可重复运行，不再因为等待通用 ACK 文本或脆弱 locator 而超时。
- Exit Criteria: `m170_rerun_acceptance.py` 在 current-main fresh runtime 上稳定跑通并产出结构化结果；相关单测更新并通过。
- Test Command: `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M214/tests/unit/test_m170_rerun_acceptance.py && python /Users/czj/Repos/nano-multiagent/.worktrees/M214/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- Scope: `ACCEPTANCE/**`, `scripts/acceptance/**`, `tests/**`, `TASKS/**`, `PROGRESS/**`, `LOGBOOK.md`
- Out of Scope: `data/dev-tasks.json`, `src/IM/frontend/**`

## R1 锁定 rerun 成功判据并移除脆弱 ACK/locator 依赖
- Status: TODO
- Acceptance:
  - fresh runtime 脚本不再直接等待 `ALPHA_ACK_M170` / `BETA_ACK_M170` 文本可见。
  - 脚本改为等待 current-main 稳定 UI/运行态信号，例如线程消息落库、relay/event 完成、mention picker 可操作。
  - 结果 JSON 继续保留每轮 turn 的结构化摘要，便于自动复验。
  - mention picker 路径与 NO_REPLY probe 仍可完成且不会因脆弱 locator 超时。
- Tests Plan:
  - unit: 需要，锁定“成功判据来自 DB/事件，而不是 ACK 文本”和“脆弱 locator 的替代策略”。
  - contract: 不单列；现有结果 JSON 字段作为轻量契约在 unit 中覆盖。
  - integration: 不新增，Milestone 门禁已经用真实 rerun 脚本覆盖入口链路。
  - e2e: 使用 `python .../m170_rerun_acceptance.py` 作为真实浏览器入口验证。
- Expected Tests:
  - `tests/unit/test_m170_rerun_acceptance.py::test_wait_for_turn_completion_*`
  - `tests/unit/test_m170_rerun_acceptance.py::test_pick_mention_candidate_*`
  - 入口：`python /Users/czj/Repos/nano-multiagent/.worktrees/M214/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- DoD:
  - `test_command` 全绿。
  - 形成 C1/C2/C3 三提交。
  - `PROGRESS/M214-stabilize-m170-rerun.md` 记录决策、证据、提交哈希。
