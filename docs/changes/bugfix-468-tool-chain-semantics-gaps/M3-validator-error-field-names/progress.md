# bugfix-468-M3 — Progress

## R1 — 对齐 validator 报错文案并补单元测试

- Context: `registry.py` 的 `_validate_args` / `_validate_value` 报错无字段名，模型难以自我纠正；design 决策 4 要求对齐 CC 模板并保留 `details` dict。
- Decision: 新增 `_format_validation_error` / `_type_name` helper；missing/unexpected/type 统一输出 `<tool> failed due to the following issue(s):\n<逐条字段名>`；`load_skills` 特例保留旧文案；details 结构不变。
- Rationale: 复用现有验证阶段顺序与 details 形状，最小化对程序消费者的影响；只改文本格式。
- Evidence:
  - Tests: `pytest tests/unit/test_tool_validation_errors.py -q` → 15 passed
  - Tests: `pytest tests/integration/test_tools_registry_loader_integration.py -q` → 2 passed
  - Entry: N/A（纯内核逻辑变更，R2 用真栈补入口验证）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert ff46abd4b`（C2）then `git revert 1cdab647e`（C1）
- Commits: C1=1cdab647e, C2=ff46abd4b
- Next: R2 全测试树回归 + 真栈验证

## R2 — 全测试树回归 + 真栈验证

- Context: 需要确认新文案没有破坏全测试树，并证明真实调用链能看到字段名。
- Decision: 跑 `pytest tests/unit tests/integration tests/contract -q` 全绿；用 `scripts/e2e-up.sh` 起隔离栈后，按 design 许可的 fallback 通过 agent.sdk 直接驱动 `edit` 工具传入错误参数名，捕获 ToolError 文本。
- Rationale: 模型自然触发参数错误不可靠，显式 SDK 驱动可稳定复现并精确展示 `oldText`/`newText` 字段名；e2e 栈本身已验证服务能正常起停、无回归。
- Evidence:
  - Tests: `pytest tests/unit tests/integration tests/contract -q` → 3013 passed
  - Entry: `PYTHONPATH=src python evidence/demo_wrong_edit_params.py` 输出含 `edit failed due to the following issues:\nThe required parameter \`oldText\` is missing\nThe required parameter \`newText\` is missing`（持久化见 `evidence/demo_wrong_edit_params.txt`）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `scripts/e2e-up.sh` / `scripts/e2e-down.sh` 在 worktree 内正常起停；未观察到进程残留
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: `git revert d956e09dd`（C3/R2）
- Commits: C3=d956e09dd
- Next: 合并到 unit/bugfix-468
