# refactor-460-M2 — Progress

## 启动记录

- 2026-07-13：已完整读取 motivation/design、项目 AGENTS/SPEC/注释与测试规范、worker 模板及 M1/current code/test 结构。
- 基线：worktree 初始缺少 `node_modules`，`npm run test` 在 Vitest 启动前报 `vitest: command not found`；确认 `package-lock.json` 完整且主仓存在同版本依赖后执行 `npm ci`，未改源码，随后全量 Vitest 基线通过。
- 范围确认：只改 design M2 范围与路径移动牵连的 frontend imports/tests、README、M2 tasks/progress/evidence；不修改 motivation/design/delta-spec，不返工 M1。

## R1 — canonical Chat 提升与 legacy cluster 删除

- Status: DONE
- Context: 生产路由使用的 current Chat 仍位于 `v2/`，根目录同时保留 4200+ 行 legacy client/mock/types/旧组件；大规模移动必须保持 UI 与数据行为不变。
- Decision: 先用 architecture guard 锁定无版本目录、legacy 文件零残留与 canonical query key，再删除同名 legacy 表面并以 `git mv` 提升 current 文件；同步迁移 router/shell/toast/notifier/Settings imports、`chat-v2` keys、窄 bind 请求、Agent config envelope normalization 与 Agent 详情 canonical createConversation。
- Rationale: 删除根目录同名 legacy 文件后再移动，Git 保留 30+ 个 current 文件的 rename history；迁移全部最后 import 才能真实删除 cluster，不保留 shim。批量 query-key 替换后主动复查并移除了 Agent 详情重复 invalidation，避免两个旧 key 机械收敛成同一调用。
- Evidence:
  - Tests: `npm run test -- --reporter=dot`，61 files / 569 tests passed；`npm run build` passed；`pytest -q tests/contract/test_im_frontend_user_stream_ownership.py`，2 passed。
  - Entry: 真实 IM + Gateway 栈登录 `/chat`，desktop/mobile canonical Chat 均正常加载；路由、shell、workspace、toast、notifier 与 Agent detail 集成回归通过。
  - Frontend State Matrix: desktop/mobile/default/empty 已真浏览器覆盖；loading/error/permission/long-content 保留并通过 current Chat Vitest；无 UI 设计变化。
  - Browser QA: `evidence/r1-browser-report.md`；1440×900 与 390×844，console 0 error/0 warning，登录/nodes/conversations/agents network 均 200。
  - E2E/Regression: `canonical-chat-architecture.test.ts` 锁定无 `v2/`、无 legacy cluster、无 `VITE_CHAT_API_MODE`/`chat-v2`；全量 569 tests 回归 current Chat 行为。
  - Visual/Interaction: `evidence/r1-canonical-chat-desktop.png`、`evidence/r1-canonical-chat-mobile.png`；与现有真实 Web IM 基线一致。
  - Prototype Comparison: N/A（design 明确无 prototype/视觉变化）。
- Rollback: 回退 C2 `86b07fee` 恢复 legacy/v2 双表面；C1 保留最终 architecture 缺口。
- Commits: C1=`14d132d7`, C2=`86b07fee`, C3=本提交。
- Next: R2 实现不可重复 confirm 与可重试 reconciliation 的严格绑定收敛。

## R2 — 绑定确认 session/cache 收敛

- Status: DOING
- Context: 待完成。

## R3 — 零残留收尾与全量真栈验收

- Status: TODO
- Context: 待完成。
