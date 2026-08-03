# refactor-489-M14 — Progress

## Baseline

- Claim: 清理前 M14 chat Vitest 可稳定运行，后续删除/合并能与同一范围直接对照。
- Baseline: `milestone/refactor-489-M14` from `origin/unit/refactor-489@52af34076`。
- Method: 在 `src/IM/frontend/` 运行 `./node_modules/.bin/vitest run src/features/chat`；worktree 的 ignored `node_modules` 链接到主仓已安装的同版本 frontend dependencies。
- Result: PASS；`27 test files / 493 tests passed in 5.87s`。
- Locator: `src/IM/frontend/src/features/chat/**/*.test.{ts,tsx}` 与本 milestone `tasks.md` 处置表。
- Limit: Vitest/jsdom + mocked fetch/user stream；不证明真实浏览器视觉、真实 IM 服务或外部网络。既存输出含 React `act(...)` 与 Node `--localstorage-file` warnings，本 milestone 不把 warning 当失败升级产品范围。

## R1 — 删除静态扫描与叶子重复

- 状态: TODO
- Next: 按 tasks.md 删除静态扫描并收敛 leaf tests。

## R2 — 收敛消息与工具交互保护

- 状态: TODO

## R3 — 收敛状态协作并完成门禁

- 状态: TODO

## Promotion Candidates

None.
