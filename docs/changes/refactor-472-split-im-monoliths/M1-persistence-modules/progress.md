# refactor-472-M1 — Progress

## 基线

- 已阅读 motivation、design、项目约定、IM 长青契约与测试规范。
- `PYTHONPATH=src pytest -m "not e2e"` 基线通过：3676 passed, 21 deselected。

## R1 — 锁定最终 package 边界与导入契约

- Context: 本次重构必须 replace-don't-layer，最终结构不允许旧 module 或聚合 re-export 继续成为事实入口。
- Decision: 先以 architecture contract 固定 package、私有 primitive 和禁止旧入口的可观察结构，再迁移 concrete importer。
- Rationale: contract 的失败可证明当前缺失的是最终边界，不把后续实现细节锁进测试。
- Evidence:
  - Tests: `PYTHONPATH=src pytest tests/contract/test_im_persistence_seam_contract.py -q` 失败 4 项，原因仅为 final package 尚未创建、legacy file 尚在。
  - Entry: N/A；本 roadpoint 为内部 architecture contract，HTTP 入口回归在 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/contract/test_im_persistence_seam_contract.py`，待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C1 commit。
- Commits: C1=6ef66468f，C2=待提交，C3=待提交。
- Next: 写入 red contract 并确认只因最终 package 尚未实现而失败。

## [暂停] R1: 机械分段迁移遗漏 aggregate 私有依赖

- 现象: 首次聚焦仓库测试的 collection 暴露 `messages`/`agents`/测试 import 三类分段边界错误；修复后仍先后暴露 Message retry key、Conversation active delivery status 等原文件顶部/尾部 helper 的实际归属。
- 根因: 以原文件静态行区间复制 class 区段，将跨 class 定义位置的类型与 helper 错归/漏归；这不改变 design 的 aggregate/transaction ownership 决策，但证明该迁移方式不可靠。
- 已验证: `PYTHONPATH=src pytest <7 个 repository 聚焦测试> -q` 当前 10 failed, 43 passed；失败统一源于 `ConversationRepository._resolve_run_state()` 缺少原 module-level `_ACTIVE_AGENT_DELIVERY_STATUSES`。
- 决策请求: 已通知 orchestrator，等待确认改用 class range + 实际引用依赖图逐 aggregate 移动的迁移方式；暂停继续编码，避免在红色实现上叠加补丁。
- Next: 等待 orchestrator 继续信号；获准后从 R1 C1 基线重新执行可审计的 aggregate migration。

### R1 — 锁定最终 package 边界与导入契约

- Context: 旧单文件同时暴露所有 persistence aggregate，调用方无法表达实际依赖；最终结构不得保留 façade。
- Decision: 建立空 `repositories` package 与 domain modules；所有生产、测试和 contract caller 直接导入其实际 aggregate，删除 `repositories.py`。
- Rationale: package 空 `__init__.py` 防止未来重新形成总出口；contract 将 legacy file、re-export 与私有 event primitive 的边界固定为回归保护。
- Evidence:
  - Tests: C1 `PYTHONPATH=src pytest tests/contract/test_im_persistence_seam_contract.py -q` 为 4 failed（final package 缺失）；C2 为 11 passed。
  - Entry: R4 真 IM HTTP 验收覆盖可观察的持久化读写与 owner 隔离。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/contract/test_im_persistence_seam_contract.py`；`pytest tests/ --collect-only -q` 通过；`ruff check .` 与 `ruff format --check .` 通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `34983d113` 后再回退 C1 `6ef66468f`。
- Commits: C1=6ef66468f，C2=34983d113，C3=0783e9ad8；首次 unit merge=874d5ab6b。
- Next: 已补齐 reviewer 指定的真 HTTP 入口覆盖，更新验收记录后重新集成。

### R2 — 基础 aggregate 与共享时间格式

- Context: 用户、策略、会话、Agent、节点、绑定、用量分别具有独立变化原因，原文件顶部/尾部 helpers 实际被不同 aggregate 消费。
- Decision: 先用 AST 盘点 module-level definition 的引用闭包，再将 users/settings/conversations/agents/nodes/bindings/metrics 移到各自 canonical module；将 UTC 格式搬到 `IM.infra._timestamps`，并让 watchdog 直接消费该 public-in-infra helper。
- Rationale: 以实际引用闭包确定 `_ConversationConfigSnapshot`、external result、active status、profile version conflict、node/metric helpers 等 owner，避免按静态行号遗漏类型或常量。
- Evidence:
  - Tests: 聚焦 SQLite repository + watchdog：53 passed；IM 非 E2E：472 passed、1 skipped。
  - Entry: 真 IM HTTP 已验证注册 owner 的 conversation 创建、policy 读取与 metrics owner 过滤。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/unit/test_repositories_user_conversation.py`、`test_repositories_agent_profile.py`、`test_nodes_metrics_repositories.py`、`test_relay_watchdog.py`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `34983d113`。
- Commits: C1=6ef66468f，C2=34983d113，C3=0783e9ad8；首次 unit merge=874d5ab6b。
- Next: 已完成。

### R3 — timeline aggregate 与 transaction-neutral event row

- Context: Message create/discard、Event append 与 config boundary record 均写 conversation event，但各自的 transaction/projection/notify 所有权不同。
- Decision: 新增 package-private `_event_rows.insert_event_row()`，只插入并映射 row；Message、Event、Boundary 在各自已有 transaction 内调用它，且分别在 commit 后执行原 notify。
- Rationale: 共享 row shape 而不把 commit 或 notify 抽到另一个 repository，保持 message/event/projection 与 boundary row 的原子性。
- Evidence:
  - Tests: `tests/contract/test_im_persistence_seam_contract.py` 断言 primitive 无 commit/notify，三 owner 均消费；聚焦 SQLite repository suite 53 passed。
  - Entry: 真 IM HTTP 创建消息后重新读取 timeline，`durable message` 持久出现。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/unit/test_repositories_message.py`、`test_event_repository.py`、`test_event_repository_queries.py`；`tests/im_service/integration/test_messages_api.py` 已纳入全量非 E2E 回归。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `34983d113`。
- Commits: C1=6ef66468f，C2=34983d113，C3=0783e9ad8；首次 unit merge=874d5ab6b。
- Next: 已完成。

### R4 — 删除旧入口与真实 HTTP 回归

- Context: 纯内部重构仍须证明浏览器使用的 HTTP 数据面没有因 import 或 transaction seam 迁移退化。
- Decision: 以 `scripts/e2e-up.sh` 启动 worktree 隔离 IM/Gateway，使用公开 auth/conversation/messages/policies/metrics HTTP endpoints 验收，随后执行 `scripts/e2e-down.sh` 清理服务。
- Rationale: 真服务进程和 HTTP boundary 覆盖 app wiring、repository construction、SQLite 读写及 tenant authorization，不能由直接 repository 调用替代。
- Evidence:
  - Tests: 完整 `PYTHONPATH=src pytest -m "not e2e"`：3678 passed、1 skipped、21 deselected；`ruff check .`、`ruff format --check .`、`pytest tests/ --collect-only -q` 均通过。
  - Entry: 隔离真栈 IM=`http://127.0.0.1:53982`；注册两个 owner，owner A 创建 conversation 与带 `sender_user_id` 的 message，历史读取包含 `durable message`；owner B 读取该 conversation 返回 404；A 的 policy fields 完整，metrics 返回行均属于 A。证据对象：conversation `5915bd94e406467d979012e568b6d45b`、message `f4fd6e14e19b4a72881ab5b70530cf10`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；M1 无前端改动。
  - E2E/Regression: `tests/im_service/integration/test_auth_multiuser_isolation.py`、`test_nodes_metrics_api.py`、`test_bind_atomicity.py`、`test_account_binding_api.py`、`test_messages_api.py` 均在完整非 E2E run 中通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `34983d113`。
- Commits: C1=6ef66468f，C2=34983d113，C3=0783e9ad8；首次 unit merge=874d5ab6b。
- Next: 已完成。

## [验收补齐] Reviewer 真实 HTTP 入口覆盖

- Context: reviewer 要求对 M1 的持久化改动以隔离真 IM/Gateway 覆盖账号、会话、消息、Agent、节点、绑定、策略及用量的成功、冲突、跨 owner 拒绝和离线可观察结果；不能只引用 pytest。
- Decision: 从首次集成的 `unit/refactor-472` HEAD `874d5ab6b` 重建 milestone worktree，以 `scripts/e2e-up.sh` 启动隔离真栈，在公开 HTTP 端点用两个登录 owner 执行完整旅程；随后显式停止 Gateway，轮询节点 board 的 offline 投影，再执行 `scripts/e2e-down.sh`。
- Rationale: HTTP 边界证明 app wiring、认证 owner scope、repository construction 和 SQLite 持久化共同保持，而离线状态必须来自断开的真实 Gateway，不能由进程内 fixture 代替。
- Evidence:
  - Stack: IM=`http://127.0.0.1:55410`，node=`wt-refactor-472-M1-30602`；owner A=`01c70cb49925436f9169c4c4231f0fc6`、owner B=`05751f42c7a6402cb7ca26134324f1c9` 均通过 `POST /im/v1/auth/login`（200）。
  - Account/tenant: A 的 `GET /im/v1/me` 为 200 且返回其 owner；B 读取 A 的 conversation `09c6ab3500d54e6b8b9ce102e5e03b05` 及向其发消息均为 404 `conversation_id not found`。
  - Conversation/message/history: A 创建该 conversation（201），改名为 `M1 renamed final`（200），添加 `default-agent` 成员（200）后以 participant `user_id=144e7db3785841a38ed4fa07ea8b32fb` 删除（204）；消息 `3d2945307547499baa9210ca506fbd9d` 创建为 201，随后历史读取为 200 且包含该 message id。
  - Node/binding/status: A 节点列表为 200 并显示 `online`；A 更新 node config alias=`M1 verified node` 为 200，B 更新同一 node 为 404 `node_id not found`；A bind start/confirm 分别为 201 pending/201 confirmed，B 对同 node start 后 confirm 为 409 `node already bound to another owner`。停止 Gateway pid `30674` 后轮询 `GET /im/v1/nodes`，同一 node 显示 `offline`（200，last_heartbeat_at=`2026-07-22T08:36:18.934488Z`）。
  - Agent/config/create: A 读取 `default-agent` mirror config 为 200（profile_version=3），PATCH 为 200（version=4）；使用过期 version 重试为 409 `profile_version conflict`，B 读取该 agent 为 404 `agent_id not found`。A 经真实 Gateway RPC 创建 `m1-evidence-agent-owned`（201，owner A、node 同上、version=1），B 读取该 Agent mirror 为 404。
  - Policy/metrics: A policy 初值 `retention_days=30`，PATCH 到 31 为 200、GET 读回 31 为 200，随后恢复 30；A `GET /im/v1/metrics/usage` 为 200（4 行，均属 A scope），B 为 200（0 行），确认 owner 过滤。
  - Tests/static: 完整 `PYTHONPATH=src pytest -m "not e2e"` 为 3678 passed、1 skipped、21 deselected；`tests/im_service -m "not e2e"` 为 472 passed、1 skipped；persistence seam contract 为 11 passed；`ruff check .`、`ruff format --check .`、`pytest tests/ --collect-only -q` 均通过。
  - Cleanup: 验收终态运行 `./scripts/e2e-down.sh`，隔离 IM/Gateway 均停止；本段不引入产品代码或持久化 schema 变更。
- Rollback: 仅验收文档，回退本次文档 commit；代码回退目标仍为 `34983d113`。
- Commits: 验收补齐文档=7e08fdef9；补证 unit merge=54314bd44。
- Next: 已完成。
