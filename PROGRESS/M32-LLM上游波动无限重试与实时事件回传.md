# PROGRESS (Milestone: M32)

- Title: LLM上游波动无限重试与实时事件回传
- Goal: 为异步 run 主链路提供上游瞬时失败的可持续恢复能力（无限重试 + 指数退避 + 冷却），并在重试期间实时输出可消费事件，避免 CLI 静默等待。
- Exit Criteria:
  - openai_compat/anthropic 请求失败支持无限循环重试，节奏 `0.5s/1s/2s`，每连续 5 次失败冷却 30s 后重置节奏。
  - 异步 run 重试过程持续产出状态事件（attempt/delay/cooldown/last_error）。
  - run 仅在成功时 completed；未取消前不得因瞬时上游错误 failed。
  - 覆盖 unit + integration + contract（必要时 e2e）并通过 `PYTHONPATH=src pytest -q`。
- Test command: `PYTHONPATH=src pytest -q`
- Branch: `milestone/M32`

### Baseline
- Context:
  - execution_mode=`serial`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M32`，branch=`milestone/M32`。
  - 已按要求在 worktree 共享 `data/dev-tasks.json` 与 `data/locks`（符号链接到主仓）。
  - 已读取 `LOGBOOK.md` 与 prevention_rules：真实入口优先、REPL 事件去重+run_id 过滤、禁止终态补发、错误摘要可诊断。
- Decision:
  - 采用两阶段 Roadpoint：先收敛 run registry 重试状态机，再扩展事件契约与 CLI 可视反馈。
- Rationale:
  - 先稳住状态机可避免在 CLI 展示层补丁式处理，确保事件语义来源唯一。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q`（baseline：`10 failed, 356 passed, 4 skipped`）
  - Baseline failures（超出 M32 直接目标，后续集成阶段再与 main 对齐复验）:
    - `tests/contract/test_core_types_contract.py::test_turn_result_contract_fields_are_stable`
    - `tests/contract/test_llm_interfaces_contract.py::test_llm_generate_response_contract`
    - `tests/integration/test_cli_http_flow_integration.py` 中 8 个既有断言失败
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R32.1 Red：先写 registry 重试节奏/取消行为测试并确认先红。

### R32.1 异步 run 引入无限重试节奏与取消保持
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R32.2 事件契约扩展与 CLI 实时重试反馈
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
