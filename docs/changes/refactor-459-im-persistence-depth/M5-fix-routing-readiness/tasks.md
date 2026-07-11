# refactor-459-M5: 修正 routing freshness 与 restart readiness — Tasks

> 对齐: ../design.md（2026-07-11 acceptance round 2 Changelog）

## 目标

恢复 origin/main 的 lifecycle/query 顺序，并把易变 node route 从 typed snapshot 移到每次 enqueue 前即时解析；Gateway restart readiness 只接受旧进程终止后由 replacement 产生的公开 heartbeat generation。

## 退出标准

- [ ] restart readiness 的时间下限在旧 Gateway 完全终止后采样，原 conversation 随后可立即继续收发。
- [ ] direct message/dispatch 写入窗口发生 rebind 时投递到最新 node。
- [ ] group fanout 保留旧 concrete participant query iteration order；后一 peer 在前一 peer await 期间 rebind 时投递到最新 node；participant/user resolution 无逐 participant N+1。
- [ ] force-offline 在 persistence 失败前已移除 stale connection；stale-node scan 保留旧无排序 query iteration order。
- [ ] 真栈 restart/rebind/offline/order 通过，完整 non-e2e、e2e-critical、ruff/diff 全绿。

## 测试策略

- 被测行为（来自退出标准）：post-termination heartbeat generation；direct/group enqueue-time node lookup；group bulk user hydration 与旧 query 顺序；pop-before-persistence failure；stale scan 旧 query 顺序。
- 已有测试在：`tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py`、`tests/e2e/critical_paths/_im_{client,gateway}.py`、`tests/im_service/unit/test_gateway_{handler,conversation_persistence,node_persistence,status_broadcast}.py`、`tests/im_service/unit/test_offline_guard.py`（扩展）；若 handler 巨型文件不适合承载 rebind fixture，则新建不超过 400 行的 routing test 文件。
- 落层/目录/marker：`tests/im_service/unit|integration/` marker 无；`tests/e2e/critical_paths/` marker `e2e`。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真栈公开 HTTP/WS restart、direct/group rebind、force-offline 与多 node/group 顺序驱动输出。
- 前端 UI：N/A。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — replacement Gateway readiness

- 状态：DONE
- 步骤：用 reviewer 失败日志与确定性 snapshot 时间线锁定旧进程收尾 heartbeat 越过 pre-restart baseline；由 restart helper 返回旧进程终止后的 replacement generation 下限，公开 node wait 只接受更晚 heartbeat。
- 验证：旧收尾 heartbeat 不能满足 wait；replacement register/heartbeat 可以；原 conversation 真栈续发不再 503。

### R2 — direct enqueue-time route

- 状态：DONE
- 步骤：`DispatchResolution` 仅保留稳定 target/conversation identity；在 message/dispatch 写后、relay enqueue 前通过 persistence public interface 解析 node。
- 验证：确定性写入窗口 rebind 后 relay task 与 push 均指向新 node；missing node 仍不 enqueue。

### R3 — group bulk hydration 与 enqueue-time route

- 状态：TODO
- 步骤：group route 用旧 concrete bulk users query 构造稳定 peer identity，取消字典序与 node snapshot；handler 在每个 peer enqueue 前即时查 node。
- 验证：非字典序 peer fanout 与 origin/main query iteration 一致；前一 peer await 时后一 peer rebind 后投新 node；participant/user SQL 为 O(1) bulk query，无逐 participant get_user。

### R4 — offline failure sequencing 与 stale order

- 状态：TODO
- 步骤：force-offline 恢复 connection pop-before-persistence；stale scan SQL 移除新增 `ORDER BY node_id`。
- 验证：注入 SQLite failure 后 connection 已移除、DB 保持失败态；多 stale node 按旧 query iteration order处理。

### R5 — 真栈与完整门禁

- 状态：TODO
- 步骤：按 Runbook 真栈验证 restart 原会话续发、direct/group rebind、force-offline 与顺序；运行所有门禁并清理资源。
- 验证：聚焦、non-e2e、完整 e2e-critical、ruff check/format、diff check 全绿。
