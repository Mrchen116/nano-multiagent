# PROGRESS (Milestone: M15)

- Title: 第二 Provider（anthropic）与切换验收
- Goal: 在不改 runtime/tool/session 核心代码前提下新增 `anthropic` 协议实现与工厂接线。
- Exit Criteria:
  - `llm/protocols/anthropic/*` 落地并通过与 `openai_compat` 同一契约测试集。
  - provider 切换仅改配置（不改 runtime/tool/session 代码）。
  - OpenAI/Anthropic 双链路集成测试通过，`pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M15`

> 说明：本文件用于记录 M15 的关键决策、证据、回滚点与 C1/C2/C3 哈希。`LOGBOOK.md` 仅记录可复用经验。

## Baseline
- Context:
  - 按执行技能要求在 worktree 中先执行 `pytest -q` 建立基线。
- Evidence:
  - Tests: `pytest -q` -> `1 failed, 171 passed, 2 skipped`
  - Failing test: `tests/contract/test_core_events_contract.py::test_runtime_event_types_are_stable`
  - Scope: 失败位于 runtime 事件契约，不在 M15 `allowed_scope`（`src/nano_multiagent/llm/**`）内。
- Decision:
  - 记录为既有基线失败，M15 期间保证“不新增失败”；Milestone 收口时再基于 rebase 后主线状态做全量 gate 复核。

### R15.1 Provider 契约测试集统一（OpenAI + Anthropic）
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R15.2 新增 anthropic 协议实现（llm/protocols/anthropic）
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R15.3 工厂接线与 provider 切换验收（配置驱动）
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
