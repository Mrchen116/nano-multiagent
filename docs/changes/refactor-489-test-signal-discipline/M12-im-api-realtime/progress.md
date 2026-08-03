# refactor-489-M12 — Progress

## Baseline

- Context: M12 范围包含 32 个 test 文件、2 个大型重复 helper 和 138 个 collected case；HTTP/WS 跨 seam 保护与 M11 unit/contract 重述、静态 bundle/私有 mapper/helper 自测混杂。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/im_service/integration tests/im_service/e2e` → `137 passed, 1 skipped, 3 warnings in 35.19s`；skip 为可选 frontend `dist/` 缺失触发的静态 bundle 测试。

## R1 — Auth、租户、账户与基础 HTTP 收敛

- Context: auth、route-auth 和 multiuser 三处同时验证 bearer/owner；chat-flow、conversation/messages contract 与 fork service 又重复基本 CRUD、404 和 duplicate register。绑定并发虽有独立风险，却绕过 HTTP 直接调用 BindService。
- Decision: 保留 auth 注册/login/refresh/logout HTTP owner；把 data-route 无 token、token 主体更新、同 app conversation/message/agent/node 跨租隔离各收敛为一个行为；删除重复 chat-flow/fork/basic conversation/duplicate register。把 bind 竞争改为两个真实 owner TestClient 并发 confirm；policies 合并为 singleton reseed→PATCH→新 app reload。
- Rationale: HTTP seam 只需一次证明每类 route family 已接上 auth/owner；资源级 repository/contract 细节由 M11 独立拥有。bind 的唯一独立风险是 route 到事务 owner 的连接，direct service 调用不能证明它；policies 的独立风险是 app reload 后 durable，而不是再断言一次字段集。
- Evidence:
  - Tests: R1 surviving M12 `19 tests collected`；R1 public HTTP + M11 replacement gate → `57 passed, 13 warnings in 12.07s`；changed files Ruff → `All checks passed!`；`git diff --check` 通过。原同口径 44 项收敛到 19 项。
  - Entry: `/im/v1/auth/*`、`/im/v1/me`、conversation/message/agent/node data routes、`/im/v1/bind`、`/im/v1/policies` 均经真实 TestClient HTTP；bind race 由两个同 app tenant 并发 confirm 得到一个 201 和一个 409。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: M11 auth/account/policies/chat/messages/fork/repository 最低层替代保护与 R1 public seam 同批全绿；无外部服务 E2E，因为本 roadpoint 只验证进程内 HTTP/API 连接。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 commit。
- Commits: 本 R1 commit。

## R2 — Message 与 user-stream 实时路径收敛

- Context: 待执行。

## R3 — Agent、Node 与配置 RPC 收敛

- Context: 待执行。

## R4 — Gateway、群聊与共享 harness 收敛

- Context: 待执行。

## R5 — 全量门禁与测试 census

- Context: 待执行。

## Promotion Candidates

None.
