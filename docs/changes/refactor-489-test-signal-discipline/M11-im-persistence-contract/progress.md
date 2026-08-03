# refactor-489-M11 — Progress

## R1 — 公开契约与认证 helper 收敛

- Context: M11 基线覆盖 61 个范围文件、424 个 pytest case；同一行为同时存在 repository、service、route 与 contract 断言，需要先确立公开 contract owner。
- Decision: 保留全部公开 contract；删除仅枚举 FastAPI route/module 对象的 3 个测试与专用 introspection helper；把 REST process-detail 7 个逐字段 mapper case 合并为 current/legacy 两个结果 case；删除 participant/rename 在 repository 与 HTTP 两层完全重复的 9 个 case，保留配置快照不被 refreeze 的独立持久化风险。
- Rationale: 路由是否存在已由真实 HTTP contract 证明，模块归属不是产品或架构契约；同一响应对象的相关字段应在一个 history serialization 行为里验证；participant/rename 的状态码、幂等、身份与错误语义以 HTTP seam 为最低完整保护。
- Evidence:
  - Tests: 基线 `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/IM tests/im_service/unit tests/im_service/contract` → `424 passed, 13 warnings in 23.38s`；focused R1 → `53 passed in 9.17s`；R1 减少 17 个重复/实现形态 case。
  - Entry: N/A；本 milestone 零产品行为变化，公开 contract pytest 是 design 指定入口。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/contract/**`、`test_messages_route_detail.py`、participant/rename HTTP tests 均通过；N/A E2E，因为零产品行为变化且 M11 入口为进程内 HTTP/WS contract。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 的测试删改 commit 即可恢复原测试集合。
- Commits: 本 roadpoint commit。

## R2 — schema 与 repository 持久化保护收敛

- Context: repository 测试同时包含真实 migration/transaction 风险、字段逐项 round-trip、私有连接读列与历史修复备注；必须区分当前运行仍依赖的 durable 语义与实现形态。
- Decision: 保留所有当前启动迁移、数据修复、跨线程 shared SQLite、owner isolation、external conversation 竞争、消息/事件 stable order、fork 原子回滚与完整气泡复制；把 profile 配置字段并入 optimistic-lock roundtrip，把 owner list/get 和 event cursor/high-water 各按同一风险合并；将 stale reconcile 9 项收敛为 missing/idempotent、revive、selectable 三项；删除 dataclass `hasattr`、默认 getter、日志 warning 和 participant repository 重复。
- Rationale: schema migration 与 SQLite 并发仍直接承载生产数据库升级和 app-scoped connection；fork/relay 的事务与排序风险不能由普通 getter 代替。反之，字段存在性、默认 `None`、私有 SQL 和 warning 文案不应成为独立长期契约。
- Evidence:
  - Tests: repository/schema/fork focused suite → `81 passed in 2.12s`；changed-test `ruff check` → `All checks passed`；R2 减少 21 个重复/实现细节 case。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_db_init.py` shared-connection regression、schema migrations、repository/fork focused tests 全绿；N/A E2E，因为零行为变化。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 commit。
- Commits: 本 roadpoint commit。

## R3 — Gateway、relay 与实时状态持久化保护收敛

- Context: Gateway/relay 范围中大量测试把同一 ToolCall 字段沿 private parse、dict、event、JSON encode/decode、repository 各测一遍；Gateway handler 也用 `inspect.signature`、dataclass field 和 PRAGMA 重复证明 heartbeat 字段存在。
- Decision: 把 ToolCall detail/emoji/approval 的 24 项逐跳测试收敛为 completed-event、durable history、legacy defaults 三项；把 19 项 user-stream builder 测试收敛为 7 个稳定 wire behavior；合并 token usage current/legacy normalization、四类 offline RPC、permission reason current/omitted、permission request list lifecycle；删除 incoming `permission_response` no-op、private notify owner、timestamp formatter 单元形态和 capability model getter 断言。Gateway durable winner、dispatch concurrency、routing freshness、register order、stale status、tombstone、replay、liveness 与 owner isolation 全部保留。
- Rationale: 同一 wire/persistence outcome 不需要每个内部函数一项测试；但 shared SQLite 竞争、ACK/dedup、freshness barrier 和 replay/liveness 是历史上真实发生且 current spec 明确要求的时序风险，必须继续从最低完整 seam 观察。
- Evidence:
  - Tests: changed-test `ruff check` → `All checks passed`；M11 全范围 → `329 passed, 13 warnings in 21.91s`；R3 减少 57 个实现逐跳/重复 case。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: Gateway/relay/event/user-stream regressions 随 M11 全范围通过；N/A E2E，因为 design 指定零用户 delta，真实进程/API 由 M12/M13 独立负责。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R3 commit。
- Commits: 本 roadpoint commit。

## R4 — 全量门禁与测试 census

- Context: R1-R3 后需要证明删减没有降低 IM 公开契约、持久化事务和异步时序保护，并确认没有把测试重构扩散到 M11 之外。
- Decision: 在最新 `origin/unit/refactor-489` 基线上完成 collect、M11 全范围 pytest、全范围 Ruff、形状审计和 diff/scope 检查；保留 schema/transaction/concurrency regression 中必要的私有连接与 PRAGMA 注入，不再机械删除。最终测试从 424 收敛到 329，删除 95 项（22.4%），范围文件从 61 减到 59，代码行从 16,357 减到 14,769。
- Rationale: 公开 seam 与独立生产风险都仍有 surviving test；剩余 private connection/SQL 只用于构造无法从公开 API 稳定触发的 migration、rollback、stale ordering 和 shared-connection 竞争。22.4% 的删减来自重复层级、逐字段/逐跳及实现形态，不来自降低 current spec 风险覆盖。
- Evidence:
  - Tests: `pytest --collect-only -q tests/unit/IM tests/im_service/unit tests/im_service/contract` → `329 tests collected in 0.30s`；`pytest -q` 同范围 → `329 passed, 13 warnings in 21.10s`；`ruff check` 同范围及 `_auth_helpers.py` → `All checks passed!`。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: M11 全范围从基线 `424 passed, 13 warnings` 到最终 `329 passed, 13 warnings`；13 项均为未变化的测试 secret PyJWT `InsecureKeyLengthWarning`。`git diff --check origin/unit/refactor-489...HEAD` 无输出；形状审计未发现残留 `inspect`/`getsource`/`hasattr`/route-introspection 锁定；改动仅位于 M11 测试与工件范围。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 文档可随对应实现 commit 回退。
- Commits: 本 roadpoint commit。

## Promotion Candidates

None.
