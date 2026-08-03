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

- Context: messages integration 同时包含 M11 contract 已拥有的 basic roundtrip/rich pagination/sync/user-stream、三个直接 mapper/字段存在测试，以及一个依赖可选 `dist/` 且只查 bundle 字符串的常态 skip；`events_sse_api` 和所谓 e2e 也都用同一进程 TestClient 重复 resume。
- Decision: 保留 shadow conversation+完整 live payload、mark-as-read、boundary pagination、relay history、upload/download/限制、offline 结果和 caller idempotency scope；删除重复 basic CRUD/sync/resume、直接 mapper 和未验证标题所称 agent elapsed 的 placeholder。把 user-stream 的 missing/invalid/legacy identity 合并为一项严格 1008 行为，保留合法 JWT resume；删除伪 E2E 与重复 SSE 文件。
- Rationale: 消息 schema、repository order/runtime 字段和通用 resume 由 M11 contract/unit 最低层拥有；M12 只为 HTTP 与 WS 连接增加独立信号。静态 bundle 字符串既不证明前端交互也依赖未提交产物，不应进入 Python 永久套件。
- Evidence:
  - Tests: R2 M12 同口径从 26 项收敛到 `13 tests collected`；M12 surviving + M11 message/events/runtime/repository replacement gate → `43 passed, 1 warning in 5.03s`；Ruff 与 diff-check 通过。
  - Entry: message/upload HTTP 与 `/im/ws/user` 真实 TestClient WebSocket；非法身份逐项观察 close code 1008，有效 JWT 观察 owner message event。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 删除的 `tests/im_service/e2e/test_human_chat_sse_e2e.py` 未起真进程且与 contract/integration 相同；真实 runtime/E2E 由 M13 独立负责，M12 不把 TestClient 证据升级为 live E2E。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 commit。
- Commits: 本 R2 commit。

## R3 — Agent、Node 与配置 RPC 收敛

- Context: agent config integration 重复 M11 contract 的 list/get/patch/conflict、owner scope 与 capabilities mapper；agent create 重复 omitted-workspace fallback；metrics 用合成消息再次重述 repository aggregation。cron/skill/delete/heartbeat 在线用例还用 call-log 断言内部 mock 是否被调用，而 HTTP 返回体已经能证明结果跨过 route/GatewayControl 边界。
- Decision: 删除上述最低层重述，保留 real Gateway WebSocket live config/mismatch 防护、配置仅影响新会话、绑定后重注册、agent create→relay/config-sync、bootstrap/channel、node status 和真实 relay usage；把 stale→hidden→re-advertise→revive 合并为一个 WebSocket/HTTP 生命周期。RPC 在线用例改名为公开结果，并删除重复内部 call-log 断言；离线公开结果继续保留。
- Rationale: M11 已独立拥有字段合同、owner repository、Gateway persistence、metrics aggregation 与 stale 状态机；M12 的新增信号应来自 HTTP、WebSocket、持久化和 relay 的连接结果。mock GatewayControl 返回值仍用于隔离远端节点，但只断言公开 HTTP 结果，避免同时锁死内部调用记账。
- Evidence:
  - Tests: 本组四个高重复文件净减 `515` 行；R3 agent/node/config surviving tests + M11 replacements → `57 passed in 11.21s`；changed files Ruff → `All checks passed!`；`git diff --check` 通过。
  - Entry: `/im/v1/agents*`、`/im/v1/nodes*`、`/im/v1/metrics/usage` 与 `/im/ws/gateway` 均经真实 TestClient HTTP/WS；live config 由并发 HTTP 请求和 Gateway frame 应答完成，真实 relay usage 在 completion report 后按 owner/conversation/agent 投影。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: M11 agent config/create/owner-scoped repository/Gateway persistence/metrics/stale 替代保护与 R3 跨 seam 用例同批全绿；无外部服务 E2E。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R3 commit。
- Commits: 本 R3 commit。

## R4 — Gateway、群聊与共享 harness 收敛

- Context: 待执行。

## R5 — 全量门禁与测试 census

- Context: 待执行。

## Promotion Candidates

None.
