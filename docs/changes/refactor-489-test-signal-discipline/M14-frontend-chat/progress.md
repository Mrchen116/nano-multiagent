# refactor-489-M14 — Progress

## Baseline

- Claim: 清理前 M14 chat Vitest 可稳定运行，后续删除/合并能与同一范围直接对照。
- Baseline: `milestone/refactor-489-M14` from `origin/unit/refactor-489@52af34076`。
- Method: 在 `src/IM/frontend/` 运行 `./node_modules/.bin/vitest run src/features/chat`；worktree 的 ignored `node_modules` 链接到主仓已安装的同版本 frontend dependencies。
- Result: PASS；`27 test files / 493 tests passed in 5.87s`。
- Locator: `src/IM/frontend/src/features/chat/**/*.test.{ts,tsx}` 与本 milestone `tasks.md` 处置表。
- Limit: Vitest/jsdom + mocked fetch/user stream；不证明真实浏览器视觉、真实 IM 服务或外部网络。既存输出含 React `act(...)` 与 Node `--localstorage-file` warnings，本 milestone 不把 warning 当失败升级产品范围。

## R1 — 删除静态扫描与叶子重复

- 状态: DONE
- Context: M14 基线含三份读取生产源码/CSS 的布局终态测试，以及 leaf components 对私有 `data-*`、Error 类形状、重复 token/permission/visual 状态的断言。
- Decision: 删除 canonical Chat 文件布局、toolbar z-index 与 web-search 色值三份源码扫描；attachment 只保留真实 drop/upload/error 结果，bind 不再断言 cache key 顺序，sidebar/new-group/group/token/permission 合并同义展示和私有 DOM 形状。PermissionCard 的已知中文 decision 与未知 backend label 合入一个用户可见 case，并用 React `act` 完成语言切换。
- Rationale: 文件/源码字符串、CSS 数值和内部 attribute 不能证明用户体验；当前风险由直接渲染、点击、请求 payload、错误反馈与 workspace 接线测试保护。相同状态在 leaf component 上断言一次即可。
- Evidence:
  - Tests: R1 定向 `9 files / 57 tests passed in 1.73s`；完整 M14 从 `27 files / 493 tests` 收敛为 `24 files / 469 tests passed in 5.40s`。
  - Entry: attachment/group/permission/sidebar 等测试继续通过 Testing Library 驱动用户操作，并从 DOM、callback 或 fetch payload 观察结果；零产品源修改。
  - Frontend State Matrix: default、error、disabled、submitting、permission denied、mobile/desktop 代表性风险仍由 leaf/workspace tests 覆盖。
  - Browser QA: N/A（测试资产重构，无 UI delta）。
  - E2E/Regression: 永久 regression 为保留的 Vitest；本 R 不新增临时或浏览器 E2E。
  - Visual/Interaction: N/A（删除的 CSS 源码正则本就不能作为真实视觉证据）。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复三份静态扫描与被合并用例，不影响产品源码或数据。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 收敛 MessagePane、content policy 与 tool panel 的 framework/常量边界/同义状态断言。

## R2 — 收敛消息与工具交互保护

- 状态: TODO

## R3 — 收敛状态协作并完成门禁

- 状态: TODO

## Promotion Candidates

None.
