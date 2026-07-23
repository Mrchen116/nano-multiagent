# refactor-472-M1: 持久化模块拆分 — Tasks

> 对齐: ../design.md

## 目标

将 IM 的 SQLite repository 巨石替换为按 durable aggregate 与事务所有权组织的唯一 `IM.infra.repositories` package；保持既有 HTTP/API、事务、提交及 post-commit notify 行为。

## 退出标准

- [x] 所有 repository production/test/contract importer 直接指向各领域 canonical module，旧 `repositories.py` 删除，package `__init__.py` 不聚合 re-export。
- [x] Message create/discard、Event append、Agent config boundary record 保持各自事务与 post-commit notify；共享 event-row primitive 不提交、不通知。
- [x] Conversation read model/hydration、external race、profile optimistic lock、BindingStore 独立事务和 Gateway register 历史分段提交语义均保持。
- [x] 账号/租户数据隔离、会话历史刷新完整、会话/Agent/节点/policy/metrics HTTP 入口回归通过。
- [x] persistence seam contract、全测试 collect、ruff check、ruff format check 通过。

## 测试策略

- 被测行为（来自退出标准）：owner 隔离与持久化 HTTP 数据读取；消息/事件/边界原子写和提交后通知；完整 conversation read model；profile 乐观锁；绑定与 Gateway register 既有事务边界；旧模块不再成为导入入口。
- 已有测试在：`tests/im_service/integration/test_auth_multiuser_isolation.py`、`test_nodes_metrics_api.py`、`test_bind_atomicity.py`、`test_account_binding_api.py`、`test_messages_api.py` 及现有 conversation/agent config unit tests（扩展或保持）；`tests/contract/test_im_persistence_seam_contract.py`（迁移为最终结构断言）。不新建仅为迁移路径服务的回归文件。
- 落层/目录/marker：`tests/im_service/unit/`、`tests/im_service/integration/`、`tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree 真 IM HTTP 验收命令与输出，记录于 progress.md。

## Roadpoints

### R1 — 锁定最终 package 边界与导入契约

- 状态: DONE
- 步骤: 将 persistence seam contract 改为最终 package 结构的 red contract；建立 tasks/progress 及 old→new coverage matrix。
- 验证: C1 证明旧巨石缺少 final package；C2 `tests/contract/test_im_persistence_seam_contract.py` 11 passed。

### R2 — 迁移基础 aggregate repositories 与时间格式

- 状态: DONE
- 步骤: 拆分 users/settings/agents/nodes/bindings/metrics/conversations，抽取共享 UTC formatter，直接迁移所有 importer。
- 验证: owner scope、profile optimistic lock、node/metrics、binding 与 Gateway registration 现有 SQLite/interface 测试通过；旧 import 零命中。

### R3 — 迁移 timeline aggregates 与原子 event row

- 状态: DONE
- 步骤: 拆分 messages/events/config_boundaries 及 projection/event-row private modules；以 transaction-neutral primitive 复用行插入，保留各 owner 的 commit/notify。
- 验证: messages/event/boundary SQLite tests 与 HTTP messages/timeline regression 通过；`_event_rows.py` 不 commit、不 notify，三个 transaction owner 直接复用。

### R4 — 删除旧入口并完成入口回归

- 状态: DONE
- 步骤: 删除 `repositories.py`，迁移所有 production/test/contract imports，更新 seam architecture contract，运行全量静态和持久化测试；启动隔离 IM 走关键 HTTP 数据面入口。
- 验证: 全仓 old import 零命中、collect/ruff 通过；真 IM HTTP 验证 owner 隔离、消息历史、policy 与 metrics 数据面。

## Old→New Coverage Matrix

| 原实现测试面 | 最终 interface/入口证据 | 处理 |
|---|---|---|
| repository aggregate CRUD、owner scope | 各现有 `tests/im_service/unit/test_*repositories*.py` | 迁移 import，保留行为断言 |
| HTTP multi-owner、nodes/metrics、binding、messages | 既有 `tests/im_service/integration/test_auth_multiuser_isolation.py`、`test_nodes_metrics_api.py`、`test_bind_atomicity.py`、`test_account_binding_api.py`、`test_messages_api.py` | 直接入口回归 |
| message/event/boundary transaction 与 notify | 既有 message runtime、event repository、agent config boundary tests | 迁移到 concrete domain module interface |
| repository architecture ownership | `tests/contract/test_im_persistence_seam_contract.py` | 改为 package ownership/no legacy import contract |
