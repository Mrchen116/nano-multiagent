# refactor-463-M7: binding isolation and concurrency closure — Tasks

> 对齐: `../design.md`（2026-07-16 Round 3 M7）

## 目标

在不改变 SQLite schema、session key 与 reply-context 格式的前提下，令带 `_` / `%` 的 Agent id 始终按字面值隔离，并把 Kernel workspace ownership 慢校验移出 binder 全局临界区；并发 publish / invalidate / reuse / create 仍保持 revision + generation 原子写回语义。

## 退出标准

- [x] `_`、`%` 与相似 Agent id 的持久化 binding 查询、canonical lookup 和 stale invalidation 互不串扰，只删除目标 Agent 的旧 binding。
- [x] workspace ownership 校验不在 binder 全局锁内，也不阻塞 event loop；一个长 transcript 的校验不会串行阻塞无关 Agent 的 resolve / invalidate。
- [x] 两阶段 recheck 在慢校验期间遇到 config publish / invalidate 时不 stale publish；新请求只复用或创建当前 revision/workspace 的 binding。
- [x] 永久 repository/binder race 回归、最窄测试、`ruff check src tests`、`pytest -m "not e2e"` 全绿；新增或修改后的测试文件小于 400 行。

## 测试策略

- 被测行为（来自退出标准）：SQLite 对 Agent/channel 标识按字面值匹配；binder stale invalidation 只影响目标 Agent；慢 workspace 校验期间无关 resolve/invalidate 可进展；publish/invalidate 穿过慢校验时旧 binding 不被重新写回。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_session_binder.py`（扩展 repository 字面值匹配）；并发行为新建 `tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py`，理由：既有 binder interface 文件已达 372 行，继续加入可控线程协作 fixture 会越过 400 行门禁；新文件只承载独立的慢校验并发语义。
- 落层/目录/marker：`tests/unit/personal_assistant/`，marker：无；测试只走 repository/binder 公共行为，不断言私有 lock/map。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；PersistentSessionBindingStore 与 GatewaySessionBinder 公共接口回归即为长期可重复入口证据。
- 前端 UI：N/A（纯 Gateway 后端内部 ownership 修复，无浏览器/原型/reference）。

## Roadpoints

### R1 — SQLite binding 字面值隔离

- 状态：DONE
- 步骤：先补真实 PersistentSessionBindingStore + binder.invalidate_stale 红测，再对所有 Agent/channel `LIKE` 查询统一做字面值转义，不改 schema/key。
- 验证：红测精确复现 `_` / `%` 跨 Agent 匹配；实现后 repository/interface 最窄测试与 size contract 通过。

### R2 — Binder workspace 校验两阶段并发协议

- 状态：DONE
- 步骤：先补可控慢 `get_session` 并发红测，再把校验移到锁外 worker thread，并在短临界区按 candidate identity + revision + generation + catalog current recheck；保留 stale operation 可使用旧 snapshot、禁止 repository stale writeback。
- 验证：无关 Agent resolve / invalidate 在慢校验释放前完成；publish/invalidate race 不复活旧 row；现有 create/reuse/conversation-bind race 全绿，随后跑 ruff 与非 e2e 全量。
