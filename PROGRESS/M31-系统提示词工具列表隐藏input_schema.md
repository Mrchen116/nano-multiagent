# PROGRESS (Milestone: M31)

- Title: 系统提示词工具列表隐藏 `input_schema`
- Goal: 调整 system prompt 的 `Available tools` 展示，仅输出工具名与描述，不再输出 `input_schema` 文本。
- Exit Criteria:
  - prompt 文本中不出现 `input_schema`。
  - 工具执行契约不变（仅展示层调整）。
  - 相关 unit/contract/integration 测试更新并通过。
  - `pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M31`

### Baseline
- Context:
  - execution_mode=`serial`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M31`；branch=`milestone/M31`。
  - 已读取 `LOGBOOK.md`，沿用规则：只改展示层，不触碰工具执行链路与运行时行为。
  - prevention_rules：不改 schema/执行路径；保留 placeholder/skills 注入逻辑；每个 Roadpoint 严格 C1/C2/C3。
- Decision:
  - 先建立 M31 的 `TASKS/PROGRESS`，再以单 Roadpoint（R31.1）执行“测试先红 -> 最小实现 -> 文档收口”。
  - 测试分层选择 unit/contract/integration，验证展示层变更不影响运行时填充契约。
- Rationale:
  - 需求聚焦于 prompt 文案展示，单 Roadpoint 可最小化变更面并保持可回滚。
- Evidence:
  - Tests: `pytest -q`（baseline：`337 passed, 4 skipped`）
  - Entry: `milestone/M31` worktree 已创建并可执行测试。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - 执行 R31.1 的 C1（先更新测试断言并确认失败）。
