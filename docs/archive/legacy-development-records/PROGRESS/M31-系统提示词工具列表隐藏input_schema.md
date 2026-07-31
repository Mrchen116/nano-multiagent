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

### R31.1 调整 Available tools 展示并同步测试断言
- Context:
  - 现状是 `_format_available_tools` 会在每个工具后拼接 `input_schema` JSON，导致 system prompt 暴露 schema 细节，不符合本 Milestone 目标。
  - 约束是仅改展示层；`ToolSpec` 结构、tool execution contract 与 placeholder/skills 注入逻辑必须保持不变。
- Decision:
  - C1 先在 unit/contract/integration 三层新增“prompt 不含 `input_schema`”断言，并补充 unit 用例验证仅展示 `- name: description`。
  - C2 仅修改 `src/nano_multiagent/agent/prompting.py::_format_available_tools`，移除 schema 文本拼接，保留工具名与描述输出。
  - 不改 `_default_tool_specs` 与 runtime 执行链路，确保工具调用契约保持原样。
- Rationale:
  - 先红后绿可证明变更必要性；最小实现只触及渲染函数，风险最低且满足“仅展示层调整”。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_agent_prompting.py tests/contract/test_system_prompt_contract.py tests/integration/test_prompt_runtime_fill_integration.py`（4 failed）
    - Green: `pytest -q`（`338 passed, 4 skipped`）
  - Entry:
    - system prompt `Available tools` 仅含工具名与描述；
    - prompt 文本中无 `input_schema`；
    - runtime placeholders 仍可正常替换，skills 注入逻辑未变。
- Rollback:
  - `6570943`（R31.1 C1）
- Commits: C1=`6570943`, C2=`af2b54d`, C3=`<pending>`
- Next:
  - 提交 C3 文档收口，然后执行 `rebase origin/main` + `pytest -q` 并整体合并到 `main`。
