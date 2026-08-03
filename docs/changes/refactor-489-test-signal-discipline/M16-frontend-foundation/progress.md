# refactor-489-M16 — Progress

## Baseline

- Claim: 清理前 M16 foundation Vitest 可稳定运行，后续删除/合并能与同一范围直接对照。
- Baseline: `milestone/refactor-489-M16` from `origin/unit/refactor-489@90415c3d1`。
- Method: 在 `src/IM/frontend/` 对不属于 M14/M15 的 19 个 tracked `*.test.{ts,tsx}` 运行 Vitest；worktree 的临时未跟踪 `node_modules` 链接到主仓已安装的同版本 frontend dependencies，收尾时删除。
- Result: PASS；`19 test files / 105 tests passed in 2.91s`。
- Locator: `src/IM/frontend/src/` foundation tests、`src/IM/frontend/tests/vite-proxy-config.test.ts` 与本 milestone `tasks.md` 处置表。
- Limit: Vitest/jsdom + fake WebSocket/Notification/fetch；不证明真实浏览器视觉、真实 IM 服务或外部网络。既存输出含 router 测试未隔离全局 stream 导致的 `/im/v1/sync` invalid-URL console error，以及 Node `--localstorage-file` warnings；基线仍绿，前者在 R1 从测试 harness 隔离，后者记录但不扩张产品范围。

## R1 — 删除静态扫描与 app/me 伪视觉重复

- 状态: TODO

## R2 — 收敛 auth 与 notification 状态保护

- 状态: TODO

## R3 — 收敛 realtime 并完成配置门禁

- 状态: TODO

## Promotion Candidates

None.
