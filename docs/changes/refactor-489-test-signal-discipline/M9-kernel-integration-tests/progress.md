# refactor-489-M9 — Progress

## R1 — 删除历史和重复断言

- 状态: DONE
- Context: M9 基线 11 文件共收集 32 个 case；其中 idle 文件复制生产格式化逻辑而不调用生产入口，kernel skeleton 文件锁定旧迁移 golden 字节，bash signal、read truncation、registry validation 已有更低层同路径保护。
- Decision: 删除 3 个低信号文件和 4 条 unit/contract 重复用例，同时移除仅服务被删断言的 fixture/import；M9 收集数从 32 降为 18。
- Rationale: 永久 integration 资产应只为跨 seam 的独立风险付费；实现复制品、迁移终态和下层已拥有的细节不增加回归信号。
- Evidence:
  - Tests: 删除前 M9 基线 `32 passed in 9.01s`；删除后替代保护 `tests/unit/agent/platform/tools/builtins/test_bash_policy.py tests/unit/test_tool_validation_errors.py tests/unit/test_tools_read.py tests/unit/test_idle_callback.py tests/contract/test_tools_bash_contract.py tests/unit/agent/prompt_sections` 为 `116 passed in 0.67s`，M9 `--collect-only` 为 `18 tests collected` 且无已删 node。
  - Entry: 保留集合仍从 `build_kernel`、ToolRegistry、workspace loader 和 provider mapper seam 观察结果；本 unit 无产品行为变化。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: N/A（无外部服务/真浏览器风险；永久回归由上述 unit/contract 与 R2 保留的 integration 承担）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `33cf0581c`。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 收敛保留用例的断言高度与时序等待。

## Promotion Candidates

None.
