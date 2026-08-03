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

- Context: direct/group integration 各自维护大段同源 fake kernel；另有用例只自测 fake terminal snapshot，所谓 kernel-stream E2E 也明确绕过 InboundPipeline、内联翻译后直调 EventBridge/repository。基础 relay/config/bind/suppress 用例与更强的 direct/group/config-sync 和 R1/R2 已重复；auth boundary 还读取 session seq 与 waiter 私有字典。
- Decision: 统一到 `_gateway_helpers.py`，删除重复 group helper、fake 自测、伪 E2E 和被更强路径包含的基本 roundtrip/bind/config/suppress。保留并收敛 owner WS 安全、完整 receipt/report、last-error/offline/broken-socket、direct/group 配置采用、双 agent identity、status broadcast、heartbeat→scheduler 与 CLI→HTTP。把 forged `agent.created` 私有 waiter 断言改为真实 Bob HTTP create 保持 pending、Alice 伪造被拒、Bob 正确结果完成 201；双 mention 的 running/report/completed/delivered identity 合为一个 WS 生命周期。
- Rationale: M12 要证明跨 seam 可观察结果，而非 helper、mapper 或 private dict。共享 fake 只模拟 kernel SDK 边界，断言由真实 IM HTTP/WS、Gateway pipeline 和 durable/public result 承担。删除的 inline EventBridge 用例由 M11 `test_event_bridge.py`、Gateway handler 与 events contract 独立拥有。
- Evidence:
  - Tests: R4 原同口径 `34` 项收敛到 `20` 项；R4 surviving + M11 Gateway/EventBridge/events replacements → `68 passed, 2 warnings in 13.59s`；integration Ruff → `All checks passed!`；diff-check 通过。
  - Entry: `/im/ws/gateway`、`/im/ws/user`、message/agent/node HTTP、Gateway InboundPipeline、ConfigSyncClient 与 HeartbeatScheduler；owner 伪造结果只能收到 `gateway_owner_mismatch`，合法 owner HTTP 最终得到 201。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: real TestClient HTTP/WS 与进程内 Gateway pipeline；未将其升级为外部进程 live E2E。当前两项 warning 来自 `lark_oapi` 的 datetime/event-loop deprecation，未新增 warning 类别。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debugging: focused gate 首轮发现 owner socket 队列先到 channel bootstrap frame，以及统一 helper 的 current system prompt 多于 legacy helper。按 `systematic-debugging` 追到绑定后 `initialize_channel_control()` 的确定性 bootstrap 入队和新 helper 的 current config metadata；分别显式消费 bootstrap frame、对齐 current `system_prompt` 预期，单测与整组复验全绿。
- Rollback: 回退 R4 commit。
- Commits: 本 R4 commit。

## R5 — 全量门禁与测试 census

- Context: R1–R4 完成后，unit 已并入 M10/M13 等并行 milestone，需要先 rebase 最新 `origin/unit/refactor-489` 再确认收集、依赖和路径归属没有漂移。
- Decision: rebase 到 unit `c2f64d290`；运行 M12 整树 pytest、ruff、docs-check、diff-check 与 name-only scope audit，并复核 `_auth_helpers.py` 未进入 diff。以 baseline 同口径记录 test 文件、helper、case 与 Python 行数。
- Rationale: rebase 前 focused 绿灯不能代表最终 unit 组合；只有在最新 unit 基线上重跑整树，才能证明删除没有依赖旧收集顺序或遗漏并行变更。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/im_service/integration tests/im_service/e2e` → `79 passed, 3 warnings in 24.02s`；无 skip。warning 为既有 `lark_oapi` 两项 deprecation 与 FastAPI HTTP 413 常量一项 deprecation。
  - Census: collected case `138 → 79`（`-59 / -42.8%`）；test 文件 `32 → 24`；大型同域 helper `2 → 1`；M12 Python 行数 `9482 → 6448`（`-3034 / -32.0%`）。milestone 总 diff（含文档）为 `31 files changed, 501 insertions, 3369 deletions`。
  - Gates: `ruff check tests/im_service/integration tests/im_service/e2e` → `All checks passed!`；`scripts/docs_check.py` → `214 maintained Markdown sources, 65 required routes`；`git diff --check origin/unit/refactor-489...HEAD` 通过。
  - Scope: `git diff --name-only origin/unit/refactor-489...HEAD` 仅含 `tests/im_service/integration/**`、`tests/im_service/e2e/**` 与 M12 artifacts；`tests/im_service/_auth_helpers.py` 无 diff；worktree clean。
  - Entry: N/A（本 roadpoint 为 rebase 后自动化门禁；跨 seam 入口证据见 R1–R4）。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: M12 `e2e/` 已无伪 E2E case；真实 operational E2E 由已合入 unit 的 M13 独立拥有。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 M12 milestone commits。
- Commits: R5 final evidence commit。

## Promotion Candidates

None.
