# refactor-489-M11: IM 持久化与契约测试信号收敛 — Tasks

> 对齐: ../design.md

## 目标

保留 IM 持久化、schema 与公开 contract 的最小必要保护，删改实现细节和跨层重叠断言；`_auth_helpers.py` 继续作为 M12 可复用但不修改的认证 helper。

## 退出标准

- [x] IM 的公开 HTTP/WebSocket contract、owner 隔离、持久化原子性、幂等与稳定顺序仍有最小必要保护。
- [x] 删除或改写只锁定私有调用步骤、源码/路由形态、历史迁移措辞以及跨 repository/service/route 重复的断言。
- [x] M11 范围完整 pytest 门禁全绿，测试 census 与删改理由可复查。

## 测试策略

- 被测行为（来自退出标准）：JWT/租户隔离与稳定响应；SQLite schema 和 durable write；消息、事件、配置边界、fork、relay 的事务/幂等/顺序；Gateway 注册、路由与状态 freshness；公开 WS frame 契约。
- 已有测试在：`tests/im_service/contract/`（公开 API/WS contract）、`tests/im_service/unit/` 与 `tests/unit/IM/`（repository/service seam）；本 milestone 先定位并收敛现有覆盖，不为相同行为新建平行测试。
- 落层/目录/marker：`tests/im_service/contract/` 与 `tests/im_service/unit/`；保留 `tests/unit/IM/` 中尚未迁移且确有独立风险的测试；marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：pytest collection/census 与 overlap inventory；不创建额外临时测试文件。
- 用户路径分类：N/A（零产品行为变化的测试重构）。
- UI 状态矩阵：N/A。
- 测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 公开 API/WS payload、状态码与 owner 隔离退化 | 保留最低层 contract 用例并跑 contract suite | 是 |
| durable write、rollback、idempotency、pagination/order 退化 | 保留真实 in-memory SQLite repository/service regression | 是 |
| app-scoped SQLite 跨线程并发与 Gateway stale frame/registration ordering | 保留显式 concurrency/freshness regression | 是 |
| 删除测试后遗漏现行风险 | 全范围 pytest + collect/census + diff 审核 | 否（验收证据） |

- Prototype / Reference Contract：N/A。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| HTTP/WS 公开字段、状态码、鉴权与 owner 隔离 | `tests/im_service/contract/**`、root route tests、`test_app_factory.py`、`test_message_repo.py`、`test_messages_route_detail.py` | keep + rewrite-merge + delete | contract 作为公开 seam owner；删除只枚举路由对象/模块归属的框架与布局断言，把重复 route/repository case 合并到最小公开结果 | R1 focused pytest |
| auth fixture 的稳定复用 | `tests/im_service/_auth_helpers.py` | keep | M11 contract 与 M12 integration 共用，保持单一 helper owner，不重写协议 | R1 collect + pytest |
| schema 初始化、线上迁移与共享 SQLite 跨线程安全 | `test_db_init.py`、`test_repositories_schema.py` | keep + rewrite-merge | 保留当前启动路径仍执行的迁移、数据修复及 shared handle regression；合并纯 schema existence/重复幂等断言 | R2 focused pytest |
| users/agents/nodes/conversations/messages/events/boundaries 的 durable round-trip、owner scope、幂等、分页与排序 | `test_repositories_*.py`、`test_owner_scoped_repositories.py`、`test_message_runtime_state.py`、`test_event_repository*.py`、fork tests | keep + rewrite-merge | 删除 getter/默认值逐字段重复，保留真实 SQLite 事务、关系、唯一性、回滚及 stable ordering | R2 focused pytest |
| Gateway 注册、ACK、dispatch winner、路由 freshness 与状态防倒退 | `test_gateway_*.py`、channel persistence/projection tests | keep + rewrite-merge | 这些是共享连接与异步顺序风险；去掉 private call choreography，保留 durable outcome 与并发/旧帧 regression | R3 focused pytest |
| relay、EventBridge、watchdog、user stream 与 payload serialization | `test_event_bridge.py`、`test_relay_*.py`、`test_streaming_chain.py`、`test_permission_streaming.py`、`test_tool_call_detail.py`、`test_ws_event_types.py` | rewrite-merge + delete | 合并字段逐跳/逐 getter 测试为最低层持久化或公开 frame 结果；保留 tombstone、liveness、权限、replay 去重与 owner isolation | R3 focused pytest |

## Roadpoints

### R1 — 公开契约与认证 helper 收敛

- 状态: DONE
- 步骤: 审核 `tests/im_service/contract/**`、`_auth_helpers.py` 与 route-shape unit 测试；以 current spec 的 HTTP/WS 可观察结果为 owner，去掉 route/source 私有形态和跨层重复。
- 验证: contract suite 全绿；认证 helper 仍被 contract/M12 消费；公开状态码与字段集不降级。

### R2 — schema 与 repository 持久化保护收敛

- 状态: DONE
- 步骤: 审核 schema migration、users/agents/nodes/conversations/messages/events/boundaries/fork 测试；合并重复 getter/round-trip，保留事务、外键、幂等、分页、owner isolation 与 stable ordering 风险。
- 验证: repository-focused suite 全绿，unique risk 到 surviving test 的映射可复查。

### R3 — Gateway、relay 与实时状态持久化保护收敛

- 状态: DONE
- 步骤: 审核 Gateway handler、node/conversation persistence、routing freshness、dispatch concurrency、EventBridge、relay/watchdog/status projection 与 root IM 重复测试；保留 shared-connection concurrency、ACK、rollback、freshness 与 liveness 风险。
- 验证: gateway/relay/event focused suite 全绿，跨层重复减少且时序 regression 仍在。

### R4 — 全量门禁与测试 census

- 状态: DONE
- 步骤: 复查 scope、测试命名/大小/重复、`git diff --check`，运行 M11 全范围 pytest，记录前后 census 与 warning。
- 验证: M11 全范围全绿；无越界修改；tasks/progress 证据完备。
