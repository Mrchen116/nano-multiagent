# M214 稳定 M170 fresh browser 复验脚本重复运行

## Milestone 目标
- 让 current-main 的 M170 real-browser rerun 脚本在 fresh runtime 上可重复运行，不再因为等待通用 ACK 文本或脆弱 locator 而超时。
- 保持结构化结果 JSON 产出，继续适配 current-main 单一真源 schema / UI。

### R1 锁定 rerun 成功判据并移除脆弱 ACK/locator 依赖
- Context:
  - fresh rerun 在 `wait_for_text(page, ALPHA_ACK)` 超时；等待具体 ACK 文本会被产品文案/NO_REPLY/渲染时序击穿。
  - picker 路径还会因为 composer 文本与最终落库文本不完全一致而误判超时。
- Decision:
  - 新增 `wait_for_turn_completion`，以 runtime DB 中 `messages + relay_tasks.status=completed + conversation_events.relay.completed` 作为回合完成判据。
  - mention picker 改用稳定 accessible name `option[name="<label> <handle>"]`；消息查询增加 exact/normalized/prefix 三层兜底。
- Rationale:
  - DB/事件是 current-main 的单一真源，比等待页面 ACK 文本更稳定；picker accessible name 比链式 `has=get_by_text(...)` 更不脆弱。
- Evidence:
  - Tests: `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M214/tests/unit/test_m170_rerun_acceptance.py && python /Users/czj/Repos/nano-multiagent/.worktrees/M214/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - Entry: unit 9 例全绿；真实脚本已不再卡在 ACK 文本或 picker locator，成功产出结构化 JSON。
  - Runtime note: 本次 fresh runtime 输出显示 alpha 初始已处于 `NO_REPLY` 配置、`no_reply_turn.status=failed`，说明环境仍有独立产品态问题，但已不属于“等待 ACK / 脆弱 locator 超时”。
- Rollback: `4b4eb15`
- Commits: C1=`4b4eb15`, C2=`cbf398e`, C3=
- Next:
  - 若主 agent 继续追 fresh runtime 语义一致性，需要单独处理 alpha 初始配置漂移与 NO_REPLY 页面泄漏，不应回退本次稳定等待条件修复。

## 备注
- 当前单测通过主仓绝对路径加载 acceptance 脚本，因此实现需同步到主仓对应文件，worktree 内测试才会命中新逻辑。
- 该接线限制使“严格只测不改源码的 C1”在本 Milestone 内无法完全物理分离，已在执行过程中记录。
