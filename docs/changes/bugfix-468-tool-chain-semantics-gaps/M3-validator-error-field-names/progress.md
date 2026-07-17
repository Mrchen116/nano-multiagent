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

- Context: <待填充>
- Decision: <待填充>
- Rationale: <待填充>
- Evidence:
  - Tests: <待填充>
  - Entry: <待填充>
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: <待填充>
- Commits: <待填充>
