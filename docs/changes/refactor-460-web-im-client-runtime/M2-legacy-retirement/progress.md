# refactor-460-M2 — Progress

## 启动记录

- 2026-07-13：已完整读取 motivation/design、项目 AGENTS/SPEC/注释与测试规范、worker 模板及 M1/current code/test 结构。
- 基线：worktree 初始缺少 `node_modules`，`npm run test` 在 Vitest 启动前报 `vitest: command not found`；确认 `package-lock.json` 完整且主仓存在同版本依赖后执行 `npm ci`，未改源码，随后全量 Vitest 基线通过。
- 范围确认：只改 design M2 范围与路径移动牵连的 frontend imports/tests、README、M2 tasks/progress/evidence；不修改 motivation/design/delta-spec，不返工 M1。

## R1 — canonical Chat 提升与 legacy cluster 删除

- Status: DOING
- Context: 待完成。

## R2 — 绑定确认 session/cache 收敛

- Status: TODO
- Context: 待完成。

## R3 — 最后非实时入口迁移与全量真栈验收

- Status: TODO
- Context: 待完成。
