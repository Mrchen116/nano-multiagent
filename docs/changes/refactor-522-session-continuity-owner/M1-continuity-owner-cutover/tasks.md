# refactor-522-M1: continuity owner cutover — Tasks

> 对齐: ../design.md

## 目标

GatewaySessionBinder 成为 session continuity persistence 的唯一公开 owner；composition、dispatcher 与行为测试不再认识 raw store，同时保留现有 SQLite 数据、session/control/boundary 行为和重启恢复。

## 退出标准

- [x] binder 内建私有 SQLite implementation，公开 memory/persistent store、全局实例、HTTP client seam 与 bind helper 删除。
- [x] boundary dispatcher 只使用 `next_boundary_dispatch` / `complete_boundary_dispatch` 两步领域 transition。
- [x] composition 只创建并传递同一个 binder，pending shadow promotion 也经 binder。
- [x] 现有六类表、事务、序列化、legacy migration 与 restart continuity 保持兼容。
- [x] `/new`、FIFO `/compact`、pending external control、pending shadow boundary 与 superseded run 回归全绿。
- [x] focused、cross-process recovery、非 E2E 全量、Ruff check/format-check 全绿。

## 测试策略

- 被测行为（来自退出标准）：binder 作为唯一 continuity owner；SQLite 重建恢复；boundary Ready/Wait/Idle 与 Acked/PermanentlyRejected/RetryableFailure；composition 单 binder wiring；reset/compact/control/shadow recovery 不回归。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_session_binder.py`、`test_gateway_boundary_outbox.py`、`test_gateway_boundary_delivery.py`、`test_external_control_delivery.py`、`test_session_run_coordinator_admission.py`、`test_gateway_build_runtime.py`（rewrite-merge）；`tests/integration/test_send_message_restart_routing.py`（扩展）；新建 `tests/e2e/critical_paths/test_session_continuity_partial_recovery.py`，用于跨进程 durable recovery。
- 落层/目录/marker：`tests/unit/`、`tests/integration/` 无 marker；`tests/e2e/critical_paths/` 使用 `e2e` marker。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据：无；真实重启证据落可重复测试。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 公开双 store seam | `tests/unit/personal_assistant/test_persistent_session_binding_store.py` | rewrite-merge | 改为 binder-owned persistence behavior，保留 schema/restart/race 保护 | focused pytest |
| boundary durable 状态机 | `test_gateway_boundary_outbox.py`、`test_gateway_boundary_delivery.py` | rewrite-merge | 经 binder 两步 transition 覆盖 retry/quarantine/ACK | focused pytest |
| 普通 inbound fixture | `tests/helpers/inbound_pipeline.py` 与使用者 | rewrite-merge | fixture 只暴露 binder，普通测试统一 `:memory:` SQLite | non-E2E pytest |
| `/new`、FIFO `/compact` 与 external control | `test_session_run_coordinator_admission.py`、`test_external_control_delivery.py` | rewrite-merge | 改为 binder intent/assertion，不再直读 store | focused pytest |
| production wiring | `test_gateway_build_runtime.py` | rewrite-merge | 断言 DB path 进入 binder、outbox 共享 binder | focused pytest |
| restart continuity | `tests/integration/test_send_message_restart_routing.py` | rewrite-merge | 重建 binder 验证同一 durable binding | integration pytest |

UI：N/A。

## Roadpoints

### R1 — Binder 独占 SQLite persistence — DONE

- 步骤：先写 binder construction/restart/deletion-contract 红测；私有化 SQLite，删除内存 store/global/helper/HTTP seam；迁移 binder 与普通 fixture/test setup。
- 验证：binder/session focused tests、repository symbol deletion search。

### R2 — Boundary 两步 transition 与 composition cutover — DONE

- 步骤：先写 Ready/Wait/Idle 与三类 outcome 红测；实现 binder durable transition；dispatcher/composition/shadow promotion 改用同一 binder；清理 caller 文档。
- 验证：outbox/delivery/composition/control focused tests。

### R3 — Durable compatibility 与产品行为回归 — DONE

- 步骤：迁移 SQLite/schema/control/coordinator/restart coverage 到 binder；保留六表与既有 transaction；覆盖重建 binder、FIFO compact、reset、supersession。
- 验证：focused unit/integration、legacy schema compatibility、Gateway-only restart regression。

### R4 — Cross-process partial recovery 与全量收口 — DONE

- 步骤：新增 test-only 双 subprocess launcher，覆盖 pending shadow boundary 与 pending external control 唯一恢复；运行全量门禁并记录 evidence。
- 验证：critical-path E2E、非 E2E 全量、Ruff check/format-check、`git diff --check`。

## Reviewer Feedback Fix 3

反馈同时涉及 crash ordering、private surface deletion 与 outbox backlog complexity，超过 §FL 的单点/三文件轻量判据，因此在既有 milestone tasks 中追加三个 roadpoint；仍保持单个 feedback commit 可整体回退。

### F3-R1 — Shadow anchor/promotion crash recovery — DONE

- 先用 subprocess barrier 构造 promotion 已提交而 saga anchor 未提交的精确 crash state，并构造历史反向 state（saga anchor 已提交、pending promotion 尚在）。
- 调整提交顺序并增加显式 legacy recovery seam；A/B 恢复后只保留一个 IM anchor、一个 eligible/applied boundary。

### F3-R2 — Private store surface deletion — DONE

- 删除无 production caller 的 `drop`、`drop_agent`、`pending_boundaries`；普通 bind/get/restart/reverse lookup 覆盖迁到 binder public/domain interface。
- quarantine 行为只从 binder outcome、restart 与 Idle 可见；仅明确 race/schema/serialization/transaction tests 可触达 private repository。

### F3-R3 — O(N) boundary drain — DONE

- 保持 `Ready/Wait/Idle` 与 outcome 两步 public seam，private SQLite 每次只选择并反序列化下一条 eligible row。
- 用确定性 constructor/deserialization count 保护 N 条 backlog 只做 N 次 row materialization，并保留未尝试优先、deadline/rowid/retry=0 公平性。
