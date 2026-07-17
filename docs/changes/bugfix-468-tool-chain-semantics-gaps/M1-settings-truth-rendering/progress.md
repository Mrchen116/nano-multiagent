# bugfix-468-M1 — Progress

## R1 — 删除 PillSelector useDefaultOn 语义并清理 create 页传参

- Context: design 决策 1：detail 页删除 `useDefaultOn` 语义，`PillSelector` 空名单 = 全不亮；`useDefaultOn` prop 整体删除。
- Decision: 待补充。
- Rationale: 待补充。
- Evidence:
  - Tests: 待补充。
  - Entry: 前端组件测试。
  - Frontend State Matrix: N/A（本 R 只改组件内部语义）。
  - Browser QA: N/A（R3 统一做）。
  - E2E/Regression: N/A（组件测试覆盖）。
  - Visual/Interaction: N/A（R3 统一做）。
  - Prototype Comparison: N/A。
- Rollback: 待补充。
- Commits: 待补充。

## R2 — 删除 detail 页 allowlistUserTouched 及物化分支

- Context: 待补充。
- Decision: 待补充。
- Rationale: 待补充。
- Evidence:
  - Tests: 待补充。
  - Entry: 前端组件测试。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A（R3 统一做）。
  - E2E/Regression: N/A（组件测试覆盖）。
  - Visual/Interaction: N/A（R3 统一做）。
  - Prototype Comparison: N/A。
- Rollback: 待补充。
- Commits: 待补充。

## R3 — 全量测试、构建与浏览器验收

- Context: 待补充。
- Decision: 待补充。
- Rationale: 待补充。
- Evidence:
  - Tests: 待补充。
  - Entry: 真栈 IM + Gateway + 浏览器。
  - Frontend State Matrix: default / empty / mobile / desktop。
  - Browser QA: 待补充 URL 与操作路径。
  - E2E/Regression: N/A（本项目前端无 browser E2E 套件，组件测试 + 真栈截图验收）。
  - Visual/Interaction: 截图落 `evidence/`。
  - Prototype Comparison: N/A。
- Rollback: 待补充。
- Commits: 待补充。
